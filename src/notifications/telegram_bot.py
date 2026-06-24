"""
Telegram Bot — per-user message sender and polling.

Each user brings their own bot token (created via @BotFather). The app
polls each user's bot independently for messages so they can link their
Telegram chat to their Sentinel account.

Sender: POSTs to the Telegram API with the user's bot token.
Poller: polls getUpdates per user, captures chat_id from any message,
         and links it to their Sentinel account.
"""

import json
import time
import logging
from typing import Optional, Dict

import requests

from src.data.auth_db import link_telegram
from src.data.fetcher import _cached_ticker_info, fetch_price_growth, fetch_company_data

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
    """Format a notification dict into a clean HTML Telegram message.

    Includes notification type context, current values for custom alerts,
    and a 'View in Dashboard' link.
    """
    severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
    type_emoji = {
        "health_change": "💊",
        "verdict_change": "📊",
        "risk_flag_change": "🔴",
        "zscore_zone_change": "📐",
        "fscore_change": "📋",
    }
    type_labels = {
        "health_change": "💊 Health Score Change",
        "verdict_change": "📊 Valuation Change",
        "risk_flag_change": "🔴 Risk Flag Change",
        "zscore_zone_change": "📐 Z-Score Zone Change",
        "fscore_change": "📋 F-Score Change",
        "custom_alert": "⚡ Custom Alert",
    }

    direction = ""
    if notification.get("type") != "custom_alert":
        if notification.get("old_value") and notification.get("new_value"):
            try:
                old_v = float(str(notification["old_value"]))
                new_v = float(str(notification["new_value"]))
                direction = " 📈" if new_v > old_v else " 📉"
            except (ValueError, TypeError):
                pass

    emoji = severity_emoji.get(notification.get("severity", "info"), "ℹ️")
    type_icon = type_emoji.get(notification.get("type", ""), "")
    ntype = notification.get("type", "")

    lines = [
        f"{emoji} {type_icon} <b>{notification.get('ticker', '???')}</b> — {notification.get('title', '')}{direction}",
    ]

    if notification.get("body"):
        lines.append(f"<i>{notification['body']}</i>")

    # Notification type context
    type_label = type_labels.get(ntype, ntype.replace("_", " ").title())
    lines.append(f"Type: {type_label}")

    # For custom alerts, show current values from the value_map
    if ntype == "custom_alert" and notification.get("new_value"):
        try:
            value_map = json.loads(notification["new_value"])
            if value_map:
                values_str = ", ".join(
                    f"{sid.replace('_', ' ').title()}: {v}"
                    for sid, v in value_map.items()
                )
                lines.append(f"📊 {values_str}")
        except (json.JSONDecodeError, TypeError):
            pass

    # Dashboard link
    ticker = notification.get("ticker", "")
    if ticker:
        link = f"https://sentinel.app/company/{ticker}"
        if notification.get("rule_id"):
            link += f"?alert={notification['rule_id']}"
        lines.append(f"🔗 <a href='{link}'>View in Dashboard</a>")

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

