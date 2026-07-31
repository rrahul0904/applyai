# ApplyAI Job Source Connector Guide

## Purpose

A connector fetches one legitimate public source and converts every posting into the same `RawJobPosting` contract. Provider details must remain inside the connector rather than leaking into API routes, search code, or the canonical job pipeline.

## Connector responsibilities

Each implemented adapter must provide:

```python
class JobSourceConnector(ABC):
    key: str

    def source_company_identity(self) -> str: ...
    def fetch(self, checkpoint: dict | None) -> list[dict]: ...
    def normalize(self, payload: dict) -> NormalizedJob: ...
    def checkpoint(self) -> dict: ...
    def health(self) -> ConnectorHealth: ...
```

New V1 adapters also expose `to_raw(payload) -> RawJobPosting`. The compatibility helper `raw_from_connector` converts the existing Greenhouse/seed adapters until every legacy adapter is migrated directly.

## Public-access rule

Only use documented or otherwise legitimate public posting interfaces.

Do not implement:

- authenticated/private endpoint scraping;
- login bypass;
- CAPTCHA solving;
- proxy rotation to evade blocking;
- anti-bot fingerprint evasion;
- collection of candidate or recruiter private data.

When a provider denies automated access, classify/disable the source rather than attempting circumvention.

## Required identity

Every connector needs stable board/site and posting identity.

Examples:

```text
Greenhouse company identity: board token
Greenhouse posting identity: {board_token}:{post_id}

Lever company identity: site
Lever posting identity: {site}:{posting_id}

Ashby company identity: board name
Ashby posting identity: {board_name}:{posting_id}
```

Do not assume a provider posting ID is globally unique unless its documentation guarantees that.

## Required provenance

Populate:

- `source_type`;
- `source_name`;
- `source_company_identity`;
- `source_job_identity`;
- `external_job_id`;
- `internal_job_id` when present;
- `source_url`;
- `apply_url`;
- `fetched_at`;
- `source_updated_at` when present;
- raw payload;
- source metadata.

The source URL should point to the public job page or canonical provider posting. The apply URL should be the employer/provider application destination, not a fabricated route.

## Text handling

Preserve the provider's meaningful description. HTML may be converted to readable text, but do not discard the original payload.

Do not log complete descriptions during routine ingestion.

## Location and workplace type

Preserve all source locations in order.

Workplace type normalization is conservative:

- explicit remote -> REMOTE;
- explicit hybrid -> HYBRID;
- explicit onsite -> ONSITE;
- otherwise infer only from clear location text;
- otherwise UNKNOWN.

Do not invent city, state, country, or remote eligibility.

## Employment type

Map explicit source labels to:

```text
FULL_TIME
PART_TIME
CONTRACT
TEMPORARY
INTERNSHIP
OTHER
UNKNOWN
```

Unknown provider values remain OTHER/UNKNOWN rather than guessed.

## Compensation

Only populate compensation when the source explicitly returns it.

Preserve:

- minimum;
- maximum;
- currency;
- interval;
- source-reported provenance.

Never estimate salary from title, employer, location, or a third-party model in this ingestion layer.

## Pagination and budgets

A connector must have bounded pagination.

Lever V1 uses configurable page size and `max_pages`. Other providers should expose comparable bounded controls.

Do not loop indefinitely based only on provider cursors.

## Rate limiting and retry behavior

A connector should:

- use conservative request timeouts;
- identify itself with the ApplyAI ingestion user agent;
- respect 429 and `Retry-After` where supported;
- use bounded exponential retry with jitter for transient failures;
- avoid retrying permanent configuration/auth/not-found errors indefinitely.

The registry scheduler owns source-level backoff after failed runs.

## Health check

`health()` must perform a lightweight public check and return:

```python
ConnectorHealth(
    healthy: bool,
    checked_at: datetime,
    detail: str,
)
```

The detail must not include credentials, tokens, full payloads, or sensitive response content.

## Factory registration

Register the provider once in `JobSourceAdapterFactory`:

```python
if source_type == JobSourceType.PROVIDER:
    return ProviderConnector(...)
```

Do not add provider conditionals to routes, the scheduler, search, or candidate UI.

## Provider fixture tests

Every connector must have deterministic HTTP fixtures covering:

- normal response;
- empty source;
- malformed item;
- source-level HTTP failure;
- pagination/cursor behavior when applicable;
- provider identity;
- original source/apply URLs;
- location/work mode;
- compensation when exposed;
- repeated normalization determinism.

Tests must not rely on the live internet.

## Pipeline regression tests

In addition to parser fixtures, add PostgreSQL-backed tests for:

- first ingest creates one canonical job;
- identical ingest advances freshness without duplicate raw/version rows;
- material change creates one new `JobVersion`;
- invalid posting remains raw and non-searchable;
- successful disappearance changes source-level misses;
- failed/partial runs do not change freshness;
- reappearance restores ACTIVE;
- a fresh second source keeps the canonical job ACTIVE;
- dedup reason/provenance is retained.

## Adding a new provider checklist

1. Add/confirm `JobSourceType`.
2. Implement a connector using public access only.
3. Implement `to_raw`.
4. Register it in the factory.
5. Add configuration fields without secrets in JSON/logs.
6. Add deterministic HTTP fixtures.
7. Add database idempotency/change/freshness tests.
8. Add environment/operator documentation.
9. Run Alembic/OpenAPI/backend/full CI gates.
10. Validate a small explicit source set in staging before enabling a broad schedule.
