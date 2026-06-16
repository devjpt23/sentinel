"""
Standalone notification checker CLI.

Runs notification checks for one or all users and optionally delivers
via Telegram and/or ntfy push. Designed for cron-based fallback when the
in-process APScheduler isn't running (e.g., separate machine, system cron backup).

Usage:
    python -m src.cli.sentinel_notify --user trader1
    python -m src.cli.sentinel_notify --all --telegram
    python -m src.cli.sentinel_notify --all --ntfy
    python -m src.cli.sentinel_notify --user trader1 --telegram --ntfy

Cron example (weekdays at 8 AM):
    0 8 * * 1-5 /path/to/.venv/bin/python -m src.cli.sentinel_notify --all --ntfy
"""

import argparse
import sys
import os
from datetime import datetime, timezone

# Ensure the project root is on sys.path so src.* imports work
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.data.auth_db import get_all_users, get_user_by_username
from src.data.notification_db import (
    init_notification_db,
    start_check_run,
    finish_check_run,
)
from src.data.watchlist_db import load_user_watchlist
from src.notifications.checker import run_check_for_ticker, deliver_notifications


def main():
    parser = argparse.ArgumentParser(
        description="Sentinel Notification Checker — run watchlist checks and deliver alerts."
    )
    parser.add_argument(
        "--user", type=str, help="Check watchlist for a specific username"
    )
    parser.add_argument(
        "--all", action="store_true", help="Check watchlists for all users"
    )
    parser.add_argument(
        "--telegram", action="store_true", help="Deliver notifications via Telegram"
    )
    parser.add_argument(
        "--ntfy", action="store_true", help="Deliver notifications via ntfy push"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show per-ticker progress"
    )
    args = parser.parse_args()

    if not args.user and not args.all:
        parser.error("Specify --user USERNAME or --all")

    # Init
    init_notification_db()

    # Determine which users to check
    users = []
    if args.user:
        user = get_user_by_username(args.user)
        if not user:
            print(f"User '{args.user}' not found.", file=sys.stderr)
            sys.exit(1)
        users = [user]
    else:
        users = get_all_users()

    if not users:
        print("No users found.")
        return

    # Run checks
    total_notifications = 0
    total_delivered = 0

    for user in users:
        tickers = load_user_watchlist(user["id"])
        if not tickers:
            if args.verbose:
                print(f"User '{user['username']}': no tickers in watchlist, skipping.")
            continue

        job_id = f"cli_manual_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        run_id = start_check_run(user["id"], job_id)

        notifications_by_ticker = {}

        for ticker in tickers:
            if args.verbose:
                print(f"  Checking {ticker}...", end=" ", flush=True)

            try:
                notifications = run_check_for_ticker(user["id"], ticker)
                if notifications:
                    notifications_by_ticker[ticker] = notifications
                    total_notifications += len(notifications)
                    if args.verbose:
                        print(f"{len(notifications)} alert(s)")
                else:
                    if args.verbose:
                        print("no changes")
            except Exception as e:
                if args.verbose:
                    print(f"error: {e}")

        # Deliver via enabled channels
        if notifications_by_ticker and (args.telegram or args.ntfy):
            delivered = deliver_notifications(user["id"], notifications_by_ticker)
            total_delivered += delivered

        # Log run
        finish_check_run(
            run_id, len(tickers), total_notifications,
            status="ok",
        )

        if notifications_by_ticker:
            ticker_list = ", ".join(notifications_by_ticker.keys())
            channels = []
            if args.telegram:
                channels.append("Telegram")
            if args.ntfy:
                channels.append("ntfy")
            channel_str = " + ".join(channels) if channels else ""
            print(
                f"User '{user['username']}': {len(notifications_by_ticker)} ticker(s) with changes "
                f"({ticker_list}), {total_notifications} notification(s)"
                + (f", {total_delivered} delivered via {channel_str}" if channel_str else "")
            )
        elif args.verbose:
            print(f"User '{user['username']}': no changes detected.")

    print(f"\nTotal: {total_notifications} notification(s) across {len(users)} user(s).")
    if args.telegram or args.ntfy:
        channels = []
        if args.telegram:
            channels.append("Telegram")
        if args.ntfy:
            channels.append("ntfy")
        print(f"Delivered: {total_delivered} message(s) via {' + '.join(channels)}.")


if __name__ == "__main__":
    main()
