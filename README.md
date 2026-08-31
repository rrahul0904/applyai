# ApplyAI

ApplyAI is a career platform spanning candidate job search, Career Intelligence,
resume/application/interview workflows, employer recruiting, billing, mobile and job capture.

The repository deliberately separates **source/platform completion** from **real external deployment
and provider acceptance**. Cloud accounts, provider secrets, signing identities and store
publication are never fabricated from repository source.

## Production architecture

The canonical first production launch is the **lean profile**:

```text
Candidate Web: Next.js App Router + Clerk on Vercel
Candidate Mobile: Expo / React Native + Clerk
Browser Extension: Manifest V3 public-job URL handoff

                         HTTPS
                           |
                           v
                    Railway / FastAPI
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
 Railway PostgreSQL   Cloudflare R2      task_outbox
                                            |
                                            v
                                      postgres_tasks
                                            |
                                  Railway durable worker
                                  /        |        \
                                 v         v         v
                              resume     source      AI/agent
                              tasks      tasks       tasks
```

The backend remains a modular monolith. ApplyAI does not add Kafka, Kubernetes, Redis or a
microservice split merely to simulate scale.

`DEPLOYMENT_PROFILE=lean` is the launch profile. It uses one PostgreSQL database for canonical
application data and durable background-task state. The transactional outbox remains the first
commit boundary, while workers claim `postgres_tasks` with `FOR UPDATE SKIP LOCKED`, leases,
heartbeat, retry/backoff, dead-task visibility and crash recovery.

The existing AWS infrastructure is preserved as `DEPLOYMENT_PROFILE=aws` for future scale or
enterprise needs. It continues to support ALB/ECS/Fargate, Aurora PostgreSQL, private S3, SQS,
EventBridge and CloudWatch, but AWS is **not required** to launch the lean production product.

See:

- [`docs/LEAN_PRODUCTION_ARCHITECTURE.md`](docs/LEAN_PRODUCTION_ARCHITECTURE.md)
- [`DEPLOYMENT.md`](DEPLOYMENT.md)
- [`docs/RAILWAY_DEPLOYMENT.md`](docs/RAILWAY_DEPLOYMENT.md)
- [`docs/R2_STORAGE.md`](docs/R2_STORAGE.md)
- [`docs/PRODUCTION_RELEASE_CHECKLIST.md`](docs/PRODUCTION_RELEASE_CHECKLIST.md)
- [`docs/PRODUCTION_RUNBOOK.md`](docs/PRODUCTION_RUNBOOK.md)

## Repository layout

```text
apps/web/               canonical Next.js candidate/employer/admin web
apps/extension/         Manifest V3 job-import extension
mobile/                 Expo / React Native candidate application
services/api/           FastAPI API + workers + migrations + evaluation
infra/bootstrap/        optional AWS/GitHub OIDC + Terraform-state bootstrap
infra/staging/          optional AWS scale-profile Terraform
services/api/evals/     Career Intelligence golden evaluation data
docs/                   architecture, status and deployment/recovery runbooks
```

## Candidate product

Canonical candidate surfaces:

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
/interview/[jobId]
/network
/analytics
/alerts
/profile
/billing
/settings
/import-job
```

Historical `/demo` and `/beta` routes redirect into the canonical product.

Implemented candidate capabilities include:

- authenticated onboarding and candidate-owned profile/skills/preferences;
- durable private resume upload, parsing, review and version history;
- Resume Studio with editable job-specific variants and export;
- PostgreSQL job search, filters, saved jobs and saved searches;
- explainable Career Intelligence ranking with deterministic evidence-bound baseline;
- candidate-side Recruiter Lens with supported/partial/not-evidenced criteria;
- application command center with status history and notes;
- candidate-approved application submission orchestration;
- Career Memory;
- evidence-locked resume/application/interview copilots;
- interview practice history and feedback;
- recruiter/referral contacts and follow-ups;
- job alerts, interview reminders and notification inbox;
- privacy-preserving Resume Share Intelligence;
- candidate analytics;
- company intelligence derived from known posting evidence;
- billing/entitlement controls;
- account data export and application-side deletion.

## Career Intelligence

ApplyAI keeps deterministic product signals and model inference separate.

### Explainable baseline

The deterministic baseline scores target-role alignment, verified skills, location/work mode,
compensation, seniority and freshness. It is retained as an auditable source of truth rather than
being replaced by an opaque hiring-probability claim.

### Durable V2

```text
verified candidate/job evidence
        |
        v