def discover_chat_id(bot_token: str, user_id: Optional[int] = None) -> Optional[str]:
    """Poll a bot's getUpdates once to find any chat_id.

    Call this after the user saves their token. If someone has sent any
    message to the bot, returns their chat_id. Returns None if no messages
    found (user hasn't messaged the bot yet).

    When *user_id* is provided, all commands (/help, /start, /link, /status,
    etc.) are routed through the same ``_process_update`` handler that the
    daemon uses — so every command gets a response, not just ``/link``.
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
                # When user_id is known, route ALL commands through the
                # same handler the daemon uses.
                if user_id is not None:
                    _process_update(user_id, bot_token, update)
                elif text.startswith("/link"):
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

    if text.startswith("/watchlist"):
        _cmd_watchlist(bot_token, chat_id, user_id)
        return

    if text.startswith("/add "):
        _cmd_add(bot_token, chat_id, user_id, text)
        return

    if text.startswith("/remove "):
        _cmd_remove(bot_token, chat_id, user_id, text)
        return

    if text.startswith("/score "):
        _cmd_score(bot_token, chat_id, user_id, text)
        return

    if text.startswith("/price "):
        _cmd_price(bot_token, chat_id, text)
        return

    if text.startswith("/news "):
        _cmd_news(bot_token, chat_id, text)
        return

    if text.startswith("/market"):
        _cmd_market(bot_token, chat_id)
        return

    if text.startswith("/macro"):
        _cmd_macro(bot_token, chat_id)
        return

    if text.startswith("/alerts"):
        _cmd_alerts(bot_token, chat_id, user_id)
        return

    if text.startswith("/check "):
        _cmd_check(bot_token, chat_id, user_id, text)
        return

    if text.startswith("/prefs"):
        _cmd_prefs(bot_token, chat_id, user_id)
        return

    if text.startswith("/interval "):
        _cmd_interval(bot_token, chat_id, user_id, text)
        return

    if text.startswith("/help"):
        _cmd_help(bot_token, chat_id)
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


def _cmd_help(bot_token: str, chat_id: str) -> None:
    """Send a static message listing all available commands."""
    send_telegram_message(
        bot_token, chat_id,
        "👋 <b>Sentinel Bot Commands</b>\n\n"
        "Account:\n"
        "  /start — Connect your Telegram\n"
        "  /link &lt;username&gt; — Link to your account\n\n"
        "Watchlist:\n"
        "  /watchlist — View your watchlist\n"
        "  /add &lt;TICKER&gt; — Add a ticker\n"
        "  /remove &lt;TICKER&gt; — Remove a ticker\n\n"
        "Stock Info:\n"
        "  /status — Full watchlist price growth\n"
        "  /score &lt;TICKER&gt; — Full health report\n"
        "  /price &lt;TICKER&gt; — 3/6/12 month growth\n"
        "  /news &lt;TICKER&gt; — Recent news\n\n"
        "Market:\n"
        "  /market — Top movers &amp; indices\n"
        "  /macro — Macro indicators (VIX, yield curve, etc.)\n\n"
        "Notifications:\n"
        "  /alerts — Recent notifications\n"
        "  /check &lt;TICKER&gt; — Force re-check a ticker\n"
        "  /prefs — View preferences\n"
        "  /interval &lt;hours&gt; — Set check frequency\n\n"
        "/help — Show this message",
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


# ─── Watchlist Commands ────────────────────────────────────

def _cmd_watchlist(bot_token: str, chat_id: str, user_id: int) -> None:
    """List all tickers in the user's watchlist with price, daily change, and 3m growth."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from src.data.watchlist_db import load_user_watchlist

    tickers = load_user_watchlist(user_id)

    if not tickers:
        send_telegram_message(
            bot_token, chat_id,
            "📭 Your watchlist is empty. Add tickers with <code>/add &lt;TICKER&gt;</code>.",
        )
        return

    def _fetch_one(ticker: str) -> tuple[str, Optional[dict], Optional[dict]]:
        try:
            info = _cached_ticker_info(ticker)
            growth = fetch_price_growth(ticker)
            return (ticker, info, growth)
        except Exception:
            return (ticker, None, None)

    with ThreadPoolExecutor(max_workers=min(len(tickers), 6)) as executor:
        results = list(executor.map(_fetch_one, tickers))

    lines = [f"📋 <b>Your Watchlist ({len(tickers)} tickers)</b>", ""]

    for ticker, info, growth in results:
        if not info:
            lines.append(f"<b>{ticker}</b>  <i>Unavailable</i>")
            continue

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose")
        daily_pct = info.get("regularMarketChangePercent")
        if daily_pct is None and price and prev_close and prev_close > 0:
            daily_pct = ((price - prev_close) / prev_close) * 100

        price_str = f"${price:.2f}" if price else "N/A"
        daily_str = ""
        if daily_pct is not None:
            arrow = "📈" if daily_pct >= 0 else "📉"
            daily_str = f" {arrow} {daily_pct:+.1f}%"

        growth_3m = None
        if growth and growth.get("3m") is not None:
            growth_3m = growth["3m"]

        growth_str = ""
        if growth_3m is not None:
            arrow = "📈" if growth_3m >= 0 else "📉"
            growth_str = f" {arrow} {growth_3m:+.1f}% 3mo"

        lines.append(f"<b>{ticker}</b>  {price_str}{daily_str}{growth_str}")

    text = "\n".join(lines)
    send_telegram_message(bot_token, chat_id, text)


