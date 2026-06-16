"""
Sentinel Notification Daemon — 24/7 background service.

Runs as a systemd service, polling Telegram bots every 5 seconds for
incoming commands, running watchlist checks on each user's schedule,
and performing daily database maintenance.

Usage:
    python3 -m src.notifications.daemon
"""

import sys
import time
import logging
from datetime import datetime

from src.data.auth_db import init_auth_db
from src.data.notification_db import (
    init_notification_db,
    get_user_ids_with_watchlist,
    get_preferences,
    get_user_bot_tokens,
    prune_old_notifications,
    prune_check_runs,
)
from src.notifications.checker import (
    check_all_tickers_for_user,
    deliver_notifications,
)
from src.notifications.telegram_bot import poll_user_bot

logger = logging.getLogger(__name__)

# Track last check time per user (in-memory, reset on daemon restart).
# Keys are user_id, values are Unix timestamps from time.time().
_last_check: dict[int, float] = {}


def check_tick() -> None:
    """Run watchlist checks for users who are due.

    Called every 60 seconds by the main loop. For each user with a
    watchlist, checks whether they are due based on their configured
    check_interval_hours and the stagger formula (user_id * 37) % 60
    which spreads users across the hour so they don't all fire at the
    same minute.
    """
    user_ids = get_user_ids_with_watchlist()
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
        with tempfile.NamedTemporaryFile(dir=cache_dir) as f:
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
    databases, then enters an infinite loop with three ticks:

    - check_tick  (every 60 s):  scheduled watchlist checks
    - poll_tick   (every  5 s):  Telegram bot polling
    - maintenance (daily):       DB pruning
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

    last_check_tick = 0.0
    last_poll_tick = 0.0
    last_maintenance_tick = time.time()

    logger.info("Entering main loop (check=60s, poll=5s, maintenance=24h)")

    while True:
        now = time.time()

        # Check tick — every 60 seconds
        if now - last_check_tick >= 60:
            check_tick()
            last_check_tick = now

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