#!/usr/bin/env bash
set -Eeuo pipefail

# ApplyAI lean-production Railway bootstrap.
# This script intentionally performs no login and stores no token. Authenticate with
# `railway login` locally or set RAILWAY_API_TOKEN in a trusted operator/CI environment.

PROJECT_NAME="${APPLYAI_RAILWAY_PROJECT_NAME:-applyai}"
WORKSPACE="${APPLYAI_RAILWAY_WORKSPACE:-}"
REPO="${APPLYAI_RAILWAY_REPO:-rrahul0904/applyai}"
BRANCH="${APPLYAI_RAILWAY_BRANCH:-main}"

command -v railway >/dev/null 2>&1 || {
  echo "ERROR: Railway CLI is required. Install the current CLI from https://docs.railway.com/cli" >&2
  exit 1
}

if [[ -z "${RAILWAY_API_TOKEN:-${RAILWAY_TOKEN:-}}" ]]; then
  railway whoami >/dev/null 2>&1 || {
    echo "ERROR: authenticate with 'railway login' or provide RAILWAY_API_TOKEN/RAILWAY_TOKEN." >&2
    exit 1
  }
fi

if railway status >/dev/null 2>&1; then
  echo "Using already-linked Railway project:"
  railway status
else
  args=(init --name "$PROJECT_NAME")
  if [[ -n "$WORKSPACE" ]]; then
    args+=(--workspace "$WORKSPACE")
  fi
  railway "${args[@]}"
fi

service_exists() {
  railway service list --json 2>/dev/null | python3 -c '
import json, sys
name=sys.argv[1]
data=json.load(sys.stdin)
items=data if isinstance(data, list) else data.get("services", data.get("items", []))
raise SystemExit(0 if any(str(item.get("name")) == name for item in items if isinstance(item, dict)) else 1)
' "$1"
}

ensure_service() {
  local name="$1"
  if service_exists "$name"; then
    echo "Service '$name' already exists"
  else
    railway add --service "$name"
  fi
}

if ! service_exists "Postgres" && ! service_exists "postgres"; then
  echo "Adding Railway PostgreSQL"
  railway add --database postgres
else
  echo "PostgreSQL service already exists"
fi

for service in applyai-api applyai-worker applyai-browser-worker; do
  ensure_service "$service"
  railway service source connect --repo "$REPO" --branch "$BRANCH" --service "$service"
  railway environment edit --service-config "$service" source.rootDirectory /services/api
  railway environment edit --service-config "$service" build.watchPatterns '["/services/api/**"]'
done

railway environment edit --service-config applyai-api deploy.healthcheckPath /ready
railway environment edit --service-config applyai-api deploy.healthcheckTimeout 300
railway environment edit --service-config applyai-api deploy.restartPolicyType ALWAYS
railway environment edit --service-config applyai-worker deploy.startCommand 'python -m app.workers.postgres'
railway environment edit --service-config applyai-worker deploy.restartPolicyType ALWAYS

# Browser execution is intentionally isolated. The repository does not claim this service is
# production-ready until its browser image/runtime acceptance has passed; keep it at zero/paused
# if the browser executor is not enabled for the launch.
railway environment edit --service-config applyai-browser-worker deploy.restartPolicyType ON_FAILURE

echo
echo "Railway project skeleton is ready."
echo "Next operator steps:"
echo "  1. Set DATABASE_URL on API/worker using a private Postgres service reference."
echo "  2. Set Clerk and R2 secrets described in docs/RAILWAY_DEPLOYMENT.md."
echo "  3. Configure API pre-deploy command: alembic upgrade head."
echo "  4. Generate a public domain only for applyai-api."
echo "  5. Deploy API and worker, then verify /health and /ready."
echo "  6. Run pnpm job-supply:initial-acceptance after bounded Open Jobs ingestion."
