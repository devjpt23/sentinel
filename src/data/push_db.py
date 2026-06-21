"""Push subscription storage helpers. Plain functions, raw SQLite."""

import sqlite3
import os
from typing import List, Optional
from dataclasses import dataclass

_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "watchlist.db",
)

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@dataclass
class PushSubscription:
    id: int
    user_id: int
    endpoint: str
    p256dh: str
    auth: str
    browser: Optional[str]

def upsert_push_subscription(user_id: int, endpoint: str, p256dh: str, auth: str, browser: str) -> None:
    """Insert or update a push subscription."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth, browser, created_at)
           VALUES (?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(endpoint) DO UPDATE SET
               user_id=excluded.user_id,
               p256dh=excluded.p256dh,
               auth=excluded.auth,
               browser=excluded.browser,
               last_used=datetime('now')""",
        (user_id, endpoint, p256dh, auth, browser),
    )
    conn.commit()
    conn.close()

def remove_push_subscription(endpoint: str) -> None:
    """Mark a push subscription as inactive."""
    conn = _get_conn()
    conn.execute("UPDATE push_subscriptions SET active = 0 WHERE endpoint = ?", (endpoint,))
    conn.commit()
    conn.close()

def get_push_subscriptions_for_user(user_id: int) -> List[PushSubscription]:
    """Return all active push subscriptions for a user."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, user_id, endpoint, p256dh, auth, browser "
        "FROM push_subscriptions WHERE user_id = ? AND active = 1",
        (user_id,),
    ).fetchall()
    conn.close()
    return [PushSubscription(**dict(row)) for row in rows]

def get_all_active_subscriptions(user_ids: List[int]) -> dict:
    """Batch fetch all active subscriptions for multiple users. Returns {user_id: [PushSubscription]}."""
    if not user_ids:
        return {}
    conn = _get_conn()
    placeholders = ",".join("?" for _ in user_ids)
    rows = conn.execute(
        f"SELECT id, user_id, endpoint, p256dh, auth, browser "
        f"FROM push_subscriptions WHERE user_id IN ({placeholders}) AND active = 1",
        user_ids,
    ).fetchall()
    conn.close()
    result: dict = {}
    for row in rows:
        uid = row["user_id"]
        result.setdefault(uid, []).append(PushSubscription(**dict(row)))
    return result

def deactivate_push_subscription(subscription_id: int) -> None:
    """Mark a subscription as inactive (expired or revoked)."""
    conn = _get_conn()
    conn.execute("UPDATE push_subscriptions SET active = 0 WHERE id = ?", (subscription_id,))
    conn.commit()
    conn.close()
