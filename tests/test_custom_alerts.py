"""Tests for custom_alerts.py — rule_id, hysteresis, cross operators."""

import json

import pandas as pd

from src.notifications.custom_alerts import (
    evaluate_custom_alerts,
    _evaluate_single_rule,
    _build_merged_params,
    _op_crosses_above,
    _op_crosses_below,
)
from tests.helpers import seed_custom_alert_rule, make_market_data


# ─── _evaluate_single_rule: rule_id in return dict ──────────────

class TestEvaluateSingleRule:
    """Return dict must include rule_id for push delivery routing."""

    def test_rule_id_in_return_dict(self, notification_db):
        """The returned notification dict must contain rule_id."""
        rule = {
            "id": 42,
            "conditions": json.dumps([
                {"signal_id": "price", "operator": ">", "value": 100.0}
            ]),
            "logic_operator": "AND",
            "name": "Price Alert",
            "severity": "info",
            "currently_triggered": 0,
        }
        data = make_market_data(price=150.0)
        result = _evaluate_single_rule(rule, data, {}, 1, "NVDA")
        assert result is not None
        assert result["rule_id"] == 42
        assert result["type"] == "custom_alert"

    def test_no_snapshot_skip_cross_operator(self, notification_db):
        """Cross operators with no previous snapshot should return None."""
        rule = {
            "id": 43,
            "conditions": json.dumps([
                {"signal_id": "price", "operator": "crosses_above", "value": 100.0}
            ]),
            "logic_operator": "AND",
            "name": "Cross Alert",
            "severity": "info",
            "currently_triggered": 0,
        }
        data = make_market_data(price=150.0)
        # No snapshot exists, so cross operator should skip this condition
        result = _evaluate_single_rule(rule, data, {}, 1, "NVDA")
        # With a single cross condition that has no snapshot, results is empty -> None
        assert result is None

    def test_cross_operator_with_snapshot(self, notification_db):
        """Cross operator should fire when previous <= threshold and current > threshold."""
        # Save a snapshot first
        from src.data.notification_db import save_custom_alert_snapshot
        save_custom_alert_snapshot(1, "NVDA", "price", 90.0)

        rule = {
            "id": 44,
            "conditions": json.dumps([
                {"signal_id": "price", "operator": "crosses_above", "value": 100.0}
            ]),
            "logic_operator": "AND",
            "name": "Cross Above Alert",
            "severity": "info",
            "currently_triggered": 0,
        }
        data = make_market_data(price=150.0)
        result = _evaluate_single_rule(rule, data, {}, 1, "NVDA")
        assert result is not None
        assert result["rule_id"] == 44
        assert result["title"] == "⚡ Cross Above Alert"

    def test_condition_not_met_no_notification(self, notification_db):
        """Rule should return None when condition is not met."""
        rule = {
            "id": 45,
            "conditions": json.dumps([
                {"signal_id": "price", "operator": ">", "value": 200.0}
            ]),
            "logic_operator": "AND",
            "name": "High Price Alert",
            "severity": "info",
            "currently_triggered": 0,
        }
        data = make_market_data(price=150.0)
        result = _evaluate_single_rule(rule, data, {}, 1, "NVDA")
        assert result is None

    def test_unknown_signal_skipped(self, notification_db):
        """Conditions with unknown signal_id should be silently skipped."""
        rule = {
            "id": 46,
            "conditions": json.dumps([
                {"signal_id": "nonexistent_signal", "operator": ">", "value": 100.0}
            ]),
            "logic_operator": "AND",
            "name": "Bad Signal",
            "severity": "info",
            "currently_triggered": 0,
        }
        data = make_market_data(price=150.0)
        result = _evaluate_single_rule(rule, data, {}, 1, "NVDA")
        assert result is None  # No valid conditions


# ─── Hysteresis Tests ───────────────────────────────────────────