def _cmd_add(bot_token: str, chat_id: str, user_id: int, text: str) -> None:
    """Add a ticker to the user's watchlist."""
    from src.data.watchlist_db import add_user_ticker, is_ticker_watched_by_user

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(
            bot_token, chat_id,
            "Usage: <code>/add &lt;TICKER&gt;</code> — Example: <code>/add AAPL</code>",
        )
        return

    ticker = parts[1].strip().upper()

    if is_ticker_watched_by_user(user_id, ticker):
        send_telegram_message(
            bot_token, chat_id,
            f"<b>{ticker}</b> is already in your watchlist.",
        )
        return

    # Validate ticker exists
    info = _cached_ticker_info(ticker)
    if not info or not info.get("currentPrice") and not info.get("regularMarketPrice"):
        send_telegram_message(
            bot_token, chat_id,
            f"❌ Ticker <b>{ticker}</b> not found. Check the spelling and try again.",
        )
        return

    add_user_ticker(user_id, ticker)
    send_telegram_message(
        bot_token, chat_id,
        f"✅ Added <b>{ticker}</b> to your watchlist.\n\n"
        f"Send <code>/score {ticker}</code> for a full health report.",
    )


def _cmd_remove(bot_token: str, chat_id: str, user_id: int, text: str) -> None:
    """Remove a ticker from the user's watchlist."""
    from src.data.watchlist_db import remove_user_ticker, is_ticker_watched_by_user

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(
            bot_token, chat_id,
            "Usage: <code>/remove &lt;TICKER&gt;</code> — Example: <code>/remove AAPL</code>",
        )
        return

    ticker = parts[1].strip().upper()

    if not is_ticker_watched_by_user(user_id, ticker):
        send_telegram_message(
            bot_token, chat_id,
            f"<b>{ticker}</b> is not in your watchlist.",
        )
        return

    remove_user_ticker(user_id, ticker)
    send_telegram_message(
        bot_token, chat_id,
        f"✅ Removed <b>{ticker}</b> from your watchlist.",
    )


# ─── Stock Detail Commands ─────────────────────────────────

def _cmd_score(bot_token: str, chat_id: str, user_id: int, text: str) -> None:
    """Full health report for a ticker."""
    from src.scoring.health import compute_health_score
    from src.scoring.zscore import compute_altman_zscore
    from src.scoring.valuation import compute_price_verdict
    from src.scoring.intrinsic import compute_intrinsic_worth
    from src.scoring.risk import compute_risk_assessment, compute_red_flags

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(
            bot_token, chat_id,
            "Usage: <code>/score &lt;TICKER&gt;</code> — Example: <code>/score AAPL</code>",
        )
        return

    ticker = parts[1].strip().upper()

    try:
        data = fetch_company_data(ticker)
    except Exception:
        send_telegram_message(
            bot_token, chat_id,
            f"⚠️ Couldn't fetch data for <b>{ticker}</b> right now. Try again in a moment.",
        )
        return

    if not data:
        send_telegram_message(
            bot_token, chat_id,
            f"⚠️ No data available for <b>{ticker}</b>.",
        )
        return

    # Compute scores
    health_score, health_verdict, fscore, _ = compute_health_score(data)
    z_score, z_zone, _ = compute_altman_zscore(data)
    _, price_verdict, _, _ = compute_price_verdict(data, {})
    _, intrinsic_verdict, _, _, _ = compute_intrinsic_worth(data)
    risk_score, risk_label, _, risk_factors = compute_risk_assessment(data, z_score, z_zone)
    red_flags = compute_red_flags(data, risk_factors)
    red_flag_count = len([f for f in red_flags if f[0] == "danger"]) if red_flags else 0

    # Risk zone emoji
    risk_emoji = {"Low": "🟢", "Moderate": "🟡", "High": "🔴"}.get(risk_label, "⚪")

    company_name = data.get("company", {}).get("name", ticker)

    lines = [
        f"📊 <b>{ticker}</b> — {company_name}",
        "",
        f"Health: {health_score}/100 ({health_verdict}) {['🟢' if health_score >= 70 else '🟡' if health_score >= 40 else '🔴'][0]}",
        f"F-Score: {fscore}/9",
        f"Z-Score: {z_score:.1f} ({z_zone})" if z_score else f"Z-Score: N/A",
        f"Risk: {risk_label} {risk_emoji}",
        f"Red Flags: {red_flag_count}",
        "",
        "Valuation:",
        f"  Price vs Peers: {price_verdict}",
        f"  Intrinsic Worth: {intrinsic_verdict}",
    ]

    price = data.get("market", {}).get("price")
    if price:
        lines.append(f"\nPrice: ${price:.2f}")

    text = "\n".join(lines)
    send_telegram_message(bot_token, chat_id, text)


