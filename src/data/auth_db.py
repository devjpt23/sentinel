"""
User authentication and account management using SQLite.

Adds multi-user support to Sentinel: registration, login, password hashing,
and migration from the legacy shared watchlist to per-user watchlists.

Passwords are hashed with SHA-256 + 16-byte per-user salt via stdlib only.
This is a research tool, not a bank — the goal is to prevent casual snooping,
not to withstand a determined attacker. For stronger auth, put Sentinel behind
a reverse proxy with OAuth or Cloudflare Access.

Usage:
    from src.data.auth_db import init_auth_db, register_user, login_user

    init_auth_db()
    user = register_user("trader1", "hunter2", display_name="Trader One")
    user = login_user("trader1", "hunter2")
"""

import hashlib
import logging
import os
import secrets
import smtplib
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, List, Dict

# Same database file as the watchlist
_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "watchlist.db",
)


def _get_conn() -> sqlite3.Connection:
    """Get a connection with WAL mode for concurrent reads/writes."""
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


# ─── Password Hashing ────────────────────────────────────────

def _hash_password(password: str, salt: Optional[bytes] = None) -> tuple:
    """Hash a password with SHA-256 and a random salt.

    Returns (hash_hex, salt_bytes). If salt is None, generates a new one.
    """
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return dk.hex(), salt


# ─── Database Initialization ─────────────────────────────────

def init_auth_db() -> None:
    """Create users and user_watchlist tables if they don't exist.

    Safe to call on every startup — uses IF NOT EXISTS.
    """
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            salt BLOB,
            display_name TEXT,
            email TEXT,
            google_id TEXT UNIQUE,
            avatar_url TEXT,
            auth_provider TEXT NOT NULL DEFAULT 'password',
            telegram_chat_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, ticker)
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE,
            expires_at TIMESTAMP,
            used INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    # ── Migrations ──────────────────────────────────────────
    _migrate_auth_db(conn)
    conn.commit()
    conn.close()


def _migrate_auth_db(conn: sqlite3.Connection) -> None:
    """Add columns introduced after the initial schema. Safe to call repeatedly."""
    migrations = [
        "ALTER TABLE users ADD COLUMN google_id TEXT",
        "ALTER TABLE users ADD COLUMN avatar_url TEXT",
        "ALTER TABLE users ADD COLUMN auth_provider TEXT NOT NULL DEFAULT 'password'",
    ]
    for stmt in migrations:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already exists
    # Create unique index on google_id if it doesn't exist
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")
    except sqlite3.OperationalError:
        pass
    conn.commit()


# ─── User CRUD ───────────────────────────────────────────────

