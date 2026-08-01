# Prompt 3 Implementation Index

## Runtime

- `app/jobs/dispatcher.py` — transactional due-source and verification dispatch
- `app/workers/source.py` — dedicated source ingestion/discovery/verification worker
- `app/jobs/registry.py` — adaptive scheduling and lease recovery
- `app/jobs/source_authority.py` — primary-source authority and provenance
- `app/jobs/verifier.py` — bounded apply-link checks and closure evidence
- `app/jobs/quality.py` — measured quality/source coverage KPIs
- `app/jobs/closure_metrics.py` — measured evidence-to-closure latency
- `app/jobs/retention.py` — latest-preserving raw-payload cleanup

## Persistence

- `app/job_quality_models.py`
- `alembic/versions/b2f8d5e6a390_job_data_scale_quality.py`

## AWS

- dedicated source SQS + DLQ
- source worker ECS service
- bounded EventBridge dispatcher task
- source queue/DLQ/failure/throughput CloudWatch signals
- release/rollback/verification V2 workflows
- private reviewed-source bootstrap task

## Scale evidence

- `scripts/benchmark_job_search.py`
- `.github/workflows/job-search-benchmark.yml`
- `docs/JOB_DATA_PLATFORM_SCALE_REPORT.md`
- `docs/benchmarks/README.md`

This checkpoint changes no runtime behavior. It exists so all automated gates evaluate the complete, formatted Prompt 3 source set.