def _cmd_price(bot_token: str, chat_id: str, text: str) -> None:
    """Show 3/6/12 month price growth for a single ticker."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(
            bot_token, chat_id,
            "Usage: <code>/price &lt;TICKER&gt;</code> — Example: <code>/price AAPL</code>",
        )
        return

    ticker = parts[1].strip().upper()
    growth = fetch_price_growth(ticker)

    if not growth:
        send_telegram_message(
            bot_token, chat_id,
            f"⚠️ Couldn't fetch price data for <b>{ticker}</b> right now.",
        )
        return

    lines = [f"📈 <b>{ticker}</b> Price Growth", ""]

    for period, label in [("3m", "3mo"), ("6m", "6mo"), ("12m", "12mo")]:
        val = growth.get(period)
        if val is not None:
            emoji = "📈" if val >= 0 else "📉"
            lines.append(f"{emoji} <b>{val:+.1f}%</b> {label}")
        else:
            lines.append(f"  N/A  {label}")

    send_telegram_message(bot_token, chat_id, "\n".join(lines))


def _cmd_news(bot_token: str, chat_id: str, text: str) -> None:
    """Show recent news headlines for a ticker."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(
            bot_token, chat_id,
            "Usage: <code>/news &lt;TICKER&gt;</code> — Example: <code>/news AAPL</code>",
        )
        return

    ticker = parts[1].strip().upper()

    try:
        data = fetch_company_data(ticker)
    except Exception:
        send_telegram_message(
            bot_token, chat_id,
            f"⚠️ Couldn't fetch news for <b>{ticker}</b> right now.",
        )
        return

    news_items = data.get("news", []) if data else []
    if not news_items:
        send_telegram_message(
            bot_token, chat_id,
            f"📰 No recent news for <b>{ticker}</b>.",
        )
        return

    lines = [f"📰 <b>{ticker}</b> — Recent News", ""]
    for item in news_items[:5]:
        title = item.get("title", "No title")
        publisher = item.get("publisher", "")
        published = item.get("published", "")

        # Make relative time human-friendly
        time_str = ""
        if published:
            try:
                from datetime import datetime, timezone
                pub_time = datetime.fromisoformat(published)
                if pub_time.tzinfo is None:
                    pub_time = pub_time.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                diff = now - pub_time
                hours = int(diff.total_seconds() / 3600)
                if hours < 1:
                    mins = int(diff.total_seconds() / 60)
                    time_str = f"{mins}m ago"
                elif hours < 24:
                    time_str = f"{hours}h ago"
                else:
                    time_str = f"{hours // 24}d ago"
            except Exception:
                time_str = published[:10]

        lines.append(f"• {title}")
        if publisher or time_str:
            parts_line = " — ".join(p for p in [publisher, time_str] if p)
            lines.append(f"  <i>{parts_line}</i>")
        lines.append("")

    send_telegram_message(bot_token, chat_id, "\n".join(lines))


# ─── Market Overview Commands ──────────────────────────────

def _cmd_market(bot_token: str, chat_id: str) -> None:
    """Show top 10 movers and major indices."""
    from src.data.fetcher import fetch_top_movers, fetch_market_indices

    movers = fetch_top_movers(top_n=10)
    indices = fetch_market_indices()

    lines = ["📊 <b>Market Overview</b>", "", "<b>Top Movers:</b>"]

    if not movers:
        lines.append("  <i>No significant movers today.</i>")
    else:
        for m in movers:
            emoji = "📈" if m["direction"] == "up" else "📉"
            price_str = f"${m['price']:.2f}" if m.get("price") else "N/A"
            lines.append(f"{emoji} <b>{m['ticker']}</b> {m['change_pct']:+.1f}%  {price_str}")

    lines.append("")
    lines.append("<b>Indices:</b>")

    if not indices:
        lines.append("  <i>Index data unavailable.</i>")
    else:
        for idx in indices:
            emoji = idx.get("emoji", "📊")
            price_str = f"{idx['price']:,.2f}" if idx.get("price") else "N/A"
            change_str = ""
            if idx.get("change_pct") is not None:
                arrow = "📈" if idx["direction"] == "up" else "📉"
                change_str = f" {arrow} {idx['change_pct']:+.1f}%"
            lines.append(f"{emoji} {idx['name']}  {price_str}{change_str}")

    send_telegram_message(bot_token, chat_id, "\n".join(lines))


