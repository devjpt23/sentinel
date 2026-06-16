"""
ntfy push notification sender.

Self-hosted ntfy gives us push via APNs (iOS) + FCM/WebSocket (Android) with
zero polling and no third-party rate limits. The server is under our control.

Usage:
    from src.notifications.ntfy_sender import (
        send_ntfy_message,
        format_ntfy_notification,
        generate_ntfy_topic,
        send_ntfy_test_message,
    )
"""

import secrets
import logging
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

# Default ntfy server URL — override via environment variable
_NTFY_BASE_URL = "https://ntfy.sh"


def set_ntfy_base_url(url: str) -> None:
    """Override the default ntfy server URL (e.g., your self-hosted instance)."""
    global _NTFY_BASE_URL
    _NTFY_BASE_URL = url.rstrip("/")


def get_ntfy_base_url() -> str:
    """Return the current ntfy server URL."""
    return _NTFY_BASE_URL


# ─── Topic Generation ──────────────────────────────────────────


def generate_ntfy_topic() -> str:
    """Generate a unique, unguessable ntfy topic name.

    Returns a string like "sentinel_user_a7f3d9e1-c2b4-4f8a-9e6d-5c1a8b3f7d2e"
    with 128+ bits of entropy (18 url-safe base64 bytes = 144 bits).

    The topic name itself acts as a secret — only someone who knows it can
    subscribe to or publish to it. The write_token provides an additional
    layer for publishing.
    """
    return "sentinel_user_" + secrets.token_urlsafe(18)


def generate_write_token() -> str:
    """Generate a write token for ntfy topic access control.

    Returns a 32-byte url-safe base64 token (256 bits of entropy).
    This is stored server-side and never shown to the user.
    """
    return secrets.token_urlsafe(32)


# ─── Message Sending ───────────────────────────────────────────


def send_ntfy_message(
    topic: str,
    text: str,
    title: str = "",
    priority: str = "default",
    tags: str = "",
    write_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> bool:
    """Send a push notification to an ntfy topic.

    POSTs to {base_url}/{topic} with optional authentication and metadata.

    Args:
        topic: The ntfy topic name (e.g., "sentinel_user_abc123")
        text: Message body in Markdown format
        title: Notification title shown on the phone lock screen
        priority: One of "min", "low", "default", "high", "max" (or 1-5)
        tags: Comma-separated tags (emoji or short labels shown in notification)
        write_token: Optional bearer token for write-protected topics
        base_url: ntfy server URL (defaults to https://ntfy.sh)

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    url = f"{base_url or _NTFY_BASE_URL}/{topic}"

    def _safe_header(value: str) -> str:
        """Strip non-latin-1 characters from a header value.

        HTTP headers must be representable in latin-1. Emoji and other
        non-BMP characters cause UnicodeEncodeError at the socket level.
        """
        return value.encode("latin-1", errors="ignore").decode("latin-1")

    headers = {
        "Priority": priority,
        "Markdown": "yes",
    }
    if title:
        headers["Title"] = _safe_header(title)
    if tags:
        headers["Tags"] = _safe_header(tags)
    if write_token:
        headers["Authorization"] = f"Bearer {write_token}"

    for attempt in range(2):
        try:
            resp = requests.post(url, data=text.encode("utf-8"), headers=headers, timeout=5)
            if resp.status_code == 200:
                return True

            # 4xx errors are not retryable
            if 400 <= resp.status_code < 500:
                logger.warning(
                    f"ntfy send failed ({resp.status_code}) for topic {topic}: "
                    f"{resp.text[:200]}"
                )
                return False

            # 5xx or connection error — retry once
            if attempt == 0:
                logger.debug(f"ntfy send retrying after {resp.status_code} for topic {topic}")

        except requests.RequestException as e:
            logger.warning(f"ntfy send attempt {attempt+1}/2 failed: {e}")
            if attempt == 0:
                import time
                time.sleep(1)

    return False


def send_ntfy_test_message(
    topic: str,
    write_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> bool:
    """Send a test message to verify the ntfy topic is working."""
    return send_ntfy_message(
        topic=topic,
        text="✅ **Sentinel notifications are active!**\n\n"
             "You'll receive alerts when your watched stocks have meaningful changes "
             "in health scores, risk flags, valuations, and more.",
        priority="default",
        tags="white_check_mark",
        write_token=write_token,
        base_url=base_url,
    )


# ─── Notification Formatting ───────────────────────────────────


def format_ntfy_notification(notification: Dict) -> str:
    """Format a notification dict into a clean Markdown message for ntfy.

    ntfy supports Markdown natively — no HTML parse mode switch needed.
    Same emoji mappings and structure as format_telegram_notification().
    """
    severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
    type_emoji = {
        "health_change": "💊",
        "verdict_change": "📊",
        "risk_flag_change": "🔴",
        "zscore_zone_change": "📐",
        "fscore_change": "📋",
    }
    direction = ""
    if notification.get("old_value") and notification.get("new_value"):
        try:
            old_v = float(str(notification["old_value"]))
            new_v = float(str(notification["new_value"]))
            direction = " 📈" if new_v > old_v else " 📉"
        except (ValueError, TypeError):
            pass

    emoji = severity_emoji.get(notification.get("severity", "info"), "ℹ️")
    type_icon = type_emoji.get(notification.get("type", ""), "")

    lines = [
        f"{emoji} {type_icon} **{notification.get('ticker', '???')}** — {notification.get('title', '')}{direction}",
    ]

    if notification.get("body"):
        lines.append(f"*{notification['body']}*")

    if notification.get("old_value") and notification.get("new_value"):
        lines.append(
            f"Change: **{notification['old_value']}** → **{notification['new_value']}**"
        )

    return "\n\n".join(lines)


def format_ntfy_welcome(tickers: list) -> str:
    """Format a welcome message with the user's watchlist for ntfy delivery."""
    if tickers:
        ticker_lines = "\n".join(f"• {t}" for t in tickers)
        message = (
            f"✅ **Connected to Sentinel!**\n\n"
            f"Here's what your watchlist consists of:\n"
            f"{ticker_lines}\n\n"
            f"You'll be notified when these stocks have meaningful changes "
            f"in health scores, risk flags, valuations, and more."
        )
    else:
        message = (
            f"✅ **Connected to Sentinel!**\n\n"
            f"Your watchlist is empty. Add stocks on the dashboard and "
            f"you'll be notified when they have meaningful changes."
        )
    return message
