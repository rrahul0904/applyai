# ApplyAI

ApplyAI is an evidence-bound candidate career platform spanning job discovery, Career Intelligence, résumé/application/interview preparation, candidate-controlled sharing and persistent career memory.

Repository/source completion is deliberately separated from real provider acceptance. A feature is never called live merely because code exists.

## Launch architecture

The public product target is **Vercel**:

```text
Candidate
   ↓
Vercel / Next.js + Clerk
   ↓
FastAPI
   ↓
PostgreSQL
   ├─ canonical product data
   └─ transactional outbox → durable PostgreSQL task queue

Private S3-compatible object storage → résumé/document objects
```

The launch must remain capable of a **$0.00 required monthly infrastructure cost**. Mandatory paid AI, queues, monitoring, email, databases or automatic upgrades are not allowed without explicit approval. AWS remains an optional future scale/enterprise profile, not a launch prerequisite.

## Repository layout

```text
apps/web/               Next.js candidate/employer/admin web
apps/extension/         Manifest V3 public-job URL handoff
mobile/                 Expo / React Native candidate client
services/api/           FastAPI API, workers, migrations, evaluation
infra/bootstrap/        optional AWS/GitHub OIDC bootstrap
infra/staging/          optional AWS scale-profile Terraform
docs/                   architecture, audits, status and runbooks
```

## Candidate product

Canonical authenticated surfaces include:

```text
/dashboard
/matches
/jobs
/jobs/[id]
/saved
/applications
/applications/[id]
/resume
/resume/studio
/resume/signals
/career
/career/navigation
/portfolio
/interview/[jobId]
/network
/analytics
/alerts
/profile
/billing
/settings
/import-job
```

Candidate-controlled public surfaces include:

```text
/u/{candidate-slug}
/r/{resume-share-token}
/recruiter-report/{token}
```

Implemented/source-controlled capabilities include:

- Clerk-backed candidate identity and owner-scoped APIs;
- onboarding and verified profile/skills/preferences;
- private résumé upload, bounded parsing, review and versioning;
- Resume Studio and job-specific variants;
- deterministic explainable Resume Intelligence;
- PostgreSQL job search, filters, saved jobs and saved searches;
- explainable Career Intelligence and durable Career Memory;
- unified job-specific Career System;
- candidate-side Recruiter Lens with supported/partial/not-evidenced criteria;
- Recruiter Lens perspectives and candidate-owned reusable criteria;
- candidate-controlled print/private-share/revoke Recruiter Lens reports;
- application command center and candidate-approval boundary;
- evidence-bound résumé/application/interview preparation;
- Technical Interview Lab for behavioral, technical, system-design, SQL and coding reasoning practice;
- recruiter/referral contacts and follow-ups;
- job alerts, reminders and notification inbox;
- privacy-preserving Resume Share Intelligence;
- anonymous share-session reports and 7/30/90-day trends;
- opt-in public portfolio with original themes, projects and field visibility;
- career role navigation, skill-gap and canonical-job market intelligence;
- candidate analytics;
- account export and application-side deletion.

Readiness and engagement signals are **not** employer scores, interview probabilities or hiring probabilities.

## Reverse-engineering coverage

ApplyAI used publicly observable product behavior from modern career tools only to understand product problems and workflows. The implementation remains clean-room and original.

Canonical audit files:

- [`docs/REVERSE_ENGINEERING_COVERAGE_AUDIT.md`](docs/REVERSE_ENGINEERING_COVERAGE_AUDIT.md)
- [`docs/reverse-engineering-feature-matrix.json`](docs/reverse-engineering-feature-matrix.json)

The gap-closure work adds the highest-value safe capabilities identified in the final audit:

```text
Portfolio Identity
Career Navigation
Skill-gap / Market Intelligence
Deterministic Resume Intelligence
Recruiter Lens modes + reusable criteria
Recruiter Lens candidate report/share/revoke
Resume Share anonymous session detail + trends
Technical Interview Lab
```

Deliberate exclusions are part of the product design:

- employer bulk candidate ranking/automatic advancement/rejection → legal-risk boundary;
- raw-IP/company/named-viewer inference and cross-link fingerprinting → privacy boundary;
- arbitrary remote coding execution → deferred until a hardened zero-cost sandbox exists;
- QR, print-intent tracking, section-depth analytics and recruiter contact form → useful P2 enhancements, not release blockers.

## Career Intelligence

The deterministic baseline evaluates role alignment, verified skills, work mode/location, compensation, seniority and freshness. Durable model-backed work remains separate and evidence-bound:

```text
verified candidate/job evidence
        ↓
AIJobRun + transactional outbox
        ↓
durable task queue
        ↓
worker → reviewed provider
        ↓
strict schema + evidence-reference validation
        ↓
versioned artifact + candidate review
```

Core product behavior remains usable with `AI_PROVIDER=deterministic`; paid inference is optional.

## Recruiter Lens safety

