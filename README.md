# ApplyAI

ApplyAI is a structured career platform that helps candidates discover relevant
jobs, prepare applications, and preserve their job-search history.

The repository is currently focused on the Candidate MVP and legitimate real-job
ingestion. Advanced AI, employer, mobile, and public-launch work is intentionally
paused until the candidate workflow and staging foundation are verified.

## Repository

```text
apps/
  web/                 Official Next.js App Router client
services/
  api/                 FastAPI modular monolith
  api/app/workers/     Durable background workers
infra/
  staging/             AWS staging Terraform; Vercel and Clerk remain external
docs/                  Product and architecture decisions
compose.yaml           Local PostgreSQL
```

## Prerequisites

- Node.js 22+
- pnpm 10+
- Python 3.12+
- uv
- PostgreSQL 17, or Docker
- Terraform 1.9+ for staging infrastructure work

## Local setup

```bash
docker compose up -d postgres
pnpm install
uv sync --system-certs --project services/api
```

Create `applyai_test` once for the API tests:

```bash
docker compose exec -T postgres createdb -U applyai applyai_test
```

Apply migrations:

```bash
cd services/api
DATABASE_URL=postgresql+psycopg://applyai:applyai@localhost:55432/applyai \
  uv run alembic upgrade head
```

Run the applications:

```bash
pnpm dev
pnpm dev:api
```

Authentication requires the Clerk values documented in
`apps/web/.env.example` and `services/api/.env.example`.

## Resume upload and processing

Development may use the local object store, in-memory queue, and API background
processor for a deterministic developer experience.

Staging/production use the durable path:

```text
Browser
  ↓ create upload intent
FastAPI
  ↓ presigned PUT
private S3
  ↓ upload-complete verification
PostgreSQL transaction
  ├─ ResumeVersion → QUEUED
  └─ task_outbox RESUME_PARSE
          ↓
outbox publisher
          ↓
SQS + configured DLQ
          ↓
resume worker
          ↓
ResumeExtraction → NEEDS_REVIEW
          ↓ candidate confirmation
COMPLETED + USER_VERIFIED profile
```

Configure the durable providers:

```text
TASK_QUEUE_PROVIDER=sqs
SQS_QUEUE_URL=...
SQS_DLQ_URL=...
SQS_REGION=us-east-1
SQS_MAX_RECEIVE_COUNT=5
SQS_VISIBILITY_TIMEOUT_SECONDS=300
SQS_VISIBILITY_HEARTBEAT_SECONDS=120
RESUME_PROCESSING_TIMEOUT_SECONDS=900
OBJECT_STORAGE_PROVIDER=s3
S3_BUCKET=...
```

The S3 bucket must be private. Its CORS policy must allow browser `PUT` from the
configured `WEB_ORIGIN`, including `Content-Type` and
`x-amz-server-side-encryption` request headers. No AWS credentials are exposed to
the browser; the API returns short-lived object-specific presigned URLs.

Run the outbox publisher and worker independently from the API container:

```bash
cd services/api
uv run python -m app.core.outbox
uv run python -m app.workers.resume
```

Configure the SQS redrive policy so `resume-processing` moves exhausted messages
to `resume-processing-dlq`; the AWS `maxReceiveCount` should match
`SQS_MAX_RECEIVE_COUNT`. `SQS_VISIBILITY_TIMEOUT_SECONDS` defines the broker
visibility lease, `SQS_VISIBILITY_HEARTBEAT_SECONDS` renews it while work is
active, and `RESUME_PROCESSING_TIMEOUT_SECONDS` determines when a persisted
PROCESSING attempt is stale enough to recover.

Operators can inspect failed task identifiers without printing raw queue payloads
or candidate resume content:

```bash
cd services/api
uv run python -m app.ops.dlq --limit 10
```

The API intentionally does not make RDS Proxy a hard dependency. Enable RDS Proxy
when connection pressure from horizontally scaled API/worker tasks, failover
requirements, or database connection churn justify it; SQLAlchemy pool settings
are configurable through the API environment first.

## Greenhouse ingestion

ApplyAI includes a connector for Greenhouse's public Job Board GET API. Configure
explicit board tokens as a JSON array:

```text
GREENHOUSE_BOARD_TOKENS=["example-company","another-company"]
```

Run ingestion:

```bash
cd services/api
uv run python -m app.jobs.ingest
```

The connector preserves board-scoped source identity, raw source payloads, source
provenance, Greenhouse update metadata, and fetch times. Company source mapping,
deterministic source identity, canonical deduplication, versioning, and miss-based
freshness transitions are handled before jobs are exposed through ACTIVE search.
It does not submit applications or scrape authenticated/private career systems.

## Candidate E2E

The deterministic Playwright journey exercises the real Next.js and FastAPI
processes against PostgreSQL. CI is allowed to substitute controlled dev auth,
local object storage, and an in-memory task queue; the staging journey must use
real Clerk, S3, SQS/DLQ, and ECS workers.

With local PostgreSQL and migrations ready:

```bash
uv run --project services/api python services/api/scripts/create_e2e_resume.py /tmp/applyai-e2e-resume.docx
E2E_RESUME_PATH=/tmp/applyai-e2e-resume.docx pnpm test:e2e
```

The CI job owns database migration, deterministic job seeding, the generated DOCX
fixture, Chromium installation, and the Candidate A/Candidate B isolation flow.

## Production API image

The API, resume worker, outbox publisher, migration task, and Greenhouse ingestion
task use one immutable container image with different commands:

```bash
docker build -t applyai-api:local services/api
```

The image runs as a non-root user. CI builds it on every verification run before
staging activation.

## Staging infrastructure

AWS staging Terraform lives in [`infra/staging`](infra/staging/README.md). It
covers VPC/subnets/security groups, HTTPS ALB, ECS/Fargate, ECR, Aurora
PostgreSQL, private S3 resume storage, SQS/DLQ, IAM, CloudWatch, and EventBridge.
Vercel remains the web host and Clerk remains the identity provider.

The first Terraform apply deliberately leaves API/worker/outbox desired counts at
zero and scheduled ingestion disabled. Push the exact image, run the migration
task, then activate services. Infrastructure source is not equivalent to a
verified staging deployment; real AWS + Clerk + Vercel execution is required for
that status.

## Validation

```bash
pnpm lint
pnpm --dir apps/web typecheck
pnpm test:web
pnpm build
pnpm openapi:check
pnpm test:e2e

docker build -t applyai-api:ci services/api

terraform -chdir=infra/staging fmt -check -recursive
terraform -chdir=infra/staging init -backend=false
terraform -chdir=infra/staging validate

cd services/api
uv run alembic upgrade head
uv run alembic check
uv run pytest
```

GitHub CI runs lint, typecheck, Vitest, production build, OpenAPI contract drift,
Alembic validation, backend tests, Candidate MVP Playwright, the production API
container build, and staging Terraform validation independently. The workflow can
also be started manually through `workflow_dispatch` when a fresh verification run
is needed without creating a source-only commit.

Do not reuse historical test counts as verification for a newer PR head. The
implementation status and evidence are in
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).
