# ApplyAI Job Data Provenance and Deduplication

## Principle

ApplyAI stores one candidate-facing canonical job while retaining every legitimate source posting that supports it.

```text
Canonical Job
    |
    +-- Greenhouse posting
    +-- Lever posting
    +-- Ashby posting
    +-- future employer career page
    +-- future licensed feed
```

The platform must never lose where a field or application link came from.

## Data layers

### Source registry

`JobSourceRegistry` represents a board/site/feed and stores:

- provider/source type;
- stable source identity;
- base/career URL;
- non-secret configuration;
- trust level;
- schedule;
- health;
- lease state.

### Posting provenance

`JobSource` represents one source posting and stores:

- connector key;
- provider-scoped external job ID;
- source/apply URL;
- first/last seen timestamps;
- source registry ID in checkpoint metadata;
- source company/job identity;
- internal requisition ID when available;
- canonicalized apply URL;
- validation outcome;
- last verified timestamp;
- source-specific miss count;
- dedup reason.

### Raw payload

`RawJobPosting` stores the original provider payload and a material content hash.

Fetched-at-only changes are excluded from the material hash so a routine refresh does not create duplicate raw rows or job versions.

### Canonical job

`Job` contains the selected candidate-facing representation used by PostgreSQL search.

`JobSourceLink` provides the many-source-to-one-job relationship.

`JobVersion` records material canonical changes.

## Company resolution

Company resolution follows strong identities before names:

1. existing provider company/source identity;
2. future verified company domain;
3. existing source mapping;
4. exact normalized company name;
5. create a new canonical company.

A fuzzy company-name match alone must not merge legal entities.

## URL canonicalization

Canonicalization is conservative:

- lower-case scheme/host;
- remove fragments;
- remove default ports;
- trim non-root trailing slash;
- remove known tracking parameters;
- preserve unknown/query identifiers required to locate the posting.

Only HTTP/HTTPS URLs are accepted by the public-job validation layer.

## Deduplication order

Deduplication is deterministic and explainable.

### 1. Exact source identity

```text
provider + provider-scoped external job ID
```

This is the strongest same-source identity and should always reuse the existing posting link.

Reason:

```text
EXACT_SOURCE_ID
```

### 2. Exact canonical apply URL

If a different source points to the same safely canonicalized application URL, link it to the existing canonical job.

Reason:

```text
EXACT_APPLY_URL
```

Do not remove query parameters that carry job or requisition identity.

### 3. Internal requisition identity

When a provider exposes a stable requisition ID, use:

```text
company + internal requisition ID
```

Reason:

```text
INTERNAL_REQUISITION_ID
```

Provider IDs are not presumed globally unique.

### 4. Deterministic content fingerprint

Use a strict combination such as:

- canonical company;
- normalized title;
- normalized primary location;
- employment type where known;
- normalized description fingerprint.

Reason:

```text
CONTENT_FINGERPRINT
```

A title-only match is never sufficient.

### 5. Explainable heuristic match

V1 preserves the existing conservative company/title/location/description matching behavior and its non-perfect confidence.

Reason:

```text
HEURISTIC_MATCH
```

No embeddings or opaque AI similarity are used in this milestone.

### 6. New canonical job

When no candidate passes the deterministic rules:

```text
NEW_CANONICAL_JOB
```

## Confidence

Perfect confidence is reserved for exact deterministic identity.

A heuristic/content match must not be stored as `1.0000`. The existing conservative content match remains `0.8500` until staging evidence justifies a different explicit threshold.

Do not present confidence as a probability of factual correctness.

## Primary source

The source link that creates a new canonical job is initially primary.

Prompt 1 does not yet implement a full authority/freshness conflict resolver. The scale milestone will choose `primary_source_link_id` using:

- employer ownership;
- official ATS authority;
- freshness;
- apply URL quality;
- provider reliability.

A recently fetched third-party copy must not automatically outrank an employer/official ATS source.

## Material change detection

Create a new `JobVersion` for changes to candidate-facing content, including:

- title;
- description;
- location/workplace type;
- employment type;
- seniority;
- explicit compensation;
- source apply URL when it affects canonical application behavior;
- skills/requirements when supplied.

Do not create a version for:

- `fetched_at`;
- `last_seen_at`;
- source health;
- scheduler lease metadata;
- identical provider payload.

## Freshness and multiple sources

Every source posting has its own miss count.

The canonical status is selected from all linked sources:

```text
any source fresh                       -> ACTIVE
all sources past unknown threshold     -> UNKNOWN
all sources past stale threshold       -> STALE
all trusted sources explicitly closed  -> CLOSED
```

A failed or partial source run does not count as evidence that a posting disappeared.

A reappearing source resets its miss count and can reactivate the canonical job.

## Validation provenance

The posting checkpoint records:

- validation status;
- errors;
- warnings;
- source metadata;
- source registry ID.

Invalid records are retained for audit/connector repair but remain unlinked from candidate search.

## Conflict handling

Prompt 1 preserves source-level values in raw payloads and metadata. It does not silently erase disagreements.

Example:

```text
Official ATS: Boston, hybrid
Secondary source: Remote
```

The canonical value remains explainable from the chosen source. Field-level provenance and automated conflict scoring are deferred to the scale/quality milestone.

## Operational queries and indexes

V1 adds indexes for:

- unique source registry identity;
- due-source claims;
- lease recovery;
- ingestion runs by source/time;
- source type;
- posting source links.

Further indexes must be based on measured `EXPLAIN ANALYZE` results at synthetic 10K/50K/250K scales rather than added speculatively.

## Candidate-facing trust target

The future job detail should be able to display:

```text
Source: Example Careers
Apply on employer site
Last verified: <timestamp>
```

Prompt 1 stores the required provenance but does not redesign the candidate UI.
