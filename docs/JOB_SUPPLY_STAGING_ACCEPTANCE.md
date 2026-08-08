# ApplyAI Global Job Supply — Staging Acceptance

Updated: 2026-08-08

## Purpose

This runbook proves the real job-supply system against public/authorized sources after staging infrastructure and credentials are configured. It is deliberately separate from deterministic CI/local certification.

Do not mark a source `LIVE_PUBLIC_SOURCE_VERIFIED` until the corresponding acceptance evidence below exists.

## Prerequisites

- staging API/database/source worker running
- migrations applied at the exact release commit
- source queue and DLQ active
- outbound network access configured for source workers
- reviewed organization/source registry loaded
- provider credentials supplied only for approved APIs/feeds
- no raw credentials committed to GitHub or Terraform state
- operator access available for source inspection

## Minimum source matrix

Exercise a representative set, not only one company per implementation path:

1. Multiple Greenhouse employers
2. Multiple Lever employers
3. Multiple Ashby employers
4. Multiple SmartRecruiters employers
5. Several Workday or other detected ATS employers through the permitted employer-career path
6. Universities/research institutions
7. Hospital/health-system employers
8. Nonprofits/NGOs
9. USAJOBS official API
10. ReliefWeb official API
11. Startup employers discovered from company/portfolio datasets but sourced from employer ATS/career pages
12. Generic employer pages containing schema.org `JobPosting`
13. At least one generic employer page without structured JSON-LD that passes conservative extraction
14. At least one intentionally disallowed/blocked source to prove policy enforcement

## Evidence captured for every source run

Record:

```text
release_commit
source_id
organization
provider
access_mode
implementation_status
started_at
completed_at
fetch_duration_ms
http_status/error_category
records_received
jobs_accepted
jobs_created
jobs_updated
jobs_unchanged
jobs_quarantined
dedup_candidates
duplicates_merged
possibly_closed
closed
reopened
source_checkpoint
source_last_seen
next_scheduled_at
429_count
5xx_count
```

Never include API secrets or full sensitive payload bodies in the evidence bundle.

## Acceptance tests

### 1. Provider policy

- Marketplace/provider records expose the reviewed access mode.
- `PARTNERSHIP_REQUIRED` sources cannot accidentally execute as anonymous crawler adapters.
- robots/access-policy denial results in a blocked state and no bypass attempt.

### 2. Organization universe

Load a representative dataset containing companies, startup, university, hospital/health system, nonprofit/NGO, government and research organizations.

Confirm:

- canonical-domain normalization
- aliases preserved
- exact repeated imports are idempotent
- domain conflicts move to review instead of merging silently
- dataset provenance is retained
- source discovery can be queued independently of candidate traffic

### 3. ATS discovery

For sampled employer domains:

- careers URL is discovered within crawl budget
- known ATS provider is detected where evidence exists
- source identity is stable
- unsupported ATS routes to the safe generic career-site path
- discovery respects domain/redirect/response-size/robots constraints

### 4. Structured ATS connectors

For Greenhouse, Lever, Ashby and SmartRecruiters:

- fetch live public postings
- normalize title/company/location/apply URL
- preserve provider/source identity
- preserve source metadata and raw hash/provenance
- repeated sync is idempotent
- changed source content updates the canonical job
- healthy complete snapshot can contribute closure evidence

### 5. USAJOBS

Using an issued API key/user-agent:

- fetch official results
- preserve agency/department metadata
- capture security/hiring-path metadata when supplied
- normalize salary and close date without overwriting raw source data
- paging-limit truncation must not be treated as an authoritative complete snapshot

### 6. ReliefWeb

Using an approved app name:

- fetch humanitarian jobs from the official API
- preserve originating organization where available
- preserve career/experience/theme metadata
- pagination/truncation must not create false closures

### 7. JSON-LD / generic career pages

- single valid `JobPosting` is accepted
- multiple `JobPosting` nodes on a listing page are quarantined unless the source path explicitly supports listing extraction
- generic HTML requires one clear title, one apply path and substantial job-specific content
- ambiguous/listing pages are quarantined

### 8. Cross-source deduplication

Create or find a role observable through more than one source.

Prove that:

- exact canonical application URL wins first
- provider/source job identity is stable
- employer + requisition can resolve the same role
- fuzzy title/location/description signals create review candidates rather than unsafe automatic merges where confidence is insufficient
- one canonical job can retain multiple source observations
- higher-trust employer source remains canonical over lower-trust aggregator/import observations

### 9. Freshness and closure

Prove:

- missing once does not immediately close a job
- transient source failure does not generate closure evidence
- repeated healthy-source absence increases closure confidence
- confirmed inactive/expired job becomes non-searchable
- reappearing/reopened job can return to active state
- partial/truncated feeds never close unseen jobs as if the snapshot were complete

### 10. Adaptive scheduling and sharding

Load enough sources to exercise multiple shards.

Confirm:

- deterministic shard assignment
- priority/high-change sources schedule faster
- ordinary sources settle into normal cadence
- empty/low-change sources back off
- repeated failures back off with bounded retry behavior
- multiple workers can lease work without duplicate execution

### 11. Rate limiting and failure handling

Exercise controlled 429, 5xx and timeout scenarios.

Confirm:

- `Retry-After` is honored where supplied
- exponential backoff/jitter is bounded
- retries are idempotent
- terminal failures reach DLQ when appropriate
- operator can inspect/retry/recover without editing database rows manually

### 12. Search and candidate matching

After live ingestion:

- active jobs appear in canonical search
- closed jobs disappear from active results
- source provenance is available to job detail/operator surfaces
- matching uses the canonical job rather than duplicate observations
- expensive AI is not required for base ingestion

## Marketplace/aggregator rule

For Indeed, LinkedIn, Dice, Monster, ZipRecruiter, Glassdoor, CareerBuilder, SimplyHired, Wellfound, Built In, HigherEdJobs, Handshake, Idealist, Devex and similar services:

- do not claim live ingestion merely because public pages can be viewed in a browser
- use an official/authorized API or licensed feed when contracted
- otherwise resolve opportunities to the original employer ATS/career source
- never bypass authentication, CAPTCHA, anti-bot systems, robots or rate limits

## Pass criteria

The staging job-supply milestone passes when:

- all implemented source types have representative successful real runs or are explicitly blocked by unavailable required credentials
- no policy-restricted source is bypassed
- canonical jobs retain provenance
- duplicate observations do not create duplicate search results
- source failures do not falsely close jobs
- closure/reopen behavior is demonstrated
- worker retry/DLQ recovery is demonstrated
- live source latency/error/freshness/job-count metrics are captured
- candidate search and Career Intelligence operate on the ingested real catalog

## Final evidence table

Produce a release artifact/table with one row per tested source and these final classifications:

```text
SOURCE IMPLEMENTED
LIVE PUBLIC SOURCE VERIFIED
PARTNERSHIP REQUIRED
BLOCKED BY PROVIDER POLICY
NOT YET SUPPORTED
```

Do not convert `SOURCE IMPLEMENTED` into `LIVE PUBLIC SOURCE VERIFIED` without actual staging evidence.
