# Architecture

## Approved system

```text
                           APPLYAI
                              │
              ┌───────────────┼────────────────┐
              │               │                │
         CANDIDATE WEB    MOBILE (planned)  EMPLOYER WEB (planned)
         Next.js App      Expo RN           Next.js App
              └───────────────┼────────────────┘
                              │ HTTPS / JSON
                         FastAPI API
                              │
          ┌───────────────────┼────────────────────┐
          │                   │                    │
   PostgreSQL + pgvector  SearchProvider        TaskQueue
   canonical data         PostgreSQL now        SQS production
          │               OpenSearch later          │
          ├──────────── ObjectStorageProvider       ├─ resume processing
          │             local dev / S3 prod         ├─ job ingestion
          └──────────── Redis/Valkey later           └─ matching/AI later
```

## CURRENT

- pnpm workspace.
- Official Next.js 16 App Router web application.
- FastAPI modular monolith under `services/api`.
- SQLAlchemy 2 models using PostgreSQL UUID, JSONB, constraints, and indexes.
- Alembic-only schema changes.
- Clerk RS256/JWKS token verification boundary.
- User ownership derived server-side from the authenticated session.
- `ObjectStorageProvider`, `TaskQueue`, `SearchProvider`, and
  `JobSourceConnector` interfaces.
- Local/S3 object storage implementations and local/SQS queue implementations.

## PLANNED

- Complete candidate UI consuming the FastAPI API.
- Resume parsing workers and candidate verification workflow.
- Development seed ingestion through the connector pipeline.
- One legitimate provider connector.
- PostgreSQL full-text search and pgvector retrieval.

## FUTURE SCALE

- Aurora PostgreSQL, ECS/Fargate workers, ElastiCache, and SQS.
- OpenSearch behind the existing `SearchProvider`.
- Extract independently scaled services only when throughput or ownership
  boundaries justify them.

## Portability

The web application is Vercel-compatible. The API and workers are container
deployable. Business logic has no Cloudflare D1, Vinext, or Worker binding
dependency.
