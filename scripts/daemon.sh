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
