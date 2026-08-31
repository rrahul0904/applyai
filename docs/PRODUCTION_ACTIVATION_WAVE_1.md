# ApplyAI Production Activation Wave 1

Updated: 2026-08-31

## Mission

Move ApplyAI from source-complete product code toward a real preview/staging candidate journey without fabricating external-provider success.

The target path is:

```text
sign up -> resume -> reviewed career profile -> real jobs -> Career Intelligence
        -> Recruiter Lens -> application workspace -> interview prep
        -> tracked resume -> engagement -> return to persistent workspace
```

## Evidence vocabulary

Use these states literally:

- `SOURCE_IMPLEMENTED` — production-path repository code exists.
- `SOURCE_TESTED` — exact-head automated tests exercise the implementation.
- `LOCAL_RUNTIME_VERIFIED` — clean-room/local runtime evidence passed.
- `LIVE_PREVIEW_VERIFIED` — a real hosted Preview environment passed the documented candidate journey.
- `LIVE_STAGING_VERIFIED` — staging infrastructure plus real provider/data acceptance passed.
- `PRODUCTION_VERIFIED` — production operation was separately proven.
- `BLOCKED_EXTERNAL_CONFIGURATION` — remaining evidence depends on a real account, secret, provider approval, billing confirmation, or cloud resource not available to source control.

Do not collapse these states into `DONE`.

## Current evidence matrix

This table records the highest evidence level proven by this branch. It must be revised only from measured evidence.

| Subsystem | Evidence | Notes |
| --- | --- | --- |
| Candidate dashboard | `SOURCE_TESTED` | Next Best Action, Jobs For You, Career Readiness and Active Opportunities covered by web/Playwright tests. |
| Clerk auth source | `SOURCE_TESTED` | Dedicated sign-in/sign-up routes and redirect behavior exist; live tenant acceptance is still external. |
| Database | `SOURCE_TESTED` | Alembic zero-to-head and drift validation pass against CI PostgreSQL; AWS staging is configured for private Aurora PostgreSQL. |
| Resume storage | `SOURCE_TESTED` | Private S3 architecture and source tests exist; live AWS bucket acceptance is external. |
| Resume parsing | `SOURCE_TESTED` | PDF/DOCX security limits and durable processing tests exist. |
| Job ingestion | `SOURCE_TESTED` | Canonicalization, provenance, authority, dedupe and source scheduling tested. |
| Open Jobs | `SOURCE_TESTED` | Mocked connector tests plus bounded real-network public corpus acceptance (1 group, <=25 postings) pass. Live DB insertion awaits staging runtime. |
| Job search | `SOURCE_TESTED` | Scale benchmark passes on production-shaped synthetic inventory; real inventory acceptance awaits staging. |
| Career Intelligence | `SOURCE_TESTED` | Deterministic evidence-bound product path tested; no hiring-probability claim. |
| Recruiter Lens | `SOURCE_TESTED` | Candidate-side, evidence-only screening mirror tested. |
| Career System | `SOURCE_TESTED` | Unified per-role workspace tested. |
| Application workspace | `SOURCE_TESTED` | Candidate ownership/persistence and Playwright path tested. |
| Interview prep | `SOURCE_TESTED` | Evidence-bound artifact path tested. |
| Resume Share Intelligence | `SOURCE_TESTED` | Smart-link/privacy/engagement path tested; live public hosting awaits deployed web/API. |
| AI durable runtime | `SOURCE_TESTED` | Durable deterministic/provider path source-tested; live provider acceptance is separate. |
| Source scheduler | `SOURCE_TESTED` | Scheduler scale benchmark passes. |
| Source worker | `SOURCE_TESTED` | Worker/source pipeline tested; live ECS runtime awaits AWS staging variables. |
| Application executor | `SOURCE_TESTED` | Candidate approval and stop/handoff safeguards tested; live employer execution remains intentionally gated. |
| Vercel | `BLOCKED_EXTERNAL_CONFIGURATION` | Dedicated workflow is ready; required Vercel/API/Clerk GitHub secrets are absent. |
| FastAPI AWS runtime | `BLOCKED_EXTERNAL_CONFIGURATION` | Terraform/ECS release source exists; staging AWS/API/Clerk variables are absent. |
| Observability | `SOURCE_IMPLEMENTED` | CloudWatch/runtime source exists; live logs require deployed AWS services. |
| Production candidate journey | `BLOCKED_EXTERNAL_CONFIGURATION` | Cannot be promoted beyond local/source evidence until the real web, API, DB and Clerk environment exists. |

`LOCAL_RUNTIME_VERIFIED` is assigned only after the exact current branch head completes the repository clean-room certification. A prior head passing clean-room must not be used to promote a newer commit.

## Candidate first-value dashboard

The candidate Home experience is intentionally organized around four questions rather than feature inventory:

