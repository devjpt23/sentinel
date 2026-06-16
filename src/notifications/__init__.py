"""
Notification package — background checks, multi-channel delivery, and
Telegram + ntfy push integration for the Sentinel fundamental analysis dashboard.
"""

from src.notifications.checker import (
    run_check_for_ticker,
    check_all_tickers_for_user,
    deliver_notifications,
)
from src.notifications.ntfy_sender import (
    send_ntfy_message,
    format_ntfy_notification,
    generate_ntfy_topic,
    generate_write_token,
    send_ntfy_test_message,
    set_ntfy_base_url,
    get_ntfy_base_url,
)

__all__ = [
    "run_check_for_ticker",
    "check_all_tickers_for_user",
    "deliver_notifications",
    "send_ntfy_message",
    "format_ntfy_notification",
    "generate_ntfy_topic",
    "generate_write_token",
    "send_ntfy_test_message",
    "set_ntfy_base_url",
    "get_ntfy_base_url",
]
