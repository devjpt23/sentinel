# Telegram Two-Way Integration — Feature Design

**Date:** 2026-06-15
**Status:** Draft
**Context:** Restore and harden Telegram integration so each Sentinel user can receive alerts and query data via their own Telegram bot, driven by a standalone 24/7 daemon.

---

## 1. Goal

Each of the ~10 Sentinel users brings their own Telegram bot token (created via BotFather). Once connected, communication flows in both directions:

- **Site → User:** The daemon checks watchlist tickers on schedule and pushes alerts for meaningful changes.
- **User → Site:** The user messages their bot with predefined commands (`/start`, `/link`, `/status`) and gets responses back from the daemon.

Alerts and commands work 24/7 regardless of whether anyone is visiting the Streamlit dashboard.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Linux VPS                             │
│                                                          │
│  ┌──────────────────────┐  ┌──────────────────────────┐ │
│  │  Sentinel Daemon     │  │  Streamlit Dashboard     │ │
│  │  (systemd service)   │  │  (on-demand web UI)      │ │Once you have an active subscription, run az login again and I'll be able to manage your resources. Want help with anything else in the meantime?


│  │  Runs 24/7           │  │  Hibernates when idle    │ │
│  │                      │  │                          │ │
│  │  Main loop (~1 Hz):  │  │  Pages:                  │ │
│  │  • Check tick: 60s   │  │  • Dashboard             │ │
│  │  • Poll tick: 5s     │  │  • Watchlist             │ │
│  │  • Maint tick: daily │  │  • Settings (Telegram)   │ │
│  └────────┬─────────────┘  │  • Notifications list    │ │
│           │                 └────────┬─────────────────┘ │
│           │                          │                   │
│           └──────────┬───────────────┘                   │
│                      ▼                                   │
│           ┌──────────────────┐                           │
│           │  watchlist.db    │  SQLite, WAL mode         │
│           │  (shared state)  │                           │
│           └──────────────────┘                           │
└──────────────────────────────────────────────────────────┘
```

### 2.1 Key Principle

The daemon and the dashboard share one SQLite database (`watchlist.db`, WAL mode). The daemon reads user watchlists, bot tokens, and preferences from the DB — it never serves HTTP. The dashboard is purely a web UI for users to manage their data. No message queue, no Redis, no additional infrastructure.

### 2.2 Deployment

The daemon runs as a systemd service:

```ini
[Unit]
Description=Sentinel Notification Daemon
After=network.target

[Service]
Type=simple
User=sentinel
ExecStart=/usr/bin/python3 -m src.notifications.daemon
WorkingDirectory=/opt/sentinel
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Single command to activate: `systemctl enable --now sentinel-daemon`.

---

## 3. Daemon Design

### 3.1 New File: `src/notifications/daemon.py`

A single Python module with a main loop. No dependencies beyond what the project already uses (`requests`, `sqlite3`, stdlib).

### 3.2 Main Loop

```
initialize:
    init_auth_db()
    init_notification_db()
    last_check_tick = 0
    last_poll_tick = 0
    last_maintenance_tick = time.time()

loop forever:
    now = time.time()

    # 1. Check tick — every 60 seconds
    if now - last_check_tick >= 60:
        check_tick()
        last_check_tick = now

    # 2. Telegram poll tick — every 5 seconds
    if now - last_poll_tick >= 5:
        poll_tick()
        last_poll_tick = now

    # 3. Maintenance tick — daily
    if now - last_maintenance_tick >= 86400:
        maintenance_tick()
        last_maintenance_tick = now

    time.sleep(1)
```

### 3.3 check_tick()

For each user with a watchlist, determine if they are due for a check based on their `check_interval_hours`. If due, run `check_all_tickers_for_user()` and `deliver_notifications()`. Stagger users across the interval using the existing `(user_id * 37) % 60` formula.

### 3.4 poll_tick()

Call `get_user_bot_tokens()` to get all users with a configured bot token. For each, call `poll_user_bot(user_id, bot_token)`. This processes incoming `/start`, `/link`, `/status`, and fallback commands. Track `last_update_id` per user (already implemented in `telegram_bot.py`).

### 3.5 maintenance_tick()

Prune notifications older than 90 days and check runs beyond 200 per user. Uses existing `prune_old_notifications()` and `prune_check_runs()`.

---

## 4. User Commands (Inbound)

Handled by `telegram_bot.py:_process_update()` — no changes needed to the command handlers, only the polling needs restoration.

| Command | Behavior |
|---------|----------|
| `/start` | Welcome message, auto-links `chat_id` to user account, sends watchlist price summary |
| `/link <username>` | Manually associates Telegram `chat_id` with a Sentinel username. Sends confirmation or error |
| `/status` | Returns watchlist with 3/6/12-month price growth for each ticker |
| Any other text | Treated as intent to connect — same behavior as `/start` |

