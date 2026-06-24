"""Integration tests for the IDOR (Insecure Direct Object Reference) fix.

Every user-scoped endpoint must verify the session token matches the
requested user_id. Tests use a temp database with two users (Alice, Bob).

Test pattern for each endpoint:
  1. No session token -> 401
  2. Wrong user's session -> 403
  3. Own session -> 200 (or appropriate success code)
"""

import json
import os

os.environ.setdefault("SENTINEL_API_KEY", "test-key")

import pytest
from src.api.server import app
from src.data.auth_db import (
    register_user,
    create_session,
)
from src.data.watchlist_db import add_user_ticker
from src.data.notification_db import (
    create_notification,
    create_custom_alert_rule,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def client(notification_db):
    """Flask test client wired to the temp notification_db."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def alice(notification_db):
    """Register Alice and return {user, session_token}."""
    user = register_user("alice", "pass_a", display_name="Alice")
    assert user is not None
    token = create_session(user["id"])
    return {**user, "session_token": token}


@pytest.fixture
def bob(notification_db):
    """Register Bob and return {user, session_token}."""
    user = register_user("bob", "pass_b", display_name="Bob")
    assert user is not None
    token = create_session(user["id"])
    return {**user, "session_token": token}


def _headers(token=None):
    h = {"X-API-Key": "test-key"}
    if token:
        h["X-Session-Token"] = token
    return h


# ─── Watchlist Endpoints ───────────────────────────────────────────────────


class TestWatchlistIDOR:
    GET = "/api/watchlist/{}"
    COUNT = "/api/watchlist/{}/count"
    HAS = "/api/watchlist/{}/has/AAPL"
    ENRICHED = "/api/watchlist/{}/enriched"
    ADD = "/api/watchlist"
    CLEAR = "/api/watchlist/{}"
    REMOVE = "/api/watchlist/{}/AAPL"

    @pytest.fixture(autouse=True)
    def seed(self, notification_db, alice):
        """Give Alice one ticker so enriched/remove/has/count work."""
        add_user_ticker(alice["id"], "AAPL")

    # -- api_get_watchlist --
    def test_get_watchlist_no_session(self, client, alice):
        r = client.get(self.GET.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_get_watchlist_wrong_user(self, client, alice, bob):
        r = client.get(self.GET.format(alice["id"]),
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_get_watchlist_ok(self, client, alice):
        r = client.get(self.GET.format(alice["id"]),
                       headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_watchlist_count --
    def test_watchlist_count_no_session(self, client, alice):
        r = client.get(self.COUNT.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_watchlist_count_wrong_user(self, client, alice, bob):
        r = client.get(self.COUNT.format(alice["id"]),
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_watchlist_count_ok(self, client, alice):
        r = client.get(self.COUNT.format(alice["id"]),
                       headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_watchlist_has --
    def test_watchlist_has_no_session(self, client, alice):
        r = client.get(self.HAS.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_watchlist_has_wrong_user(self, client, alice, bob):
        r = client.get(self.HAS.format(alice["id"]),
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_watchlist_has_ok(self, client, alice):
        r = client.get(self.HAS.format(alice["id"]),
                       headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_get_enriched_watchlist --
    def test_enriched_watchlist_no_session(self, client, alice):
        r = client.get(self.ENRICHED.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_enriched_watchlist_wrong_user(self, client, alice, bob):
        r = client.get(self.ENRICHED.format(alice["id"]),
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_enriched_watchlist_ok(self, client, alice):
        r = client.get(self.ENRICHED.format(alice["id"]),
                       headers=_headers(alice["session_token"]))
        # enriched makes yfinance calls; may 503 if no network but shouldn't 401/403
        assert r.status_code in (200, 503)

    # -- api_add_ticker (user_id in body) --
    def test_add_ticker_no_session(self, client, alice):
        r = client.post(self.ADD, json={"user_id": alice["id"], "ticker": "MSFT"},
                        headers=_headers())
        assert r.status_code == 401

    def test_add_ticker_wrong_user(self, client, alice, bob):
        r = client.post(self.ADD, json={"user_id": alice["id"], "ticker": "MSFT"},
                        headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_add_ticker_ok(self, client, alice):
        r = client.post(self.ADD, json={"user_id": alice["id"], "ticker": "MSFT"},
                        headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_clear_watchlist --
    def test_clear_watchlist_no_session(self, client, alice):
        r = client.delete(self.CLEAR.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_clear_watchlist_wrong_user(self, client, alice, bob):
        r = client.delete(self.CLEAR.format(alice["id"]),
                          headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_clear_watchlist_ok(self, client, alice):
        r = client.delete(self.CLEAR.format(alice["id"]),
                          headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_remove_ticker --
    def test_remove_ticker_no_session(self, client, alice):
        r = client.delete(self.REMOVE.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_remove_ticker_wrong_user(self, client, alice, bob):
        r = client.delete(self.REMOVE.format(alice["id"]),
                          headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_remove_ticker_ok(self, client, alice):
        r = client.delete(self.REMOVE.format(alice["id"]),
                          headers=_headers(alice["session_token"]))
        assert r.status_code == 200


# ─── User Endpoints ────────────────────────────────────────────────────────


class TestUserIDOR:
    USER = "/api/user/{}"
    LINK_TG = "/api/user/{}/link-telegram"

    # -- api_get_user --
    def test_get_user_no_session(self, client, alice):
        r = client.get(self.USER.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_get_user_wrong_user(self, client, alice, bob):
        r = client.get(self.USER.format(alice["id"]),
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_get_user_ok(self, client, alice):
        r = client.get(self.USER.format(alice["id"]),
                       headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_link_telegram --
    def test_link_telegram_no_session(self, client, alice):
        r = client.post(self.LINK_TG.format(alice["id"]),
                        json={"chat_id": "123"}, headers=_headers())
        assert r.status_code == 401

    def test_link_telegram_wrong_user(self, client, alice, bob):
        r = client.post(self.LINK_TG.format(alice["id"]),
                        json={"chat_id": "123"},
                        headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_link_telegram_ok(self, client, alice):
        r = client.post(self.LINK_TG.format(alice["id"]),
                        json={"chat_id": "123"},
                        headers=_headers(alice["session_token"]))
        assert r.status_code == 200


# ─── Notification Endpoints ────────────────────────────────────────────────


class TestNotificationIDOR:
    LIST = "/api/notifications/{}"
    UNREAD = "/api/notifications/{}/unread-count"
    MARK_READ = "/api/notifications/{}/mark-read"
    MARK_ALL_READ = "/api/notifications/{}/mark-all-read"
    DISMISS = "/api/notifications/{}/dismiss"

    @pytest.fixture(autouse=True)
    def seed(self, notification_db, alice):
        """Give Alice one notification."""
        create_notification(alice["id"], "AAPL", "test", "info", "Hello")

    # -- api_get_notifications --
    def test_get_notifications_no_session(self, client, alice):
        r = client.get(self.LIST.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_get_notifications_wrong_user(self, client, alice, bob):
        r = client.get(self.LIST.format(alice["id"]),
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_get_notifications_ok(self, client, alice):
        r = client.get(self.LIST.format(alice["id"]),
                       headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_unread_count --
    def test_unread_count_no_session(self, client, alice):
        r = client.get(self.UNREAD.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_unread_count_wrong_user(self, client, alice, bob):
        r = client.get(self.UNREAD.format(alice["id"]),
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_unread_count_ok(self, client, alice):
        r = client.get(self.UNREAD.format(alice["id"]),
                       headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_mark_read --
    def test_mark_read_no_session(self, client, alice):
        r = client.post(self.MARK_READ.format(alice["id"]),
                        json={"notification_id": 1}, headers=_headers())
        assert r.status_code == 401

    def test_mark_read_wrong_user(self, client, alice, bob):
        r = client.post(self.MARK_READ.format(alice["id"]),
                        json={"notification_id": 1},
                        headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_mark_read_ok(self, client, alice):
        r = client.post(self.MARK_READ.format(alice["id"]),
                        json={"notification_id": 1},
                        headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_mark_all_read --
    def test_mark_all_read_no_session(self, client, alice):
        r = client.post(self.MARK_ALL_READ.format(alice["id"]),
                        headers=_headers())
        assert r.status_code == 401

    def test_mark_all_read_wrong_user(self, client, alice, bob):
        r = client.post(self.MARK_ALL_READ.format(alice["id"]),
                        headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_mark_all_read_ok(self, client, alice):
        r = client.post(self.MARK_ALL_READ.format(alice["id"]),
                        headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_dismiss_notification --
    def test_dismiss_no_session(self, client, alice):
        r = client.post(self.DISMISS.format(alice["id"]),
                        json={"notification_id": 1}, headers=_headers())
        assert r.status_code == 401

    def test_dismiss_wrong_user(self, client, alice, bob):
        r = client.post(self.DISMISS.format(alice["id"]),
                        json={"notification_id": 1},
                        headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_dismiss_ok(self, client, alice):
        r = client.post(self.DISMISS.format(alice["id"]),
                        json={"notification_id": 1},
                        headers=_headers(alice["session_token"]))
        assert r.status_code == 200


# ─── Alert Endpoints ───────────────────────────────────────────────────────


class TestAlertIDOR:
    LIST = "/api/alerts/{}"
    CREATE = "/api/alerts/{}"
    UPDATE = "/api/alerts/{}/1"
    DELETE = "/api/alerts/{}/1"
    TOGGLE = "/api/alerts/{}/1/toggle"

    @pytest.fixture(autouse=True)
    def seed(self, notification_db, alice):
        """Give Alice one alert rule."""
        create_custom_alert_rule(alice["id"], "Test Alert", "price_above",
                                 conditions=json.dumps({"price": 200}))

    # -- api_get_alerts --
    def test_get_alerts_no_session(self, client, alice):
        r = client.get(self.LIST.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_get_alerts_wrong_user(self, client, alice, bob):
        r = client.get(self.LIST.format(alice["id"]),
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_get_alerts_ok(self, client, alice):
        r = client.get(self.LIST.format(alice["id"]),
                       headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_create_alert --
    def test_create_alert_no_session(self, client, alice):
        r = client.post(self.CREATE.format(alice["id"]),
                        json={"name": "New", "signal": "price_above",
                              "conditions": {"price": 100}},
                        headers=_headers())
        assert r.status_code == 401

    def test_create_alert_wrong_user(self, client, alice, bob):
        r = client.post(self.CREATE.format(alice["id"]),
                        json={"name": "New", "signal": "price_above",
                              "conditions": {"price": 100}},
                        headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_create_alert_ok(self, client, alice):
        r = client.post(self.CREATE.format(alice["id"]),
                        json={"name": "New", "signal": "price_above",
                              "conditions": {"price": 100}},
                        headers=_headers(alice["session_token"]))
        assert r.status_code in (200, 201)

    # -- api_update_alert --
    def test_update_alert_no_session(self, client, alice):
        r = client.put(self.UPDATE.format(alice["id"]),
                       json={"name": "Updated"},
                       headers=_headers())
        assert r.status_code == 401

    def test_update_alert_wrong_user(self, client, alice, bob):
        r = client.put(self.UPDATE.format(alice["id"]),
                       json={"name": "Updated"},
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_update_alert_ok(self, client, alice):
        r = client.put(self.UPDATE.format(alice["id"]),
                       json={"name": "Updated"},
                       headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_delete_alert --
    def test_delete_alert_no_session(self, client, alice):
        r = client.delete(self.DELETE.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_delete_alert_wrong_user(self, client, alice, bob):
        r = client.delete(self.DELETE.format(alice["id"]),
                          headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_delete_alert_ok(self, client, alice):
        r = client.delete(self.DELETE.format(alice["id"]),
                          headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_toggle_alert --
    def test_toggle_alert_no_session(self, client, alice):
        r = client.post(self.TOGGLE.format(alice["id"]),
                        json={"enabled": False}, headers=_headers())
        assert r.status_code == 401

    def test_toggle_alert_wrong_user(self, client, alice, bob):
        r = client.post(self.TOGGLE.format(alice["id"]),
                        json={"enabled": False},
                        headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_toggle_alert_ok(self, client, alice):
        r = client.post(self.TOGGLE.format(alice["id"]),
                        json={"enabled": False},
                        headers=_headers(alice["session_token"]))
        assert r.status_code == 200


# ─── Preferences Endpoints ─────────────────────────────────────────────────


class TestPreferencesIDOR:
    GET = "/api/preferences/{}"
    SET = "/api/preferences/{}"

    @pytest.fixture(autouse=True)
    def _reset_rate_limit(self):
        """Clear rate limit bucket so 60 prior tests don't cause 429."""
        from src.api.server import _rate_limits
        _rate_limits.clear()

    # -- api_get_preferences --
    def test_get_preferences_no_session(self, client, alice):
        r = client.get(self.GET.format(alice["id"]), headers=_headers())
        assert r.status_code == 401

    def test_get_preferences_wrong_user(self, client, alice, bob):
        r = client.get(self.GET.format(alice["id"]),
                       headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_get_preferences_ok(self, client, alice):
        r = client.get(self.GET.format(alice["id"]),
                       headers=_headers(alice["session_token"]))
        assert r.status_code == 200

    # -- api_set_preferences --
    def test_set_preferences_no_session(self, client, alice):
        r = client.post(self.SET.format(alice["id"]),
                        json={"telegram_enabled": True}, headers=_headers())
        assert r.status_code == 401

    def test_set_preferences_wrong_user(self, client, alice, bob):
        r = client.post(self.SET.format(alice["id"]),
                        json={"telegram_enabled": True},
                        headers=_headers(bob["session_token"]))
        assert r.status_code == 403

    def test_set_preferences_ok(self, client, alice):
        r = client.post(self.SET.format(alice["id"]),
                        json={"telegram_enabled": True},
                        headers=_headers(alice["session_token"]))
        assert r.status_code == 200
