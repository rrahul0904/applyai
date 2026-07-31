# ApplyAI Job Source Platform V1

## Scope

Job Source Platform V1 extends the existing Candidate MVP from one configured Greenhouse ingestion path into a provider-neutral public job ingestion platform.

This milestone implements:

- first-class source registry;
- Greenhouse compatibility;
- public Lever and Ashby adapters;
- source-neutral raw posting contract;
- validation and quarantine-by-status;
- canonical job reuse and source provenance;
- generalized source health and ingestion-run metrics;
- bounded due-source scheduling;
- PostgreSQL-backed leases;
- protected internal operator APIs.

It does **not** implement employer publishing, AI matching, embeddings, auto-apply, anti-bot circumvention, or large-scale SQS ingestion workers. Career-site discovery is the next ordered milestone.

## Runtime architecture

```text
EventBridge
    |
    v
Fargate scheduled task: python -m app.jobs.ingest
    |
    +--> synchronize configured public ATS boards/sites
    |
    +--> claim due JobSourceRegistry rows
    |       - enabled
    |       - crawl allowed
    |       - next_run_at <= now
    |       - lease absent/expired
    |       - FOR UPDATE SKIP LOCKED
    |
    +--> JobSourceAdapterFactory
            |
            +--> Greenhouse public board adapter
            +--> Lever public postings adapter
            +--> Ashby public job-board adapter
                    |
                    v
              RawJobPosting
                    |
              validate/normalize
                    |
                    v
        existing canonical ingestion pipeline
                    |
          Company / Job / JobSourceLink
                    |
              PostgreSQL search
```

The scheduled task remains one bounded dispatcher. ApplyAI does not create one EventBridge rule for every employer.

## Two source concepts

### JobSourceRegistry

`job_source_registry` represents a fetchable source:

- Greenhouse board;
- Lever site;
- Ashby board;
- future career site;
- future XML/JSON feed;
- future user-submitted source;
- future employer-direct source.

It owns configuration, source health, schedule, failure counters, and leases.

### JobSource

The existing `job_sources` table remains posting-level provenance. One row represents one source posting identity such as:

```text
GREENHOUSE / example:127817
LEVER / example:lever-posting-id
ASHBY / example:ashby-posting-id
```

This separation avoids a destructive migration and lets multiple source postings link to one canonical `Job`.

## Source-neutral posting contract

Every adapter produces `RawJobPosting` with provider-independent fields:

- source type/name;
- source company and job identities;
- external/internal job identifiers;
- source and apply URLs;
- company name/domain;
- title and description;
- source location text and structured location collection;
- employment and workplace type;
- explicit source compensation;
- posted, valid-through, updated, and fetched timestamps;
- raw provider payload;
- source metadata;
- skills and requirements when supplied.

Provider-specific values are retained in the raw payload and source metadata rather than discarded.

## Adapter boundary

Provider-specific network and parsing logic is isolated behind `JobSourceConnector` implementations and `JobSourceAdapterFactory`.

Application routes and canonical ingestion code do not branch on providers.

Supported V1 adapters:

| Source | Access path | Identity |
|---|---|---|
| Greenhouse | public Job Board API | `{board_token}:{post_id}` |
| Lever | public Postings API | `{site}:{posting_id}` |
| Ashby | public job-board API | `{board_name}:{posting_id}` |

Future source types are represented in the enum but intentionally not treated as implemented connectors.

## Validation

A connector response is not automatically searchable.

`validate_raw_job` verifies at minimum:

- non-placeholder title;
- resolvable company name;
- meaningful description;
- HTTP/HTTPS source URL;
- HTTP/HTTPS apply URL;
- stable source identity;
- coherent salary range when supplied.

Possible outcomes:

- `VALID`;
- `VALID_WITH_WARNINGS`;
- `INVALID`;
- `QUARANTINED` (reserved for later discovery/crawler flows).

Invalid records are retained as raw postings with reason codes and are not linked to a searchable canonical job.

## Source lifecycle

Source health states:

```text
HEALTHY
DEGRADED
FAILING
DISABLED
BLOCKED
```

A successful complete run resets failures and records `last_success_at`.

A partial run becomes DEGRADED and does not apply negative freshness evidence.

A failed fetch becomes DEGRADED or FAILING based on consecutive failures, records a non-sensitive error category, and does not apply negative freshness evidence.

Disabled or blocked sources are not claimed by the scheduler.

## Canonical job freshness

Posting-level source misses remain independent.

```text
ACTIVE -> UNKNOWN -> STALE
```

`CLOSED` remains explicit-evidence-only.

Rules:

- one complete successful source run can increment a posting miss;
- failed or partial runs never increment misses;
- a canonical job remains ACTIVE while any linked source is fresh;
- a reappearing source posting resets its miss count and reactivates the canonical job;
- unchanged postings refresh `last_seen_at` without creating a content version.

## Scheduler and leases

The scheduler uses a bounded query over due registry rows.

Claim fields:

- `locked_at`;
- `locked_by`;
- `lease_expires_at`.

Claims use `FOR UPDATE SKIP LOCKED`, so two scheduler processes cannot claim the same source simultaneously. Expired leases can be reclaimed after worker failure.

The claim batch size, lease duration, default interval, retry backoff, request timeout, and page budget are configuration values.

## Retry and failure classification

Failure categories include:

- NETWORK;
- TIMEOUT;
- RATE_LIMITED;
- SOURCE_NOT_FOUND;
- INVALID_RESPONSE;
- PARSER_ERROR;
- AUTH_REQUIRED;
- BLOCKED;
- CONFIG_ERROR;
- DATABASE_ERROR;
- UNKNOWN.

Consecutive failures increase the next-run interval up to a configured maximum. Permanent blocking is an explicit operator/policy action, not an automatic attempt to evade source controls.

## Internal operations

Protected routes:

```text
GET    /api/v1/internal/job-sources
POST   /api/v1/internal/job-sources
GET    /api/v1/internal/job-sources/{id}
PATCH  /api/v1/internal/job-sources/{id}
POST   /api/v1/internal/job-sources/{id}/run
POST   /api/v1/internal/job-sources/{id}/disable
POST   /api/v1/internal/job-sources/{id}/enable
GET    /api/v1/internal/job-sources/{id}/runs
```

These routes use `X-ApplyAI-Internal-Token`, separate from candidate Clerk authorization. The token belongs in a secret store and must never be committed.

## Structured events

Operational events include source/run correlation identifiers and counts:

- `job_ingestion_started`;
- `job_ingestion_completed`;
- `job_ingestion_partial`;
- `job_ingestion_failed`;
- `job_ingestion_record_failed`;
- `job_source_run_failed`.

Logs do not intentionally include credentials, authorization headers, or full job descriptions.

## Ordered next milestone

Career-site discovery and user URL import remain blocked until this source platform passes migrations and CI. That work is specified separately and must reuse this registry and adapter architecture rather than redesign it.
