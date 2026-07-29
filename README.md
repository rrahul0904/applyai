# ApplyAI

ApplyAI is a structured career platform that helps candidates discover relevant
jobs, prepare applications, and preserve their job-search history.

The repository is currently in a foundation-validation milestone. Advanced AI,
employer, mobile, and public-launch work is intentionally paused.

## Repository

```text
apps/
  web/                 Official Next.js App Router client
services/
  api/                 FastAPI modular monolith
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

## Validation

```bash
pnpm build
pnpm lint
DATABASE_URL=postgresql+psycopg://applyai:applyai@localhost:55432/applyai_test \
  pnpm test:api
```

The implementation status and evidence are in
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md).
