#!/usr/bin/env bash
# Sentinel Daemon — VPS Installation Script
#
# Usage:
#   From within the project directory:
#       bash deploy/install-daemon.sh
#   Or with a git repo:
#       bash deploy/install-daemon.sh https://github.com/you/sentinel.git
#
# This script:
#   1. Creates a 'sentinel' system user (no login shell)
#   2. Clones/copies the project to /opt/sentinel
#   3. Creates a Python venv and installs dependencies
#   4. Installs the systemd unit file
#   5. Enables and starts the daemon service
#   6. Verifies the service is running

set -euo pipefail

INSTALL_DIR="/opt/sentinel"
SERVICE_FILE="deploy/sentinel-daemon.service"
SYSTEMD_DIR="/etc/systemd/system"
UNIT_NAME="sentinel-daemon.service"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
log() { echo "[install] $*"; }
fail() { echo "[install] ERROR: $*" >&2; exit 1; }

require_root() {
    if [ "$(id -u)" -ne 0 ]; then
        fail "This script must be run as root (sudo)"
    fi
}

# ------------------------------------------------------------------
# Determine source
# ------------------------------------------------------------------
SOURCE="${1:-}"

if [ -z "$SOURCE" ]; then
    # Try to use the directory where this script lives
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    if [ -f "$PROJECT_DIR/pyproject.toml" ]; then
        SOURCE="$PROJECT_DIR"
        MODE="local"
    else
        fail "No pyproject.toml found. Run from the project directory or provide a git URL."
    fi
elif [[ "$SOURCE" =~ ^https?:// ]]; then
    MODE="git"
else
    SOURCE="$(realpath "$SOURCE")"
    if [ -f "$SOURCE/pyproject.toml" ]; then
        MODE="local"
    else
        fail "No pyproject.toml found at $SOURCE"
    fi
fi

# ------------------------------------------------------------------
# Pre-flight
# ------------------------------------------------------------------
require_root

for cmd in python3 systemctl; do
    command -v "$cmd" >/dev/null 2>&1 || fail "$cmd is required but not installed"
done

# ------------------------------------------------------------------
# 1. Create sentinel system user
# ------------------------------------------------------------------
if id sentinel >/dev/null 2>&1; then
    log "User 'sentinel' already exists"
else
    log "Creating system user 'sentinel'"
    useradd --system --no-create-home --shell /usr/sbin/nologin sentinel
fi

# ------------------------------------------------------------------
# 2. Install project files
# ------------------------------------------------------------------
if [ "$MODE" = "git" ]; then
    log "Cloning from $SOURCE"
    if [ -d "$INSTALL_DIR/.git" ]; then
        cd "$INSTALL_DIR"
        git fetch origin
        git reset --hard origin/main
    else
        git clone --depth 1 "$SOURCE" "$INSTALL_DIR"
    fi
else
    log "Copying from $SOURCE"
    mkdir -p "$INSTALL_DIR"
    rsync -a --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
        --exclude='*.pyc' --exclude='.claude' --exclude='node_modules' \
        "$SOURCE/" "$INSTALL_DIR/"
fi

chown -R sentinel:sentinel "$INSTALL_DIR"

# ------------------------------------------------------------------
# 2b. Create runtime directories
# ------------------------------------------------------------------
log "Creating runtime directories"
mkdir -p "$INSTALL_DIR/data"
chmod 755 "$INSTALL_DIR/data"
# Ensure home cache dir exists for yfinance caching
CACHE_DIR="/home/sentinel/.cache/trade_proj/yf_cache"
mkdir -p "$CACHE_DIR"
chown -R sentinel:sentinel "/home/sentinel/.cache"

# ------------------------------------------------------------------
# 3. Create venv and install dependencies
# ------------------------------------------------------------------
log "Setting up Python virtual environment"
if [ -d "$INSTALL_DIR/.venv" ]; then
    log "Removing old virtual environment"
    rm -rf "$INSTALL_DIR/.venv"
fi

python3 -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip >/dev/null 2>&1
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR" >/dev/null 2>&1
log "Dependencies installed"

# ------------------------------------------------------------------
# 4. Install systemd unit file
# ------------------------------------------------------------------
if [ "$MODE" = "local" ]; then
    UNIT_SRC="$SOURCE/$SERVICE_FILE"
else
    UNIT_SRC="$INSTALL_DIR/$SERVICE_FILE"
fi

if [ ! -f "$UNIT_SRC" ]; then
    fail "Service file not found: $UNIT_SRC"
fi

log "Installing systemd unit file"
cp "$UNIT_SRC" "$SYSTEMD_DIR/$UNIT_NAME"
systemctl daemon-reload

# ------------------------------------------------------------------
# 5. Enable and start
# ------------------------------------------------------------------
log "Enabling and starting $UNIT_NAME"
systemctl enable "$UNIT_NAME"
systemctl start "$UNIT_NAME"

# ------------------------------------------------------------------
# 6. Verify
# ------------------------------------------------------------------
sleep 2
if systemctl is-active --quiet "$UNIT_NAME"; then
    log "Daemon is running"
    log ""
    log "  View logs:  journalctl -u $UNIT_NAME -f"
    log "  Stop:       systemctl stop $UNIT_NAME"
    log "  Status:     systemctl status $UNIT_NAME"
else
    log "WARNING: Service failed to start. Check logs:"
    log "  journalctl -u $UNIT_NAME -n 50 --no-pager"
    exit 1
fi
