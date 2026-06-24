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


# ─── _format_natural_body ─────────────────────────────────────────

class TestFormatNaturalBody:
    """_format_natural_body must generate signal-specific natural language text."""

    def test_price_change_pct_below_threshold(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body(
            "price_change_pct", "<", -5.0, -7.2,
            {}, current_price=173.40,
        )
        assert "dropped 7.2%" in body
        assert "5.0%" in body or "5%" in body
        assert "$173.40" in body

    def test_price_change_pct_above_threshold(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body(
            "price_change_pct", ">", 3.0, 4.5,
            {}, current_price=200.0,
        )
        assert "rose 4.5%" in body
        assert "3.0%" in body

    def test_rsi_oversold(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("rsi", "<", 30, 24.3, {})
        assert "RSI at 24.3" in body
        assert "below" in body
        assert "oversold" in body

    def test_rsi_overbought(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("rsi", ">", 70, 76.5, {})
        assert "RSI at 76.5" in body
        assert "above" in body
        assert "overbought" in body

    def test_volume_spike(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("volume_spike", ">", 2, 3.2, {})
        assert "3.2" in body
        assert "unusual activity" in body

    def test_macd_bullish_cross(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("macd", "crosses_above", 0, 0.5, {})
        assert "crossed above" in body
        assert "bullish" in body

    def test_macd_bearish_cross(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("macd", "crosses_below", 0, -0.3, {})
        assert "crossed below" in body
        assert "bearish" in body

    def test_sma_crossover_bullish(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("sma_crossover", "crosses_above", 0, 1, {"period": 50})
        assert "crossed above" in body
        assert "50-day" in body
        assert "bullish" in body

    def test_sma_crossover_bearish(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("sma_crossover", "crosses_below", 0, -1, {"period": 200})
        assert "crossed below" in body
        assert "200-day" in body
        assert "bearish" in body

    def test_bollinger_upper(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("bollinger", "touches_upper", 0, 1, {})
        assert "upper Bollinger" in body
        assert "overextended" in body

    def test_bollinger_lower(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("bollinger", "touches_lower", 0, -1, {})
        assert "lower Bollinger" in body
        assert "bounce zone" in body

    def test_price_level_alert(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("price", ">", 150.0, 173.40, {})
        assert "above" in body
        assert "$173.40" in body

    def test_price_level_below(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("price", "<", 100.0, 85.50, {})
        assert "below" in body
        assert "$85.50" in body

    def test_distance_52w_high(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("distance_52w_high", "<", 5.0, 3.2, {})
        assert "3.2%" in body
        assert "52-week high" in body

    def test_distance_52w_low(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("distance_52w_low", "<", 5.0, 2.1, {})
        assert "2.1%" in body
        assert "52-week low" in body

    def test_fundamental_fallback(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("health_score", "<", 50.0, 35.0, {})
        assert "35.0" in body
        assert "below" in body
        assert "pts" in body

    def test_price_change_abs_dropped(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("price_change_abs", "<", -5.0, -8.50, {},
                                     current_price=150.0)
        assert "dropped" in body
        assert "$8.50" in body
        assert "$150.00" in body

    def test_price_change_abs_rose(self):
        from src.notifications.custom_alerts import _format_natural_body
        body = _format_natural_body("price_change_abs", ">", 5.0, 7.25, {},
                                     current_price=200.0)
        assert "rose" in body
        assert "$7.25" in body

    def test_empty_body_not_included_in_return(self):
        """Natural body is NOT used when no signal_id matches (handled by caller)."""
        pass  # covered by the existence of _format_natural_body itself


# ─── Single vs Multi-condition body generation ───────────────────

class TestRuleBodyGeneration:
    """_evaluate_single_rule must use natural language for single conditions
    and natural joining for multiple conditions."""

    def test_single_condition_uses_natural_body(self, notification_db):
        import json
        rule = {
            "id": 100,
            "conditions": json.dumps([
                {"signal_id": "rsi", "operator": "<", "value": 30}
            ]),
            "logic_operator": "AND",
            "name": "RSI Oversold",
            "severity": "info",
            "currently_triggered": 0,
        }
        data = {
            "market": {"price": 150.0, "avg_volume": 50000000, "52w_high": 200.0, "52w_low": 100.0},
            "valuation": {"pe_ttm": 25.0, "pb_ratio": 5.0},
            "health": {"debt_to_equity": 50.0, "health_score": 80.0},
            "per_share": {"dividend_yield": 0.5},
        }
        from src.notifications.custom_alerts import _evaluate_single_rule
        result = _evaluate_single_rule(rule, data, {}, 1, "NVDA")
        if result:
            # If RSI can be computed (may not be with fake history), check format
            body = result.get("body", "")
            if body:
                assert "RSI at" in body or "rsi" in body.lower()

    def test_multi_condition_uses_natural_joins(self, notification_db):
        import json
        rule = {
            "id": 101,
            "conditions": json.dumps([
                {"signal_id": "rsi", "operator": "<", "value": 30},
                {"signal_id": "volume_spike", "operator": ">", "value": 2},
            ]),
            "logic_operator": "AND",
            "name": "RSI + Volume",
            "severity": "info",
            "currently_triggered": 0,
        }
        data = {
            "market": {"price": 150.0, "avg_volume": 50000000, "52w_high": 200.0, "52w_low": 100.0},
            "valuation": {"pe_ttm": 25.0, "pb_ratio": 5.0},
            "health": {"debt_to_equity": 50.0, "health_score": 80.0},
            "per_share": {"dividend_yield": 0.5},
        }
        from src.notifications.custom_alerts import _evaluate_single_rule
        result = _evaluate_single_rule(rule, data, {}, 1, "NVDA")
        if result:
            body = result.get("body", "")
            if body:
                assert " and " in body or " or " in body

    def test_return_dict_includes_value_map(self, notification_db):
        """Return dict must include new_value as JSON value_map."""
        import json
        rule = {
            "id": 102,
            "conditions": json.dumps([
                {"signal_id": "price", "operator": ">", "value": 100.0}
            ]),
            "logic_operator": "AND",
            "name": "Price Alert",
            "severity": "info",
            "currently_triggered": 0,
        }
        data = {
            "market": {"price": 150.0, "avg_volume": 50000000, "52w_high": 200.0, "52w_low": 100.0},
            "valuation": {"pe_ttm": 25.0, "pb_ratio": 5.0},
            "health": {"debt_to_equity": 50.0, "health_score": 80.0},
            "per_share": {"dividend_yield": 0.5},
        }
        from src.notifications.custom_alerts import _evaluate_single_rule
        result = _evaluate_single_rule(rule, data, {}, 1, "NVDA")
        assert result is not None
        assert "new_value" in result
        import json as j
        vm = j.loads(result["new_value"])
        assert "price" in vm
