"""
Telegram Bot — per-user message sender and polling.

Each user brings their own bot token (created via @BotFather). The app
polls each user's bot independently for messages so they can link their
Telegram chat to their Sentinel account.

Sender: POSTs to the Telegram API with the user's bot token.
Poller: polls getUpdates per user, captures chat_id from any message,
         and links it to their Sentinel account.
"""

import time
import logging
from typing import Optional, Dict

import requests

from src.data.auth_db import link_telegram

logger = logging.getLogger(__name__)


# ─── Message Sending ─────────────────────────────────────────

def send_telegram_message(
    bot_token: str,
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = True,
) -> bool:
    """Send a message via a user's Telegram Bot API.

    Uses exponential backoff on rate limits (429). Returns True on success.

    Args:
        bot_token: The user's bot token from @BotFather
        chat_id: Telegram chat ID (string of digits)
        text: Message body, supports HTML tags when parse_mode='HTML'
        parse_mode: 'HTML' or 'MarkdownV2'
        disable_web_page_preview: disable link previews
    """
    if not bot_token:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }

    for attempt in range(3):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()

            if resp.status_code == 200 and data.get("ok"):
                return True

            if resp.status_code == 429:
                retry_after = data.get("parameters", {}).get("retry_after", 2 ** attempt)
                time.sleep(retry_after)
                continue

            if resp.status_code in (403, 400):
                logger.warning(
                    f"Telegram {resp.status_code} for chat {chat_id}: "
                    f"{data.get('description', 'unknown')}"
                )
                return False

            time.sleep(2 ** attempt)

        except requests.RequestException as e:
            logger.warning(f"Telegram send attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)

    return False


# ─── Notification Formatting ─────────────────────────────────

def format_telegram_notification(notification: Dict) -> str:
    """Format a notification dict into a clean HTML Telegram message."""
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
        f"{emoji} {type_icon} <b>{notification.get('ticker', '???')}</b> — {notification.get('title', '')}{direction}",
    ]

    if notification.get("body"):
        lines.append(f"<i>{notification['body']}</i>")

    if notification.get("old_value") and notification.get("new_value"):
        lines.append(
            f"Change: <b>{notification['old_value']}</b> → <b>{notification['new_value']}</b>"
        )

    return "\n".join(lines)


def send_test_message(bot_token: str, chat_id: str) -> bool:
    """Send a test message to verify the bot is working."""
    return send_telegram_message(
        bot_token,
        chat_id,
        "✅ <b>Sentinel notifications are active!</b>\n\n"
        "You'll receive alerts when your watched stocks have meaningful changes "
        "in health scores, risk flags, valuations, and more.",
    )


# ─── Watchlist Price Summary ───────────────────────────────────

