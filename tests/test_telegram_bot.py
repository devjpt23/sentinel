"""Tests for telegram_bot.py — notification formatting and message sending."""

from src.notifications.telegram_bot import format_telegram_notification


# ─── format_telegram_notification ─────────────────────────────────

class TestFormatTelegramNotification:
    """format_telegram_notification must produce clean HTML Telegram messages."""

    def test_custom_alert_shows_value_map(self):
        """Custom alerts should display current values from JSON new_value."""
        result = format_telegram_notification({
            "ticker": "NVDA",
            "title": "RSI Alert",
            "severity": "warning",
            "type": "custom_alert",
            "body": "RSI at 24.3 — oversold",
            "new_value": '{"rsi": 24.3, "price_change_pct": -7.2}',
        })
        assert "Rsi: 24.3" in result
        assert "Price Change Pct: -7.2" in result
        assert "📊" in result

    def test_custom_alert_no_value_map(self):
        """Custom alert without new_value should not crash."""
        result = format_telegram_notification({
            "ticker": "AAPL",
            "title": "Simple Alert",
            "severity": "info",
            "type": "custom_alert",
            "body": "Something happened",
        })
        assert "AAPL" in result
        assert "Custom Alert" in result

    def test_system_alert_shows_direction(self):
        """System alerts with comparable old/new values show direction arrows."""
        result = format_telegram_notification({
            "ticker": "NVDA",
            "title": "Health Score",
            "severity": "warning",
            "type": "health_change",
            "body": "Score dropped",
            "old_value": "82",
            "new_value": "58",
        })
        assert "📉" in result  # 58 < 82 so down arrow

    def test_system_alert_improvement_shows_up_arrow(self):
        """System alert where score improved gets 📈."""
        result = format_telegram_notification({
            "ticker": "AAPL",
            "title": "Health Score",
            "severity": "info",
            "type": "health_change",
            "body": "Score improved",
            "old_value": "45",
            "new_value": "72",
        })
        assert "📈" in result  # 72 > 45 so up arrow

    def test_skips_direction_for_custom_alerts(self):
        """Custom alerts should NOT get direction arrows (values are JSON maps)."""
        result = format_telegram_notification({
            "ticker": "NVDA",
            "title": "Custom Rule",
            "severity": "info",
            "type": "custom_alert",
            "old_value": '{}',
            "new_value": '{"rsi": 24}',
        })
        assert "📈" not in result
        assert "📉" not in result

    def test_includes_type_label(self):
        """Notification type context must be included."""
        result = format_telegram_notification({
            "ticker": "NVDA",
            "title": "Risk Flags",
            "severity": "critical",
            "type": "risk_flag_change",
            "body": "3 new red flags",
        })
        assert "Type:" in result
        assert "Risk Flag Change" in result

    def test_custom_alert_type_label(self):
        """Custom alerts should show Type: Custom Alert."""
        result = format_telegram_notification({
            "ticker": "AAPL",
            "title": "My Rule",
            "severity": "warning",
            "type": "custom_alert",
        })
        assert "Custom Alert" in result

    def test_includes_dashboard_link(self):
        """Dashboard link must be present with ticker."""
        result = format_telegram_notification({
            "ticker": "NVDA",
            "title": "Alert",
            "severity": "info",
            "type": "health_change",
        })
        assert "View in Dashboard" in result
        assert "NVDA" in result

    def test_dashboard_link_includes_rule_id_for_custom_alerts(self):
        """Custom alert dashboard link should include ?alert=rule_id."""
        result = format_telegram_notification({
            "ticker": "NVDA",
            "title": "Custom Alert",
            "severity": "warning",
            "type": "custom_alert",
            "rule_id": 42,
        })
        assert "?alert=42" in result

    def test_severity_emoji_mapping(self):
        """Severity maps to correct emoji."""
        info = format_telegram_notification({
            "ticker": "AAPL", "title": "Info", "severity": "info", "type": "health_change",
        })
        assert "ℹ️" in info

        warning = format_telegram_notification({
            "ticker": "AAPL", "title": "Warning", "severity": "warning", "type": "health_change",
        })
        assert "⚠️" in warning

        critical = format_telegram_notification({
            "ticker": "AAPL", "title": "Critical", "severity": "critical", "type": "health_change",
        })
        assert "🚨" in critical

    def test_includes_ticker_in_header(self):
        """Ticker must be bolded in the message header."""
        result = format_telegram_notification({
            "ticker": "TSLA",
            "title": "Price Alert",
            "severity": "warning",
            "type": "custom_alert",
        })
        assert "<b>TSLA</b>" in result

    def test_includes_body_when_present(self):
        """Body text must be included as italic when present."""
        result = format_telegram_notification({
            "ticker": "AAPL",
            "title": "Health Score",
            "severity": "info",
            "type": "health_change",
            "body": "Score dropped from 80 to 60",
        })
        assert "<i>Score dropped from 80 to 60</i>" in result

    def test_skips_body_when_empty(self):
        """Notification without body should not produce empty tags."""
        result = format_telegram_notification({
            "ticker": "AAPL",
            "title": "Alert",
            "severity": "info",
            "type": "health_change",
        })
        assert "<i></i>" not in result