AIJobRun + transactional outbox
        |
        v
durable task queue -> AI worker -> reviewed provider
        |
        v
strict schema + evidence-reference validation
        |
        v
versioned domain artifacts
        |
        v
candidate review + feedback
```

In lean production the durable task queue is PostgreSQL. In the optional AWS profile the same
application task families can be delivered through SQS.

First-class persistence includes AI runs/artifacts, career matches, resume-tailoring revisions,
cover letters, application-question drafts, candidate feedback and verified Career Memory.

Supported durable tasks cover deep match, resume tailoring, application copilot and interview prep.
The model-provider boundary records provider/model/prompt/schema version, latency, token usage and
configured cost estimates when available. Terminal schema/evidence failures fail closed; transient
provider transport/429/5xx failures remain retryable.

## Semantic matching and AI evaluation

ApplyAI adds a provider-abstracted semantic reranker:

- deterministic local hashed embeddings for CI/development;
- optional server-side OpenAI embeddings in reviewed environments.

Golden evaluation measures:

```text
Precision@5
Precision@10
Mean Reciprocal Rank
Evidence Support Rate
Unsupported Evidence References
```

Operators can compare a candidate ranking/prompt/model dataset against the baseline before rollout.

## Employer platform

ApplyAI Hire includes:

- employer organizations and role membership;
- operator verification/suspension;
- job drafting, publishing and closure;
- verified first-party roles in the same canonical candidate marketplace;
- first-party applicant intake;
- recruiter stages, ratings and notes;
- employer dashboard metrics.

Candidate and employer products share the same canonical jobs/applications rather than parallel demo
data.

## Application submission boundary

ApplyAI never submits an application without explicit candidate approval.

- Verified first-party ApplyAI employers can receive an approved application directly.
- Third-party employers use a recorded external handoff to their public application page.
- ApplyAI does not bypass login, CAPTCHA, anti-bot controls or private employer endpoints.

## Billing

Source includes:

- Free / Pro / Team entitlements;
- subscription and usage persistence;
- Stripe Checkout adapter;
- Stripe Billing Portal adapter;
- signed Stripe webhook verification;
- billing ledger and candidate billing UI.

Stripe account IDs, price IDs and secrets are real-environment configuration. The free candidate
journey must remain usable when paid checkout has not yet passed provider acceptance; unavailable
paid actions must be hidden or safely disabled rather than exposed as broken CTAs.

## Job-data platform

Dedicated adapters support Greenhouse, Lever, Ashby and SmartRecruiters plus the public Open Jobs
coverage source. The discovery layer also recognizes other public career technologies and can use
the bounded structured public-page importer when no reviewed public board API is available.

Open Jobs is a lower-authority discovery/coverage source. Employer-origin ATS observations retain
higher authority for canonical fields and closure evidence.

Source ingestion includes registry/scheduling/leasing, transactional dispatch, authority/provenance,
deduplication, freshness, closure evidence, apply-URL verification and quality metrics. Public-page
import enforces robots, redirect, SSRF and response-size controls. No authentication or anti-bot
circumvention is used to claim provider coverage.

For first production activation use bounded Open Jobs ingestion and run:

```bash
pnpm job-supply:initial-acceptance
```

The mature `pnpm job-supply:acceptance` gate remains strict and is not weakened for launch.

## Resume storage and sharing

Lean production stores private résumé objects in Cloudflare R2 through the existing S3-compatible
storage boundary. The production bucket remains private; R2 credentials stay server-side and raw
private object URLs are never exposed through Resume Share Intelligence.

Resume Share Intelligence records privacy-preserving engagement events without storing raw IP
addresses or cross-link browser fingerprints. A first human view creates one viewed notification;
the first observed return creates one returned notification; later repeat views remain analytics
only rather than generating notification spam.

## Mobile

`/mobile` contains the Expo/React Native candidate application using the same FastAPI contract as
web and Clerk secure token handling.

Native screens include AI Matches, Jobs, Applications, Alerts and Profile/Career Memory. Repository
web tests transpile the native TS/TSX source so mobile source has an exact-head syntax gate.

Apple/Google signing, native release builds and App Store/Play Store publication remain external
distribution/deployment tasks.

## Browser extension

`/apps/extension` contains a Manifest V3 extension with only `activeTab` and `storage` permissions.
After a user click it hands the active public page URL to `/import-job`; the existing safe
server-side import pipeline remains authoritative.

Repository tests validate the extension manifest permission set and JavaScript syntax. Browser-store
signing/publication remains external distribution work.

## Operations, privacy and notifications

The operator surface includes platform metrics, employer trust controls, engagement dispatch, source
quality, AI runtime quality and golden AI evaluation.

Candidate privacy includes machine-readable export, application-side deletion, anonymized audit
tombstones where referential integrity must remain, and a deleted-identity hash preventing silent
recreation from the same external identity.

Durable engagement includes saved-search job alerts, interview reminders, recruiter follow-ups,
notification preferences and inbox/read state. Real email/push delivery providers remain optional
deployment integrations and must not make the core candidate journey unavailable.

## Local development

Prerequisites:

- Node.js 22+
- pnpm 10+
- Python 3.12+
- uv
- PostgreSQL 17 or Docker

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

Development uses controlled local/deterministic substitutes for external auth/storage/queue/model
providers. See `apps/web/.env.example`, `services/api/.env.example` and `mobile/.env.example`.

## Repository validation

The platform completion gate covers:

```bash
pnpm lint
pnpm --dir apps/web typecheck
pnpm test:web                 # includes native-mobile + extension source checks
pnpm build
pnpm openapi:check
pnpm test:e2e

