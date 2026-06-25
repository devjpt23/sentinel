"""
Sentinel Notification Daemon — 24/7 background service.

Runs as a systemd service, polling Telegram bots every 5 seconds for
incoming commands, running watchlist checks on each user's schedule,
and performing daily database maintenance.

Usage:
    python3 -m src.notifications.daemon
"""

import os
import sys
import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from src.data.auth_db import init_auth_db
from src.data.notification_db import (
    init_notification_db,
    get_user_ids_needing_checks,
    get_preferences,
    get_user_bot_tokens,
    get_all_active_alerts_grouped_by_ticker,
    prune_old_notifications,
    prune_check_runs,
)
from src.data.ticker_fetcher import TickerDataFetcher
from src.notifications.checker import (
    check_all_tickers_for_user,
    deliver_notifications,
    check_ticker_news,
    evaluate_price_alert,
)
from src.notifications.custom_alerts import evaluate_custom_alerts
from src.notifications.price_feed import FinnhubPriceFeed
from src.notifications.telegram_bot import poll_user_bot

logger = logging.getLogger(__name__)

# Track last check time per user (in-memory, reset on daemon restart).
# Keys are user_id, values are Unix timestamps from time.time().
_last_check: dict[int, float] = {}

_last_news_check = 0.0
NEWS_CHECK_INTERVAL = 900  # 15 minutes


def news_check_tick() -> None:
    """Run news check if enough time has passed (every 15 min).

    Fire-and-forget: spawns a daemon thread so it doesn't block
    the main reconciliation loop.
    """
    global _last_news_check
    now = time.time()
    if now - _last_news_check < NEWS_CHECK_INTERVAL:
        return
    _last_news_check = now

    logger.info("News check tick starting")
    thread = threading.Thread(target=check_ticker_news, daemon=True)
    thread.start()


def check_tick() -> None:
    """Run watchlist checks for users who are due.

    Called every 60 seconds by the main loop. For each user with a
    watchlist, checks whether they are due based on their configured
    check_interval_hours and the stagger formula (user_id * 37) % 60
    which spreads users across the hour so they don't all fire at the
    same minute.
    """
    user_ids = get_user_ids_needing_checks()
    if not user_ids:
        return

    now = time.time()
    current_minute = datetime.now().minute

    for user_id in user_ids:
        try:
            prefs = get_preferences(user_id)
            interval_hours = prefs.get("check_interval_hours", 2)
            stagger = (user_id * 37) % 60

            # Only check this user if their stagger minute matches AND
            # enough time has passed since their last check.
            last = _last_check.get(user_id, 0)
            if current_minute == stagger and (now - last) >= interval_hours * 3600:
                logger.info(
                    "Check tick: user %d (interval=%dh, stagger=%d)",
                    user_id,
                    interval_hours,
                    stagger,
                )
                notifications_by_ticker = check_all_tickers_for_user(user_id)
                if notifications_by_ticker:
                    delivered = deliver_notifications(
                        user_id, notifications_by_ticker
                    )
                    logger.info(
                        "User %d: %d tickers with notifications, %d delivered",
                        user_id,
                        len(notifications_by_ticker),
                        delivered,
                    )
                _last_check[user_id] = now
        except Exception:
            logger.exception("check_tick failed for user %d", user_id)


_fetcher = TickerDataFetcher(max_workers=5)

# Price feed instance (initialized in main(), None if no API key)
_price_feed: Optional[FinnhubPriceFeed] = None
_last_sub_refresh = 0.0
_SUB_REFRESH_INTERVAL = 300  # 5 minutes


