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

The 1536-dimensional upstream embedding field is deliberately discarded during ingestion. ApplyAI retains its own semantic-ranking/provider boundary.

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

The registered-source pipeline now preserves the raw posting's per-record company/board identity. This is required for any multi-company feed and prevents one aggregator registry row from collapsing unrelated employers into one canonical company.

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

## Real job inventory boundary

Repository/source support includes Greenhouse, Lever, Ashby, SmartRecruiters, USAJOBS, ReliefWeb, permitted employer career pages/JSON-LD, authorized feeds, and Open Jobs discovery coverage.

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

## Database activation

Target lean initial managed database:

**Dedicated ApplyAI Supabase Postgres**

Responsibility boundary:

```text
Clerk     -> identity / session / authentication
FastAPI   -> authorization / ownership / business logic
SQLAlchemy + Alembic -> canonical database access/schema
Supabase  -> managed PostgreSQL only
```

Do **not** add Supabase Auth.

Do **not** reuse an unrelated Supabase project.

As of 2026-08-31, the connected Supabase account exposes one healthy project, but it is not an ApplyAI project. Creation of a new Supabase project requires an explicit organization/cost confirmation through the provider tooling, so database activation remains `BLOCKED_EXTERNAL_CONFIGURATION` until that approval is supplied.

When the dedicated project exists, require:

```bash
alembic upgrade head
alembic current
alembic check
```

and verify pgvector availability before enabling any database-backed semantic path.

## Vercel activation

Target project:

- project: `applyai`
- team: `rrahul0904-5013s-projects`
- repository: `rrahul0904/applyai`
- root: `apps/web`
- framework: Next.js

As of 2026-08-31, the connected Vercel team does not contain an `applyai` project. Existing projects are unrelated and must not be reused as a fallback.

The repository already contains a dedicated Vercel configuration/workflow. Preview activation remains `BLOCKED_EXTERNAL_CONFIGURATION` until the required Vercel/ApplyAI environment values are genuinely available to that workflow.

Minimum runtime configuration:

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
CLERK_SECRET_KEY
APPLYAI_API_URL
APP_ENV
```

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
- aggregate-feed company identity preserved
- source authority remains employer-first
- existing migrations stay drift-free
- existing web/API/OpenAPI/container/Terraform/Playwright gates stay green
- exact-head clean-room stays green
- job-scale/source-scheduler gates remain green
- external blockers reported exactly

Live-preview completion additionally requires the real 22-step candidate journey from the implementation prompt. Source completion alone cannot promote this wave to `LIVE_PREVIEW_VERIFIED`.
