#!/usr/bin/env bash
# Start (or stop) the local dev stack: Redis (docker) + FastAPI backend + Vite frontend.
#
# Usage:
#   ./scripts/run-dev.sh         # first-run setup + start all services
#   ./scripts/run-dev.sh stop    # stop the dev servers (Redis container stays up)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
VENV="$BACKEND_DIR/.venv"
BACKEND_PORT=8001
FRONTEND_PORT=5173
REDIS_PORT=6379
REDIS_CONTAINER=teacher-workbench-redis
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

wait_for_port() {
  local port="$1" attempts="${2:-50}" i
  for ((i = 0; i < attempts; i++)); do
    if (: <"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
      return 0
    fi
    sleep 0.3
  done
  return 1
}

ensure_redis() {
  # Verification codes (forgot password) are stored in Redis; the backend
  # defaults to redis://127.0.0.1:6379/0, which the compose file publishes.
  if [[ -n "$(port_pids "$REDIS_PORT")" ]]; then
    echo "==> Redis already running on port $REDIS_PORT"
    return 0
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "WARNING: Docker is not running — forgot-password will return 503." >&2
    echo "         Start Docker Desktop, then: docker compose up -d redis" >&2
    return 0
  fi
  echo "==> Starting Redis (docker container $REDIS_CONTAINER)"
  if docker container inspect "$REDIS_CONTAINER" >/dev/null 2>&1; then
    docker start "$REDIS_CONTAINER" >/dev/null ||
      { echo "WARNING: failed to start $REDIS_CONTAINER — forgot-password will return 503." >&2; return 0; }
  else
    docker compose -f "$ROOT/docker-compose.yml" up -d redis ||
      { echo "WARNING: docker compose failed to start redis — forgot-password will return 503." >&2; return 0; }
  fi
  if ! wait_for_port "$REDIS_PORT"; then
    echo "WARNING: Redis not ready on port $REDIS_PORT after 15s — forgot-password may return 503." >&2
  fi
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
  if [[ "$(docker container inspect -f '{{.State.Running}}' "$REDIS_CONTAINER" 2>/dev/null)" == "true" ]]; then
    echo "Redis container $REDIS_CONTAINER is still running (stop it with: docker stop $REDIS_CONTAINER)."
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
    ensure_redis
    echo "Run ./scripts/run-dev.sh stop first, or open http://localhost:$FRONTEND_PORT/gao/" >&2
    exit 1
  fi

  ensure_backend
  ensure_frontend
  ensure_redis

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
  echo "  Redis     redis://127.0.0.1:$REDIS_PORT (docker: $REDIS_CONTAINER)"
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
    sed -n '2,6p' "$0" | sed 's/^# //'
    ;;
  *)
    echo "Unknown command: $1 (try: start, stop)" >&2
    exit 1
    ;;
esac
