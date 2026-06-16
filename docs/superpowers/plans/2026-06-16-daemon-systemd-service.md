# Sentinel Daemon — systemd Service Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install a systemd user service so the Sentinel notification daemon runs 24/7 independently of the Streamlit web app.

**Architecture:** A systemd user service (`sentinel-daemon.service`) runs the daemon as a long-lived background process under the user's account. It uses the project's Python venv, sets the working directory to the project root, and auto-restarts on failure. A helper script wraps start/stop/status for convenience.

**Tech Stack:** systemd (user mode), bash, Python 3.12, SQLite

**Current state:**
- Daemon entry point: `src.notifications.daemon:main` (already registered as `sentinel-daemon` in `pyproject.toml:22`)
- Python venv: `.venv/bin/python3`
- Database: `watchlist.db` (in project root)
- Project root: `/home/devjpt23/openSourceProjects/tradeProj`
- User: `devjpt23`
- No existing systemd service or venv activation helpers

---

### Task 1: Create the systemd unit file

**Files:**
- Create: `systemd/sentinel-daemon.service`

- [ ] **Step 1: Write the unit file**

```ini
[Unit]
Description=Sentinel Notification Daemon — 24/7 background alert service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/openSourceProjects/tradeProj
ExecStart=%h/openSourceProjects/tradeProj/.venv/bin/python3 -m src.notifications.daemon
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sentinel-daemon

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=%h/openSourceProjects/tradeProj/watchlist.db %h/openSourceProjects/tradeProj/watchlist.db-wal %h/openSourceProjects/tradeProj/watchlist.db-shm
PrivateTmp=true

[Install]
WantedBy=default.target
```

Key decisions:
- `%h` expands to the user's home dir — portable across machines
- Uses the venv Python directly (no `source activate` needed)
- `Restart=on-failure` with 10s backoff — survives transient network issues
- `ProtectSystem=strict` with explicit `ReadWritePaths` — read-only filesystem except the DB
- `journal` logging — viewable with `journalctl --user -u sentinel-daemon`

- [ ] **Step 2: Install and enable the service**

```bash
mkdir -p ~/.config/systemd/user
cp systemd/sentinel-daemon.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable sentinel-daemon.service
```

Expected output:
```
Created symlink /home/devjpt23/.config/systemd/user/default.target.wants/sentinel-daemon.service → /home/devjpt23/.config/systemd/user/sentinel-daemon.service.
```

- [ ] **Step 3: Commit**

```bash
git add systemd/sentinel-daemon.service
git commit -m "feat: add systemd user service for sentinel daemon"
```

---

### Task 2: Enable systemd user linger so daemon survives logout

**Files:**
- No files to create

- [ ] **Step 1: Enable linger for the user**

```bash
loginctl enable-linger devjpt23
```

**Why:** By default, systemd user services stop when the user logs out (ends the user session). `loginctl enable-linger` starts a user manager at boot and keeps it running even with no active login session, so the daemon survives SSH disconnects, terminal closes, and reboots.

- [ ] **Step 2: Verify linger is enabled**

```bash
loginctl show-user devjpt23 -p Linger
```

Expected output:
```
Linger=yes
```

---

### Task 3: Test the daemon runs and sends Telegram notifications

**Files:**
- No files to create

- [ ] **Step 1: Start the service**

```bash
systemctl --user start sentinel-daemon.service
```

- [ ] **Step 2: Verify it's running**

```bash
systemctl --user status sentinel-daemon.service
```

Expected output (key lines):
```
● sentinel-daemon.service - Sentinel Notification Daemon — 24/7 background alert service
     Active: active (running)
   Main PID: <number> (python3)
```

- [ ] **Step 3: Check logs for startup messages**

```bash
journalctl --user -u sentinel-daemon.service --no-pager -n 20
```

Expected output:
```
sentinel-daemon[PID]: Sentinel daemon starting...
sentinel-daemon[PID]: Databases initialized
sentinel-daemon[PID]: Entering main loop (check=60s, poll=5s, maintenance=24h)
```

- [ ] **Step 4: Force a score change to trigger a notification**

```bash
sqlite3 ~/openSourceProjects/tradeProj/watchlist.db "UPDATE snapshots SET health_score=30, health_verdict='Poor' WHERE user_id=1 AND ticker='AAPL';"
```

(Uses the known user id=1. If AAPL isn't on the watchlist, pick a ticker that is.)

- [ ] **Step 5: Wait for the check tick and verify delivery**

```bash
journalctl --user -u sentinel-daemon.service --no-pager -f
```

Within 60 seconds, expect to see:
```
sentinel-daemon[PID]: Check tick: user 1 (interval=2h, stagger=37)
sentinel-daemon[PID]: User 1: 1 tickers with notifications, 1 delivered
```

Also check Telegram on chat_id `8367863087` for the health score alert message.

- [ ] **Step 6: Stop the daemon for now**

```bash
systemctl --user stop sentinel-daemon.service
journalctl --user -u sentinel-daemon.service --no-pager -n 5
```

- [ ] **Step 7: Commit (no code changes, just verify state)**

```bash
git status
```

---

### Task 4: Create a convenience helper script

**Files:**
- Create: `scripts/daemon.sh`

- [ ] **Step 1: Write the helper script**

```bash
#!/usr/bin/env bash
# Sentinel daemon helper — start/stop/status/logs
set -euo pipefail

ACTION="${1:-status}"

case "$ACTION" in
  start)
    systemctl --user start sentinel-daemon.service
    echo "Daemon started."
    systemctl --user status sentinel-daemon.service --no-pager
    ;;
  stop)
    systemctl --user stop sentinel-daemon.service
    echo "Daemon stopped."
    ;;
  status)
    systemctl --user status sentinel-daemon.service --no-pager
    ;;
  logs)
    LINES="${2:-50}"
    journalctl --user -u sentinel-daemon.service --no-pager -n "$LINES"
    ;;
  restart)
    systemctl --user restart sentinel-daemon.service
    echo "Daemon restarted."
    ;;
  *)
    echo "Usage: $0 {start|stop|status|restart|logs [lines]}"
    exit 1
    ;;
esac
```

- [ ] **Step 2: Make it executable and test**

```bash
chmod +x scripts/daemon.sh
scripts/daemon.sh start
scripts/daemon.sh status
scripts/daemon.sh logs 10
scripts/daemon.sh stop
```

- [ ] **Step 3: Commit**

```bash
git add scripts/daemon.sh
git commit -m "feat: add daemon helper script for start/stop/status/logs"
```
