"""
Background notification scheduler — the heartbeat of the notification system.

Inspired by OpenClaw's cron system: SQLite-backed persistent job store,
staggered per-user schedules, channel-based delivery, and bounded run history.

Runs as a daemon thread alongside the Streamlit server. Each user gets one
recurring job that checks their entire watchlist. Users are staggered by
(N * 37) % 60 minutes to prevent all checks from firing simultaneously.

Usage:
    from src.notifications.scheduler import start_scheduler

    scheduler = start_scheduler()   # starts background thread, returns immediately
    # ... Streamlit app runs ...
    scheduler.shutdown(wait=False)  # optional: clean shutdown
"""

import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger

from src.data.notification_db import (
    init_notification_db,
    get_preferences,
    start_check_run,
    finish_check_run,
    prune_check_runs,
    prune_old_notifications,
    get_user_ids_with_watchlist,
)
from src.data.watchlist_db import load_user_watchlist
from src.notifications.checker import (
    run_check_for_ticker,
    deliver_notifications,
)

logger = logging.getLogger(__name__)


def start_scheduler() -> BackgroundScheduler:
    """Start the background notification scheduler.

    Called once at app startup. Returns the scheduler instance so the
    caller can shut it down gracefully if needed.
    """
    # Ensure all notification tables exist
    init_notification_db()

    db_url = _get_scheduler_db_url()

    jobstores = {
        "default": SQLAlchemyJobStore(url=db_url),
    }
    executors = {
        "default": ThreadPoolExecutor(4),
    }
    job_defaults = {
        "coalesce": True,            # skip missed runs, don't pile up
        "max_instances": 1,          # prevent overlapping runs
        "misfire_grace_time": 600,   # 10 min grace period
    }

    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
    )

    # ─── Per-user check jobs ────────────────────────────

    # Use user_watchlist table (multi-user), not the old global one
    user_ids = get_user_ids_with_watchlist()

    for idx, user_id in enumerate(user_ids):
        prefs = get_preferences(user_id)
        interval_hours = prefs.get("check_interval_hours", 2)
        # Stagger: spread users across the interval to avoid load spikes
        stagger_minutes = (idx * 37) % 60

        scheduler.add_job(
            _check_user_watchlist,
            CronTrigger(
                hour=f"*/{interval_hours}",
                minute=stagger_minutes,
            ),
            args=[user_id],
            id=f"check_user_{user_id}",
            name=f"Watchlist check for user {user_id}",
            replace_existing=True,
        )
        logger.info(
            f"Scheduled user {user_id}: every {interval_hours}h at "
            f":{stagger_minutes:02d} past the hour"
        )

    # ── Startup catch-up: run checks immediately on app wake ──
    # Streamlit Cloud hibernates idle apps. When the app wakes up,
    # fire a one-shot check for every user so no alerts are missed.
    for user_id in user_ids:
        scheduler.add_job(
            _check_user_watchlist,
            "date",  # fire once, immediately
            args=[user_id],
            id=f"startup_catchup_{user_id}",
            name=f"Startup catch-up for user {user_id}",
            replace_existing=True,
        )
    logger.info(f"Scheduled startup catch-up checks for {len(user_ids)} user(s)")

    # ─── Maintenance jobs ───────────────────────────────

    scheduler.add_job(
        _maintenance_tick,
        CronTrigger(hour=3, minute=17),  # 3:17 AM daily
        id="notification_maintenance",
        name="Prune old notifications and check runs",
        replace_existing=True,
    )

    # ─── Rescan for new users (daily) ────────────────────

    scheduler.add_job(
        _rescan_users,
        CronTrigger(hour=2, minute=7),  # 2:07 AM daily
        args=[scheduler],
        id="rescan_users",
        name="Discover and schedule checks for new users",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Notification scheduler started")
    return scheduler


# ─── Job Functions ───────────────────────────────────────────

def _check_user_watchlist(user_id: int) -> None:
    """Check all tickers in a user's watchlist. Called by the scheduler."""
    tickers = load_user_watchlist(user_id)
    if not tickers:
        return

    job_id = f"check_user_{user_id}"
    run_id = start_check_run(user_id, job_id)

    total_notifications = 0
    notifications_by_ticker = {}

    try:
        for ticker in tickers:
            try:
                notifications = run_check_for_ticker(user_id, ticker)
                if notifications:
                    notifications_by_ticker[ticker] = notifications
                    total_notifications += len(notifications)
            except Exception:
                logger.exception(f"Error checking {ticker} for user {user_id}")

        if notifications_by_ticker:
            delivered = deliver_notifications(user_id, notifications_by_ticker)
            logger.info(
                f"User {user_id}: {len(notifications_by_ticker)} tickers with changes, "
                f"{total_notifications} notifications, {delivered} delivered"
            )

        finish_check_run(run_id, len(tickers), total_notifications, status="ok")

    except Exception as e:
        logger.exception(f"Check run {run_id} crashed for user {user_id}")
        finish_check_run(
            run_id, len(tickers), total_notifications,
            status="error", error_message=str(e),
        )


def _maintenance_tick() -> None:
    """Daily cleanup: prune old notifications and check run history."""
    deleted_notifs = prune_old_notifications(days=90)
    deleted_runs = prune_check_runs(max_per_user=200)
    logger.info(f"Maintenance: pruned {deleted_notifs} notifications, {deleted_runs} check runs")


def _rescan_users(scheduler: BackgroundScheduler) -> None:
    """Discover new users and schedule their watchlist check jobs."""
    existing_jobs = {job.id for job in scheduler.get_jobs()}

    # New users with watchlists
    user_ids = get_user_ids_with_watchlist()
    for idx, user_id in enumerate(user_ids):
        job_id = f"check_user_{user_id}"
        if job_id not in existing_jobs:
            prefs = get_preferences(user_id)
            interval_hours = prefs.get("check_interval_hours", 2)
            stagger_minutes = (idx * 37) % 60
            scheduler.add_job(
                _check_user_watchlist,
                CronTrigger(hour=f"*/{interval_hours}", minute=stagger_minutes),
                args=[user_id],
                id=job_id,
                name=f"Watchlist check for user {user_id}",
                replace_existing=True,
            )
            logger.info(f"New user {user_id} scheduled: every {interval_hours}h")


# ─── Public API (called from Settings page) ──────────────────

_SCHEDULER_INSTANCE: Optional[BackgroundScheduler] = None


def set_scheduler_instance(scheduler: BackgroundScheduler) -> None:
    """Store the scheduler instance so the settings page can reach it."""
    global _SCHEDULER_INSTANCE
    _SCHEDULER_INSTANCE = scheduler


# ─── Internal Helpers ────────────────────────────────────────

def _get_scheduler_db_url() -> str:
    """Build the APScheduler SQLite URL pointing at the shared DB."""
    import os
    db_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "watchlist.db",
    )
    return f"sqlite:///{db_path}"
