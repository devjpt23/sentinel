"""Tests for daemon.py — reconciliation_tick and main loop integration."""

from unittest.mock import patch

import pandas as pd

from src.notifications.daemon import reconciliation_tick
from tests.helpers import seed_custom_alert_rule


class TestReconciliationTick:
    """Must run without errors in various DB states."""

    def test_empty_db(self, notification_db):
        """Empty DB should not throw."""
        reconciliation_tick()

    def test_disabled_rules_only(self, notification_db):
        """Only disabled rules should not trigger anything."""
        seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", enabled=False,
        )
        reconciliation_tick()

    def test_no_market_data(self, notification_db):
        """Rules with no market data should be handled gracefully."""
        seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", signal_id="price",
            operator=">", value=100.0,
        )
        reconciliation_tick()

    def test_with_market_data(self, notification_db):
        """Full flow with market data should not error."""
        seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA", signal_id="price",
            operator=">", value=100.0,
        )
        with patch(
            "src.notifications.daemon._fetcher"
        ) as mock_fetcher:
            mock_fetcher.fetch_many.return_value = {
                "NVDA": {
                    "ticker": "NVDA",
                    "market": {"price": 150.0},
                    "history": pd.DataFrame(),
                }
            }
            # Should complete without error (no notifications delivered
            # since evaluate_custom_alerts internally fetches rules from DB
            # and will find the rule but _fetcher's data won't propagate)
            reconciliation_tick()

    def test_multiple_users_same_ticker(self, notification_db):
        """Two users with rules on same ticker should not error."""
        seed_custom_alert_rule(
            notification_db, user_id=1, ticker="NVDA",
        )
        seed_custom_alert_rule(
            notification_db, user_id=2, ticker="NVDA",
        )
        with patch(
            "src.notifications.daemon._fetcher"
        ) as mock_fetcher:
            mock_fetcher.fetch_many.return_value = {
                "NVDA": {
                    "ticker": "NVDA",
                    "market": {"price": 150.0},
                    "history": pd.DataFrame(),
                }
            }
            reconciliation_tick()