def price_tick(feed: Optional[FinnhubPriceFeed] = None) -> None:
    """Drain price feed events and evaluate price-based alert rules.

    Called every main-loop iteration (1s). Does NOT need its own timer —
    called directly since events are rare and the check is cheap.

    Args:
        feed: The price feed instance, or None (no-op).
    """
    if feed is None:
        return

    events = feed.drain_events()
    if not events:
        return

    # 1. Deduplicate: keep only the latest price per ticker per tick
    latest: Dict[str, Dict] = {}
    for ev in events:
        ticker = ev["ticker"].upper()
        latest[ticker] = ev  # last wins (queue is FIFO, so later = newer)

    # 2. For each ticker with a new price, evaluate alert rules
    rules_by_ticker = get_all_active_alerts_grouped_by_ticker()

    for ticker, ev in latest.items():
        if ticker not in rules_by_ticker:
            continue

        ticker_rules = rules_by_ticker[ticker]
        price = ev["price"]

        # Group rules by user_id
        by_user: Dict[int, List[Dict]] = {}
        for rule in ticker_rules:
            by_user.setdefault(rule["user_id"], []).append(rule)

        for user_id in by_user:
            try:
                notifications = evaluate_price_alert(
                    user_id,
                    ticker,
                    price,
                )
                if notifications:
                    delivered = deliver_notifications(
                        user_id, {ticker: notifications}
                    )
                    if delivered:
                        logger.info(
                            "Price feed: user %d, %s @ $%.2f — "
                            "%d delivered",
                            user_id,
                            ticker,
                            price,
                            delivered,
                        )
            except Exception:
                logger.exception(
                    "price_tick failed for user %d, %s",
                    user_id,
                    ticker,
                )


def _refresh_price_feed_subscriptions() -> None:
    """Query DB for tickers with active alert rules and push to price feed.

    Called on startup and every 5 minutes to pick up new alert rules.
    No-op if the price feed is not initialized.
    """
    global _price_feed
    if _price_feed is None:
        return
    rules_by_ticker = get_all_active_alerts_grouped_by_ticker()
    tickers = set(rules_by_ticker.keys())
    _price_feed.refresh_subscriptions(tickers)


def reconciliation_tick() -> None:
    """Fast reconciliation loop for custom alert rules.

    Runs every 60 seconds — no stagger, no user-level gating. Queries
    ALL active custom alert rules grouped by ticker, fetches market
    data once per ticker (shared across users), evaluates conditions,
    and delivers notifications immediately when triggered.

    Only price/technical signals fire here (they work with lightweight
    market data). Fundamental signals (health, F-score, P/E, etc.) are
    handled by ``check_tick()`` when the user's stagger window hits.
    """
    rules_by_ticker = get_all_active_alerts_grouped_by_ticker()
    if not rules_by_ticker:
        return

    tickers = set(rules_by_ticker.keys())
    if not tickers:
        return

    logger.info(
        "Reconciliation tick: %d tickers, %d total rule-instances",
        len(tickers),
        sum(len(r) for r in rules_by_ticker.values()),
    )

    # Fetch market data (price + OHLCV) for all tickers in parallel
    fetched = _fetcher.fetch_many(tickers)

    for ticker, ticker_rules in rules_by_ticker.items():
        ticker_data = fetched.get(ticker)
        if not ticker_data:
            continue

        # Build minimal data dict for price/technical signals
        data = {"market": ticker_data.get("market", {})}
        history = ticker_data.get("history", pd.DataFrame())
        scores: Dict = {}  # fundamental signals return None → skipped

        # Group rules by user_id so we can evaluate per user
        by_user: Dict[int, List[Dict]] = {}
        for rule in ticker_rules:
            by_user.setdefault(rule["user_id"], []).append(rule)

        for user_id, _ in by_user.items():
            try:
                notifications = evaluate_custom_alerts(
                    user_id,
                    ticker,
                    data,
                    scores,
                    history_override=history,
                )
                if notifications:
                    delivered = deliver_notifications(
                        user_id, {ticker: notifications}
                    )
                    if delivered:
                        logger.info(
                            "Reconciliation: user %d, %s — %d delivered",
                            user_id,
                            ticker,
                            delivered,
                        )
            except Exception:
                logger.exception(
                    "Reconciliation tick failed for user %d, %s",
                    user_id,
                    ticker,
                )

    _fetcher.clear_cycle()


def poll_tick() -> None:
    """Poll every user's Telegram bot for incoming commands.

    Called every 5 seconds by the main loop. Processes /start, /link,
    /status, and fallback messages. The poll_user_bot() function tracks
    _last_update_ids per user internally so we don't re-process the
    same messages.
    """
    users = get_user_bot_tokens()
    if not users:
        return

    for u in users:
        try:
            poll_user_bot(u["user_id"], u["telegram_bot_token"])
        except Exception:
            logger.exception("poll_tick failed for user %d", u["user_id"])