1. **Next Best Action** — one primary action based on resume/profile/application state.
2. **Jobs For You** — strongest available roles with explainable fit context and a clear path into Recruiter Lens.
3. **Career Readiness** — preparation foundations only; explicitly not employer interest or hiring probability.
4. **Active Opportunities** — application state plus linked Resume Share Intelligence activity when present.

Resume engagement remains observational. `BROWSED`, `ENGAGED`, and `DEEP_READ` never mean recruiter approval, interview selection, or hiring probability.

## Open Jobs upstream source

Public source:

- repository: `https://github.com/elliottdehn/open-jobs`
- dataset license: CC0 1.0 Universal
- public data surface: `https://backend.dehnbostele.workers.dev/data`
- upstream publishes a manifest and bounded leaf-group JSON files for its local-first client, in addition to a large Parquet snapshot.

ApplyAI uses an original connector and does not copy the upstream crawler implementation.

### Why the group data path

The upstream Parquet snapshot is multi-GB and roughly million-row scale. Loading it into the API process would violate ApplyAI's bounded-source design.

`OpenJobsConnector` therefore reads:

```text
/data/manifest.json
/data/groups/<leaf>.json
```

and processes a bounded number of groups per source run.

The upstream embedding field is deliberately discarded during ingestion. ApplyAI retains its own semantic-ranking/provider boundary.

### Authority and provenance

Open Jobs is registered as:

```text
source_type = AUTHORIZED_AGGREGATOR_FEED
trust_level = AUTHORIZED_AGGREGATOR_FEED
dataset_role = DISCOVERY_COVERAGE
closure_authority = false
```

Employer-origin observations remain higher authority:

```text
ApplyAI first party / employer direct
        > employer official API / ATS
        > employer structured page / career site
        > Open Jobs discovery observation
```

The registered-source pipeline preserves the raw posting's per-record company/board identity. This is required for any multi-company feed and prevents one aggregator registry row from collapsing unrelated employers into one canonical company.

### Cursor semantics

Each Open Jobs run is bounded by configured group count. The connector stages a pending cursor and promotes it on the next run only when the previous source-completeness evidence recorded zero failed postings.

A partial run therefore replays the same bounded slice. Canonical source identity makes the replay idempotent.

Group ids may change when the upstream index is rebuilt. If a stored leaf id disappears, ApplyAI safely restarts the corpus walk rather than guessing a replacement cursor.

### Registration

```bash
cd services/api
uv run python -m scripts.register_public_job_sources --open-jobs
```

`--all` also registers it along with the other implemented public feeds.

Default Open Jobs activation settings:

- 25 groups per run
- maximum 1000 records accepted from one group
- 30 second request timeout
- minimum 15 minute source cadence
- non-authoritative freshness semantics

These are operational bounds, not claims about real runtime throughput.

### Real-network acceptance

The dedicated `Open Jobs Live Acceptance` workflow runs an opt-in bounded public-network test with:

```text
max_groups = 1
max_jobs_per_group = 25
timeout_seconds = 30
```

It verifies a real manifest and leaf group, HTTPS application URLs, employer/board identity, normalization and vector stripping. It intentionally does **not** claim database ingestion counts.

## Real job inventory boundary

Repository/source support includes Greenhouse, Lever, Ashby, SmartRecruiters, USAJOBS, ReliefWeb, permitted employer career pages/JSON-LD, authorized feeds, and Open Jobs discovery coverage.

The AWS staging source bootstrap now permits Open Jobs as the credential-free initial real source while reviewed direct ATS boards remain optional, higher-authority additions.

This wave must not claim real inventory counts until a real database/source worker run measures them.

Required live metrics remain:

- organizations loaded
- organizations with domains/career sources
- active source count
- successful real source runs
- canonical active jobs
- Open Jobs observations
- direct ATS observations
- deduplication rate
- apply URL validity
- freshness distribution
- stale/closed jobs
- salary/location coverage
- source failure rate

`pnpm job-supply:acceptance` remains fail-closed and must not be weakened to accept deterministic seed or synthetic benchmark data.

## Database activation decision

The production-activation prompt preferred Supabase PostgreSQL only when the existing infrastructure did not clearly require another managed PostgreSQL platform. Repository inspection establishes that ApplyAI's canonical AWS staging/release path already provisions:

- private Aurora PostgreSQL Serverless v2;
- private DB subnets/security groups;
- AWS-managed master-user secret rotation/storage;
- ECS task injection of `DATABASE_HOST`, `DATABASE_USER` and `DATABASE_PASSWORD`;
- one migration task plus API/resume/source/AI/agent workers sharing that private database boundary.

Therefore this wave keeps **Aurora PostgreSQL** instead of introducing a second Supabase database and rewriting Terraform/ECS secret plumbing.

This is an infrastructure choice only. Application ownership remains:

```text
Clerk                -> identity / session / authentication
FastAPI              -> authorization / ownership / business logic
SQLAlchemy + Alembic -> canonical database access/schema
Aurora PostgreSQL    -> managed durable PostgreSQL
```

Supabase Auth is not introduced.

A separate existing Supabase project is unrelated to ApplyAI and remains untouched.

