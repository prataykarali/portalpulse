#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORTALPULSE_DEMO_PORT:-8000}"
if [[ ! "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1024 || PORT > 65535 )); then
  echo "Invalid PORTALPULSE_DEMO_PORT: $PORT" >&2; exit 2
fi
PYTHON="${PORTALPULSE_PYTHON:-.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then echo "Python environment missing: $PYTHON. Create .venv and install requirements.txt" >&2; exit 2; fi
if ! "$PYTHON" -c 'import fastapi, uvicorn, torch, xgboost, sklearn, networkx, httpx' 2>/dev/null; then
  echo "Missing Python dependencies. Run: $PYTHON -m pip install -r requirements.txt" >&2; exit 2
fi
if "$PYTHON" - "$PORT" <<'PY'
import socket,sys
s=socket.socket()
s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
try: s.bind(('127.0.0.1',int(sys.argv[1])))
except OSError: sys.exit(1)
finally: s.close()
PY
then :; else echo "Port $PORT is already in use. Set PORTALPULSE_DEMO_PORT to a free port." >&2; exit 2; fi
export PORTALPULSE_DEMO_MODE=1
export PORTALPULSE_DEMO_THERMAL_GUARD=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export PORT="$PORT"
export PORTALPULSE_API_URL="${PORTALPULSE_API_URL:-http://127.0.0.1:${PORT}}"
export NIRANTAR_DEMO_URL="${NIRANTAR_DEMO_URL:-https://bronze-tinsel-n8pb.here.now/}"
"$PYTHON" -m uvicorn backend.app:app --host 127.0.0.1 --port "$PORT" > /tmp/portalpulse_demo_${PORT}.log 2>&1 &
PID=$!
cleanup(){ kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
READY=0
for _ in {1..60}; do
  if ! kill -0 "$PID" 2>/dev/null; then echo "Backend exited; log: /tmp/portalpulse_demo_${PORT}.log" >&2; tail -25 "/tmp/portalpulse_demo_${PORT}.log" >&2; exit 1; fi
  if "$PYTHON" - "$PORT" <<'PY'
import sys,urllib.request
base=f'http://127.0.0.1:{sys.argv[1]}'
try:
  for path in ('/website','/api/v1/live-demo/snapshot','/api/v1/stream/status'):
    with urllib.request.urlopen(base+path,timeout=2) as response:
      if response.status!=200: raise RuntimeError(path)
except Exception: sys.exit(1)
PY
  then READY=1; break; fi
  sleep 1
done
if (( READY == 0 )); then echo "Readiness failed; log: /tmp/portalpulse_demo_${PORT}.log" >&2; exit 1; fi
echo "PortalPulse website: http://127.0.0.1:${PORT}/website"
echo "FastAPI backend: http://127.0.0.1:${PORT}/docs"
echo "Nirantar example: http://127.0.0.1:${PORT}/website#guide"
echo "Log: /tmp/portalpulse_demo_${PORT}.log"
wait "$PID"
