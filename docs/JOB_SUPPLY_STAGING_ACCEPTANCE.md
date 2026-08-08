# ApplyAI Global Job Supply — Staging Acceptance

Updated: 2026-08-08

## Purpose

This runbook proves the real job-supply system against public/authorized sources after staging infrastructure, credentials and a reviewed organization universe are configured. Deterministic CI and synthetic scale evidence do not satisfy this runbook.

Do not mark a provider `LIVE_PUBLIC_SOURCE_VERIFIED`, `LIVE_STAGING_VERIFIED` or `PRODUCTION_VERIFIED` without the corresponding runtime evidence.

## Primary acceptance command

From the repository root in the target runtime environment:

```bash
pnpm job-supply:acceptance
```

The command reads the real database and reports both human-readable and JSON evidence. It exits non-zero when live activation is blocked or representative staging coverage is partial.

For diagnostics before external dependencies are available:

```bash
pnpm job-supply:acceptance:report
```

That command allows blocked status but does not convert it to a pass.

Expected fail-closed state before live activation:

```text
BLOCKED_EXTERNAL_CONFIGURATION
```

Possible evidence states include:

```text
BLOCKED_EXTERNAL_CONFIGURATION
RUNTIME_EVIDENCE_AVAILABLE
PARTIAL_STAGING_ACCEPTANCE
PASS
```

Only a staging `PASS` may emit the `LIVE_STAGING_VERIFIED` claim boundary.

## Prerequisites

- staging API/database/source worker running
- migrations applied at the exact release commit
- source queue and DLQ active
- outbound network access configured for source workers
- reviewed organization/source registry loaded
- provider credentials supplied only for approved APIs/feeds
- no raw credentials committed to GitHub or Terraform state
- operator access available for source inspection

## Load a real organization universe

Use public/licensed datasets whose use has been reviewed. Repository loaders support normalized organization imports plus explicit dataset modes:

```bash
uv run --project services/api python -m scripts.import_organizations \
  --file <sec-file.json> --dataset-type sec

uv run --project services/api python -m scripts.import_organizations \
  --file <ipeds-file.csv> --dataset-type ipeds

uv run --project services/api python -m scripts.import_organizations \
  --file <cms-hospital-file.csv> --dataset-type cms

uv run --project services/api python -m scripts.import_organizations \
  --file <irs-eo-file.csv> --dataset-type irs

uv run --project services/api python -m scripts.import_organizations \
  --file <government-directory.csv> --dataset-type government
```

Run `--dry-run` first for every new dataset variant.

Record actual counts:

```text
dataset
owner
retrieved_at
license/access note
records loaded
valid
invalid
created
updated
review required
duplicate/external-ID conflicts
organizations with domains
```

Do not fabricate rows to hit the 50K design target.

## Minimum representative source matrix

The acceptance command expects successful measured source runs representing:

- Greenhouse
- Lever
- Ashby
- SmartRecruiters
- USAJOBS
- ReliefWeb
- employer `CAREER_SITE` / JSON-LD path

The broader manual matrix should additionally sample:

- Workday or another detected ATS using the permitted employer-career path
- universities/research institutions
- hospital/health systems
- nonprofits/NGOs
- startups sourced from the employer ATS/career page
- an intentionally blocked/disallowed source to prove policy enforcement
- an authorized/licensed partner feed when a contract exists

## Evidence captured for every real source run

Record:

```text
release_commit
source_id
organization
provider
access_mode
implementation_status
source_completeness
started_at
completed_at
fetch_duration_ms
http_status/error_category
records_received
jobs_valid
jobs_invalid
jobs_created
jobs_updated
jobs_unchanged
jobs_deduplicated
closed
source_last_seen
next_scheduled_at
```

Never include API secrets or full sensitive payload bodies in the evidence bundle.

## Acceptance checks

### Provider policy

- Marketplace/provider records expose the reviewed access mode.
- `PARTNERSHIP_REQUIRED` providers cannot execute as anonymous crawler adapters.
- robots/access denial becomes an explicit blocked state.
- `allowed_for_automated_ingestion=false` is respected.

### Organization identity

Confirm:

- canonical-domain normalization
- source-specific external IDs
- aliases preserved
- repeated imports are idempotent
- external-ID/domain ambiguity moves to review instead of silently merging
- dataset provenance remains attached
- parent/child metadata is evidence-driven, not guessed

### Discovery

For sampled employer domains:

- careers URL is discovered within crawl budget
- known ATS fingerprint is recorded
- unsupported/detection-only ATS remains on the bounded generic path
- source identity is stable
- SSRF/redirect/response-size/robots controls remain active