def register_user(
    username: str,
    password: str,
    display_name: Optional[str] = None,
    email: Optional[str] = None,
    telegram_chat_id: Optional[str] = None,
) -> Optional[Dict]:
    """Register a new user. Returns user dict on success, None if username taken."""
    conn = _get_conn()
    try:
        hash_hex, salt = _hash_password(password)
        cursor = conn.execute(
            """INSERT INTO users (username, password_hash, salt, display_name, email, telegram_chat_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (username.lower(), hash_hex, salt, display_name or username, email, telegram_chat_id),
        )
        conn.commit()
        user_id = cursor.lastrowid
        return {
            "id": user_id,
            "username": username.lower(),
            "display_name": display_name or username,
            "email": email,
            "telegram_chat_id": telegram_chat_id,
        }
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def login_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate a user. Returns user dict on success, None on failure."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, username, password_hash, salt, display_name, email, telegram_chat_id "
        "FROM users WHERE username = ?",
        (username.lower(),),
    ).fetchone()
    conn.close()

    if row is None:
        return None

    hash_hex, _ = _hash_password(password, bytes(row["salt"]))
    if not _constant_time_compare(hash_hex, row["password_hash"]):
        return None

    # Update last_login
    conn = _get_conn()
    conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()

    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "email": row["email"],
        "telegram_chat_id": row["telegram_chat_id"],
    }


def _constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def get_user(user_id: int) -> Optional[Dict]:
    """Fetch a user by ID."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, username, display_name, email, telegram_chat_id, created_at, last_login "
        "FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_user_by_username(username: str) -> Optional[Dict]:
    """Fetch a user by username."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, username, display_name, email, telegram_chat_id, created_at, last_login "
        "FROM users WHERE username = ?",
        (username.lower(),),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_all_users() -> List[Dict]:
    """Return all registered users."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, username, display_name, email, telegram_chat_id FROM users"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_by_email(email: str) -> Optional[Dict]:
    """Fetch a user by email address. Returns None if not found."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, username, display_name, email, google_id, avatar_url, "
        "auth_provider, telegram_chat_id, created_at, last_login "
        "FROM users WHERE email = ?",
        (email.lower(),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def create_or_update_google_user(
    email: str,
    display_name: str,
    google_id: str,
    avatar_url: str = "",
) -> Dict:
    """Create or update a user from Google OAuth credentials.

    If a user with this email already exists (password or Google auth),
    update their google_id, avatar, and display_name. Otherwise create
    a new Google-authenticated user.

    Returns the user dict.
    """
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id, username, auth_provider FROM users WHERE email = ?",
        (email.lower(),),
    ).fetchone()

    if existing:
        # Update Google profile info on existing account
        conn.execute(
            """UPDATE users SET
               google_id = ?, avatar_url = ?, display_name = ?,
               auth_provider = CASE
                   WHEN auth_provider = 'password' THEN 'password+google'
                   ELSE auth_provider
               END,
               last_login = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (google_id, avatar_url, display_name, existing["id"]),
        )
        conn.commit()
        conn.close()
        return get_user(existing["id"])

    # New Google user — derive a username from the email
    username = email.lower().split("@")[0]
    # Ensure unique username
    base_username = username
    suffix = 0
    while conn.execute(
        "SELECT 1 FROM users WHERE username = ?", (username,)
    ).fetchone():
        suffix += 1
        username = f"{base_username}{suffix}"

    cursor = conn.execute(
        """INSERT INTO users
           (username, password_hash, salt, display_name, email, google_id,
            avatar_url, auth_provider)
           VALUES (?, '', X'', ?, ?, ?, ?, 'google')""",
        (username, display_name, email.lower(), google_id, avatar_url),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    return {
        "id": user_id,
        "username": username,
        "display_name": display_name,
        "email": email.lower(),
        "google_id": google_id,
        "avatar_url": avatar_url,
        "auth_provider": "google",
        "telegram_chat_id": None,
    }


# ─── Telegram Linking ────────────────────────────────────────

def link_telegram(user_id: int, chat_id: str) -> bool:
    """Associate a Telegram chat_id with a user account. Returns True on success."""
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET telegram_chat_id = ? WHERE id = ?",
        (chat_id, user_id),
    )
    conn.commit()
    affected = conn.total_changes
    conn.close()
    return affected > 0


def link_telegram_by_username(username: str, chat_id: str) -> Optional[Dict]:
    """Link a Telegram chat_id to a user by username. Returns user dict or None."""
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET telegram_chat_id = ? WHERE username = ?",
        (chat_id, username.lower()),
    )
    conn.commit()
    affected = conn.total_changes
    conn.close()
    if affected > 0:
        return get_user_by_username(username)
    return None


# ─── Legacy Watchlist Migration ──────────────────────────────

def _legacy_watchlist_exists() -> bool:
    """Check if the old shared watchlist table has rows."""
    conn = _get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
        return count > 0
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def _users_table_empty() -> bool:
    """Check if the users table has no rows."""
    conn = _get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return count == 0
    except sqlite3.OperationalError:
        return True
    finally:
        conn.close()


def needs_migration() -> bool:
    """Return True if there's a legacy watchlist to migrate and no users yet."""
    return _legacy_watchlist_exists() and _users_table_empty()


def legacy_watchlist_count() -> int:
    """Return the number of tickers in the legacy shared watchlist."""
    conn = _get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def migrate_legacy_watchlist(user_id: int) -> int:
    """Copy all tickers from the old shared watchlist into user_watchlist.

    Returns the number of tickers migrated. Idempotent — duplicates skipped.
    """
    conn = _get_conn()
    try:
        old_tickers = conn.execute("SELECT ticker FROM watchlist").fetchall()
    except sqlite3.OperationalError:
        conn.close()
        return 0

    count = 0
    for (ticker,) in old_tickers:
        try:
            conn.execute(
                "INSERT INTO user_watchlist (user_id, ticker) VALUES (?, ?)",
                (user_id, ticker),
            )
            count += 1
        except sqlite3.IntegrityError:
            pass  # duplicate, skip

    conn.commit()
    conn.close()


# ─── Persistent Sessions ─────────────────────────────────────

def create_session(user_id: int) -> str:
    """Create a persistent session token for a user.

    The token survives Streamlit session state resets, server restarts,
    and browser tab changes. Store the returned token in st.session_state
    so it can be used to auto-restore the user on each script run.

    Returns a 64-character hex token.
    """
    token = secrets.token_hex(32)
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO sessions (session_token, user_id, created_at) "
        "VALUES (?, ?, CURRENT_TIMESTAMP)",
        (token, user_id),
    )
    conn.commit()
    conn.close()
    return token


