# Prompt 3 Verification Gate

Prompt 3 adds source-quality controls, durable dispatch, source-worker infrastructure, measured PostgreSQL benchmark tooling, and staging release/rollback/verification templates.

## Current status

| Area | Status | Evidence required for COMPLETE |
|---|---|---|
| Prompt 1 source and automated verification | COMPLETE | Previously verified stacked head |
| Prompt 2 source and automated verification | COMPLETE | Previously verified stacked head |
| Prompt 3 source implementation | COMPLETE | Source code, migration, tests, Terraform and workflows are committed |
| Prompt 3 exact-head automated verification | PARTIAL | Current head must pass every workflow listed below |
| AWS staging deployment | BLOCKED | Requires real AWS, Clerk, Vercel, DNS/certificate and reviewed source inputs |
| Live Greenhouse/Lever/Ashby validation | BLOCKED | Requires deployed staging and reviewed public sources |
| Failure-recovery drills | BLOCKED | Requires real staging SQS/DLQ/ECS workers |
| AWS cost measurement | BLOCKED | Requires measured staging usage |
| AI matching | NOT STARTED | Remains blocked until the real-service Prompt 3 gate passes |

Current verification branch:

```text
agent/applyai-job-data-scale-quality
```

The exact head SHA must be taken from the final successful GitHub Actions run. Do not retain an older hard-coded SHA after the branch moves.

## Required exact-head workflows

The following workflows must all succeed against the same PR head:

- ApplyAI CI
- ApplyAI Demo Capture
- AWS Bootstrap Validation
- GitHub Workflow Validation
- Job Search Scale Benchmark

Within ApplyAI CI, the required jobs are:

- web lint
- web typecheck
- web tests
- Next.js production build
- OpenAPI contract drift
- API tests
- Alembic zero-to-head/current/drift
- production API image build
- staging Terraform fmt/init/validate
- Candidate MVP Playwright

## Benchmark evidence

The benchmark harness must run against the current canonical schema and record:

- requested and inserted row counts
- PostgreSQL version
- generation timestamp
- source commit/ref when executed in GitHub Actions
- planning and execution time
- buffer usage
- complete JSON execution plans
- explicit non-claims for Aurora, production, live-provider and AWS-cost validation

Run the synthetic gates in order:

1. 10,000 jobs
2. 50,000 jobs
3. 250,000 jobs

Do not treat committed JSON files alone as proof. The current harness must be reproducible from the exact source head.

## Staging gate

Automated source verification is not staging verification. AWS staging remains blocked until the real deployment proves:

- API, resume worker, source worker and source-aware outbox are healthy
- source SQS and DLQ redrive behavior works
- bounded EventBridge dispatch works
- Greenhouse, Lever and Ashby public sources ingest successfully
- second-pass ingestion is idempotent
- source leases recover after abandonment
- repeated closure evidence and reactivation work
- rollback V2 works
- quality and AWS cost observations are measured

## Frozen scope

Do not start AI matching, embeddings, pgvector ranking, OpenSearch, auto-apply, employer features, billing, mobile development, Kafka, Kubernetes, Redis, or a microservice split before the real-service gate passes.
