# ApplyAI

ApplyAI is a structured career platform that helps candidates discover relevant
jobs, prepare applications, and preserve their job-search history.

The repository is currently focused on the Candidate MVP and legitimate real-job
ingestion. Advanced AI, employer, mobile, and public-launch work is intentionally
paused until the candidate workflow and job-data foundation are verified.

## Repository

```text
apps/
  web/                 Official Next.js App Router client
services/
  api/                 FastAPI modular monolith
  api/app/workers/     Durable background workers
docs/                  Product and architecture decisions
compose.yaml           Local PostgreSQL
```

## Prerequisites

- Node.js 22+
- pnpm 10+
- Python 3.12+
- uv
- PostgreSQL 17, or Docker

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

## Resume processing

Development uses the in-memory queue and may process resumes from the API's local
background-task path for a deterministic developer experience.

Production is guarded to require SQS. Configure:

```text
TASK_QUEUE_PROVIDER=sqs
SQS_QUEUE_URL=...
SQS_REGION=us-east-1
OBJECT_STORAGE_PROVIDER=s3
S3_BUCKET=...
```

Then run the worker independently from the API container:

```bash
cd services/api
uv run python -m app.workers.resume
```

Configure an SQS dead-letter queue/redrive policy so repeated parser failures are
bounded and observable.

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

The connector preserves raw source payloads and source provenance. It does not
submit applications or scrape authenticated/private career systems.

## Validation

```bash
pnpm build
pnpm lint
DATABASE_URL=postgresql+psycopg://applyai:applyai@localhost:55432/applyai_test \
  pnpm test:api
```

The implementation status and evidence are in
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).
