# ApplyAI Global Job Supply — Metrics

Updated: 2026-08-08

## Principle

Job-supply metrics must be derived from runtime/database evidence. Unknown values remain `null`; synthetic scale tests are labeled separately and never counted as live inventory.

## Catalog overview

`GET /api/v1/internal/job-supply/quality`

and:

`GET /api/v1/internal/job-supply/overview`

provide the primary measured view.

## Organization coverage

Measured fields include:

```text
organizations_total
organizations_with_domains
organizations_with_career_sites
organizations_with_detected_ats
organizations_by_type
```

Organization counts describe rows actually loaded into the current database, not the design capacity.

## Source health

```text
sources_total
sources_enabled
sources_healthy
sources_blocked
sources_failing
sources_by_type
```

Use `/failures` for source- and run-level error detail.

## Canonical catalog

```text
raw_jobs_seen
canonical_active_jobs
canonical_closed_jobs
canonical_stale_jobs
canonical_total_jobs
source_postings
canonical_source_ratio
cross_source_jobs
orphan_source_jobs
```

A source posting is an observation. A canonical job is the deduplicated user-facing entity. Raw/source counts must not be marketed as active job inventory.

## Change rates

For the selected measurement window:

```text
new_jobs
updated_jobs
closed_jobs
reopened_jobs
new_jobs_per_hour
updated_jobs_per_hour
closed_jobs_per_hour
```

## Quality

```text
duplicate_percentage
invalid_percentage
quarantine_percentage
apply_url_validity_percentage
apply_urls_checked
salary_coverage_percentage
location_coverage_percentage
```

If no apply URL checks have been executed, `apply_url_validity_percentage` is `null`.

## Freshness

Active/unknown/stale jobs with a measured `last_seen_at` are bucketed as:

```text
lt_3h
lt_6h
lt_12h
lt_24h
gte_24h
```

Freshness measures last source observation; it is not a guarantee that the employer has not closed the role between checks.

## Source authority

`jobs_by_source_authority` summarizes the trust/provenance attached to primary job-source observations when that evidence is available. Missing trust metadata remains `UNKNOWN` instead of being inferred.

## Ingestion health

```text
ingestion_duration_p50_ms
ingestion_duration_p95_ms
source_failure_rate_percentage
run_count
average_verification_age_seconds
```

## Cost/efficiency

Measured instrumentation exposes:

```text
measured_worker_seconds
measured_network_bytes
measured_source_postings
measured_estimated_cost_usd
worker_seconds_per_1000_jobs
requests_per_1000_jobs
```

`requests_per_1000_jobs` remains `null` until request-count instrumentation exists. Dollar values remain `null` unless actual pricing assumptions are attached to recorded observations.

## Synthetic scale evidence

The source scheduler benchmark writes artifacts with:

```text
evidence_class = SYNTHETIC_SCALE_EVIDENCE
```

It measures PostgreSQL scheduling/lease behavior at 1K/10K/50K sources. It does not contribute to:

```text
organizations_total
sources_total
canonical_active_jobs
LIVE_PUBLIC_SOURCE_VERIFIED
```

The existing job-search benchmark similarly measures synthetic PostgreSQL search performance at configured row counts and is not production inventory.
