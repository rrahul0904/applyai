# ApplyAI Lean Production Runbook

Updated: 2026-08-31

## Architecture

Launch profile:

```text
Vercel Next.js
  -> Clerk
  -> Railway FastAPI
       -> Railway PostgreSQL
       -> Cloudflare R2
       -> TaskOutbox -> postgres_tasks -> Railway worker
```

AWS remains an optional scale profile and is not required for the lean runbook.

## Release identifiers

For every release record:

```text
Git SHA
PR / release source
Railway API deployment ID
Railway worker deployment ID
Vercel deployment ID
Vercel URL
Alembic revision
```

Never diagnose or roll back a production incident without first identifying the exact deployed revisions.

## Deploy API

1. Confirm PR/main exact-head CI is green.
2. Confirm Railway production variables are set.
3. Run `alembic upgrade head` against production PostgreSQL.
4. Run `alembic current` and `alembic check`.
5. Deploy `applyai-api` from the intended SHA.
6. Probe `/health`.
7. Probe `/ready`.
8. Inspect startup/runtime logs for database, Clerk, R2, or AWS/SQS dependency errors.

Lean production must start without AWS credentials.

## Deploy normal worker

Start command:

```bash
python -m app.workers.postgres
```

After deploy, verify the worker can materialize and claim one disposable/synthetic task or process the next expected production task without error.

Observe task state in `postgres_tasks`:

```text
QUEUED
RUNNING
RETRY_WAIT
COMPLETED
DEAD
CANCELLED
```

## Inspect queue

Operational queries should inspect counts by status, the oldest queued/available task, expired RUNNING leases, retry/dead tasks, `attempt_count`, `lease_owner`, `lease_expires_at`, and `last_error`.

Do not manually mark an unknown/failing task completed simply to reduce backlog. Determine whether the failure is code, provider, payload, or permanent input failure.

## Retry failed work

For `RETRY_WAIT`, allow normal backoff unless an incident fix requires an operator retry.

For `DEAD`, inspect:

```text
task_type
idempotency_key
payload metadata (without exposing private content)
attempt_count
last_error
```

Only requeue after the underlying fault is corrected and idempotency semantics are understood.

## Lease recovery

A RUNNING task whose lease expires is reclaimable by another worker. Do not manually duplicate a task while a valid lease is still active.

If workers restart repeatedly:

1. inspect Railway deployment/runtime health;
2. inspect memory/CPU pressure;
3. inspect the oldest failing task;
4. confirm database connectivity and connection limits;
5. confirm the worker is using `TASK_QUEUE_PROVIDER=postgres`.

## Open Jobs ingestion

Register production source:

```bash
cd services/api
python -m scripts.register_public_job_sources --open-jobs
```

Start bounded:

```text
1–5 groups
```

Record:

```text
fetched
valid
invalid
created
updated
unchanged
deduplicated
failed
```

Inspect canonical jobs and company identity before ramping to 25 or 100 groups.

Run:

```bash
pnpm job-supply:initial-acceptance
```

The mature `pnpm job-supply:acceptance` gate must remain strict.

## Disable a job source

Use the existing operator/source-registry control path rather than deleting canonical data. Preserve provenance and source-run history so jobs can be reconciled later.

## R2 verification

Use the R2 acceptance script/workflow before first production launch and after credential/bucket changes.

For an object incident verify:

- bucket remains private;
- endpoint/bucket/credentials match the intended environment;
- `S3_SERVER_SIDE_ENCRYPTION=none` for R2;
- presigned URL is short-lived;
- API ownership checks remain in place.

Never publish a private R2 object URL as a workaround.

## Clerk incident checks

If authentication fails:

1. verify publishable key in Vercel;
2. verify server secret in Vercel where required;
3. verify `CLERK_ISSUER` and `CLERK_JWKS_URL` in Railway;
4. verify the frontend and backend point to the same Clerk instance;
5. inspect token issuer/audience errors without logging raw tokens.

Do not switch to dev authentication in production.

## Vercel deployment

The repository workflow can create/configure the dedicated `applyai` project when required deployment secrets exist.

Preview must be tested before production promotion.

Production deployment must come from the final green `main` SHA.

## Roll back Vercel

Use Vercel deployment history to promote/redeploy the last known-good web deployment whose API contract remains compatible with the active backend. Record the rollback deployment ID and SHA.

Do not roll back the web across an incompatible OpenAPI/backend migration boundary without also handling backend compatibility.

## Roll back Railway API/worker

Redeploy the last known-good image/source revision. Verify `/ready`, then resume workers.

Do not downgrade database schema destructively as an automatic first response. Prefer forward fixes or application rollback compatible with the current schema.

## Database restore

Use the production PostgreSQL provider's documented backup/restore mechanism. Before restore:

1. stop or pause write-heavy workers;
2. identify restore point and scope;
3. preserve incident evidence;
4. restore into a safe environment first when provider capabilities allow;
5. verify migration revision and data integrity;
6. only then redirect production.

Record the provider restore/retention policy once the real Railway plan/database exists.

## Secret rotation

Rotate provider credentials independently:

- Clerk secret/issuer configuration;
- Railway/API internal token;
- R2 access key pair;
- OpenAI key;
- optional Resend/Stripe/PostHog/Sentry keys;
- Vercel deployment token used by CI.

After each rotation redeploy only the services that consume the credential, then run the relevant acceptance check. Never print secret values in logs or incident notes.

## Candidate privacy incident

If a résumé/share issue is reported:

1. revoke the Resume Share link if relevant;
2. verify the underlying object is still private;
3. inspect access/event metadata without collecting new invasive identifiers;
4. preserve the no-raw-IP / no-cross-link-fingerprint boundary;
5. use the existing candidate deletion/export workflow where requested and supported.

## Health after deployment

Immediately inspect:

```text
Vercel runtime/build errors
Railway API errors
Railway worker restarts
PostgreSQL connectivity / queue backlog
Open Jobs failures
resume parser failures
Clerk authentication failures
R2 errors
```

Do not declare `LIVE_PRODUCTION_VERIFIED` while an unexplained critical error remains.

## Current provider gate

Repository implementation and runbooks do not create provider credentials. The current connected tool environment has no authorized Railway, Cloudflare R2, or Clerk integration. Live commands requiring those providers must be executed only after the account owner supplies the required authorization. Vercel is connected, but a meaningful ApplyAI deployment still requires the real Railway API URL and Clerk configuration.