def maintenance_tick() -> None:
    """Run daily database maintenance.

    Prunes notifications older than 90 days and keeps at most 200
    check-run records per user.
    """
    try:
        pruned_notifs = prune_old_notifications(days=90)
        pruned_runs = prune_check_runs(max_per_user=200)
        logger.info(
            "Maintenance: pruned %d notifications, %d check runs",
            pruned_notifs,
            pruned_runs,
        )
    except Exception:
        logger.exception("maintenance_tick failed")


def _startup_check() -> None:
    """Validate environment before entering the main loop.

    Catches common deployment issues early (permissions, missing dirs,
    unconfigured bot tokens) and logs clear warnings instead of crashing
    silently in the main loop.
    """
    import os
    import tempfile

    # Check cache directory is writable (yfinance caches data here)
    cache_dir = os.path.expanduser("~/.cache/trade_proj/yf_cache")
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cache_dir):
            pass
    except PermissionError:
        logger.error("Cache directory %s is not writable. "
                      "Check ProtectHome=false in the systemd service file.", cache_dir)
        raise

    # Warn if no bot tokens are configured (daemon will run but ignore Telegram)
    tokens = get_user_bot_tokens()
    if not tokens:
        logger.warning("No users have a Telegram bot token configured. "
                        "Telegram commands will not work until a token is set in notification_preferences.")
    else:
        logger.info("Polling %d user bot token(s)", len(tokens))


def main() -> None:
    """Initialize databases and run the main daemon loop forever.

    Configures root logging to stream to stdout so systemd captures
    log output in the journal. Initializes both the auth and notification
    databases, then enters an infinite loop with four ticks:

    - reconciliation_tick  (every 60 s): custom alerts, all users, no stagger
    - check_tick           (every 60 s): scheduled watchlist checks (stagger)
    - poll_tick            (every  5 s): Telegram bot polling
    - maintenance          (daily):      DB pruning
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stdout,
    )

    logger.info("Sentinel daemon starting...")

    # Initialize databases (safe to call repeatedly — uses IF NOT EXISTS)
    init_auth_db()
    init_notification_db()
    logger.info("Databases initialized")

    _startup_check()

    # Initialize price feed
    global _price_feed
    _api_key = os.environ.get("FINNHUB_API_KEY", "")
    if _api_key:
        _price_feed = FinnhubPriceFeed(_api_key)
        # Load initial ticker subscriptions from active alert rules
        _refresh_price_feed_subscriptions()
        _price_feed.start()
        logger.info("Price feed started via Finnhub WebSocket")
    else:
        logger.warning(
            "FINNHUB_API_KEY not set — real-time price feed disabled"
        )

    last_check_tick = 0.0
    last_reconciliation_tick = 0.0
    last_poll_tick = 0.0
    last_maintenance_tick = time.time()

    global _last_sub_refresh

    logger.info(
        "Entering main loop (reconciliation=60s, check=60s, poll=5s, "
        "news=15m, maintenance=24h)"
    )

    while True:
        now = time.time()

        # Subscription refresh for price feed — every 5 minutes
        if now - _last_sub_refresh >= _SUB_REFRESH_INTERVAL:
            _refresh_price_feed_subscriptions()
            _last_sub_refresh = now

        # Price feed tick — every loop iteration (cheap if no events)
        price_tick(_price_feed)

        # Reconciliation tick — every 60 seconds (no stagger)
        if now - last_reconciliation_tick >= 60:
            reconciliation_tick()
            last_reconciliation_tick = now

        # Check tick — every 60 seconds (stagger-gated)
        if now - last_check_tick >= 60:
            check_tick()
            last_check_tick = now

        # News check tick — internally gated to 15 minutes
        news_check_tick()

        # Telegram poll tick — every 5 seconds
        if now - last_poll_tick >= 5:
            poll_tick()
            last_poll_tick = now

        # Maintenance tick — daily
        if now - last_maintenance_tick >= 86400:
            maintenance_tick()
            last_maintenance_tick = now

        time.sleep(1)


if __name__ == "__main__":
    main()