def _cmd_macro(bot_token: str, chat_id: str) -> None:
    """Show macro indicators."""
    from src.data.fetcher import fetch_macro_context

    macro = fetch_macro_context()
    if not macro:
        send_telegram_message(
            bot_token, chat_id,
            "⚠️ Couldn't fetch macro data right now.",
        )
        return

    lines = ["🌐 <b>Macro Context</b>", ""]

    # VIX
    vix = macro.get("vix")
    if vix:
        val = vix.get("value", "N/A")
        verdict = vix.get("verdict", "")
        vix_emoji = {"Calm": "🟢", "Normal": "🟡", "Fearful": "🔴"}.get(verdict, "⚪")
        lines.append(f"VIX: {val} — {verdict} {vix_emoji}")

    # S&P 500
    spx = macro.get("sp500")
    if spx:
        val = spx.get("value", "N/A")
        verdict = spx.get("verdict", "")
        val_str = f"{val:,.1f}" if isinstance(val, (int, float)) else val
        lines.append(f"S&P 500: {val_str} — {verdict}")

    # Yield Curve
    yc = macro.get("yield_curve")
    if yc:
        val = yc.get("value", "N/A")
        verdict = yc.get("verdict", "")
        yc_emoji = {"Steep": "🟢", "Flat": "🟡", "Inverted": "🔴"}.get(verdict, "⚪")
        val_str = f"{val:.1f}%" if isinstance(val, (int, float)) else val
        lines.append(f"Yield Curve: {val_str} — {verdict} {yc_emoji}")

    # Credit
    credit = macro.get("credit")
    if credit:
        verdict = credit.get("verdict", "")
        cr_emoji = {"Healthy": "🟢", "Cautious": "🟡", "Stressed": "🔴"}.get(verdict, "⚪")
        lines.append(f"Credit: {verdict} {cr_emoji}")

    # Dollar
    dollar = macro.get("dollar")
    if dollar:
        verdict = dollar.get("verdict", "")
        d_emoji = {"Rising": "🟢", "Stable": "🟡", "Falling": "🔴"}.get(verdict, "⚪")
        lines.append(f"Dollar: {verdict} {d_emoji}")

    send_telegram_message(bot_token, chat_id, "\n".join(lines))


# ─── Notification Commands ─────────────────────────────────

def _cmd_alerts(bot_token: str, chat_id: str, user_id: int) -> None:
    """Show the last 10 notifications, unread first."""
    from src.data.notification_db import get_notifications, get_unread_count

    unread = get_unread_count(user_id)
    notifications = get_notifications(user_id, limit=10, unread_only=False)

    if not notifications:
        send_telegram_message(
            bot_token, chat_id,
            "📭 No notifications yet. I'll alert you when your watchlist stocks change.",
        )
        return

    lines = [f"🔔 Recent Alerts ({unread} unread)", ""]

    for n in notifications:
        ticker = n.get("ticker", "???")
        title = n.get("title", "")
        old_val = n.get("old_value", "")
        new_val = n.get("new_value", "")
        body = n.get("body", "")

        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(n.get("severity", "info"), "ℹ️")

        # Relative time
        time_str = ""
        created = n.get("created_at", "")
        if created:
            try:
                from datetime import datetime, timezone
                if isinstance(created, str):
                    created = datetime.fromisoformat(created.replace(" ", "T").replace("+00:00", ""))
                    created = created.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                diff = now - created
                hours = int(diff.total_seconds() / 3600)
                if hours < 1:
                    mins = int(diff.total_seconds() / 60)
                    time_str = f"{mins}m ago" if mins > 0 else "just now"
                elif hours < 24:
                    time_str = f"{hours}h ago"
                else:
                    time_str = f"{hours // 24}d ago"
            except Exception:
                time_str = str(created)[:10]

        read_status = "Unread" if not n.get("is_read") else "Read"

        lines.append(f"{severity_emoji} <b>{ticker}</b> — {title}")
        if body:
            lines.append(f"  <i>{body[:200]}</i>")
        if old_val and new_val:
            lines.append(f"  {old_val} → {new_val}")
        lines.append(f"  {time_str} — {read_status}")
        lines.append("")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n\n<i>...truncated</i>"

    send_telegram_message(bot_token, chat_id, text)