Recruiter Lens is a candidate self-assessment simulation. It supports original ApplyAI perspectives such as Default Recruiter, Strict Must-Have, Hiring Manager, Technical and Custom. Candidate-owned criteria are restricted to job-relevant factors; protected-characteristic criteria are blocked.

Candidate-created report links are high entropy, revocable and `noindex`. They do not identify viewers or infer companies and never become employer decisions.

## Resume Share Intelligence

Candidate-owned smart links support role/application/channel context, expiry, revoke/reactivate/delete, download controls, dwell, scroll, click/copy, download, anonymous returns, engagement bands, timeline and CSV export.

Privacy boundaries:

- no raw IP persistence;
- no cross-link fingerprinting;
- no company inference;
- no named-viewer guessing;
- raw private storage URLs are never exposed;
- first view / first return / first download notifications are bounded rather than spammed.

The gap-closure branch adds owner-scoped anonymous session sequence reports and period-over-period trends.

## Technical Interview Lab

ApplyAI provides job-specific behavioral, technical, system-design, SQL and coding questions, answer/notes workspace, self-review and attempt history. The `$0` launch intentionally does not add unsafe arbitrary remote code execution merely for feature parity.

## Job-data platform

The provider-neutral job platform includes source registry/scheduling/leasing, raw source preservation, validation, authority/provenance, deterministic canonical deduplication, freshness/closure evidence, apply-URL verification, source health and operator controls.

Reviewed source support includes official/public ATS paths such as Greenhouse, Lever, Ashby and SmartRecruiters, permitted structured employer career pages, configured public/government sources, authorized feeds and Open Jobs discovery coverage.

Authority is preserved conceptually as:

```text
ApplyAI first-party / employer direct
        ↓
official ATS / employer-origin source
        ↓
employer structured career page
        ↓
authorized feed
        ↓
broad discovery/coverage source
```

Broad discovery sources do not overwrite stronger employer-origin evidence or receive unsafe absence-based closure authority.

## Durable work

The lean runtime keeps the transactional outbox as the first commit boundary and uses PostgreSQL durable tasks with:

- idempotency keys;
- `FOR UPDATE SKIP LOCKED` claims;
- multiple-worker safety;
- leases/heartbeat/expiry recovery;
- bounded retry/backoff;
- dead/cancel states;
- explicit task-family routing;
- unknown task types failing closed.

## Employer and billing source

Employer organization/job/applicant workflows and billing adapters remain source controlled, but the first zero-cost candidate launch does not require employer automated decisioning or paid checkout. Stripe/paid controls must be hidden or safely disabled until intentionally activated.

## Local development

Prerequisites:

- Node.js 22+
- pnpm 10+
- Python 3.12+
- uv
- PostgreSQL 17 or Docker

Typical local flow:

```bash
docker compose up -d postgres
pnpm install
uv sync --system-certs --project services/api

cd services/api
DATABASE_URL=postgresql+psycopg://applyai:applyai@localhost:55432/applyai \
  uv run alembic upgrade head

cd ../..
pnpm dev
pnpm dev:api
```

Development uses deterministic/local substitutes where external providers are unavailable.

## Repository validation

Exact-head validation includes the applicable gates:

```bash
pnpm lint
pnpm --dir apps/web typecheck
pnpm test:web
pnpm build
pnpm openapi:check
pnpm test:e2e

cd services/api
uv run alembic upgrade head
uv run alembic check
uv run pytest
```

Additional workflows cover Lean Production validation, clean-room certification, PostgreSQL queue semantics, job search/source scheduler scale, agent runtime tests/scale, demo capture, GitHub workflow validation and optional AWS profile validation.

Do not reuse a historical PASS after a source-changing commit.

## Release topology

- PR #27: final lean-production release vehicle targeting `main`.
- PR #28: reverse-engineering gap closure stacked onto PR #27's branch.

PR #28 must pass exact-head validation before merging into the PR #27 branch. PR #27 must not merge to `main` until the real Vercel Preview/provider candidate journey passes.

## Live production boundary

Source support does not prove live production. `LIVE_PRODUCTION_VERIFIED` requires actual evidence for:

```text
real Clerk signup/signin/JWT
real persistent PostgreSQL
real private object storage
real job ingestion
Vercel ApplyAI Preview
complete persistent Preview candidate journey
exact release CI
Vercel Production
complete persistent Production candidate journey
production health review
```

Deployment/runbook references:

- [`DEPLOYMENT.md`](DEPLOYMENT.md)
- [`docs/PRODUCTION_RELEASE_CHECKLIST.md`](docs/PRODUCTION_RELEASE_CHECKLIST.md)
- [`docs/PRODUCTION_RUNBOOK.md`](docs/PRODUCTION_RUNBOOK.md)
- [`docs/CURRENT_REPOSITORY_STATE.md`](docs/CURRENT_REPOSITORY_STATE.md)
- [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md)