Real database activation is currently `BLOCKED_EXTERNAL_CONFIGURATION` because the GitHub `staging` environment lacks the AWS state/deploy variables required to provision the existing Terraform stack.

## Vercel activation

Target project:

- project: `applyai`
- team: `rrahul0904-5013s-projects`
- repository: `rrahul0904/applyai`
- root: `apps/web`
- framework: Next.js

As of 2026-08-31, the connected Vercel team does not contain an `applyai` project. Existing projects are unrelated and must not be reused as a fallback.

The branch deployment workflow can create the dedicated project, sync environment variables, build, deploy and probe a Preview when these GitHub Actions secrets exist:

```text
VERCEL_TOKEN
APPLYAI_VERCEL_API_URL
APPLYAI_VERCEL_CLERK_PUBLISHABLE_KEY
APPLYAI_VERCEL_CLERK_SECRET_KEY
```

The automatic preflight proved all four are currently absent, so no Vercel project was created or modified. This is `BLOCKED_EXTERNAL_CONFIGURATION`, not a source-code failure.

Server-only secrets must never be exposed under `NEXT_PUBLIC_*`.

## Clerk boundary

Clerk remains the sole candidate identity provider.

Source routes:

```text
/sign-in/[[...sign-in]]
/sign-up/[[...sign-up]]
```

Expected behavior:

- new account -> `/onboarding`
- returning sign-in -> `/dashboard`
- signed-in auth-page visit -> `/dashboard`
- protected candidate route while signed out -> branded sign-in

Live signup/social login/JWT/JWKS acceptance requires a real configured tenant and is not proven by local protocol tests alone.

## AWS staging activation boundary

The non-mutating staging readiness audit currently proves the GitHub `staging` environment is missing these required values:

```text
AWS_DEPLOY_ROLE_ARN
TF_STATE_BUCKET
WEB_ORIGIN
API_BASE_URL
API_CERTIFICATE_ARN
CLERK_ISSUER
CLERK_JWKS_URL
CLERK_AUDIENCE
```

`ENABLE_OPEN_JOBS` defaults to `true`, so public job-source availability itself is no longer an AWS staging prerequisite.

The repository already contains the canonical release path:

```text
GitHub OIDC -> Terraform -> ECR -> ECS/Fargate
            -> Alembic migration task
            -> API/workers/source scheduler
            -> private Aurora + S3 + SQS + CloudWatch
```

Do not create a second backend deployment architecture merely to avoid configuring those provider-owned values.

## Long-running runtime boundary

Vercel hosts the Next.js web surface only.

Long-running workloads remain outside Vercel Functions:

- job/source workers
- resume worker
- AI/agent workers
- Playwright application executor

Canonical durable path remains:

```text
PostgreSQL transactional outbox -> SQS -> worker
```

The Playwright executor remains candidate-approved and must stop for unknown/sensitive required fields, CAPTCHA, authentication challenges, or other employer controls. No bypass behavior is permitted.

## Definition of done for this wave

Repository completion requires:

- candidate first-value dashboard implemented and tested
- Open Jobs connector/registration implemented and tested
- bounded real-network Open Jobs acceptance green
- aggregate-feed company identity preserved
- source authority remains employer-first
- existing migrations stay drift-free
- existing web/API/OpenAPI/container/Terraform/Playwright gates stay green
- exact-head clean-room stays green
- job-scale/source-scheduler gates remain green
- external blockers reported exactly

Live-preview completion additionally requires the real candidate journey from the implementation prompt. Source completion alone cannot promote this wave to `LIVE_PREVIEW_VERIFIED`.

## Exact external actions still required

### Vercel / web Preview

Provider: Vercel + GitHub Actions

Resource: dedicated `applyai` project under team `rrahul0904-5013s-projects`

Why blocked: the deployment workflow has no credential/API/auth values to create and configure the project.

Exact values required in GitHub Actions secrets:

```text
VERCEL_TOKEN
APPLYAI_VERCEL_API_URL
APPLYAI_VERCEL_CLERK_PUBLISHABLE_KEY
APPLYAI_VERCEL_CLERK_SECRET_KEY
```

What runs afterward: the existing workflow creates/patches `applyai`, syncs Preview variables, builds, deploys and probes the URL.

### AWS backend/database/workers

Provider: AWS + GitHub Actions `staging` environment

Resource: ApplyAI Terraform/ECS staging stack

Why blocked: required provider-owned deployment/state/domain/Clerk variables are absent.

Exact GitHub environment variables required:

```text
AWS_DEPLOY_ROLE_ARN
TF_STATE_BUCKET
WEB_ORIGIN
API_BASE_URL
API_CERTIFICATE_ARN
CLERK_ISSUER
CLERK_JWKS_URL
CLERK_AUDIENCE
```

What runs afterward: staging preflight -> Terraform plan/apply -> ECR image -> Alembic task -> ECS API/workers -> source bootstrap including Open Jobs -> staging verification.
