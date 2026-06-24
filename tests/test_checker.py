"""Tests for checker.py — push/telegram routing and delivery logic."""

from unittest.mock import patch

from src.notifications.checker import deliver_notifications, format_push_notification


# ─── format_push_notification ─────────────────────────────────────

class TestFormatPushNotification:
    """format_push_notification() must clean up body text and extract data payload."""

    def test_strips_ticker_prefix(self):
        """Custom alert body prefixed with 'TICKER:' must strip the prefix."""
        title, body, extra = format_push_notification({
            "ticker": "AAPL",
            "title": "Price Alert",
            "body": "AAPL: Price dropped 7.2%",
        })
        assert "AAPL:" not in body
        assert body.startswith("Price dropped")

    def test_no_ticker_prefix_left_untouched(self):
        """Body without ticker prefix should pass through."""
        title, body, extra = format_push_notification({
            "ticker": "AAPL",
            "title": "Health Score Decline",
            "body": "Score dropped from 80 to 60",
        })
        assert body == "Score dropped from 80 to 60"

    def test_appends_price_context_for_custom_alerts(self):
        """Custom alerts get | Price: $XXX appended."""
        title, body, extra = format_push_notification({
            "type": "custom_alert",
            "ticker": "NVDA",
            "title": "RSI Alert",
            "body": "RSI at 24.3",
            "current_price": 173.40,
        })
        assert "Price: $173.40" in body

    def test_skips_price_context_for_system_alerts(self):
        """System alerts (not custom_alert type) don't get price context."""
        title, body, extra = format_push_notification({
            "type": "health_change",
            "ticker": "AAPL",
            "title": "Health Change",
            "body": "Score dropped",
            "current_price": 150.0,
        })
        assert "Price:" not in body

    def test_truncates_long_body(self):
        """Body over 120 chars must be truncated with ..."""
        long_body = "x" * 200
        title, body, extra = format_push_notification({
            "title": "Long Alert",
            "body": long_body,
            "ticker": "AAPL",
        })
        assert len(body) <= 120
        assert body.endswith("...")

    def test_short_body_not_truncated(self):
        """Body under 120 chars stays intact."""
        short_body = "Price dropped 5%"
        title, body, extra = format_push_notification({
            "title": "Short Alert",
            "body": short_body,
            "ticker": "AAPL",
        })
        assert body == short_body

    def test_empty_body_returns_empty(self):
        """Notification with no body returns empty string."""
        title, body, extra = format_push_notification({
            "ticker": "AAPL",
            "title": "Alert",
        })
        assert body == ""

    def test_extra_data_contains_current_price(self):
        """Extra data dict includes current_price when available."""
        title, body, extra = format_push_notification({
            "ticker": "AAPL",
            "title": "Alert",
            "body": "Something happened",
            "current_price": 175.5,
        })
        assert extra.get("current_price") == 175.5

    def test_extra_data_empty_when_no_price(self):
        """Extra data dict is empty when no current_price in notification."""
        title, body, extra = format_push_notification({
            "ticker": "AAPL",
            "title": "Alert",
            "body": "Something happened",
        })
        assert extra == {}