class TestHysteresis:
    """Rule must fire once, then suppress until condition resets."""

    def test_fire_once(self, notification_db):
        """Rule with matching condition fires when not currently_triggered."""
        conn = notification_db
        rid = seed_custom_alert_rule(
            conn, user_id=1, ticker="NVDA", signal_id="price",
            operator=">", value=100.0, currently_triggered=0,
        )
        data = make_market_data(price=150.0)
        notifications = evaluate_custom_alerts(1, "NVDA", data, {})
        assert len(notifications) == 1
        assert notifications[0]["rule_id"] == rid

        # Verify DB was updated
        row = conn.execute(
            "SELECT currently_triggered FROM custom_alert_rules WHERE id = ?",
            (rid,),
        ).fetchone()
        assert row["currently_triggered"] == 1

    def test_suppress_when_triggered(self, notification_db):
        """Rule should NOT fire when currently_triggered and condition still holds."""
        conn = notification_db
        _ = seed_custom_alert_rule(
            conn, user_id=1, ticker="NVDA", signal_id="price",
            operator=">", value=100.0, currently_triggered=1,
        )
        data = make_market_data(price=150.0)
        notifications = evaluate_custom_alerts(1, "NVDA", data, {})
        assert len(notifications) == 0  # Suppressed

    def test_reset_on_condition_false(self, notification_db):
        """When currently_triggered and condition is no longer met, reset to 0."""
        conn = notification_db
        rid = seed_custom_alert_rule(
            conn, user_id=1, ticker="NVDA", signal_id="price",
            operator=">", value=200.0, currently_triggered=1,
        )
        data = make_market_data(price=150.0)
        notifications = evaluate_custom_alerts(1, "NVDA", data, {})
        assert len(notifications) == 0  # Condition not met, no notification

        # Verify DB was reset
        row = conn.execute(
            "SELECT currently_triggered FROM custom_alert_rules WHERE id = ?",
            (rid,),
        ).fetchone()
        assert row["currently_triggered"] == 0

    def test_fire_then_reset_then_fire_again(self, notification_db):
        """Full cycle: fire -> suppress -> reset -> fire again."""
        conn = notification_db
        rid = seed_custom_alert_rule(
            conn, user_id=1, ticker="NVDA", signal_id="price",
            operator=">", value=100.0, currently_triggered=0,
        )

        # Cycle 1: price=150 > 100 -> fire
        n1 = evaluate_custom_alerts(1, "NVDA", make_market_data(price=150.0), {})
        assert len(n1) == 1

        # Cycle 2: price=150 > 100 -> suppress (still triggered)
        n2 = evaluate_custom_alerts(1, "NVDA", make_market_data(price=150.0), {})
        assert len(n2) == 0

        # Cycle 3: price=50 < 100 -> reset
        n3 = evaluate_custom_alerts(1, "NVDA", make_market_data(price=50.0), {})
        assert len(n3) == 0
        row = conn.execute(
            "SELECT currently_triggered FROM custom_alert_rules WHERE id = ?",
            (rid,),
        ).fetchone()
        assert row["currently_triggered"] == 0

        # Cycle 4: price=150 > 100 -> fire again
        n4 = evaluate_custom_alerts(1, "NVDA", make_market_data(price=150.0), {})
        assert len(n4) == 1

    def test_cross_operator_suppressed_after_fire(self, notification_db):
        """Cross operators must also respect currently_triggered."""
        from src.data.notification_db import save_custom_alert_snapshot
        conn = notification_db
        save_custom_alert_snapshot(1, "NVDA", "price", 90.0)
        _ = seed_custom_alert_rule(
            conn, user_id=1, ticker="NVDA", signal_id="price",
            operator="crosses_above", value=100.0, currently_triggered=0,
        )

        # First call: crosses above -> fire
        n1 = evaluate_custom_alerts(1, "NVDA", make_market_data(price=150.0), {})
        assert len(n1) == 1

        # Second call: still triggered -> suppress
        n2 = evaluate_custom_alerts(1, "NVDA", make_market_data(price=150.0), {})
        assert len(n2) == 0

    def test_history_override_reconciliation_mode(self, notification_db):
        """evaluate_custom_alerts with history_override skips yfinance calls."""
        conn = notification_db
        _ = seed_custom_alert_rule(
            conn, user_id=1, ticker="NVDA", signal_id="rsi",
            operator=">", value=30.0, currently_triggered=0,
        )
        # Provide a fake history with RSI-compatible data
        dates = pd.date_range(end="2024-01-15", periods=20, freq="D")
        fake_history = pd.DataFrame(
            {"Close": [100.0 + i for i in range(20)]},
            index=dates,
        )
        data = make_market_data(price=150.0)
        notifications = evaluate_custom_alerts(
            1, "NVDA", data, {},
            history_override=fake_history,
        )
        # Should evaluate without calling yfinance (assert no crash)
        assert isinstance(notifications, list)


# ─── _build_merged_params ───────────────────────────────────────

class TestBuildMergedParams:
    def test_simple_params(self):
        """Static (non-dict) params pass through directly."""
        signal_def = {"params": {"score_key": "health_score"}}
        merged = _build_merged_params(signal_def, {})
        assert merged == {"score_key": "health_score"}

    def test_dict_params_with_default(self):
        """Dict-style params use default when no override provided."""
        signal_def = {"params": {"days": {"type": "int", "default": 5}}}
        merged = _build_merged_params(signal_def, {})
        assert merged["days"] == 5

    def test_dict_params_with_override(self):
        """Dict-style params use condition override when provided."""
        signal_def = {"params": {"days": {"type": "int", "default": 5}}}
        merged = _build_merged_params(signal_def, {"days": 10})
        assert merged["days"] == 10

    def test_empty_params(self):
        assert _build_merged_params({"params": {}}, {}) == {}
        assert _build_merged_params({}, {}) == {}


# ─── Operator Unit Tests ────────────────────────────────────────

class TestCrossOperators:
    def test_crosses_above_true(self):
        """previous <= threshold and current > threshold."""
        assert _op_crosses_above(110.0, 90.0, 100.0) is True   # 90 <= 100 AND 110 > 100
        assert _op_crosses_above(110.0, 100.0, 100.0) is True  # 100 <= 100 AND 110 > 100

    def test_crosses_above_false(self):
        """Either previous > threshold or current <= threshold."""
        assert _op_crosses_above(110.0, 110.0, 100.0) is False  # 110 > 100 → False
        assert _op_crosses_above(90.0, 90.0, 100.0) is False    # 90 <= 100 but 90 <= 100 → second condition False

    def test_crosses_above_no_previous(self):
        """No snapshot available → always return False."""
        assert _op_crosses_above(110.0, None, 100.0) is False

    def test_crosses_below_true(self):
        """previous >= threshold and current < threshold."""
        assert _op_crosses_below(90.0, 110.0, 100.0) is True   # 110 >= 100 AND 90 < 100
        assert _op_crosses_below(90.0, 100.0, 100.0) is True   # 100 >= 100 AND 90 < 100

    def test_crosses_below_false(self):
        """Either previous < threshold or current >= threshold."""
        assert _op_crosses_below(50.0, 50.0, 100.0) is False   # 50 >= 100 → False
        assert _op_crosses_below(110.0, 110.0, 100.0) is False  # 110 >= 100 but 110 > 100 → second condition False

    def test_crosses_below_no_previous(self):
        """No snapshot available → always return False."""
        assert _op_crosses_below(90.0, None, 100.0) is False
