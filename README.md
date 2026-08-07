# ApplyAI

ApplyAI is a source-complete career platform spanning candidate job search, Career Intelligence,
resume/application/interview workflows, employer recruiting, billing, mobile and job capture.

The repository deliberately separates **source/platform completion** from **real external deployment
and provider acceptance**. Cloud accounts, provider secrets, signing identities and store
publication are never fabricated from repository source.

## Platform architecture

```text
Candidate Web: Next.js App Router + Clerk on Vercel
Candidate Mobile: Expo / React Native + Clerk
Browser Extension: Manifest V3 public-job URL handoff

                         HTTPS
                           |
                           v
                    AWS ALB / FastAPI
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
  Aurora PostgreSQL   private resume S3   task_outbox
                                             |
                                  queue-aware publishers
                                    /       |       \
                                   v        v        v
                              resume SQS source SQS AI SQS
                                   |        |        |
                                   v        v        v
                              resume    source    AI workers
                              worker    worker       |
                                |         |       model provider
                               DLQ       DLQ        DLQ

EventBridge -> bounded source dispatcher
CloudWatch  -> logs + alarms
```

The backend remains a modular monolith. ApplyAI does not add Kafka, Kubernetes, Redis or a
microservice split merely to simulate scale.

## Repository layout

```text
apps/web/               canonical Next.js candidate/employer/admin web
apps/extension/         Manifest V3 job-import extension
mobile/                 Expo / React Native candidate application
services/api/           FastAPI API + workers + migrations + evaluation
infra/bootstrap/        AWS/GitHub OIDC + Terraform-state bootstrap
infra/staging/          AWS staging Terraform
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
- AI Matches using semantic + explainable Career Intelligence ranking;
- application command center with status history and notes;
- candidate-approved application submission orchestration;
- Career Memory;
- evidence-locked resume/application/interview copilots;
- interview practice history and feedback;
- recruiter/referral contacts and follow-ups;
- job alerts, interview reminders and notification inbox;
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
AI SQS -> AI worker -> reviewed provider
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

Stripe account IDs, price IDs and secrets are real-environment configuration.

## Job-data platform

Dedicated adapters support Greenhouse, Lever and Ashby. The discovery layer recognizes Greenhouse,
Lever, Ashby, Workday, SmartRecruiters, Workable, iCIMS, Oracle and SuccessFactors, and can use the
bounded structured public-page importer when no reviewed public board API is available.

Source ingestion includes registry/scheduling/leasing, transactional dispatch, authority/provenance,
deduplication, freshness, closure evidence, apply-URL verification and quality metrics. Public-page
import enforces robots, redirect, SSRF and response-size controls. No authentication or anti-bot
circumvention is used to claim provider coverage.

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
notification preferences and inbox/read state. Real email/push delivery providers remain deployment
integrations.

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

Infrastructure and repository gates also include Terraform validation, CloudFormation/bootstrap
linting, GitHub workflow validation, screenshot/demo capture and 10K/50K/250K PostgreSQL job-search
benchmarks.

Do not reuse a historical PASS for a newer source-changing head.

## AWS staging and release source

Start with:

- [`infra/bootstrap/README.md`](infra/bootstrap/README.md)
- [`infra/staging/README.md`](infra/staging/README.md)
- [`docs/AWS_STAGING_DEPLOYMENT.md`](docs/AWS_STAGING_DEPLOYMENT.md)
- [`docs/CAREER_INTELLIGENCE_STAGING_ACCEPTANCE.md`](docs/CAREER_INTELLIGENCE_STAGING_ACCEPTANCE.md)
- [`docs/PRODUCTION_PROMOTION_CHECKLIST.md`](docs/PRODUCTION_PROMOTION_CHECKLIST.md)

The source-controlled runtime includes ALB, ECS/Fargate, Aurora, S3, ECR, resume/source/AI queues and
DLQs, workers, outbox publishers, migration task, source dispatcher, IAM and CloudWatch. Releases use
immutable full-SHA images and execute migrations before service activation.

## External boundary

The repository/source platform is complete. The remaining gates require genuine external resources
or distribution identities:

```text
AWS/Vercel/Clerk staging activation
real Candidate/S3/SQS/ECS/Aurora acceptance
real ATS-provider throughput/freshness/cost measurements
live OpenAI model + embedding acceptance
live Stripe checkout + webhook acceptance
real email/push provider delivery
production promotion + backup/restore/failure drills
Apple/Google signing + App Store/Play Store publication
browser-extension store publication
external Clerk identity deletion/revocation
```

Those are tracked as deployment/runtime/distribution blockers, not missing product source. See
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md),
[`docs/CURRENT_REPOSITORY_STATE.md`](docs/CURRENT_REPOSITORY_STATE.md) and
[`docs/PLATFORM_COMPLETION.md`](docs/PLATFORM_COMPLETION.md).
