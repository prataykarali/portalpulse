#!/usr/bin/env bash
# PortalPulse Daemon Management Helper Script

ACTION=${1:-status}

case "$ACTION" in
  start)
    systemctl --user start portalpulse.service
    echo "PortalPulse daemon started."
    ;;
  stop)
    systemctl --user stop portalpulse.service
    echo "PortalPulse daemon stopped."
    ;;
  restart)
    systemctl --user restart portalpulse.service
    echo "PortalPulse daemon restarted."
    ;;
  status)
    systemctl --user status portalpulse.service
    ;;
  logs)
    journalctl --user -u portalpulse.service -f
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}"
    exit 1
    ;;
esac
