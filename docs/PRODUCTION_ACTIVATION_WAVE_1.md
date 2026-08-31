# ApplyAI Production Activation Wave 1

Updated: 2026-08-31

## Status

Production Activation Wave 1 delivered the candidate first-value dashboard, Open Jobs integration, source-authority hardening, candidate entry/auth packaging and the release evidence model. Its product stack is now merged into `main` through PR #26.

The original AWS-first activation plan in this document is **superseded for the initial launch** by PR #27, the Lean Production release vehicle.

Canonical launch documentation is now:

- `DEPLOYMENT.md`
- `docs/LEAN_PRODUCTION_ARCHITECTURE.md`
- `docs/RAILWAY_DEPLOYMENT.md`
- `docs/R2_STORAGE.md`
- `docs/deployment/VERCEL.md`
- `docs/PRODUCTION_RELEASE_CHECKLIST.md`
- `docs/PRODUCTION_RUNBOOK.md`

AWS infrastructure remains preserved as an optional future scale/enterprise profile. It is not required for the first public ApplyAI candidate launch.

## Product path delivered by this wave

```text
sign up
  -> resume
  -> reviewed career profile
  -> real jobs
  -> Career Intelligence
  -> Recruiter Lens
  -> application workspace
  -> interview prep
  -> tracked resume
  -> engagement
  -> persistent returning-user workspace
```

The real deployed version of this path remains the final production acceptance target.

## Evidence vocabulary

Use these states literally:

- `SOURCE_IMPLEMENTED` — production-path repository code exists.
- `SOURCE_TESTED` — exact-head automated tests exercise the implementation.
- `LOCAL_RUNTIME_VERIFIED` — local/clean-room runtime evidence passed.
- `LIVE_PREVIEW_VERIFIED` — real hosted Preview plus provider-backed candidate journey passed.
- `LIVE_PRODUCTION_VERIFIED` — real Production deployment plus persistent candidate journey passed.
- `BLOCKED_EXTERNAL_CONFIGURATION` — remaining evidence depends on a real account, secret, provider authorization or resource not available to source control/current tooling.

Do not collapse these states into `DONE`.

## Current launch architecture

```text
Candidate
  -> Vercel / Next.js
  -> Clerk
  -> Railway / FastAPI
       -> Railway PostgreSQL
       -> Cloudflare R2
       -> TaskOutbox -> postgres_tasks -> Railway worker
```

Launch settings:

```text
DEPLOYMENT_PROFILE=lean
TASK_QUEUE_PROVIDER=postgres
AUTH_PROVIDER=clerk
OBJECT_STORAGE_PROVIDER=s3
DATABASE_URL=<Railway PostgreSQL>
```

AWS scale settings remain supported through `DEPLOYMENT_PROFILE=aws` and the existing Terraform/ECS/Aurora/SQS/S3 source.

## Candidate first-value dashboard

The candidate Home experience is intentionally organized around four questions rather than feature inventory:

1. **Next Best Action** — one primary action based on résumé/profile/application state.
2. **Jobs For You** — strongest available roles with explainable fit context and a path into Recruiter Lens.
3. **Career Readiness** — preparation foundations only; not employer interest or hiring probability.
4. **Active Opportunities** — application state plus linked Resume Share Intelligence activity.

Resume engagement remains observational. `BROWSED`, `ENGAGED`, and `DEEP_READ` never mean recruiter approval, interview selection or hiring probability.

## Open Jobs

ApplyAI uses an original bounded connector for the public CC0 Open Jobs corpus.

Public data path:

```text
manifest.json
  -> groups/<leaf>.json
  -> bounded ApplyAI normalization
  -> provenance / authority / dedupe / canonical job
```

The upstream embedding is discarded. ApplyAI retains its own semantic-provider boundary.

Open Jobs remains:

```text
source_type = AUTHORIZED_AGGREGATOR_FEED
trust_level = AUTHORIZED_AGGREGATOR_FEED
dataset_role = DISCOVERY_COVERAGE
closure_authority = false
```

Employer-origin observations remain higher authority:

```text
ApplyAI first party / employer direct
        > employer official ATS/API
        > employer structured career page
        > Open Jobs discovery observation
```

The connector preserves per-record employer/board identity so a multi-company feed cannot collapse unrelated employers into one canonical company.

### Real-network evidence

A bounded real-network acceptance has already verified the public manifest/group surface with one group and no more than 25 postings, including application URLs, employer/board identity, normalization and vector stripping.

This is source acceptance, not proof that a production database contains real jobs.

## Lean durable queue

PR #27 replaces SQS as a **launch requirement**, not as the only supported queue provider.

Lean path:

```text
business transaction
     +
TaskOutbox
     ↓ commit
postgres_tasks
     ↓
Railway worker
```

Required semantics implemented/tested include:

- unique idempotency keys;
- `FOR UPDATE SKIP LOCKED`;
- concurrent workers;
- lease owner/expiry;
- heartbeat;
- expired-lease recovery;
- retry/backoff;
- `RETRY_WAIT`;
- `DEAD`;
- cancellation;
- explicit résumé/source/AI/agent routing;
- fail-closed unknown task types.

