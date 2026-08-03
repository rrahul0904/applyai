# ApplyAI Multi-Source Job Platform Demo

This demo proves the job-source platform without requiring AWS, Clerk, Vercel, live ATS accounts, or public internet access.

It is not a static mockup. The demo runs the real SQLAlchemy models and registered-source ingestion pipeline against PostgreSQL, then generates an interactive HTML report and browser screenshots from the persisted result.

## What the demo executes

The deterministic scenario registers three sources for one fictional employer:

- Greenhouse with `EMPLOYER_DIRECT` trust;
- Lever with `OFFICIAL_ATS` trust;
- Ashby with `THIRD_PARTY_SOURCE` trust.

The pipeline receives seven provider records:

- six valid postings;
- one invalid Ashby-shaped record retained with validation evidence.

The six valid postings become four canonical jobs because the same Senior Data Engineer role appears in Greenhouse, Lever, and Ashby.

The demo verifies:

- source registry persistence;
- raw-record validation;
- invalid-record retention;
- canonical job creation;
- cross-source deduplication;
- primary-source authority;
- exactly seven canonical field-provenance records;
- ingestion-run metrics;
- multi-source freshness;
- a source miss that does not retire a job while other trusted sources remain fresh.

Artifact generation fails when any required assertion is false.

## Generated artifact

The workflow publishes one downloadable artifact containing:

```text
index.html
report.json
execution.txt
screenshots/
  01-platform-overview.png
  02-dedup-provenance.png
  03-execution-evidence.png
```

Open `index.html` locally to use the interactive tabs.

`report.json` contains the machine-readable source, canonical-job, provenance, lifecycle, and assertion evidence.

## Run locally

Start PostgreSQL and provide `DATABASE_URL` for a disposable database.

Example:

```bash
docker run --rm --name applyai-demo-postgres \
  -e POSTGRES_USER=applyai \
  -e POSTGRES_PASSWORD=applyai \
  -e POSTGRES_DB=applyai_demo \
  -p 55441:5432 \
  postgres:17
```

In another terminal:

```bash
export DATABASE_URL='postgresql+psycopg://applyai:applyai@127.0.0.1:55441/applyai_demo'

uv sync --project services/api --group dev --locked
cd services/api
uv run alembic upgrade head
uv run python scripts/build_job_source_demo.py \
  --output ../../artifacts/job-source-platform-demo
```

Serve the generated files from the repository root:

```bash
python -m http.server 4173 \
  --bind 127.0.0.1 \
  --directory artifacts/job-source-platform-demo
```

Open:

```text
http://127.0.0.1:4173
```

To capture the three browser screens:

```bash
pnpm install --frozen-lockfile
pnpm --dir apps/web exec playwright install chromium

DEMO_BASE_URL=http://127.0.0.1:4173 \
DEMO_SCREENSHOT_DIR="$PWD/artifacts/job-source-platform-demo/screenshots" \
pnpm --dir apps/web exec node scripts/capture-job-source-demo.mjs
```

## Automated validation

Focused regression test:

```text
services/api/tests/test_job_source_demo.py
```

The normal `ApplyAI CI` backend suite runs this regression with `autoflush=False`, matching the production `SessionLocal` behavior. It verifies the exact totals, primary source, active lifecycle, seven provenance fields, generated HTML, and account-free scope.

Artifact workflow:

```text
.github/workflows/job-source-platform-demo.yml
```

The artifact workflow:

1. creates a fresh PostgreSQL 17 service;
2. migrates from zero to Alembic head and checks migration drift;
3. builds the real database-backed report once on the clean schema;
4. records the source SHA, workflow run, PostgreSQL image, and generation time;
5. serves the generated artifact locally;
6. captures three Playwright screenshots;
7. verifies all required files and machine-readable evidence assertions;
8. uploads the complete artifact for 14 days.

Keeping the regression and artifact databases separate prevents test state from influencing the published demonstration.

## Explicit boundaries

Executed:

- real PostgreSQL;
- real migrations;
- real source registry;
- real validation and canonical ingestion;
- real deduplication, authority, provenance, and freshness logic;
- real Playwright rendering.

Not executed:

- live Greenhouse, Lever, or Ashby requests;
- AWS provisioning;
- Clerk or Vercel integration;
- external anti-bot or authenticated pages;
- job applications.

These external activities are intentionally outside this demo. The purpose is to prove the platform logic and presentation using a deterministic, repeatable, account-free environment.
