"""
Notification persistence using SQLite.

Six tables in the existing watchlist.db for preferences, notifications,
score snapshots, check scheduling, run history, and Telegram link codes.

All functions follow the same plain-function, raw-SQLite pattern as
watchlist_db.py — no ORM, no classes, just functions that take/return dicts.

Usage:
    from src.data.notification_db import (
        init_notification_db, get_preferences, create_notification,
        get_unread_count, get_latest_snapshot, save_snapshot, ...
    )
"""

import os
import sqlite3
from typing import Optional, List, Dict
from datetime import datetime, timedelta, timezone

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "watchlist.db",
)

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


# ─── Initialization ──────────────────────────────────────────

def init_notification_db() -> None:
    """Create all notification-related tables. Safe to call on every startup."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notification_preferences (
            user_id INTEGER PRIMARY KEY,
            health_change BOOLEAN DEFAULT 1,
            verdict_change BOOLEAN DEFAULT 1,
            risk_flag_change BOOLEAN DEFAULT 1,
            zscore_zone_change BOOLEAN DEFAULT 1,
            fscore_change BOOLEAN DEFAULT 1,
            telegram_enabled BOOLEAN DEFAULT 0,
            telegram_bot_token TEXT,
            check_interval_hours INTEGER DEFAULT 2,
            min_health_delta INTEGER DEFAULT 15,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT,
            notification_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            title TEXT NOT NULL,
            body TEXT,
            old_value TEXT,
            new_value TEXT,
            is_read BOOLEAN DEFAULT 0,
            delivered_via TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS score_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            health_score INTEGER,
            health_verdict TEXT,
            fscore INTEGER,
            risk_label TEXT,
            risk_score INTEGER,
            red_flag_count INTEGER,
            price_verdict TEXT,
            intrinsic_verdict TEXT,
            zscore REAL,
            zscore_zone TEXT,
            snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, ticker)
        );

        CREATE TABLE IF NOT EXISTS check_log (
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, ticker)
        );

        CREATE TABLE IF NOT EXISTS check_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            tickers_checked INTEGER DEFAULT 0,
            notifications_generated INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running',
            error_message TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS telegram_link_codes (
            code TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS custom_alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            enabled BOOLEAN DEFAULT 1,
            scope TEXT NOT NULL DEFAULT 'watchlist',
            ticker TEXT,
            conditions TEXT NOT NULL DEFAULT '[]',
            logic_operator TEXT NOT NULL DEFAULT 'AND',
            severity TEXT NOT NULL DEFAULT 'info',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS custom_alert_snapshots (
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            signal_id TEXT NOT NULL,
            previous_value REAL,
            snapshot_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, ticker, signal_id)
        );

        CREATE INDEX IF NOT EXISTS idx_notifications_user
            ON notifications(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_notifications_unread
            ON notifications(user_id, is_read)
            WHERE is_read = 0;
        CREATE INDEX IF NOT EXISTS idx_check_runs_user
            ON check_runs(user_id, started_at DESC);
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            browser TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_used TEXT,
            active INTEGER DEFAULT 1,
            UNIQUE(endpoint)
        );
        CREATE INDEX IF NOT EXISTS idx_push_sub_user
            ON push_subscriptions(user_id);
    """)
    # Migration: add telegram_bot_token column if upgrading from older schema
    try:
        conn.execute("ALTER TABLE notification_preferences ADD COLUMN telegram_bot_token TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists

    # Migration: add push/telegram fire flags to custom_alert_rules
    try:
        conn.execute("ALTER TABLE custom_alert_rules ADD COLUMN fire_push BOOLEAN DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE custom_alert_rules ADD COLUMN fire_telegram BOOLEAN DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE notification_preferences ADD COLUMN push_enabled BOOLEAN DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    # Migration: add hysteresis columns to custom_alert_rules
    try:
        conn.execute("ALTER TABLE custom_alert_rules ADD COLUMN currently_triggered BOOLEAN DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE custom_alert_rules ADD COLUMN last_triggered_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


# ─── Preferences CRUD ────────────────────────────────────────

def get_preferences(user_id: int) -> Dict:
    """Get a user's notification preferences, creating defaults if none exist.

    Includes telegram_chat_id from the users table so callers can check
    whether the user has linked their Telegram account.
    """
    conn = _get_conn()
    row = conn.execute(
        """SELECT np.*, u.telegram_chat_id
           FROM notification_preferences np
           JOIN users u ON u.id = np.user_id
           WHERE np.user_id = ?""",
        (user_id,),
    ).fetchone()

    if row is None:
        _create_default_preferences(user_id)
        # Retry once — if still missing, user may not exist in users table
        conn.close()
        conn = _get_conn()
        row = conn.execute(
            """SELECT np.*, u.telegram_chat_id
               FROM notification_preferences np
               JOIN users u ON u.id = np.user_id
               WHERE np.user_id = ?""",
            (user_id,),
        ).fetchone()
        if row is None:
            conn.close()
            raise RuntimeError(
                f"Cannot create preferences for user_id={user_id}. "
                f"User may not exist in users table."
            )
        conn.close()
        return dict(row)

    conn.close()
    return dict(row)


def _create_default_preferences(user_id: int) -> None:
    """Insert default preferences for a new user."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO notification_preferences (user_id) VALUES (?)",
        (user_id,),
    )
    conn.commit()
    conn.close()


def get_user_bot_tokens() -> List[Dict]:
    """Return all users who have configured a Telegram bot token.

    Returns list of dicts with keys: user_id, telegram_bot_token, telegram_chat_id.
    Only returns users where telegram_bot_token is set and telegram is enabled.
    """
    conn = _get_conn()
    rows = conn.execute(
        """SELECT np.user_id, np.telegram_bot_token, u.telegram_chat_id
           FROM notification_preferences np
           JOIN users u ON u.id = np.user_id
           WHERE np.telegram_bot_token IS NOT NULL
             AND np.telegram_bot_token != ''
             AND np.telegram_enabled = 1"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]




def set_preferences(user_id: int, **kwargs) -> None:
    """Update notification preferences for a user.

    Example:
        set_preferences(user_id, telegram_enabled=1, check_interval_hours=6)
    """
    if not kwargs:
        return

    # Ensure defaults exist
    get_preferences(user_id)

    set_clauses = [f"{k} = ?" for k in kwargs]
    values = list(kwargs.values()) + [user_id]

    conn = _get_conn()
    conn.execute(
        f"UPDATE notification_preferences SET {', '.join(set_clauses)} WHERE user_id = ?",
        values,
    )
    conn.commit()
    conn.close()


# ─── Notifications CRUD ─────────────────────────────────────

def create_notification(
    user_id: int,
    ticker: str,
    notification_type: str,
    severity: str,
    title: str,
    body: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
) -> int:
    """Insert a notification. Returns the new ID.

    Dedup: skips if an identical (user_id, ticker, type, new_value) notification
    was created in the last 24 hours.
    """
    conn = _get_conn()

    # Dedup check
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    dup = conn.execute(
        """SELECT id FROM notifications
           WHERE user_id = ? AND ticker = ? AND notification_type = ?
             AND new_value = ? AND created_at > ?
           LIMIT 1""",
        (user_id, ticker, notification_type, new_value, cutoff),
    ).fetchone()

    if dup:
        conn.close()
        return int(dup["id"])

    cursor = conn.execute(
        """INSERT INTO notifications
           (user_id, ticker, notification_type, severity, title, body, old_value, new_value)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, ticker, notification_type, severity, title, body, old_value, new_value),
    )
    conn.commit()
    nid = cursor.lastrowid
    conn.close()
    assert nid is not None
    return nid


def get_unread_count(user_id: int) -> int:
    """Return the number of unread notifications for a user."""
    conn = _get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,),
    ).fetchone()[0]
    conn.close()
    return count


def get_notifications(
    user_id: int,
    limit: int = 50,
    unread_only: bool = False,
    ticker: Optional[str] = None,
    severity: Optional[str] = None,
) -> List[Dict]:
    """Get notifications for a user, newest first. Supports optional filters."""
    query = "SELECT * FROM notifications WHERE user_id = ?"
    params: list = [user_id]

    if unread_only:
        query += " AND is_read = 0"
    if ticker:
        query += " AND ticker = ?"
        params.append(ticker.upper())
    if severity:
        query += " AND severity = ?"
        params.append(severity)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    conn = _get_conn()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_read(notification_id: int) -> None:
    """Mark a single notification as read."""
    conn = _get_conn()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()


def mark_all_read(user_id: int) -> None:
    """Mark all notifications for a user as read."""
    conn = _get_conn()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
        (user_id,),
    )
    conn.commit()
    conn.close()


def mark_delivered(notification_id: int, channel: str) -> None:
    """Record which channel delivered this notification."""
    conn = _get_conn()
    conn.execute(
        "UPDATE notifications SET delivered_via = ? WHERE id = ?",
        (channel, notification_id),
    )
    conn.commit()
    conn.close()


def dismiss_notification(notification_id: int) -> None:
    """Soft-delete a notification (sets is_read and clears body)."""
    conn = _get_conn()
    conn.execute(
        "UPDATE notifications SET is_read = 1, body = '[dismissed]' WHERE id = ?",
        (notification_id,),
    )
    conn.commit()
    conn.close()


def prune_old_notifications(days: int = 90) -> int:
    """Delete notifications older than N days. Returns count deleted."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn = _get_conn()
    cursor = conn.execute("DELETE FROM notifications WHERE created_at < ?", (cutoff,))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    return deleted


# ─── Score Snapshots ─────────────────────────────────────────

def get_latest_snapshot(user_id: int, ticker: str) -> Optional[Dict]:
    """Get the most recent score snapshot for a user+ticker, or None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM score_snapshots WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_snapshot(user_id: int, ticker: str, data: Dict) -> None:
    """Insert or update a score snapshot for a user+ticker."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO score_snapshots
           (user_id, ticker, health_score, health_verdict, fscore,
            risk_label, risk_score, red_flag_count,
            price_verdict, intrinsic_verdict, zscore, zscore_zone, snapshot_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(user_id, ticker) DO UPDATE SET
            health_score=excluded.health_score,
            health_verdict=excluded.health_verdict,
            fscore=excluded.fscore,
            risk_label=excluded.risk_label,
            risk_score=excluded.risk_score,
            red_flag_count=excluded.red_flag_count,
            price_verdict=excluded.price_verdict,
            intrinsic_verdict=excluded.intrinsic_verdict,
            zscore=excluded.zscore,
            zscore_zone=excluded.zscore_zone,
            snapshot_date=CURRENT_TIMESTAMP""",
        (
            user_id, ticker.upper(),
            data.get("health_score"), data.get("health_verdict"),
            data.get("fscore"),
            data.get("risk_label"), data.get("risk_score"),
            data.get("red_flag_count"),
            data.get("price_verdict"), data.get("intrinsic_verdict"),
            data.get("zscore"), data.get("zscore_zone"),
        ),
    )
    conn.commit()
    conn.close()


# ─── Check Log ───────────────────────────────────────────────

def get_last_check_time(user_id: int, ticker: str) -> Optional[str]:
    """Get the last check timestamp for a user+ticker, or None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT last_check FROM check_log WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper()),
    ).fetchone()
    conn.close()
    return row["last_check"] if row else None


def update_check_log(user_id: int, ticker: str) -> None:
    """Update the last check timestamp for a user+ticker."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO check_log (user_id, ticker, last_check)
           VALUES (?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(user_id, ticker) DO UPDATE SET last_check=CURRENT_TIMESTAMP""",
        (user_id, ticker.upper()),
    )
    conn.commit()
    conn.close()


# ─── Check Runs ──────────────────────────────────────────────

def start_check_run(user_id: int, job_id: str = "") -> int:
    """Create a new check run record. Returns the run ID."""
    conn = _get_conn()
    cursor = conn.execute(
        "INSERT INTO check_runs (user_id, job_id, status) VALUES (?, ?, 'running')",
        (user_id, job_id),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    assert rid is not None
    return rid


def finish_check_run(
    run_id: int,
    tickers_checked: int,
    notifications_generated: int,
    status: str = "ok",
    error_message: Optional[str] = None,
) -> None:
    """Mark a check run as finished."""
    conn = _get_conn()
    conn.execute(
        """UPDATE check_runs
           SET finished_at=CURRENT_TIMESTAMP, tickers_checked=?,
               notifications_generated=?, status=?, error_message=?
           WHERE id=?""",
        (tickers_checked, notifications_generated, status, error_message, run_id),
    )
    conn.commit()
    conn.close()


def prune_check_runs(max_per_user: int = 200) -> int:
    """Delete old check run entries beyond max_per_user for each user."""
    conn = _get_conn()
    conn.execute("""
        DELETE FROM check_runs WHERE id NOT IN (
            SELECT id FROM check_runs r1
            WHERE r1.user_id = check_runs.user_id
            ORDER BY r1.started_at DESC
            LIMIT ?
        )
    """, (max_per_user,))
    conn.commit()
    deleted = conn.total_changes
    conn.close()
    return deleted


# ─── User Cleanup (for scheduler integration) ────────────────

def get_user_ids_with_watchlist() -> List[int]:
    """Return user IDs that have at least one ticker in their watchlist."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT DISTINCT user_id FROM user_watchlist"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_user_ids_needing_checks() -> List[int]:
    """Return user IDs that need daemon attention.

    Includes users with a watchlist AND/OR active custom alert rules.
    This ensures custom-alert-only users are not silently excluded.
    """
    conn = _get_conn()
    rows = conn.execute("""
        SELECT DISTINCT user_id FROM user_watchlist
        UNION
        SELECT DISTINCT user_id FROM custom_alert_rules WHERE enabled = 1
    """).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_all_active_alerts_grouped_by_ticker() -> Dict[str, List[Dict]]:
    """Return ALL enabled custom alert rules grouped by ticker.

    Returns ``{ticker: [rule_dict, ...], ...}``. Watchlist-scoped rules
    are expanded to every ticker in the user's watchlist. Single-scope
    rules are grouped by their specific ticker.

    Rules without any matching ticker data (no watchlist, no ticker set)
    are excluded.
    """
    conn = _get_conn()
    # Watchlist-scoped rules: expand to every ticker in the user's watchlist
    watch_rules = conn.execute(
        """SELECT r.*, w.ticker AS wticker
           FROM custom_alert_rules r
           JOIN user_watchlist w ON w.user_id = r.user_id
           WHERE r.enabled = 1 AND r.scope = 'watchlist'"""
    ).fetchall()

    # Single-scope rules: use the rule's own ticker
    single_rules = conn.execute(
        """SELECT r.*, r.ticker AS wticker
           FROM custom_alert_rules r
           WHERE r.enabled = 1 AND r.scope = 'single' AND r.ticker IS NOT NULL"""
    ).fetchall()
    conn.close()

    grouped: Dict[str, List[Dict]] = {}
    for row in watch_rules:
        d = dict(row)
        ticker = d.pop("wticker", "").upper()
        if not ticker:
            continue
        grouped.setdefault(ticker, []).append(d)
    for row in single_rules:
        d = dict(row)
        ticker = d.pop("wticker", "").upper()
        if not ticker:
            continue
        grouped.setdefault(ticker, []).append(d)

    return grouped


# ─── Custom Alert Rules CRUD ──────────────────────────────────

def get_custom_alert_rules(user_id: int, enabled_only: bool = True) -> List[Dict]:
    """Return all custom alert rules for a user, newest first."""
    conn = _get_conn()
    query = "SELECT * FROM custom_alert_rules WHERE user_id = ?"
    if enabled_only:
        query += " AND enabled = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_matching_custom_alert_rules(
    user_id: int, ticker: str, enabled_only: bool = True
) -> List[Dict]:
    """Return rules that apply to a given ticker.

    Includes rules with scope='watchlist' (all tickers) plus rules with
    scope='single' that match this specific ticker.
    """
    conn = _get_conn()
    query = """SELECT * FROM custom_alert_rules
               WHERE user_id = ?
                 AND (scope = 'watchlist' OR (scope = 'single' AND ticker = ?))"""
    if enabled_only:
        query += " AND enabled = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, (user_id, ticker.upper())).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_custom_alert_rule(
    user_id: int,
    name: str,
    scope: str = "watchlist",
    ticker: Optional[str] = None,
    conditions: str = "[]",
    logic_operator: str = "AND",
    severity: str = "info",
) -> int:
    """Insert a new custom alert rule. Returns the new rule ID."""
    conn = _get_conn()
    cursor = conn.execute(
        """INSERT INTO custom_alert_rules
           (user_id, name, scope, ticker, conditions, logic_operator, severity)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id, name, scope,
            ticker.upper() if ticker else None,
            conditions, logic_operator, severity,
        ),
    )
    conn.commit()
    rid = cursor.lastrowid
    conn.close()
    assert rid is not None
    return rid


def update_custom_alert_rule(rule_id: int, **kwargs) -> None:
    """Update fields of an existing custom alert rule.

    When conditions or logic_operator change, clears the trigger
    state and deletes stale snapshots so the rule doesn't re-fire
    on stale data.

    Example:
        update_custom_alert_rule(rule_id, name="New Name", enabled=False)
    """
    if not kwargs:
        return

    # Auto-capitalize ticker if provided
    if "ticker" in kwargs and kwargs["ticker"]:
        kwargs["ticker"] = kwargs["ticker"].upper()

    # Always bump updated_at
    set_clauses = [f"{k} = ?" for k in kwargs] + ["updated_at = CURRENT_TIMESTAMP"]
    values = list(kwargs.values()) + [rule_id]

    conn = _get_conn()
    conn.execute(
        f"UPDATE custom_alert_rules SET {', '.join(set_clauses)} WHERE id = ?",
        values,
    )

    # Reset trigger state when conditions change
    if any(k in kwargs for k in ("conditions", "logic_operator")):
        conn.execute(
            "UPDATE custom_alert_rules SET currently_triggered = 0, last_triggered_at = NULL WHERE id = ?",
            (rule_id,),
        )
        # Clear snapshots for this rule's user (all signals, all tickers)
        user_row = conn.execute(
            "SELECT user_id FROM custom_alert_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        if user_row:
            conn.execute(
                "DELETE FROM custom_alert_snapshots WHERE user_id = ?",
                (user_row[0],),
            )

    conn.commit()
    conn.close()


def delete_custom_alert_rule(rule_id: int) -> None:
    """Delete a custom alert rule by ID. Caller should verify ownership."""
    conn = _get_conn()
    conn.execute("DELETE FROM custom_alert_rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()


def toggle_custom_alert_rule(rule_id: int, enabled: bool) -> None:
    """Enable or disable a custom alert rule.

    When disabling, clears the trigger state so re-enabling doesn't
    immediately re-fire on stale data.
    """
    conn = _get_conn()
    conn.execute(
        "UPDATE custom_alert_rules SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (int(enabled), rule_id),
    )
    if not enabled:
        conn.execute(
            "UPDATE custom_alert_rules SET currently_triggered = 0, last_triggered_at = NULL WHERE id = ?",
            (rule_id,),
        )
        # Also clear signal snapshots for this user
        user_row = conn.execute(
            "SELECT user_id FROM custom_alert_rules WHERE id = ?", (rule_id,)
        ).fetchone()
        if user_row:
            conn.execute(
                "DELETE FROM custom_alert_snapshots WHERE user_id = ?",
                (user_row[0],),
            )
    conn.commit()
    conn.close()


def get_custom_alert_rule_by_id(rule_id: int) -> Optional[Dict]:
    """Fetch a single custom alert rule by ID, or None."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM custom_alert_rules WHERE id = ?", (rule_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── Custom Alert Snapshots ───────────────────────────────────

def get_custom_alert_snapshot(
    user_id: int, ticker: str, signal_id: str
) -> Optional[float]:
    """Return the previously stored value for a signal+ticker, or None."""
    conn = _get_conn()
    row = conn.execute(
        """SELECT previous_value FROM custom_alert_snapshots
           WHERE user_id = ? AND ticker = ? AND signal_id = ?""",
        (user_id, ticker.upper(), signal_id),
    ).fetchone()
    conn.close()
    return row["previous_value"] if row else None


def save_custom_alert_snapshot(
    user_id: int, ticker: str, signal_id: str, value: float
) -> None:
    """Upsert the previous value for a signal+ticker."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO custom_alert_snapshots
           (user_id, ticker, signal_id, previous_value, snapshot_date)
           VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(user_id, ticker, signal_id) DO UPDATE SET
            previous_value=excluded.previous_value,
            snapshot_date=CURRENT_TIMESTAMP""",
        (user_id, ticker.upper(), signal_id, value),
    )
    conn.commit()
    conn.close()
