#!/bin/sh
set -eu

python -m app.workers.postgres &
POSTGRES_PID=$!

node /app/scripts/application-browser-worker.mjs &
BROWSER_PID=$!

shutdown() {
  kill "$POSTGRES_PID" "$BROWSER_PID" 2>/dev/null || true
  wait "$POSTGRES_PID" 2>/dev/null || true
  wait "$BROWSER_PID" 2>/dev/null || true
}

trap shutdown INT TERM EXIT

while kill -0 "$POSTGRES_PID" 2>/dev/null && kill -0 "$BROWSER_PID" 2>/dev/null; do
  sleep 2
done

exit 1
