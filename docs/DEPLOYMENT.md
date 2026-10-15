# Deployment

> Current source-controlled target: Vercel web + FastAPI with Supabase Auth, PostgreSQL and private Storage. Production currently fails readiness (HTTP 503); see [the observed architecture state](LEAN_PRODUCTION_ARCHITECTURE.md). AWS below is an optional scale profile. Older Railway/Clerk instructions are historical.

## CURRENT local environment

- Official Next.js runs with `next dev`/`next build`.
- FastAPI runs with Uvicorn.
- PostgreSQL 17 runs through `compose.yaml` on port `55432`.
- Resume files use a local provider under an ignored data directory.

## Migration commands

From `services/api`:

```bash
DATABASE_URL=postgresql+psycopg://applyai:applyai@localhost:55432/applyai \
  uv run alembic upgrade head

DATABASE_URL=postgresql+psycopg://applyai:applyai@localhost:55432/applyai \
  uv run alembic downgrade -1

DATABASE_URL=postgresql+psycopg://applyai:applyai@localhost:55432/applyai \
  uv run alembic check
```

Production never creates tables at application startup.

## Optional AWS scale profile

- Web: Vercel-compatible Next.js deployment.
- API/workers: AWS ECS/Fargate containers behind an ALB.
- Database: Aurora PostgreSQL with pooling and backups.
- Objects: private S3.
- Queue: SQS with dead-letter queues.
- Cache: ElastiCache Redis/Valkey where needed.
- Infrastructure: Terraform, separate dev/staging/prod accounts or boundaries.

## Release gate

Apply migrations as an explicit release step; then deploy backward-compatible
application code. Require web build, API tests, migration zero-to-head test,
rollback test where safe, Alembic drift check, and environment validation.

Production release remains blocked until the current Vercel + Supabase runtime passes readiness and authenticated acceptance. Do not use Clerk or Railway settings from historical profiles as evidence for the current target.
