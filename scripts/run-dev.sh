#!/usr/bin/env bash
# Start (or stop) the local dev stack: FastAPI backend + Vite frontend.
#
# Usage:
#   ./scripts/run-dev.sh         # first-run setup + start both servers
#   ./scripts/run-dev.sh stop    # stop anything listening on the dev ports
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV="$BACKEND_DIR/.venv"
BACKEND_PORT=8001
FRONTEND_PORT=5173
DB_FILE="$BACKEND_DIR/teacher_workbench.db"
FRESH_DB=0

port_pids() {
  local port="$1"
  { lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true; } | tr '\n' ' '
}

free_port() {
  local port="$1"
  local pids attempt
  pids="$(port_pids "$port")"
  [[ -z "${pids// }" ]] && return 0
  echo "Stopping process(es) on port $port: $pids"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  for attempt in 1 2 3 4 5; do
    sleep 0.4
    pids="$(port_pids "$port")"
    [[ -z "${pids// }" ]] && return 0
  done
  echo "Force-killing process(es) on port $port: $pids"
  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
}

stop_dev() {
  local had=0
  for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    if [[ -n "$(port_pids "$port")" ]]; then
      had=1
      free_port "$port"
    fi
  done
  if [[ "$had" -eq 0 ]]; then
    echo "No dev servers running on ports $BACKEND_PORT / $FRONTEND_PORT."
  else
    echo "Stopped."
  fi
}

ensure_backend() {
  if [[ ! -d "$VENV" ]]; then
    echo "==> Creating Python venv"
    python3 -m venv "$VENV"
  fi
  if [[ ! -f "$VENV/bin/uvicorn" ]]; then
    echo "==> Installing backend dependencies"
    "$VENV/bin/pip" install -r "$BACKEND_DIR/requirements.txt"
  fi
  if [[ ! -f "$DB_FILE" ]]; then
    echo "==> Seeding demo database"
    (cd "$BACKEND_DIR" && "$VENV/bin/python" -m app.seed)
    FRESH_DB=1
  fi
}

ensure_frontend() {
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "==> Installing frontend dependencies"
    (cd "$FRONTEND_DIR" && npm install)
  fi
}

start_dev() {
  local backend_pids frontend_pids
  backend_pids="$(port_pids "$BACKEND_PORT")"
  frontend_pids="$(port_pids "$FRONTEND_PORT")"
  if [[ -n "${backend_pids// }" || -n "${frontend_pids// }" ]]; then
    echo "Dev servers already running (ports $BACKEND_PORT / $FRONTEND_PORT)." >&2
    echo "Run ./scripts/run-dev.sh stop first, or open http://localhost:$FRONTEND_PORT/gao/" >&2
    exit 1
  fi

  ensure_backend
  ensure_frontend

  echo "==> Starting backend on http://127.0.0.1:$BACKEND_PORT (docs: /docs)"
  (cd "$BACKEND_DIR" && "$VENV/bin/uvicorn" app.main:app --port "$BACKEND_PORT" --reload) &
  BACKEND_PID=$!

  echo "==> Starting frontend on http://localhost:$FRONTEND_PORT/gao/"
  (cd "$FRONTEND_DIR" && npm run dev -- --port "$FRONTEND_PORT") &
  FRONTEND_PID=$!

  cleanup() {
    echo
    echo "Shutting down dev servers…"
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  }
  trap cleanup INT TERM EXIT

  echo
  echo "App ready:"
  echo "  Frontend  http://localhost:$FRONTEND_PORT/gao/"
  echo "  Backend   http://127.0.0.1:$BACKEND_PORT"
  echo "  API docs  http://127.0.0.1:$BACKEND_PORT/docs"
  echo
  if [[ "$FRESH_DB" -eq 1 ]]; then
    echo "Demo login:  chen@school.edu / 123456"
    echo "Admin login: admin@school.dev / admin123  → hidden /admin dashboard"
  else
    echo "Login with your own account (demo credentials only exist on a freshly seeded database)."
  fi
  echo "Press Ctrl+C to stop both servers."
  echo

  wait "$BACKEND_PID" "$FRONTEND_PID"
}

case "${1:-start}" in
  start) start_dev ;;
  stop) stop_dev ;;
  -h|--help)
    sed -n '2,5p' "$0" | sed 's/^# //'
    ;;
  *)
    echo "Unknown command: $1 (try: start, stop)" >&2
    exit 1
    ;;
esac
