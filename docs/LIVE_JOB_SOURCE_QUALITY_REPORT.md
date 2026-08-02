# ApplyAI live job-source quality report

Populate this document only from executed staging runs. Do not infer provider quality from fixtures, synthetic benchmarks or source-code coverage.

## Measurement identity

| Field | Value |
|---|---|
| Deployed Git SHA | `NOT EXECUTED` |
| AWS region | `BLOCKED — external input required` |
| Measurement window | `NOT EXECUTED` |
| Greenhouse sources | `NOT EXECUTED` |
| Lever sources | `NOT EXECUTED` |
| Ashby sources | `NOT EXECUTED` |
| Dispatcher enabled | `false` until manual validation passes |

## Provider results

| Provider | Sources attempted | Successful | Partial | Failed | Fetched | Valid | Invalid | Quarantined | Created | Updated | Unchanged | Deduplicated |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Greenhouse | | | | | | | | | | | | |
| Lever | | | | | | | | | | | | |
| Ashby | | | | | | | | | | | | |
| Career-site/JSON-LD URL imports | | | | | | | | | | | | |

Current status:

```text
NOT STARTED
```

## Quality and coverage

| Metric | Value | Numerator/denominator | Status |
|---|---:|---|---|
| Valid posting rate | | valid / fetched | NOT MEASURED |
| Invalid rate | | invalid / fetched | NOT MEASURED |
| Quarantine rate | | quarantined / fetched | NOT MEASURED |
| Deduplication rate | | deduplicated / accepted source postings | NOT MEASURED |
| Salary coverage | | jobs with explicit normalized compensation / active canonical jobs | NOT MEASURED |
| Structured location coverage | | jobs with validated structured location or remote status / active canonical jobs | NOT MEASURED |
| Workplace-type coverage | | REMOTE/HYBRID/ONSITE / active canonical jobs | NOT MEASURED |
| Valid apply-link rate | | VALID or expected REDIRECTED / links checked | NOT MEASURED |
| Average verification age | | current time − last verified time | NOT MEASURED |
| Source failure rate | | failed runs / completed attempts | NOT MEASURED |
| Reactivation rate | | reactivated jobs / jobs with prior inactive state | NOT MEASURED |

## Per-source execution evidence

Create one section per source:

```text
Provider:
Company:
Source registry ID:
Public source URL:
Source identity:
Trust classification:
Manual run 1 ID/status:
Manual run 2 ID/status:
Records fetched:
Valid/invalid/quarantined:
Created/updated/unchanged/deduplicated:
Duration:
Primary-source decisions:
Warnings or parser gaps:
```

A source passes only when:

- the endpoint is public and permitted;
- source identity and provenance are retained;
- initial ingestion succeeds;
- identical second pass is idempotent;
- unchanged records advance freshness without content versions;
- invalid records are explained rather than silently discarded;
- apply URLs and canonical source selection are correct;
- provider failure does not create false closure evidence.

## Multi-source deduplication

Record at least one real or controlled staging case:

| Evidence | Result |
|---|---|
| Canonical job ID | NOT STARTED |
| Linked source IDs | NOT STARTED |
| Dedup reason | NOT STARTED |
| Primary source | NOT STARTED |
| Source authority comparison | NOT STARTED |
| Field provenance | NOT STARTED |
| Lower-authority overwrite prevented | NOT STARTED |
| Lifecycle remains active with one fresh trusted source | NOT STARTED |

## Lifecycle evidence

| Transition/evidence | Result |
|---|---|
| Successful run missing posting → UNKNOWN according to threshold | NOT STARTED |
| Repeated successful misses → STALE | NOT STARTED |
| Explicit closure or repeated strong link evidence → CLOSED | NOT STARTED |
| Failed/partial run creates no negative evidence | NOT STARTED |
| Reappearing posting → ACTIVE | NOT STARTED |

## URL-import quality and safety

| Case | Result |
|---|---|
| Existing canonical job URL | NOT STARTED |
| New JSON-LD single-job page | NOT STARTED |
| Listing/search page quarantine | NOT STARTED |
| Robots-disallowed target | NOT STARTED |
| Private/loopback/link-local/metadata rejection | NOT STARTED |
| Redirect-hop revalidation | NOT STARTED |
| Oversized response budget | NOT STARTED |

## Known limitations

Record real parser gaps, provider-specific missing fields, blocked sites, ambiguous dedup candidates and quality risks. Do not convert uncertainty into a successful result.

## Final decision

Use one:

```text
COMPLETE
PARTIAL
BLOCKED
NOT STARTED
```

Current decision:

```text
NOT STARTED
```

Reason: no real provider source has been executed in AWS staging.