class TestDeliverNotifications:
    """Must respect fire_push and fire_telegram flags on custom alert rules."""

    @patch("src.notifications.checker.send_push_notifications")
    @patch("src.notifications.checker.get_all_active_subscriptions")
    @patch("src.notifications.checker.get_preferences")
    @patch("src.notifications.checker.get_custom_alert_rule_by_id")
    def test_push_delivery_with_rule_id(
        self, mock_get_rule, mock_prefs, mock_subs, mock_push
    ):
        """Notification with rule_id and fire_push=1 must send push."""
        mock_prefs.return_value = {"push_enabled": 1, "telegram_enabled": 0}
        mock_subs.return_value = {1: [{"endpoint": "https://push.example.com"}]}
        mock_get_rule.return_value = {"fire_push": 1, "fire_telegram": 1}
        mock_push.return_value = [{"status": "sent"}]

        notifications = {"NVDA": [{
            "rule_id": 42,
            "ticker": "NVDA",
            "title": "Price Alert",
            "body": "NVDA > $150",
            "id": 1,
        }]}

        delivered = deliver_notifications(1, notifications)
        assert delivered == 1
        mock_push.assert_called_once()

    @patch("src.notifications.checker.send_push_notifications")
    @patch("src.notifications.checker.get_all_active_subscriptions")
    @patch("src.notifications.checker.get_preferences")
    @patch("src.notifications.checker.get_custom_alert_rule_by_id")
    def test_push_skipped_when_fire_push_zero(
        self, mock_get_rule, mock_prefs, mock_subs, mock_push
    ):
        """Notification with rule_id and fire_push=0 must skip push."""
        mock_prefs.return_value = {"push_enabled": 1, "telegram_enabled": 0}
        mock_subs.return_value = {1: [{"endpoint": "https://push.example.com"}]}
        mock_get_rule.return_value = {"fire_push": 0, "fire_telegram": 1}

        notifications = {"NVDA": [{
            "rule_id": 42,
            "ticker": "NVDA",
            "title": "Price Alert",
            "body": "NVDA > $150",
            "id": 1,
        }]}

        delivered = deliver_notifications(1, notifications)
        assert delivered == 0
        mock_push.assert_not_called()

    @patch("src.notifications.checker.send_telegram_message")
    @patch("src.notifications.checker.format_telegram_notification")
    @patch("src.notifications.checker.get_preferences")
    @patch("src.notifications.checker.get_custom_alert_rule_by_id")
    @patch("src.notifications.checker.mark_delivered")
    def test_telegram_skipped_when_fire_telegram_zero(
        self, mock_mark, mock_get_rule, mock_prefs, mock_format, mock_tg
    ):
        """Notification with rule_id and fire_telegram=0 must skip Telegram."""
        mock_prefs.return_value = {
            "push_enabled": 0,
            "telegram_enabled": 1,
            "telegram_bot_token": "bot:token",
            "telegram_chat_id": "123",
        }
        mock_get_rule.return_value = {"fire_push": 1, "fire_telegram": 0}

        notifications = {"NVDA": [{
            "rule_id": 42,
            "ticker": "NVDA",
            "title": "Price Alert",
            "body": "NVDA > $150",
            "id": 1,
        }]}

        delivered = deliver_notifications(1, notifications)
        assert delivered == 0
        mock_tg.assert_not_called()

    @patch("src.notifications.checker.send_push_notifications")
    @patch("src.notifications.checker.send_telegram_message")
    @patch("src.notifications.checker.format_telegram_notification")
    @patch("src.notifications.checker.get_all_active_subscriptions")
    @patch("src.notifications.checker.get_preferences")
    @patch("src.notifications.checker.get_custom_alert_rule_by_id")
    @patch("src.notifications.checker.mark_delivered")
    def test_both_channels_respected(
        self, mock_mark, mock_get_rule, mock_prefs, mock_subs,
        mock_format, mock_tg, mock_push
    ):
        """Both push and telegram fire when both flags are set."""
        mock_prefs.return_value = {
            "push_enabled": 1,
            "telegram_enabled": 1,
            "telegram_bot_token": "bot:token",
            "telegram_chat_id": "123",
        }
        mock_subs.return_value = {1: [{"endpoint": "https://push.example.com"}]}
        mock_get_rule.return_value = {"fire_push": 1, "fire_telegram": 1}
        mock_push.return_value = [{"status": "sent"}]
        mock_format.return_value = "Alert text"
        mock_tg.return_value = True

        notifications = {"NVDA": [{
            "rule_id": 42,
            "ticker": "NVDA",
            "title": "Price Alert",
            "body": "NVDA > $150",
            "id": 1,
        }]}

        delivered = deliver_notifications(1, notifications)
        assert delivered >= 2  # push + TG
        mock_push.assert_called_once()
        mock_tg.assert_called_once()

    @patch("src.notifications.checker.send_push_notifications")
    @patch("src.notifications.checker.get_all_active_subscriptions")
    @patch("src.notifications.checker.get_preferences")
    @patch("src.notifications.checker.get_custom_alert_rule_by_id")
    def test_push_payload_has_correct_keys(
        self, mock_get_rule, mock_prefs, mock_subs, mock_push
    ):
        """Push payload must include rule_id, notification_id, and ticker."""
        mock_prefs.return_value = {"push_enabled": 1, "telegram_enabled": 0}
        mock_subs.return_value = {1: [{"endpoint": "https://push.example.com"}]}
        mock_get_rule.return_value = {"fire_push": 1, "fire_telegram": 1}
        mock_push.return_value = [{"status": "sent"}]

        notifications = {"NVDA": [{
            "rule_id": 42,
            "ticker": "NVDA",
            "title": "Price Alert",
            "body": "NVDA > $150",
            "id": 1,
        }]}

        deliver_notifications(1, notifications)
        call_kwargs = mock_push.call_args[1]
        data = call_kwargs["data"]
        assert data["rule_id"] == 42
        assert data["notification_id"] == 1
        assert data["ticker"] == "NVDA"

    @patch("src.notifications.checker.send_push_notifications")
    @patch("src.notifications.checker.get_all_active_subscriptions")
    @patch("src.notifications.checker.get_preferences")
    def test_no_rule_id_skips_push_gracefully(
        self, mock_prefs, mock_subs, mock_push
    ):
        """Notification without rule_id should not crash — just skip push."""
        mock_prefs.return_value = {"push_enabled": 1, "telegram_enabled": 0}
        mock_subs.return_value = {1: [{"endpoint": "https://push.example.com"}]}

        # Notification without rule_id (e.g. built-in alert type)
        notifications = {"NVDA": [{
            "type": "health_change",
            "ticker": "NVDA",
            "title": "Health Score Declined",
            "body": "Score changed from 80 to 60",
            "id": 2,
        }]}

        # Should not raise
        delivered = deliver_notifications(1, notifications)
        assert delivered == 0
        mock_push.assert_not_called()
