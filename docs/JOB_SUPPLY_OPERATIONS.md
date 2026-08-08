# ApplyAI Global Job Supply — Operations

Updated: 2026-08-08

## Operator surfaces

Primary UI:

```text
/admin
```

Internal API prefix:

```text
/api/v1/internal/job-supply
```

The internal token remains server-side. Browser clients must not receive it.

## Main endpoints

```text
GET  /overview
GET  /providers
PATCH /providers/{provider_key}
GET  /organizations
POST /organizations/{organization_id}/discover
GET  /sources
GET  /sources/{source_id}
GET  /runs
GET  /failures
GET  /dedup-review
POST /dedup-review/{candidate_id}/decision
GET  /quality
POST /sources/{source_id}/enable
POST /sources/{source_id}/disable
POST /sources/{source_id}/refresh
PATCH /sources/{source_id}/reclassify
```

`/summary` and `/capabilities` remain compatibility endpoints.

## Organization loading

Validate a normalized organization file:

```bash
uv run --project services/api python -m scripts.import_organizations \
  --file organizations.csv \
  --dataset reviewed-source \
  --dry-run
```

Load an authoritative dataset shape:

```bash
uv run --project services/api python -m scripts.import_organizations \
  --file dataset.csv \
  --dataset-type sec|ipeds|cms|irs|government \
  --dry-run
```

Remove `--dry-run` only after the validation output is reviewed.

## Source discovery

Organizations with a verified domain or careers URL can be queued from `/admin` or the internal organization-discovery endpoint. Discovery is asynchronous and uses the existing transactional outbox / source worker path.

Do not trigger mass discovery synchronously from a browser/API loop.

## Source controls

### Enable

Enabling a source permits scheduling only when `crawl_allowed=true`.

### Disable

Disabling clears leases and marks the source disabled. It does not delete source provenance or canonical jobs.

### Schedule refresh

`POST /sources/{id}/refresh` moves `next_run_at` to the current time. It does not perform the external fetch inside the operator HTTP request.

### Reclassification

Source type/trust/policy may be changed only as an operator action and should be evidence-driven. Setting `crawl_allowed=false` immediately blocks the source and clears leases.

## Provider policy

Provider policy is seeded from `app.jobs.source_capabilities` and can be inspected through `/providers`.

Fields include:

```text
access_mode
implementation_status
requires_credentials
requires_partnership
robots_policy
rate_limit_policy
pagination_strategy
supports_delta
supports_closure_detection
trust_level
allowed_for_automated_ingestion
reason
last_verified_at
```

Do not change a partnership-gated marketplace to automated ingestion merely because its pages are technically reachable.

## Authorized/licensed feeds

Authorized feed registry configuration supports:

```json
{
  "feed_url": "https://provider.example/approved-feed.json",
  "provider_key": "contracted-provider",
  "source_identity": "contract-account-or-feed",
  "feed_format": "json",
  "field_map": {
    "id": "job_id",
    "title": "title",
    "company": "company",
    "description": "description",
    "apply_url": "apply_url"
  },
  "authoritative_snapshot": false,
  "trust_level": "LICENSED_FEED"
}
```

Enable `authoritative_snapshot` only if the provider contract guarantees complete inventory for the configured scope.

## Dedup review

Dedup candidates in the review queue are ambiguous pairs below the automatic-merge threshold. Approving/rejecting a review records the operator decision. Approval does not silently execute a canonical merge; canonical mutation should remain a separately audited operation.

## Acceptance

Blocking acceptance:

```bash
pnpm job-supply:acceptance
```

Diagnostic acceptance:

```bash
pnpm job-supply:acceptance:report
```

`BLOCKED_EXTERNAL_CONFIGURATION` is expected until real organization/source/runtime evidence exists.

## Scale evidence

The source-scheduler GitHub workflow measures:

```text
1,000 sources
10,000 sources
50,000 sources
```

It checks PostgreSQL claim throughput, batch latency, unique leases and second-worker conflicts. Artifacts must be described as `SYNTHETIC_SCALE_EVIDENCE`.

## Failure handling

Investigate failures in this order:

1. source policy / robots state
2. credential/partnership dependency
3. 429 / Retry-After
4. timeout / network error
5. provider response/schema change
6. normalization failure
7. database/outbox/worker failure

Do not respond to blocked/429 behavior with proxy rotation, CAPTCHA solving or private-session automation.

## Freshness and closure

Latest source completeness is recorded as:

```text
FULL_SNAPSHOT
PAGINATED_FULL_SNAPSHOT
DELTA
PARTIAL
TRUNCATED
UNKNOWN_COMPLETENESS
```

Only full snapshot classes are closure authority. Generic employer career extraction and partial licensed feeds are not absence-based closure authority.

## Incident rule

When source behavior changes unexpectedly, disable the individual source/provider path first, preserve raw/provenance evidence, and investigate. Do not globally delete jobs or source observations to hide an ingestion defect.
