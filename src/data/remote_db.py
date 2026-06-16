"""
Remote database client for Sentinel Streamlit Cloud.

When SENTINEL_API_URL is configured in .streamlit/secrets.toml,
all database operations are routed through the VPS HTTP API
instead of the local SQLite file. This ensures the Streamlit
Cloud dashboard sees the same data as the VPS daemon and
Telegram bot commands.

Graceful degradation: if the API is unreachable, operations
fall back to local SQLite silently.

Usage:
    from src.data.remote_db import init_remote_db, get_remote_db

    init_remote_db("https://api.example.com", "secret-key")
    remote = get_remote_db()
    tickers = remote.load_user_watchlist(1)
"""

import time
import logging
from typing import Optional, List, Dict

import requests

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10


class RemoteDB:
    """HTTP client for the Sentinel VPS API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})
        # Simple in-memory cache for read operations
        self._cache: dict[str, tuple[float, dict]] = {}
        self._cache_ttl = 30  # seconds

    def _get(self, path: str, cache_key: Optional[str] = None) -> Optional[Dict]:
        """GET with optional caching."""
        if cache_key and cache_key in self._cache:
            ts, data = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return data
        try:
            resp = self.session.get(
                f"{self.base_url}{path}", timeout=_DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json()
            if cache_key:
                self._cache[cache_key] = (time.time(), data)
            return data
        except requests.RequestException as e:
            logger.warning("RemoteDB GET %s failed: %s", path, e)
            return None

    def _post(self, path: str, json: Dict) -> Optional[Dict]:
        """POST with cache invalidation."""
        try:
            resp = self.session.post(
                f"{self.base_url}{path}", json=json, timeout=_DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            self._invalidate(path)
            return resp.json()
        except requests.RequestException as e:
            logger.warning("RemoteDB POST %s failed: %s", path, e)
            return None

    def _delete(self, path: str) -> Optional[Dict]:
        """DELETE with cache invalidation."""
        try:
            resp = self.session.delete(
                f"{self.base_url}{path}", timeout=_DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            self._invalidate(path)
            return resp.json()
        except requests.RequestException as e:
            logger.warning("RemoteDB DELETE %s failed: %s", path, e)
            return None

    def _invalidate(self, path: str) -> None:
        """Clear cache entries related to a write path."""
        parts = path.split("/")
        # Invalidate all watchlist caches after any watchlist write
        if "watchlist" in path:
            keys_to_delete = [k for k in self._cache if k.startswith("wl:")]
            for k in keys_to_delete:
                del self._cache[k]
        # Invalidate user-specific caches
        if len(parts) >= 3:
            identifier = parts[2]
            keys_to_delete = [k for k in self._cache if identifier in k]
            for k in keys_to_delete:
                del self._cache[k]

    # ─── Watchlist ─────────────────────────────────────
    def load_user_watchlist(self, user_id: int) -> List[str]:
        data = self._get(f"/api/watchlist/{user_id}", cache_key=f"wl:{user_id}")
        return data["tickers"] if data else []

    def add_user_ticker(self, user_id: int, ticker: str) -> None:
        self._post("/api/watchlist", {"user_id": user_id, "ticker": ticker})

    def remove_user_ticker(self, user_id: int, ticker: str) -> None:
        self._delete(f"/api/watchlist/{user_id}/{ticker}")

    # ─── Auth ──────────────────────────────────────────
    def get_user(self, user_id: int) -> Optional[Dict]:
        data = self._get(f"/api/user/{user_id}", cache_key=f"usr:{user_id}")
        return data.get("user") if data else None

    def register_user(self, username: str, password: str, **kwargs) -> Optional[Dict]:
        body = {"username": username, "password": password, **kwargs}
        data = self._post("/api/user/register", body)
        return data.get("user") if data else None

    def login_user(self, username: str, password: str) -> Optional[Dict]:
        body = {"username": username, "password": password}
        data = self._post("/api/user/login", body)
        if data and data.get("user"):
            user = data["user"]
            if data.get("session_token"):
                user["_session_token"] = data["session_token"]
            return user
        return None

    # ─── Notifications ─────────────────────────────────
    def get_notifications(self, user_id: int, limit: int = 50, unread_only: bool = False) -> List[Dict]:
        qs = f"?limit={limit}&unread_only={'true' if unread_only else 'false'}"
        data = self._get(f"/api/notifications/{user_id}{qs}")
        return data.get("notifications", []) if data else []

    def get_unread_count(self, user_id: int) -> int:
        data = self._get(f"/api/notifications/{user_id}/unread-count")
        return data.get("count", 0) if data else 0

    def get_preferences(self, user_id: int) -> Dict:
        data = self._get(f"/api/preferences/{user_id}", cache_key=f"prefs:{user_id}")
        return data.get("preferences", {}) if data else {}

    def set_preferences(self, user_id: int, **kwargs) -> None:
        self._post(f"/api/preferences/{user_id}", kwargs)

    def is_available(self) -> bool:
        """Check if the remote API is reachable."""
        try:
            resp = self.session.get(
                f"{self.base_url}/api/health", timeout=5
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False


# ─── Module-level singleton ──────────────────────────

_remote: Optional[RemoteDB] = None


def init_remote_db(base_url: str, api_key: str) -> Optional[RemoteDB]:
    """Initialize the remote DB client. Returns None if config is empty."""
    global _remote
    if not base_url or not api_key:
        _remote = None
        return None
    _remote = RemoteDB(base_url, api_key)
    return _remote


def get_remote_db() -> Optional[RemoteDB]:
    """Return the initialized remote DB client, or None."""
    return _remote