### Structured ATS connectors

For Greenhouse, Lever, Ashby and SmartRecruiters:

- fetch real published postings
- normalize title/company/location/apply URL
- preserve provider/source identity
- preserve raw/source provenance
- repeated sync is idempotent
- changed content updates the canonical job only when source authority permits

### USAJOBS

Using issued credentials:

- official results fetch successfully
- government metadata remains preserved
- salary/close date remain source-derived
- configured paging limits cannot create false closure evidence

### ReliefWeb

Using an approved app name:

- official API fetch succeeds
- originating organization/career metadata is preserved when supplied
- pagination/truncation cannot create false closures

### Authorized/licensed feeds

When a contract/feed exists, configure a registry source using the authorized feed contract. Verify:

- explicit provider/source identity
- JSON/JSONL/CSV/XML/RSS/Atom parsing as applicable
- field map correctness
- safe fetch controls
- source trust/provenance
- ETag/Last-Modified behavior where supported
- authoritative snapshot is enabled only when the contract guarantees complete inventory

### Source completeness

Every measured source should expose one of:

```text
FULL_SNAPSHOT
PAGINATED_FULL_SNAPSHOT
DELTA
PARTIAL
TRUNCATED
UNKNOWN_COMPLETENESS
```

Only `FULL_SNAPSHOT` and `PAGINATED_FULL_SNAPSHOT` may support absence-based closure. A run with record-level failures must be treated as partial evidence.

### Cross-source deduplication

Prove that:

- exact canonical apply URL wins first
- employer + requisition can resolve the same role
- source identity remains stable
- borderline fuzzy matches become review candidates
- one canonical job retains multiple source observations
- lower-trust sources do not overwrite higher-trust employer-origin data

### Freshness / closure / reopen

Prove:

- transient fetch failures do not close jobs
- missing once does not immediately close a job
- only healthy authoritative snapshot evidence contributes to absence-based closure
- verified 404/410/closed state can contribute closure evidence
- a reappearing/reopened role can become active again

### Apply URL health

Measure latest checks as:

```text
VALID
REDIRECTED
NOT_FOUND
GONE/BLOCKED/TIMEOUT/SERVER_ERROR/UNKNOWN as applicable
```

Transient 5xx/timeouts must not be treated as immediate closure.

### Scheduling and workers

Confirm:

- deterministic sharding
- database lease ownership
- priority/high-change sources refresh faster
- quiet non-empty sources preserve the 1.25× cadence
- empty sources back off at least daily
- repeated failures use bounded exponential backoff
- multiple workers do not duplicate leased work
- retry/DLQ recovery is observable

Repository CI separately runs a PostgreSQL scheduler benchmark at 1K/10K/50K synthetic sources. Its artifact is `SYNTHETIC_SCALE_EVIDENCE`, not live-source proof.

### Search / matching

After real ingestion:

- active jobs appear in canonical search
- closed jobs disappear from active results
- provenance remains available
- matching operates on canonical jobs rather than source duplicates
- base ingestion does not depend on an LLM

## Operator evidence

Use `/admin` or `/api/v1/internal/job-supply/*` to inspect:

- overview/quality
- providers
- organizations
- sources/source details
- runs/failures
- dedup review

Controlled operator actions include source enable/disable/refresh/reclassification and queued organization discovery. A dedup review decision does not silently merge canonical records.

## Marketplace rule

For Indeed, LinkedIn, Dice, Monster, ZipRecruiter, Glassdoor, CareerBuilder, SimplyHired, Wellfound, Built In, HigherEdJobs, Handshake, Idealist, Devex and similar services:

- do not claim integration because a public page can be viewed
- use an official/authorized API or licensed feed when contracted
- otherwise resolve to the original employer ATS/career source
- never bypass authentication, CAPTCHA, anti-bot systems, robots or rate limits

## Pass criteria

Staging passes only when:

- a real organization universe is loaded
- active non-development sources are configured
- real-source runs have completed successfully
- non-development canonical jobs exist
- the required representative provider matrix has measured successful runs
- policy-restricted sources are not bypassed
- provenance/dedup/closure/reopen behavior is demonstrated
- live latency/error/freshness/job-count metrics are captured
- source workers/queues/retries are operational
- candidate search can operate on the real catalog

## Final evidence table

Produce one row per significant provider/source with:

```text
Provider
Access method
Implementation status
Test evidence
Runtime evidence
Live verification
Blocking dependency
```

Never promote `SOURCE_TESTED` to live/staging verification without actual runtime evidence.
