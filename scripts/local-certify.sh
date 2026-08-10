#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p .local

PIDS=()
cleanup() {
  local exit_code=$?
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
  wait >/dev/null 2>&1 || true
  if [[ "${KEEP_LOCAL_CERT_ENV:-0}" != "1" ]]; then
    docker compose stop postgres localstack mailpit stripe-mock >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: required command '$1' is not installed" >&2; exit 1; }
}

require docker
require node
require pnpm
require python3
require uv
require curl

docker info >/dev/null 2>&1 || { echo "ERROR: Docker daemon is not running" >&2; exit 1; }

NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if (( NODE_MAJOR < 22 )); then echo "ERROR: Node.js 22+ is required" >&2; exit 1; fi
if [[ "$PY_VERSION" != "3.12" && "$PY_VERSION" != "3.13" && "$PY_VERSION" != "3.14" ]]; then
  echo "ERROR: Python 3.12+ is required" >&2; exit 1
fi

echo "==> Installing locked dependencies"
pnpm install --frozen-lockfile
uv sync --project services/api --group dev --locked

echo "==> Starting PostgreSQL, LocalStack, Mailpit and Stripe schema mock"
docker compose up -d --wait postgres localstack mailpit
docker compose up -d stripe-mock

for _ in $(seq 1 40); do
  if curl -fsS http://127.0.0.1:12111/v1/charges -H 'Authorization: Bearer sk_test_local' >/dev/null 2>&1; then break; fi
  sleep 0.5
done
curl -fsS http://127.0.0.1:12111/v1/charges -H 'Authorization: Bearer sk_test_local' >/dev/null

reset_database() {
  docker compose exec -T postgres psql -U applyai -d postgres -v ON_ERROR_STOP=1 <<'SQL'
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'applyai_cleanroom' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS applyai_cleanroom;
CREATE DATABASE applyai_cleanroom OWNER applyai;
SQL
}

CLEAN_DATABASE_URL="postgresql+psycopg://applyai:applyai@127.0.0.1:55432/applyai_cleanroom"
export E2E_RESUME_PATH="${E2E_RESUME_PATH:-/tmp/applyai-cleanroom-resume.docx}"

reset_database

echo "==> Bootstrapping production-shaped local S3/SQS resources"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
  uv run --project services/api python services/api/scripts/bootstrap_local_services.py

# Repository tests must run in their normal deterministic test configuration. Do not source
# LocalStack/dev-auth/Stripe settings until those tests are complete; otherwise their explicit
# fail-closed configuration tests would be contaminated by clean-room runtime environment values.
echo "==> Validating migrations and API tests from a clean database"
(
  cd services/api
  export DATABASE_URL="$CLEAN_DATABASE_URL"
  export TEST_DATABASE_URL="$CLEAN_DATABASE_URL"
  export E2E_DATABASE_URL="$CLEAN_DATABASE_URL"
  uv run alembic upgrade head
  uv run alembic current
  uv run alembic check
  uv run pytest
)

echo "==> Validating web source"
pnpm lint
pnpm --dir apps/web typecheck
pnpm test:web
pnpm build
pnpm openapi:check

# Repository tests exercise rollback/reset behavior. Recreate the application database before
# switching to production-shaped local service providers and deterministic application data.
reset_database
# shellcheck disable=SC1091
source .local/runtime.env
export LOCAL_CLEANROOM=1
export LOCAL_PROVIDER_MOCK_URL="http://127.0.0.1:8099"

echo "==> Starting local Clerk/JWKS, OpenAI and Stripe behavioral protocol mock"
(cd services/api && uv run python -m scripts.local_provider_mock >"$ROOT/.local/provider-mock.log" 2>&1) & PIDS+=("$!")
for _ in $(seq 1 40); do
  if curl -fsS "$LOCAL_PROVIDER_MOCK_URL/health" >/dev/null 2>&1; then break; fi
  sleep 0.25
done
curl -fsS "$LOCAL_PROVIDER_MOCK_URL/health" >/dev/null

(
  cd services/api
  uv run alembic upgrade head
  uv run alembic check
  uv run python -m app.jobs.seed
  uv run python scripts/create_e2e_resume.py "$E2E_RESUME_PATH"
  uv run python -m scripts.local_integration_smoke
)

echo "==> Running deterministic governed-agent workflow and acceptance"
(
  cd services/api
  AI_PROVIDER=deterministic TASK_QUEUE_PROVIDER=memory uv run python -m scripts.agent_demo
  AI_PROVIDER=deterministic TASK_QUEUE_PROVIDER=memory uv run python -m scripts.agent_acceptance
)

echo "==> Launching local outbox and background workers"
(cd services/api && uv run python -m app.core.outbox >"$ROOT/.local/outbox.log" 2>&1) & PIDS+=("$!")
(cd services/api && uv run python -m app.workers.resume >"$ROOT/.local/resume-worker.log" 2>&1) & PIDS+=("$!")
(cd services/api && uv run python -m app.workers.source >"$ROOT/.local/source-worker.log" 2>&1) & PIDS+=("$!")
(cd services/api && uv run python -m app.workers.ai >"$ROOT/.local/ai-worker.log" 2>&1) & PIDS+=("$!")
(cd services/api && uv run python -m app.workers.agent >"$ROOT/.local/agent-worker.log" 2>&1) & PIDS+=("$!")
sleep 2
for pid in "${PIDS[@]}"; do
  kill -0 "$pid" >/dev/null 2>&1 || { echo "ERROR: a local provider/worker process failed to start; inspect .local/*.log" >&2; exit 1; }
done

echo "==> Installing Chromium for browser acceptance"
if [[ "${CI:-}" == "true" ]]; then
  pnpm --dir apps/web exec playwright install --with-deps chromium
else
  pnpm --dir apps/web exec playwright install chromium
fi

echo "==> Running browser -> Next.js -> FastAPI -> PostgreSQL -> LocalStack clean-room journey"
pnpm --dir apps/web exec playwright test --config=playwright.cleanroom.config.ts

echo "==> Checking local provider/worker health after browser execution"
for pid in "${PIDS[@]}"; do
  kill -0 "$pid" >/dev/null 2>&1 || { echo "ERROR: a local provider/worker process exited during certification; inspect .local/*.log" >&2; exit 1; }
done

echo
printf '%s\n' \
  "PASS ApplyAI local clean-room certification" \
  "  - fresh locked dependency install" \
  "  - clean PostgreSQL database + Alembic zero-to-head/drift" \
  "  - API/web/OpenAPI validation in isolated test configuration" \
  "  - LocalStack S3 direct/presigned object operations" \
  "  - LocalStack SQS + outbox + background workers" \
  "  - governed Agent Runtime + dedicated agent SQS/DLQ + Agent Worker" \
  "  - deterministic Scout -> Research -> Resume -> Verifier workflow" \
  "  - Mailpit SMTP delivery" \
  "  - Stripe schema mock health plus checkout/portal protocol + signed webhook persistence" \
  "  - deterministic local AI provider" \
  "  - Clerk RS256 JWT/JWKS protocol through the real ClerkAuthProvider" \
  "  - OpenAI Responses + embeddings HTTP protocol through the real provider clients" \
  "  - dev-test local browser authentication" \
  "  - canonical browser workflows and route sweep" \
  "Live Clerk/OpenAI/Stripe/AWS/email-provider/agent staging accounts remain a separate credential-backed acceptance gate."