def send_watchlist_summary(bot_token: str, chat_id: str, user_id: int) -> None:
    """Fetch price growth for every ticker in the user's watchlist and
    send a formatted summary via Telegram.

    Called automatically when a user connects their Telegram bot — gives
    immediate context on how their watched stocks have performed.

    Fetches all tickers concurrently via ThreadPoolExecutor so a 10-ticker
    watchlist completes in ~1-2 s rather than 10 s sequentially.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.data.watchlist_db import load_user_watchlist
    from src.data.fetcher import fetch_price_growth

    tickers = load_user_watchlist(user_id)

    if not tickers:
        send_telegram_message(
            bot_token, chat_id,
            "📭 <b>Your watchlist is empty</b>\n\n"
            "Add some tickers in the Sentinel app, then I'll send you "
            "their growth summary automatically.",
        )
        return

    # ── Fetch growth for all tickers in parallel ────────────
    growth_map: dict[str, Optional[dict]] = {}

    def _fetch_one(ticker: str) -> tuple[str, Optional[dict]]:
        try:
            return (ticker, fetch_price_growth(ticker))
        except Exception:
            return (ticker, None)

    with ThreadPoolExecutor(max_workers=min(len(tickers), 6)) as executor:
        futures = {executor.submit(_fetch_one, t): t for t in tickers}
        for future in as_completed(futures):
            t, data = future.result()
            growth_map[t] = data

    # ── Build the message ──────────────────────────────────
    lines = ["📊 <b>Your Watchlist Price Growth</b>", ""]

    for ticker in tickers:
        growth = growth_map.get(ticker)

        if growth is None:
            lines.append(f"<b>{ticker}</b>  <i>No price data available</i>")
            continue

        parts = []
        for period, label in [("3m", "3mo"), ("6m", "6mo"), ("12m", "12mo")]:
            val = growth.get(period)
            if val is not None:
                emoji = "📈" if val >= 0 else "📉"
                parts.append(f"{emoji} <b>{val:+.1f}%</b> {label}")
            else:
                parts.append(f"  N/A  {label}")

        lines.append(f"<b>{ticker}</b>  {'  '.join(parts)}")

    lines.append("")
    lines.append("<i>Growth shown vs. the most recent closing price.</i>")

    text = "\n".join(lines)

    # Telegram has a 4096-char limit; split if needed but a typical
    # watchlist of 20 tickers is ~1 200 chars so this is safe.
    send_telegram_message(bot_token, chat_id, text)


# ─── Chat ID Discovery ──────────────────────────────────────

def discover_chat_id(bot_token: str) -> Optional[str]:
    """Poll a bot's getUpdates once to find any chat_id.

    Call this after the user saves their token. If someone has sent any
    message to the bot, returns their chat_id. Returns None if no messages
    found (user hasn't messaged the bot yet).

    Also processes any /link commands found during discovery.
    """
    if not bot_token:
        return None

    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        resp = requests.get(url, params={"limit": 10, "timeout": 5}, timeout=10)
        data = resp.json()

        if not data.get("ok"):
            return None

        for update in data.get("result", []):
            message = update.get("message", {})
            chat = message.get("chat", {})
            chat_id = str(chat.get("id", ""))
            text = message.get("text", "").strip()

            if chat_id:
                # If there's a /link command, process it
                if text.startswith("/link"):
                    _handle_link_command(bot_token, chat_id, text)
                # Return the first chat_id found
                return chat_id

    except (requests.RequestException, ValueError) as e:
        logger.debug(f"chat_id discovery failed: {e}")

    return None


# ─── Per-User Bot Polling ────────────────────────────────────

# Tracks the last update_id per (user_id, bot_token) so we don't
# re-process the same messages on every poll tick.
_last_update_ids: Dict[int, int] = {}


def poll_user_bot(user_id: int, bot_token: str) -> None:
    """Poll one user's Telegram bot for new messages.

    Called every ~5 seconds by the scheduler for each user with a bot
    token configured. Processes any /link or /start commands found.
    """
    if not bot_token:
        return

    last_id = _last_update_ids.get(user_id, 0)

    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        params = {
            "offset": last_id + 1,
            "timeout": 5,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()

        if not data.get("ok"):
            return

        for update in data.get("result", []):
            _process_update(user_id, bot_token, update)
            _last_update_ids[user_id] = max(
                _last_update_ids.get(user_id, 0),
                update.get("update_id", 0),
            )

    except (requests.RequestException, ValueError) as e:
        logger.debug(f"Bot polling failed for user {user_id}: {e}")


def _process_update(user_id: int, bot_token: str, update: Dict) -> None:
    """Process a single Telegram update. Handles /start, /link, and /status commands."""
    message = update.get("message", {})
    if not message:
        return

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return

    if text.startswith("/start"):
        _send_welcome(bot_token, chat_id)
        # Auto-link: any /start message captures the chat_id
        link_telegram(user_id, chat_id)
        send_watchlist_summary(bot_token, chat_id, user_id)
        return

    if text.startswith("/link"):
        _handle_link_command(bot_token, chat_id, text)
        return

    if text.startswith("/status"):
        send_watchlist_summary(bot_token, chat_id, user_id)
        return

    # Any other message — treat as intent to connect
    _send_welcome(bot_token, chat_id)
    link_telegram(user_id, chat_id)
    send_watchlist_summary(bot_token, chat_id, user_id)


def _handle_link_command(bot_token: str, chat_id: str, text: str) -> None:
    """Process /link <username> command."""
    from src.data.auth_db import link_telegram_by_username

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(
            bot_token, chat_id,
            "Usage: <code>/link your-sentinel-username</code>\n\n"
            "Example: <code>/link trader1</code>",
        )
        return

    username = parts[1].strip().lower()
    user = link_telegram_by_username(username, chat_id)

    if user:
        send_telegram_message(
            bot_token, chat_id,
            f"✅ <b>Linked!</b>\n\n"
            f"Your Telegram is now connected to Sentinel account "
            f"<b>{user['display_name']}</b>.\n"
            f"You'll receive notifications for your watchlist stocks here.",
        )
        logger.info(f"Telegram chat {chat_id} linked to user {username}")
        # Send the watchlist price growth summary right after linking
        send_watchlist_summary(bot_token, chat_id, user["id"])
    else:
        send_telegram_message(
            bot_token, chat_id,
            f"❌ No Sentinel account found for username <b>{username}</b>.\n\n"
            f"Make sure you've registered on the Sentinel dashboard first, "
            f"then try again.",
        )


def _send_welcome(bot_token: str, chat_id: str) -> None:
    """Send the welcome/onboarding message."""
    send_telegram_message(
        bot_token, chat_id,
        "👋 <b>Welcome to Sentinel!</b>\n\n"
        "I'll send you notifications when your watched stocks have meaningful changes.\n\n"
        "You're now connected! ✅\n"
        "You can close this chat — alerts will arrive automatically.",
    )


def clear_polling_state(user_id: int) -> None:
    """Reset polling state when a user disconnects their bot."""
    _last_update_ids.pop(user_id, None)
