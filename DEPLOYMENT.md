# ApplyAI Deployment

Updated: 2026-08-31

## Canonical launch profile

ApplyAI's first production deployment uses:

```text
Vercel / Next.js
  -> Clerk
  -> Railway / FastAPI
       -> Railway PostgreSQL
       -> Cloudflare R2
       -> TaskOutbox -> postgres_tasks -> Railway worker
```

Set:

```text
APP_ENV=production
DEPLOYMENT_PROFILE=lean
TASK_QUEUE_PROVIDER=postgres
AUTH_PROVIDER=clerk
OBJECT_STORAGE_PROVIDER=s3
```

AWS is not required to launch. The existing AWS Terraform/ECS/Aurora/SQS/S3 stack remains an optional `DEPLOYMENT_PROFILE=aws` scale profile and must continue passing repository validation.

## Release source

Current releases must come from a green `main` SHA. Preview acceptance happens on the Lean Production PR before merge. Do not deploy Production from a feature-branch SHA and do not treat a Vercel Preview as production evidence.

## 1. Railway

Create a dedicated Railway project named `applyai` containing:

```text
Postgres
applyai-api
applyai-worker
applyai-browser-worker
```

Use `scripts/railway-bootstrap.sh` after authenticating the Railway CLI/provider.

The browser worker can remain disabled for initial launch unless browser-automation acceptance is green; core candidate functionality does not depend on automatic third-party application submission.

See [`docs/RAILWAY_DEPLOYMENT.md`](docs/RAILWAY_DEPLOYMENT.md).

## 2. PostgreSQL

Use exactly one canonical production database.

Railway's `postgresql://...` `DATABASE_URL` is normalized internally to the installed psycopg SQLAlchemy dialect. Legacy split DB variables remain for the optional AWS profile.

Run before deployment:

```bash
cd services/api
alembic upgrade head
alembic current
alembic check
```

Required result:

```text
upgrade PASS
current = repository Alembic head
drift = zero
```

## 3. PostgreSQL durable worker

Lean production uses the transactional outbox plus `postgres_tasks` rather than SQS.

Worker command:

```bash
python -m app.workers.postgres
```

Production task handling includes résumé processing, source ingestion, AI generation and agent runtime. Unknown Postgres task types fail closed.

Verify queue lease/retry/dead/cancel/recovery behavior before launch.

## 4. Cloudflare R2

Create a private bucket:

```text
applyai-resumes
```

Railway API/worker configuration:

```text
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_BUCKET=applyai-resumes
S3_REGION=auto
S3_ACCESS_KEY_ID=<secret>
S3_SECRET_ACCESS_KEY=<secret>
S3_SERVER_SIDE_ENCRYPTION=none
```

Never expose R2 credentials or permanent private-object URLs to the browser.

Run the real R2 acceptance before Preview promotion. See [`docs/R2_STORAGE.md`](docs/R2_STORAGE.md).

## 5. Clerk

Clerk is the sole production identity provider.

Configure the frontend and backend against the same Clerk instance:

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
CLERK_SECRET_KEY
CLERK_ISSUER
CLERK_JWKS_URL
CLERK_AUDIENCE   # only when applicable
```

Verify a real signup, backend JWT validation, logout/login persistence and cross-user isolation.

Do not enable development authentication in Production.

## 6. Railway API

Production command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Verify:

```text
GET /health
GET /ready
```

`/ready` must verify PostgreSQL connectivity.

Configure `WEB_ORIGIN` to the real Vercel origin. Do not use wildcard authenticated CORS.

## 7. Real jobs

After API/database/worker health is green:

```bash
cd services/api
python -m scripts.register_public_job_sources --open-jobs
```

Run a bounded 1–5 Open Jobs groups first. Inspect real canonical rows and measured source-run counts before increasing to 25/100 groups.

Run:

```bash
pnpm job-supply:initial-acceptance
```

Target at least 100 real canonical jobs if the safe ramp reaches that count without material failures. Do not weaken the mature `pnpm job-supply:acceptance` gate.

## 8. Vercel Preview

Dedicated project:

```text
name: applyai
team: rrahul0904-5013s-projects
root: apps/web
repository: rrahul0904/applyai
```

Required workflow secrets:

```text
VERCEL_TOKEN
APPLYAI_VERCEL_API_URL
APPLYAI_VERCEL_CLERK_PUBLISHABLE_KEY
APPLYAI_VERCEL_CLERK_SECRET_KEY
```

The API URL must be the real Railway HTTPS API.

The repository Vercel workflow safely skips an automatic Preview when those values are absent and can create/configure the dedicated project when they are present.

## 9. Preview acceptance

Do not merge the Lean Production PR until the complete real Preview journey passes:

```text
signup
resume upload to private R2
Postgres task + Railway processing
candidate resume review
career targets
first-value dashboard
real job inventory
Career Intelligence
Recruiter Lens
application workspace
interview prep
tracked resume share
separate-session engagement
logout/login persistence
```

Use a synthetic candidate and synthetic résumé.

## 10. Merge and Production

After Preview is fully green:

1. merge the Lean Production PR to `main`;
2. rerun exact-main CI, Lean Production validation, clean-room and scale gates;
3. deploy compatible Railway API/worker revisions from that final SHA;
4. migrate/check the production DB again;
5. promote/deploy the matching Vercel Production release;
6. run bounded production Open Jobs ingestion;
7. repeat the entire candidate journey against Production;
8. inspect Vercel/Railway/queue/Clerk/R2 errors;
9. record final SHA, deployment IDs, migration revision, real job counts and public Production URL.

## Optional integrations

Stripe, Resend, PostHog, Sentry and browser auto-submit are not mandatory for the initial free candidate launch. When provider configuration is absent, their UI must be hidden, disabled safely or clearly unavailable rather than leading users into broken flows.

## Release evidence

Use [`docs/PRODUCTION_RELEASE_CHECKLIST.md`](docs/PRODUCTION_RELEASE_CHECKLIST.md) and [`docs/PRODUCTION_RUNBOOK.md`](docs/PRODUCTION_RUNBOOK.md).

Never label the system `LIVE_PRODUCTION_VERIFIED` solely because source code, CI or a Vercel build is green. Production verification requires the real persistent candidate journey to pass on the deployed provider stack.
