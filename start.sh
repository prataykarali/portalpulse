#!/usr/bin/env bash
set -e

PORT="${PORT:-8000}"
HOST="0.0.0.0"

echo "[PortalPulse] Starting Production Control Plane API on ${HOST}:${PORT}..."
exec uvicorn backend.app:app --host "${HOST}" --port "${PORT}" --workers 1 --log-level info
