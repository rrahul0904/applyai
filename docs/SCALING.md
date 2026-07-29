# Scaling

## CURRENT: foundation

- FastAPI modular monolith.
- PostgreSQL canonical store.
- Provider boundaries for search, storage, queue, and ingestion.
- Stateless web/API design.

## Stage A: 0–10K users

- Vercel web.
- Containerized FastAPI and workers.
- Managed PostgreSQL with pgvector.
- S3, SQS, small worker pool, Redis/Valkey where justified.
- PostgreSQL search.

## Stage B: 10K–250K users

- Horizontal API and worker autoscaling.
- Connection pooling and read replicas.
- OpenSearch if relevance/facet requirements justify it.
- Dedicated ingestion workers and batch recommendations.

## Stage C: 250K–millions

Extract high-throughput domains only after measured need: ingestion, search,
recommendations, notifications, AI orchestration, or applications. Event
streaming is introduced only when SQS semantics are insufficient.

## Invariants

PostgreSQL remains authoritative. Search is rebuildable. Queue handlers are
idempotent. Cache is never the source of truth. High-volume history tables may
be partitioned after query evidence supports it.