### 4.1 Message Flow

```
User sends "/status" in Telegram
        │
        ▼
Telegram Bot API stores the message
        │
        ▼
Daemon poll_tick() calls getUpdates (every 5s)
        │
        ▼
_process_update() matches "/status"
        │
        ▼
send_watchlist_summary() calls fetch_price_growth()
for each ticker (parallel, ThreadPoolExecutor)
        │
        ▼
send_telegram_message() POSTs formatted reply
        │
        ▼
User sees the response on their phone
```

---

## 5. Settings UI (Dashboard)

### 5.1 Section Placement

A new "🤖 Telegram Notifications" section in the existing Settings page (`render_settings_page()`), placed **above** the existing ntfy section.

### 5.2 States

**Not connected — user has no bot token saved:**

Instructions:
1. Open @BotFather on Telegram
2. Send `/newbot` and follow the prompts
3. Paste the token below

A token input field + "Connect" button. On submit: save `telegram_bot_token` and `telegram_enabled = 1`, then attempt `discover_chat_id()`. If a `chat_id` is found (user already messaged the bot), auto-link. Otherwise show: "Now send any message to your bot on Telegram so we can connect."

**Connected — token saved and chat_id found:**

Show:
- "✅ Connected to chat `{chat_id}`"
- Test message button — sends a test alert via `send_test_message()`
- Disconnect button — clears token, chat_id, and disables Telegram

**Token saved but no chat_id yet:**

Show:
- "⚠️ Bot token saved but not linked yet."
- "Send any message to your bot on Telegram, then come back."
- Retry button to re-run `discover_chat_id()`
- Option to use `/link <username>` as an alternative path

### 5.3 Integration with Existing Channels

The Telegram section lives alongside the existing ntfy and Gmail sections. All three are independent — a user can enable any combination. The `deliver_notifications()` function already supports parallel delivery to all enabled channels.

---

## 6. Database

No schema changes needed. All columns already exist:

### 6.1 Existing Columns Used

**`notification_preferences`:**
- `telegram_bot_token TEXT` — per-user bot token from BotFather
- `telegram_enabled BOOLEAN` — user toggle

**`users`:**
- `telegram_chat_id TEXT` — discovered chat_id, linked to account

**`telegram_link_codes`:** — existing table for `/link` code flow (unused but available)

### 6.2 Concurrency

SQLite WAL mode is already enabled. The daemon and dashboard both read/write the same DB. WAL allows concurrent reads and serialized writes — sufficient for this load (~10 users).

---

## 7. Error Handling

| Scenario | Handling |
|----------|----------|
| Invalid bot token (401) | Log warning, skip polling for that user, show error in Settings |
| Bot blocked by user (403) | Log warning, clear `telegram_chat_id`, stop sending |
| Rate limit (429) | Exponential backoff in `send_telegram_message()` (already implemented) |
| Network timeout | Retry once, log warning, move on |
| Daemon crash | systemd auto-restarts after 10 seconds |
| DB locked | WAL mode — writer waits for readers, no action needed |
| User has no watchlist | Reply with "Your watchlist is empty" instead of crashing |

---

## 8. Files Changed

| File | Change |
|------|--------|
| `src/notifications/daemon.py` | **New** — main loop, check/poll/maintenance ticks |
| `src/display/notifications.py` | Add Telegram setup section to `render_settings_page()` |
| `src/notifications/__init__.py` | Export daemon entry point if needed |

### 8.1 Files NOT Changed

| File | Why |
|------|-----|
| `src/notifications/telegram_bot.py` | Already complete — sending, formatting, polling, commands, all work |
| `src/notifications/checker.py` | Already has working Telegram delivery path in `deliver_notifications()` |
| `src/notifications/scheduler.py` | Unchanged — startup catch-up checks still fire when dashboard wakes. Duplicate delivery is harmless: `create_notification()` deduplicates on (user_id, ticker, type, new_value) within 24h, and the daemon's stagger prevents both checking the same user at the same minute |
| `src/notifications/ntfy_sender.py` | Unrelated — ntfy works independently |
| `src/notifications/gmail_sender.py` | Unrelated — Gmail works independently |
| `src/data/notification_db.py` | No schema changes needed |

---

## 9. Rollback Safety

- `telegram_bot.py` is a complete, untouched module — it works standalone
- The Streamlit scheduler (`scheduler.py`) keeps its current behavior as a fallback
- The daemon is additive — if it fails, the dashboard still functions
- All Telegram DB columns remain as-is

---

## 10. Out of Scope

- Adding new bot commands beyond `/start`, `/link`, `/status`
- Webhook-based Telegram updates (polling is fine for 10 users)
- Telegram group chat support
- Claude Code Telegram channel integration (separate feature)
- Removing ntfy or Gmail
- Extracting the Streamlit scheduler's check logic (stays as fallback)