def _cmd_check(bot_token: str, chat_id: str, user_id: int, text: str) -> None:
    """Force immediate re-check of a ticker."""
    from src.notifications.checker import run_check_for_ticker

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(
            bot_token, chat_id,
            "Usage: <code>/check &lt;TICKER&gt;</code> — Example: <code>/check TSLA</code>",
        )
        return

    ticker = parts[1].strip().upper()

    # Send a "checking..." message first
    send_telegram_message(bot_token, chat_id, f"🔍 Checking <b>{ticker}</b>...")

    notifications = run_check_for_ticker(user_id, ticker)

    if not notifications:
        send_telegram_message(
            bot_token, chat_id,
            f"No changes detected — scores are stable for <b>{ticker}</b>.",
        )
        return

    lines = [f"🔍 <b>{ticker}</b> Check Results", ""]
    for n in notifications:
        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(n.get("severity", "info"), "ℹ️")
        title = n.get("title", "")
        body = n.get("body", "")
        old_val = n.get("old_value", "")
        new_val = n.get("new_value", "")

        lines.append(f"{severity_emoji} {title}")
        if body:
            lines.append(f"  <i>{body[:200]}</i>")
        if old_val and new_val:
            lines.append(f"  {old_val} → {new_val}")
        lines.append("")

    send_telegram_message(bot_token, chat_id, "\n".join(lines))


def _cmd_prefs(bot_token: str, chat_id: str, user_id: int) -> None:
    """Show current notification preferences."""
    from src.data.notification_db import get_preferences

    prefs = get_preferences(user_id)

    interval = prefs.get("check_interval_hours", 2)
    delta = prefs.get("min_health_delta", 15)

    lines = [
        "⚙️ <b>Your Preferences</b>",
        "",
        f"Check interval: Every {interval} hours",
        f"Health delta threshold: {delta} points",
        "",
        "Notifications:",
        f"  Health changes: {'✅' if prefs.get('health_change') else '❌'}",
        f"  Valuation changes: {'✅' if prefs.get('verdict_change') else '❌'}",
        f"  Risk flag changes: {'✅' if prefs.get('risk_flag_change') else '❌'}",
        f"  Z-Score zone changes: {'✅' if prefs.get('zscore_zone_change') else '❌'}",
        f"  F-Score changes: {'✅' if prefs.get('fscore_change') else '❌'}",
        "",
        f"Telegram: {'✅ Connected' if prefs.get('telegram_chat_id') else '❌ Not linked'}",
    ]

    send_telegram_message(bot_token, chat_id, "\n".join(lines))


def _cmd_interval(bot_token: str, chat_id: str, user_id: int, text: str) -> None:
    """Change how often the daemon checks watchlist."""
    from src.data.notification_db import set_preferences

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(
            bot_token, chat_id,
            "Usage: <code>/interval &lt;hours&gt;</code> — Example: <code>/interval 6</code>",
        )
        return

    try:
        hours = int(parts[1].strip())
    except ValueError:
        send_telegram_message(
            bot_token, chat_id,
            "Interval must be a number. Example: <code>/interval 6</code>",
        )
        return

    if hours < 1 or hours > 24:
        send_telegram_message(
            bot_token, chat_id,
            "Interval must be between 1 and 24 hours.",
        )
        return

    set_preferences(user_id, check_interval_hours=hours)
    send_telegram_message(
        bot_token, chat_id,
        f"✅ Check interval set to every {hours} hours.",
    )


def clear_polling_state(user_id: int) -> None:
    """Reset polling state when a user disconnects their bot."""
    _last_update_ids.pop(user_id, None)
