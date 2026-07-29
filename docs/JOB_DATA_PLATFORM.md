# Job Data Platform

## Canonical pipeline

```text
Connector fetch
→ JobSource
→ RawJobPosting
→ normalize
→ canonical Company
→ canonical Job
→ source link / dedup decision
→ versions and status history
→ search index
```

## CURRENT

- Canonical company, job, source, raw payload, location, compensation, skill,
  requirement, version, and status-history tables.
- `JobSourceConnector` contract with `fetch`, `normalize`, `checkpoint`, and
  `health`.
- `DevelopmentSeedConnector` for deterministic development ingestion.
- Source external ID and raw content-hash uniqueness.
- First/last-seen timestamps and non-destructive status history.

## Deduplication design

Exact signals:

1. Connector key plus external ID.
2. Normalized application URL.
3. Canonical company source identity.

Probabilistic signals:

- normalized title;
- location overlap;
- posting date proximity;
- description similarity.

Source rows are never deleted when merged. The canonical link stores the
decision and confidence.

## PLANNED

Implement the ingestion service and one supported public provider—initially
Greenhouse or another provider with a legitimate public API—after the candidate
foundation remains green. Seed data must stay isolated and visibly labeled.

## Freshness

Jobs move through `ACTIVE`, `POSSIBLY_CLOSED`, `CLOSED`, and `ARCHIVED`. A source
disappearance changes status only after connector-specific confirmation rules.
