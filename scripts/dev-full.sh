#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p .local

PIDS=()
cleanup() {
  local code=$?
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
  wait >/dev/null 2>&1 || true
  if [[ "${KEEP_DEV_INFRA:-0}" != "1" ]]; then
    docker compose stop postgres localstack mailpit stripe-mock >/dev/null 2>&1 || true
  fi
  exit "$code"
}
trap cleanup EXIT INT TERM

for command in docker node pnpm python3 uv curl; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "ERROR: required command '$command' is not installed" >&2
    exit 1
  }
done

docker info >/dev/null 2>&1 || {
  echo "ERROR: Docker daemon is not running" >&2
  exit 1
}

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  echo "==> Installing locked dependencies"
  pnpm install --frozen-lockfile
  uv sync --project services/api --group dev --locked
fi

echo "==> Starting local infrastructure"
docker compose up -d --wait postgres localstack mailpit
docker compose up -d stripe-mock

echo "==> Bootstrapping local S3/SQS runtime"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
  uv run --project services/api python services/api/scripts/bootstrap_local_services.py

# shellcheck disable=SC1091
source .local/runtime.env
export LOCAL_CLEANROOM=1
export LOCAL_PROVIDER_MOCK_URL="${LOCAL_PROVIDER_MOCK_URL:-http://127.0.0.1:8099}"
export APP_ENV="${APP_ENV:-test}"
export ENVIRONMENT="${ENVIRONMENT:-test}"
export DEV_AUTH_ENABLED="${DEV_AUTH_ENABLED:-true}"
export DEV_AUTH_SECRET="${DEV_AUTH_SECRET:-applyai-local-development-secret-2026}"
export APPLYAI_API_URL="${APPLYAI_API_URL:-http://127.0.0.1:8000}"

echo "==> Migrating and seeding deterministic local data"
(
  cd services/api
  uv run alembic upgrade head
  uv run python -m app.jobs.seed
)

start_process() {
  local name="$1"
  shift
  echo "==> Starting $name"
  "$@" >".local/$name.log" 2>&1 &
  PIDS+=("$!")
}

start_process provider-mock bash -lc "cd services/api && uv run python -m scripts.local_provider_mock"
for _ in $(seq 1 60); do
  curl -fsS "$LOCAL_PROVIDER_MOCK_URL/health" >/dev/null 2>&1 && break
  sleep 0.25
done
curl -fsS "$LOCAL_PROVIDER_MOCK_URL/health" >/dev/null

start_process outbox bash -lc "cd services/api && uv run python -m app.core.outbox"
start_process resume-worker bash -lc "cd services/api && uv run python -m app.workers.resume"
start_process source-worker bash -lc "cd services/api && uv run python -m app.workers.source"
start_process ai-worker bash -lc "cd services/api && uv run python -m app.workers.ai"
start_process agent-worker bash -lc "cd services/api && uv run python -m app.workers.agent"
start_process api bash -lc "cd services/api && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000"
start_process web bash -lc "cd apps/web && APP_ENV='$APP_ENV' DEV_AUTH_ENABLED='$DEV_AUTH_ENABLED' DEV_AUTH_SECRET='$DEV_AUTH_SECRET' APPLYAI_API_URL='$APPLYAI_API_URL' pnpm dev --hostname 127.0.0.1 --port 3000"

for _ in $(seq 1 120); do
  if curl -fsS http://127.0.0.1:8000/ready >/dev/null 2>&1 \
     && curl -fsS http://127.0.0.1:3000/dev-login >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

curl -fsS http://127.0.0.1:8000/ready >/dev/null
curl -fsS http://127.0.0.1:3000/dev-login >/dev/null

for pid in "${PIDS[@]}"; do
  kill -0 "$pid" >/dev/null 2>&1 || {
    echo "ERROR: a local ApplyAI process failed to start; inspect .local/*.log" >&2
    exit 1
  }
done

cat <<'EOF'

ApplyAI full local environment is running:
  Web:      http://127.0.0.1:3000
  API:      http://127.0.0.1:8000
  Mailpit:  http://127.0.0.1:8025

Vercel deployment is not involved.

Press Ctrl-C to stop the local processes.
Set KEEP_DEV_INFRA=1 to leave Docker infrastructure running after exit.
EOF

wait -n "${PIDS[@]}"
echo "ERROR: an ApplyAI process exited unexpectedly; inspect .local/*.log" >&2
exit 1
