# ApplyAI Railway Deployment

Updated: 2026-08-31

## Purpose

Railway is the launch runtime for ApplyAI's lean production profile. AWS remains an optional scale profile and is not required for this deployment.

Target Railway project:

```text
applyai
├── Postgres
├── applyai-api
├── applyai-worker
└── applyai-browser-worker
```

The API and normal worker use `services/api`. The browser worker remains isolated because Chromium has different runtime and memory requirements and should stay disabled until browser-runtime acceptance is explicitly green.

## Bootstrap

The repository includes:

```bash
scripts/railway-bootstrap.sh
```

The script intentionally does not perform authentication or persist provider tokens. Authenticate with the current Railway CLI or provide a Railway API token in a trusted operator environment, then run the script from the repository root.

It creates or reuses the dedicated `applyai` project, adds PostgreSQL, creates the three service shells, connects them to `rrahul0904/applyai`, configures `/ready` for the API health check, and sets the Postgres worker command.

Do not use a Railway project shared with another product.

## API runtime

Production API command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The image is built from:

```text
services/api/Dockerfile
```

Verify:

```text
GET /health -> process alive
GET /ready  -> PostgreSQL reachable
```

`/ready` must fail when PostgreSQL is unavailable.

## Required API environment

Secrets below are examples of variable names only. Never commit their values.

```text
APP_ENV=production
DEPLOYMENT_PROFILE=lean
AUTH_PROVIDER=clerk
TASK_QUEUE_PROVIDER=postgres
OBJECT_STORAGE_PROVIDER=s3
DATABASE_URL=${{Postgres.DATABASE_URL}}
WEB_ORIGIN=https://<applyai-vercel-production-host>

CLERK_ISSUER=https://<clerk-instance>
CLERK_JWKS_URL=https://<clerk-instance>/.well-known/jwks.json
CLERK_AUDIENCE=<only when configured by the Clerk app>

S3_ENDPOINT_URL=https://<cloudflare-account-id>.r2.cloudflarestorage.com
S3_BUCKET=applyai-resumes
S3_REGION=auto
S3_ACCESS_KEY_ID=<secret>
S3_SECRET_ACCESS_KEY=<secret>
S3_SERVER_SIDE_ENCRYPTION=none

INTERNAL_API_TOKEN=<high-entropy secret when required by operator/internal routes>
AI_PROVIDER=deterministic
```

When OpenAI production generation is enabled, add `OPENAI_API_KEY` and set `AI_PROVIDER=openai`. Core authentication, résumé review, deterministic job matching, and job discovery must not depend on the AI provider being healthy.

## Database migration

Before promoting an API release, run against the real production database:

```bash
cd services/api
alembic upgrade head
alembic current
alembic check
```

Required result:

```text
upgrade: PASS
current: repository Alembic head
drift: zero
```

Do not create production application tables manually.

## Normal worker

Start command:

```bash
python -m app.workers.postgres
```

The worker publishes committed `TaskOutbox` rows into `postgres_tasks` and claims work with PostgreSQL row locking and `SKIP LOCKED`.

Supported task families are explicit:

```text
RESUME_PARSE
SOURCE_DISCOVERY
SOURCE_INGEST
SOURCE_VERIFY
AI_DEEP_MATCH
AI_RESUME_TAILOR
AI_APPLICATION_COPILOT
AI_INTERVIEW_PREP
AGENT_RUN
```

Unknown Postgres task types fail closed and must never silently route to the résumé processor.

## Queue safety

Production validation must cover:

- multiple workers claiming distinct rows;
- idempotent task materialization;
- lease ownership and expiry;
- heartbeat/lease extension;
- retry with bounded exponential backoff;
- `RETRY_WAIT`;
- `DEAD` after max attempts;
- cancellation;
- expired-lease recovery;
- visible error details.

No SQS configuration is required when `DEPLOYMENT_PROFILE=lean` and `TASK_QUEUE_PROVIDER=postgres`.

## Browser worker

Keep `applyai-browser-worker` separate. Enable it only when its image contains the required Playwright/Chromium runtime and the production safety gate is green.

The executor must stop for CAPTCHA, authentication challenges, anti-bot challenges, unknown required questions, sensitive required questions, unsupported file requirements, and unexpected employer workflows. It must not implement bypass behavior.

## Production activation order

1. Create the Railway `applyai` project and PostgreSQL service.
2. Configure API/worker private environment variables.
3. Run Alembic zero-to-head migration and drift check.
4. Deploy `applyai-api`.
5. Verify `/health` and `/ready`.
6. Deploy `applyai-worker`.
7. Register Open Jobs with `python -m scripts.register_public_job_sources --open-jobs`.
8. Execute a bounded Open Jobs source run.
9. Run `pnpm job-supply:initial-acceptance` against the real database.
10. Only then point the Vercel Preview at the Railway API.

## Current external gate

Repository source and validation are prepared, but this environment does not currently expose an authorized Railway connection or Railway API token. A live Railway project, database URL, deployment ID, or API URL must therefore not be reported until provider authentication is supplied and the steps above actually pass.
