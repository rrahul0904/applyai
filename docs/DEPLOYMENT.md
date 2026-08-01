# Deployment

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

## PLANNED production

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

Live deployment is BLOCKED until Clerk and AWS/Vercel environment ownership is
configured. No Cloudflare/Vinext deployment path is used.