The optional AWS profile keeps SQS.

## Private résumé storage

Lean production uses Cloudflare R2 through the existing S3-compatible adapter.

```text
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
S3_BUCKET=applyai-resumes
S3_REGION=auto
S3_SERVER_SIDE_ENCRYPTION=none
```

AWS S3 mode retains `AES256` behavior.

Resume Share Intelligence never exposes the raw private object key or permanent R2/S3 object URL.

Return-view notification behavior has also been bounded:

```text
first human VIEW   -> RESUME_SHARE_VIEWED
first later VIEW   -> one RESUME_SHARE_RETURNED
later repeat VIEWs -> analytics only
```

This prevents refresh-driven notification spam while preserving engagement history.

## Current source evidence

Repository-side evidence includes:

| Subsystem | Current source evidence |
| --- | --- |
| Candidate entry/auth UX | `SOURCE_TESTED` |
| Candidate first-value dashboard | `SOURCE_TESTED` |
| Resume parser/security | `SOURCE_TESTED` |
| Career System | `SOURCE_TESTED` |
| Recruiter Lens | `SOURCE_TESTED` |
| Resume Share Intelligence | `SOURCE_TESTED` |
| Open Jobs connector | real public-source acceptance + source tests |
| Career Intelligence | `SOURCE_TESTED` |
| Application workspace | `SOURCE_TESTED` |
| Interview preparation | `SOURCE_TESTED` |
| Postgres durable queue | `SOURCE_TESTED` / Lean Production Validation |
| R2 adapter | `SOURCE_TESTED`; real provider acceptance still required |
| Railway packaging | `SOURCE_TESTED`; real provider deployment still required |
| AWS scale profile | retained repository validation |

Exact-head workflow evidence must always be rechecked after the final source-changing commit.

## Current live-provider boundary

### Railway

Provider: Railway

Missing item: authorized Railway account session/API token.

Exact action required: authenticate Railway for the dedicated `applyai` project. The repository can then run `scripts/railway-bootstrap.sh` to create/reuse:

```text
Postgres
applyai-api
applyai-worker
applyai-browser-worker
```

Launch cannot be fully verified without the Railway PostgreSQL/API/normal worker. The browser worker may remain safely disabled if browser auto-submit is not part of the initial free candidate launch.

### Cloudflare R2

Provider: Cloudflare R2

Missing item: authorized account plus private bucket credentials.

Exact action required: create/use a dedicated private `applyai-resumes` bucket and provide the endpoint, access key and secret to Railway plus the R2 acceptance workflow.

What runs afterward: real PUT/HEAD/GET/presigned-PUT/DELETE acceptance, then synthetic candidate résumé upload/processing.

### Clerk

Provider: Clerk

Missing item: real ApplyAI Clerk instance credentials/configuration.

Required values include the frontend publishable key/server secret and backend issuer/JWKS values (plus audience when configured).

What runs afterward: real signup, FastAPI JWT validation, `/me`, logout/login persistence and cross-user isolation.

### Vercel

Provider: Vercel + GitHub Actions

Target:

```text
project = applyai
team = rrahul0904-5013s-projects
root = apps/web
```

The connected team currently has no dedicated `applyai` project. The deployment workflow is prepared to create/configure it when these values exist:

```text
VERCEL_TOKEN
APPLYAI_VERCEL_API_URL
APPLYAI_VERCEL_CLERK_PUBLISHABLE_KEY
APPLYAI_VERCEL_CLERK_SECRET_KEY
```

The latest preflight confirmed those values are absent, so project creation/deployment was intentionally skipped rather than fabricating a Preview.

## Preview merge gate for PR #27

Do not merge PR #27 until all critical items pass:

1. exact-head repository CI/Lean Production/clean-room/scale gates are green;
2. Railway PostgreSQL is real and Alembic is current with zero drift;
3. Railway API `/health` and `/ready` pass;
4. Railway Postgres worker processes real tasks without AWS/SQS dependency;
5. R2 live acceptance passes and the résumé bucket is private;
6. Clerk real signup/JWT/user-isolation acceptance passes;
7. Open Jobs performs a bounded real database ingestion;
8. `pnpm job-supply:initial-acceptance` passes;
9. dedicated Vercel ApplyAI Preview is healthy;
10. the full Preview candidate journey passes through logout/login persistence.

After that:

```text
merge PR #27 -> main
run exact-main release gate
deploy Railway production release
deploy Vercel production release
run bounded production job ingestion
repeat complete candidate journey on Production
inspect production errors
```

Only then may ApplyAI be classified `LIVE_PRODUCTION_VERIFIED`.

## Final authority

This document preserves the product and evidence decisions from Production Activation Wave 1, but the detailed operator instructions now live in the lean launch documentation listed at the top of this file. Do not resurrect the earlier AWS-first launch path solely because historical sections or old PR descriptions mention Aurora/ECS/SQS.
