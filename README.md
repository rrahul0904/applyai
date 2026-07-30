# ApplyAI

ApplyAI is a structured candidate career platform for job discovery, application preparation, and durable job-search history.

The repository is intentionally focused on the Candidate MVP, reliable public-job ingestion, and deployment readiness. AI matching, embeddings, mobile, employer workflows, billing, and auto-apply stay gated until the real staging Candidate MVP is verified.

## Architecture

```text
Vercel
  Next.js App Router + Clerk
             |
             | HTTPS
             v
AWS ALB -> ECS/Fargate FastAPI
                |
                +-> Aurora PostgreSQL
                +-> private S3 resume storage
                +-> PostgreSQL transactional outbox
                              |
                              v
                            SQS -> resume worker
                              |
                              +-> DLQ

EventBridge -> Greenhouse ingestion Fargate task
CloudWatch  -> logs + alarms
```

Repository layout:

```text
apps/web/               Next.js candidate web
services/api/           FastAPI modular monolith + workers
infra/bootstrap/        one-time AWS/GitHub OIDC bootstrap
infra/staging/          validated staging Terraform
docs/                   architecture, status, deployment and recovery runbooks
compose.yaml             local PostgreSQL
```

## Local development

Prerequisites:

- Node.js 22+
- pnpm 10+
- Python 3.12+
- uv
- PostgreSQL 17 or Docker

Setup:

```bash
docker compose up -d postgres
pnpm install
uv sync --system-certs --project services/api
```

Create the API test database once:

```bash
docker compose exec -T postgres createdb -U applyai applyai_test
```

Apply migrations:

```bash
cd services/api
DATABASE_URL=postgresql+psycopg://applyai:applyai@localhost:55432/applyai \
  uv run alembic upgrade head
```

Run web/API:

```bash
pnpm dev
pnpm dev:api
```

See `apps/web/.env.example` and `services/api/.env.example` for development configuration.

## Durable resume lifecycle

Development may use controlled local storage and an in-memory queue. Staging/production are fail-closed around the durable path:

```text
Browser
  -> FastAPI upload intent
  -> presigned private-S3 PUT
  -> FastAPI upload-complete / S3 HEAD verification
  -> PostgreSQL transaction
       ResumeVersion -> QUEUED
       task_outbox    -> RESUME_PARSE
  -> outbox publisher
  -> SQS
  -> resume worker
  -> ResumeExtraction NEEDS_REVIEW
  -> candidate confirmation
  -> COMPLETED + USER_VERIFIED profile
```

Durable environments require real S3, SQS + DLQ, Clerk, HTTPS `WEB_ORIGIN`, and PostgreSQL. Resume bytes bypass the Vercel BFF.

Useful worker/operator commands:

```bash
cd services/api
uv run python -m app.core.outbox
uv run python -m app.workers.resume
uv run python -m app.ops.dlq --limit 10
```

The DLQ inspection path intentionally reports task identifiers rather than raw resume content.

## Greenhouse ingestion

ApplyAI ingests explicit public Greenhouse Job Board tokens only:

```text
GREENHOUSE_BOARD_TOKENS=["example-company","another-company"]
```

Run manually:

```bash
cd services/api
uv run python -m app.jobs.ingest
```

The pipeline preserves board-scoped source identity, raw provenance and source timestamps; repeat fetches refresh `last_seen_at`; material source changes update the canonical job/search document and create job versions; successful complete board runs drive ACTIVE -> UNKNOWN -> STALE freshness while failed/partial runs do not create negative freshness evidence.

## Candidate E2E

The deterministic Playwright journey runs real Next.js + FastAPI + PostgreSQL while CI is allowed controlled substitutes for auth/storage/queue. It covers Candidate A onboarding/resume/search/save/application/status/note/relogin persistence and Candidate B isolation.

```bash
uv run --project services/api python services/api/scripts/create_e2e_resume.py /tmp/applyai-e2e-resume.docx
E2E_RESUME_PATH=/tmp/applyai-e2e-resume.docx pnpm test:e2e
```

Real staging must replace those controlled substitutes with Clerk, S3, SQS/DLQ and ECS workers.

## Production API image

API, resume worker, outbox publisher, migration task and Greenhouse ingestion use the same immutable image with role-specific commands:

```bash
docker build -t applyai-api:local services/api
```

The image runs as a non-root user. Staging releases tag ECR images with the full Git commit SHA.

## AWS staging deployment package

Start here:

- [`infra/bootstrap/README.md`](infra/bootstrap/README.md) — one-time AWS state/OIDC bootstrap
- [`infra/staging/README.md`](infra/staging/README.md) — Terraform stack
- [`docs/AWS_STAGING_DEPLOYMENT.md`](docs/AWS_STAGING_DEPLOYMENT.md) — complete operator runbook
- [`docs/PRODUCTION_PROMOTION_CHECKLIST.md`](docs/PRODUCTION_PROMOTION_CHECKLIST.md) — production gate after staging
- [`infra/staging/github.environment.example`](infra/staging/github.environment.example) — GitHub `staging` environment manifest
- [`apps/web/.env.staging.example`](apps/web/.env.staging.example) — Vercel/Clerk staging template

Deployment sequence:

```text
1. CloudFormation bootstrap
      state S3 + GitHub OIDC + staging deploy role
2. GitHub staging environment
      AWS/ACM/Clerk/domain variables
3. ApplyAI Staging Preflight
      OIDC + state + ACM + Clerk prerequisite checks
4. ApplyAI Staging Infrastructure
      plan -> dormant AWS foundation apply
5. API DNS -> ALB
6. ApplyAI Staging Release
      immutable image -> migration -> service activation -> health/readiness
7. ApplyAI Staging Infrastructure Verification
      ECS/ALB/Aurora/S3/SQS/DLQ/CloudWatch checks
8. real Candidate A/B acceptance + failure injection
9. rollback/recovery drills
```

Normal deployment workflows use GitHub OIDC and require no long-lived `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` credentials.

The first infrastructure apply deliberately leaves API/worker/outbox desired counts at zero and scheduled ingestion disabled. The release workflow runs Alembic from the exact image before changing application services and aborts service activation on migration failure.

`ApplyAI Staging Rollback` can restore a previous immutable application image. Database schema remains roll-forward; rollback images must remain compatible with the current schema.

## Validation

Application/runtime gates:

```bash
pnpm lint
pnpm --dir apps/web typecheck
pnpm test:web
pnpm build
pnpm openapi:check
pnpm test:e2e

docker build -t applyai-api:ci services/api

cd services/api
uv run alembic upgrade head
uv run alembic check
uv run pytest
```

Infrastructure source gates:

```bash
terraform -chdir=infra/staging fmt -check -recursive
terraform -chdir=infra/staging init -backend=false
terraform -chdir=infra/staging validate

cfn-lint infra/bootstrap/applyai-staging-bootstrap.yaml
actionlint
```

GitHub CI independently exercises application tests/builds/migrations, OpenAPI drift, Docker build, Terraform validation, Candidate MVP Playwright, CloudFormation bootstrap lint and workflow static analysis.

Do not reuse historical PASS results for a newer source-changing head. Current evidence and external deployment boundaries are recorded in [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).