docker build -t applyai-api:ci services/api

cd services/api
uv run alembic upgrade head
uv run alembic check
uv run pytest
```

Lean-production validation additionally checks PostgreSQL durable-queue semantics, R2/AWS storage
compatibility, production fail-closed configuration, Railway bootstrap syntax and a production API
container build.

Infrastructure and repository gates also retain Terraform validation, CloudFormation/bootstrap
linting, GitHub workflow validation, screenshot/demo capture and PostgreSQL job-search/source
benchmarks so the optional AWS profile does not rot.

Do not reuse a historical PASS for a newer source-changing head.

## Deployment source

For the launch profile start with:

- [`DEPLOYMENT.md`](DEPLOYMENT.md)
- [`docs/RAILWAY_DEPLOYMENT.md`](docs/RAILWAY_DEPLOYMENT.md)
- [`docs/R2_STORAGE.md`](docs/R2_STORAGE.md)
- [`docs/deployment/VERCEL.md`](docs/deployment/VERCEL.md)
- [`docs/PRODUCTION_RELEASE_CHECKLIST.md`](docs/PRODUCTION_RELEASE_CHECKLIST.md)
- [`docs/PRODUCTION_RUNBOOK.md`](docs/PRODUCTION_RUNBOOK.md)

For the optional AWS scale profile see:

- [`infra/bootstrap/README.md`](infra/bootstrap/README.md)
- [`infra/staging/README.md`](infra/staging/README.md)
- [`docs/AWS_STAGING_DEPLOYMENT.md`](docs/AWS_STAGING_DEPLOYMENT.md)

## External boundary

The lean source/runtime path is implemented, but live production evidence still requires genuine
provider resources. Do not infer deployment from source support.

Critical launch provider acceptance includes:

```text
Railway project + PostgreSQL + API/worker deployment
Cloudflare R2 private bucket + live object acceptance
Clerk real signup/signin/JWT validation
Vercel dedicated ApplyAI Preview and Production deployment
real Open Jobs ingestion into the production database
full Preview and Production candidate journeys
```

Optional integrations such as Stripe, Resend, PostHog, Sentry and browser auto-submit may remain
disabled for the first free candidate launch, but the UI must not expose broken provider-dependent
actions.

See [`docs/PRODUCTION_RELEASE_CHECKLIST.md`](docs/PRODUCTION_RELEASE_CHECKLIST.md) for the exact
`LIVE_PREVIEW_VERIFIED` and `LIVE_PRODUCTION_VERIFIED` gates.
