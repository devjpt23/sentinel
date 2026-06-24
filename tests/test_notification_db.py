"""Tests for notification_db.py — queries, migrations, and edge cases."""

import json

import pytest

from src.data.notification_db import (
    get_user_ids_needing_checks,
    get_all_active_alerts_grouped_by_ticker,
    get_preferences,
    update_custom_alert_rule,
    toggle_custom_alert_rule,
    create_notification,
    get_unread_count,
)
from tests.helpers import seed_user_watchlist, seed_custom_alert_rule


class TestGetUserIdsNeedingChecks:
    """Must return users from watchlist AND custom_alert_rules (union)."""

    def test_empty_db(self, notification_db):
        assert get_user_ids_needing_checks() == []

    def test_watchlist_user_only(self, notification_db):
        conn = notification_db
        conn.execute(
            "INSERT INTO user_watchlist (user_id, ticker) VALUES (?, ?)",
            (1, "AAPL"),
        )
        conn.commit()
        assert get_user_ids_needing_checks() == [1]

    def test_custom_alert_user_only(self, notification_db):
        seed_custom_alert_rule(notification_db, user_id=2, ticker="NVDA")
        assert get_user_ids_needing_checks() == [2]

    def test_union_no_duplicates(self, notification_db):
        conn = notification_db
        conn.execute(
            "INSERT INTO user_watchlist (user_id, ticker) VALUES (?, ?)",
            (1, "AAPL"),
        )
        conn.commit()
        seed_custom_alert_rule(notification_db, user_id=1, ticker="NVDA")
        seed_custom_alert_rule(notification_db, user_id=2, ticker="TSLA")
        assert sorted(get_user_ids_needing_checks()) == [1, 2]

    def test_disabled_alert_excluded(self, notification_db):
        seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", enabled=False
        )
        assert get_user_ids_needing_checks() == []

    def test_both_watchlist_and_alerts(self, notification_db):
        conn = notification_db
        conn.execute(
            "INSERT INTO user_watchlist (user_id, ticker) VALUES (?, ?)",
            (1, "AAPL"),
        )
        conn.commit()
        seed_custom_alert_rule(notification_db, user_id=2, ticker="NVDA")
        assert sorted(get_user_ids_needing_checks()) == [1, 2]


class TestGetAllActiveAlertsGroupedByTicker:
    """Must group rules by ticker, expanding watchlist-scope rules."""

    def test_empty_db(self, notification_db):
        assert get_all_active_alerts_grouped_by_ticker() == {}

    def test_single_scope_rules_grouped(self, notification_db):
        rid1 = seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", scope="single"
        )
        _ = seed_custom_alert_rule(
            notification_db, user_id=1, ticker="AAPL", scope="single"
        )
        result = get_all_active_alerts_grouped_by_ticker()
        assert set(result.keys()) == {"NVDA", "AAPL"}
        assert len(result["NVDA"]) == 1
        assert result["NVDA"][0]["id"] == rid1

    def test_watchlist_scope_expanded(self, notification_db):
        conn = notification_db
        seed_user_watchlist(conn, 1, ["AAPL", "MSFT"])
        seed_custom_alert_rule(
            notification_db, user_id=1, scope="watchlist"
        )
        result = get_all_active_alerts_grouped_by_ticker()
        assert set(result.keys()) == {"AAPL", "MSFT"}
        # One rule expanded to 2 tickers
        total = sum(len(rules) for rules in result.values())
        assert total == 2

    def test_disabled_rules_excluded(self, notification_db):
        seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", enabled=False
        )
        assert get_all_active_alerts_grouped_by_ticker() == {}

    def test_mixed_scope(self, notification_db):
        conn = notification_db
        seed_user_watchlist(conn, 1, ["AAPL"])
        seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", scope="single"
        )
        seed_custom_alert_rule(
            notification_db, user_id=1, scope="watchlist"
        )
        result = get_all_active_alerts_grouped_by_ticker()
        assert set(result.keys()) == {"NVDA", "AAPL"}
        # NVDA has 1 rule (single-scope), AAPL has 1 (watchlist expanded)
        assert len(result["NVDA"]) == 1
        assert len(result["AAPL"]) == 1


class TestGetPreferences:
    """Must handle missing prefs without infinite recursion."""

    def test_existing_user_prefs(self, notification_db):
        """Preferences are auto-created for any user in the users table."""
        conn = notification_db
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, email, password_hash) VALUES (?, ?, ?, ?)",
            (42, "prefuser", "pref@example.com", "abc"),
        )
        conn.commit()
        prefs = get_preferences(42)
        assert prefs["user_id"] == 42

    def test_missing_user_raises(self, notification_db):
        """Orphan user_id with no users table entry should raise cleanly."""
        with pytest.raises(RuntimeError, match="Cannot create preferences"):
            get_preferences(99999)


class TestSchemaMigrations:
    """currently_triggered column must exist on custom_alert_rules."""

    def test_currently_triggered_column_exists(self, notification_db):
        conn = notification_db
        row = conn.execute(
            "PRAGMA table_info(custom_alert_rules)"
        ).fetchall()
        cols = {r["name"] for r in row}
        assert "currently_triggered" in cols
        assert "last_triggered_at" in cols


class TestUpdateCustomAlertRule:
    """Editing conditions must clear currently_triggered and snapshots."""

    def test_clear_triggered_on_conditions_change(self, notification_db):
        conn = notification_db
        rid = seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", currently_triggered=1
        )
        update_custom_alert_rule(
            rid,
            conditions=json.dumps([
                {"signal_id": "price", "operator": ">", "value": 200.0}
            ]),
        )
        row = conn.execute(
            "SELECT currently_triggered FROM custom_alert_rules WHERE id = ?",
            (rid,),
        ).fetchone()
        assert row["currently_triggered"] == 0

    def test_preserve_triggered_on_name_change(self, notification_db):
        rid = seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", currently_triggered=1
        )
        update_custom_alert_rule(rid, name="New Name")
        conn = notification_db
        row = conn.execute(
            "SELECT currently_triggered FROM custom_alert_rules WHERE id = ?",
            (rid,),
        ).fetchone()
        assert row["currently_triggered"] == 1


class TestToggleCustomAlertRule:
    """Disabling must clear currently_triggered and snapshots."""

    def test_disable_clears_triggered(self, notification_db):
        conn = notification_db
        rid = seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", currently_triggered=1
        )
        toggle_custom_alert_rule(rid, enabled=False)
        row = conn.execute(
            "SELECT currently_triggered, enabled FROM custom_alert_rules WHERE id = ?",
            (rid,),
        ).fetchone()
        assert row["currently_triggered"] == 0
        assert row["enabled"] == 0


class TestNotifications:
    """Basic CRUD for notifications table."""

    def test_create_and_unread_count(self, notification_db):
        nid = create_notification(
            user_id=1,
            ticker="NVDA",
            notification_type="custom_alert",
            severity="info",
            title="Test Alert",
        )
        assert nid is not None
        assert get_unread_count(1) == 1

    def test_unread_count_multi_user(self, notification_db):
        create_notification(user_id=1, ticker="NVDA", notification_type="test", severity="info", title="A")
        create_notification(user_id=2, ticker="AAPL", notification_type="test", severity="info", title="B")
        assert get_unread_count(1) == 1
        assert get_unread_count(2) == 1
