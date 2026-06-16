#!/usr/bin/env bash
# Sentinel Daemon — Update/Redeploy Script
#
# Run this on the VPS after pulling new code, or via CI/CD:
#
#   bash deploy/update-daemon.sh
#
# This script:
#   1. Reinstalls Python dependencies (handles new deps)
#   2. Restarts the daemon service
#   3. Verifies the service came back healthy

set -euo pipefail

INSTALL_DIR="/opt/sentinel"
UNIT_NAME="sentinel-daemon.service"

log() { echo "[update] $*"; }
fail() { echo "[update] ERROR: $*" >&2; exit 1; }

# Run under sudo if not already root
if [ "$(id -u)" -ne 0 ]; then
    exec sudo bash "$0" "$@"
fi

# Check that the install exists
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    fail "No daemon installation found at $INSTALL_DIR. Run deploy/install-daemon.sh first."
fi

# ------------------------------------------------------------------
# 1. Reinstall dependencies
# ------------------------------------------------------------------
log "Reinstalling dependencies"
"$INSTALL_DIR/.venv/bin/pip" install --upgrade pip >/dev/null 2>&1
"$INSTALL_DIR/.venv/bin/pip" install -e "$INSTALL_DIR" >/dev/null 2>&1

# ------------------------------------------------------------------
# 2. Restart daemon
# ------------------------------------------------------------------
log "Restarting $UNIT_NAME"
systemctl restart "$UNIT_NAME"

# ------------------------------------------------------------------
# 3. Verify
# ------------------------------------------------------------------
sleep 2
if systemctl is-active --quiet "$UNIT_NAME"; then
    log "Daemon restarted successfully"
    log ""
    log "  View logs:  journalctl -u $UNIT_NAME -f --since '2 min ago'"
else
    log "WARNING: Service failed to restart. Check logs:"
    log "  journalctl -u $UNIT_NAME -n 50 --no-pager"
    exit 1
fi