def restore_user_from_session(session_token: str) -> Optional[Dict]:
    """Look up a session token and return the user dict, or None if expired/missing."""
    conn = _get_conn()
    row = conn.execute(
        """SELECT u.id, u.username, u.display_name, u.email, u.telegram_chat_id
           FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.session_token = ?""",
        (session_token,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def delete_session(session_token: str) -> None:
    """Delete a session token (used on sign-out)."""
    conn = _get_conn()
    conn.execute("DELETE FROM sessions WHERE session_token = ?", (session_token,))
    conn.commit()
    conn.close()


def delete_all_sessions(user_id: int) -> int:
    """Delete all active sessions for a user (e.g., after password reset).

    Returns the number of sessions deleted.
    """
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


# ─── Password Reset Tokens ────────────────────────────────────

def create_password_reset_token(user_id: int) -> str:
    """Generate a password reset token for the given user.

    The token is valid for 1 hour. Returns the 64-character hex token string.
    """
    token = secrets.token_hex(32)
    conn = _get_conn()
    conn.execute(
        """INSERT INTO password_reset_tokens (user_id, token, expires_at)
           VALUES (?, ?, datetime('now', '+1 hour'))""",
        (user_id, token),
    )
    conn.commit()
    conn.close()
    return token


def get_user_from_reset_token(token: str) -> Optional[Dict]:
    """Atomically claim and validate a password reset token.

    Returns None if the token is invalid, expired, or already used.
    Marks the token as used in the same SQL statement to prevent concurrent reuse.
    """
    conn = _get_conn()
    cursor = conn.execute(
        """UPDATE password_reset_tokens SET used = 1
           WHERE token = ?
             AND used = 0
             AND expires_at > datetime('now')""",
        (token,),
    )
    affected = cursor.rowcount
    conn.commit()

    if affected == 0:
        conn.close()
        return None

    row = conn.execute(
        """SELECT u.id, u.username
           FROM password_reset_tokens prt
           JOIN users u ON u.id = prt.user_id
           WHERE prt.token = ?""",
        (token,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def invalidate_reset_token(token: str) -> None:
    """Mark a password reset token as used."""
    conn = _get_conn()
    conn.execute(
        "UPDATE password_reset_tokens SET used = 1 WHERE token = ?",
        (token,),
    )
    conn.commit()
    conn.close()


def update_user_password(user_id: int, new_password: str) -> None:
    """Hash and update a user's password in the database."""
    hash_hex, salt = _hash_password(new_password)
    conn = _get_conn()
    conn.execute(
        "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
        (hash_hex, salt, user_id),
    )
    conn.commit()
    conn.close()


# ─── Email Sending ────────────────────────────────────────────

logger = logging.getLogger(__name__)


def send_password_reset_email(email: str, reset_link: str) -> bool:
    """Send a password reset email via SMTP.

    Configured via environment variables:
        SMTP_HOST      (default: "smtp.gmail.com")
        SMTP_PORT      (default: 587)
        SMTP_USER      (required)
        SMTP_PASSWORD  (required)
        SMTP_FROM      (default: same as SMTP_USER)
        RESET_BASE_URL (default: "http://localhost:3000") — used to build reset_link

    Returns True on success, False on failure (logs warnings on misconfiguration).
    """
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        logger.warning(
            "SMTP_USER or SMTP_PASSWORD not set — cannot send password reset email. "
            "Set these environment variables to enable email delivery."
        )
        return False

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Sentinel — Password Reset"
    msg["From"] = smtp_from
    msg["To"] = email

    # Plain text fallback
    text_body = (
        "You requested a password reset for your Sentinel account.\n\n"
        f"Click the link below to set a new password:\n{reset_link}\n\n"
        "This link expires in 1 hour.\n\n"
        "If you did not request this, you can safely ignore this email."
    )

    # HTML version
    html_body = f"""\
    <html>
      <body style="font-family: Arial, sans-serif; color: #333; padding: 20px;">
        <h2>Sentinel — Password Reset</h2>
        <p>You requested a password reset for your Sentinel account.</p>
        <p><a href="{reset_link}" style="display: inline-block; padding: 10px 20px;
           background-color: #2563eb; color: #fff; text-decoration: none;
           border-radius: 6px;">Reset Your Password</a></p>
        <p style="color: #666; font-size: 14px;">This link expires in 1 hour.</p>
        <p style="color: #999; font-size: 12px;">
          If you did not request this, you can safely ignore this email.
        </p>
      </body>
    </html>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_from, [email], msg.as_string())
        return True
    except Exception as e:
        logger.error("Failed to send password reset email to %s: %s", email, e)
        return False
