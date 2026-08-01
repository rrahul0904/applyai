# Prompt 3 Verification Gate

The Prompt 3 branch must not be described as complete until the exact branch head proves:

```text
web lint
web typecheck
Vitest
Next.js production build
OpenAPI contract drift
PostgreSQL backend tests
Alembic zero-to-head/current/drift
Candidate MVP Playwright
production API Docker build
Terraform fmt/provider init/validate
CloudFormation bootstrap validation
GitHub workflow validation
10K synthetic PostgreSQL EXPLAIN ANALYZE benchmark
```

Additional gates:

```text
50K synthetic PostgreSQL benchmark: manual
250K synthetic PostgreSQL benchmark: manual
real Greenhouse/Lever/Ashby AWS staging: external
real SQS/DLQ/worker recovery: external
real cost telemetry: external
```

No AI matching, embeddings, employer portal or search-engine replacement is authorized by this gate.
