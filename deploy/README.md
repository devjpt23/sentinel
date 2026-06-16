# Sentinel Daemon Deployment

## Overview

The Sentinel daemon (`src/notifications/daemon.py`) runs 24/7 in the background,
checking user watchlists for alert triggers and polling Telegram bots for incoming
commands — even when no one has the Streamlit dashboard open.

## Architecture

```
┌─────────────────────────────────────────────────┐
│  VPS (systemd)                                   │
│                                                  │
│  sentinel-daemon.service                         │
│  ┌────────────────────────────────────┐          │
│  │  python -m src.notifications.daemon│          │
│  │                                    │          │
│  │  check_tick   (every 60s)          │          │
│  │  poll_tick    (every  5s)          │          │
│  │  maintenance  (daily)              │          │
│  └──────────┬─────────────────────────┘          │
│             │                                    │
│  ┌──────────▼─────────────────────────┐          │
│  │  watchlist.db (SQLite, WAL mode)   │          │
│  └────────────────────────────────────┘          │
└──────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Streamlit Cloud (or separate server)            │
│                                                  │
│  app.py + APScheduler (in-process fallback)     │
│  └── reads same watchlist.db                    │
└──────────────────────────────────────────────────┘
```

Both processes share `watchlist.db` in WAL mode for safe concurrent reads/writes.

## Files

| File | Purpose |
|------|---------|
| `sentinel-daemon.service` | systemd unit file with security hardening |
| `install-daemon.sh` | One-time VPS setup script |
| `update-daemon.sh` | Redeploy after code changes |
| `../.github/workflows/deploy-daemon.yml` | CI/CD auto-deploy on push to main |

## Initial Setup (one-time)

```bash
# SSH into your VPS, then:
cd /path/to/sentinel
sudo bash deploy/install-daemon.sh

# Or from a git repo:
sudo bash deploy/install-daemon.sh https://github.com/you/sentinel.git
```

The script:
1. Creates a `sentinel` system user (no login shell)
2. Copies/clones the project to `/opt/sentinel`
3. Creates a Python venv and installs all dependencies
4. Installs and starts the systemd service

## Update After Code Changes

```bash
# Manual (SSH into VPS):
cd /opt/sentinel
sudo bash deploy/update-daemon.sh

# Or via CI/CD — just push to main. The GitHub Action handles the rest.
```

## CI/CD Setup

Add these secrets to your GitHub repo settings:

| Secret | Value |
|--------|-------|
| `DAEMON_HOST` | VPS IP or hostname |
| `DAEMON_USER` | SSH username (must have sudo access) |
| `DAEMON_KEY` | SSH private key (no passphrase) |

## Operations

```bash
# View live logs
journalctl -u sentinel-daemon -f

# View recent logs
journalctl -u sentinel-daemon --since "1 hour ago"

# Stop / start / restart
systemctl stop sentinel-daemon
systemctl start sentinel-daemon
systemctl restart sentinel-daemon

# Check status
systemctl status sentinel-daemon

# Disable (prevent auto-start on boot)
systemctl disable sentinel-daemon
```
