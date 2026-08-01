# ApplyAI Benchmark Evidence

Benchmark artifacts in this directory must be produced by executable workflows or clearly labeled static methodology files.

## Job search scale

Run:

```text
Job Search Scale Benchmark
```

Supported synthetic non-production sizes:

```text
10,000
50,000
250,000
```

The workflow applies every Alembic migration to PostgreSQL 17, creates deterministic synthetic jobs, runs `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, uploads the JSON artifact, and removes the synthetic rows.

A size may be marked PASS only when its exact workflow run succeeds.

Do not infer:

- 50K results from 10K;
- 250K results from 50K;
- one million support from 250K synthetic data;
- Aurora behavior from GitHub-hosted PostgreSQL;
- AWS cost from local worker duration;
- real source quality from synthetic jobs.

## Required recorded fields

Each JSON artifact contains:

- requested and inserted row count;
- seed duration;
- database size after seed;
- query planning and execution times;
- top plan node;
- estimated and actual rows;
- shared hit/read blocks when reported;
- explicit synthetic environment label.

## Promotion rule

PostgreSQL remains the search backend until measured behavior demonstrates a concrete limitation that cannot reasonably be addressed through query/index/schema improvements.

OpenSearch must not be added based only on anticipated scale.
