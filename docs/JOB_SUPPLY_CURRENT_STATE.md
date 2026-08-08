# ApplyAI Global Job Supply — Current State

Updated: 2026-08-08

## Status boundary

The repository now contains the source-side platform required to load a real organization universe, discover employer job sources, ingest supported public/authorized feeds, operate the source catalog and evaluate staging acceptance. This is not evidence that a live organization universe has already been loaded or that every provider has been exercised in staging.

Use these evidence states consistently:

- `SOURCE_DESIGNED` — architecture/contract exists.
- `SOURCE_IMPLEMENTED` — production-path source code exists.
- `SOURCE_TESTED` — repository tests/gates exercise the source implementation.
- `LIVE_PUBLIC_SOURCE_VERIFIED` — a real public/authorized source produced measured runtime evidence.
- `LIVE_STAGING_VERIFIED` — staging acceptance passed against the required representative matrix.
- `PRODUCTION_VERIFIED` — production operation has separately been proven.
- `PARTNERSHIP_REQUIRED` — the desired source path requires authorized/licensed provider access.
- `BLOCKED_BY_PROVIDER_POLICY` — automated use of the attempted path is disallowed.
- `NOT_YET_SUPPORTED` — no reviewed production-grade ingestion path exists.

Do not collapse these states into one generic "complete" flag.

## Organization universe

`app.jobs.organization_universe` now supports repeatable organization ingestion with:

- canonical name/domain normalization
- aliases and former-name style aliases
- source-specific external organization identifiers through `CompanySource`
- domain-first, external-ID, canonical-name and alias identity resolution
- ambiguity/conflict-to-review behavior rather than unsafe merge
- parent-domain/parent-company metadata where evidence exists
- identity-resolution audit metadata
- dataset provenance
- CSV, JSON and JSONL normalized imports

Supported organization taxonomy includes:

`PUBLIC_COMPANY`, `PRIVATE_COMPANY`, `STARTUP`, `UNIVERSITY`, `COLLEGE`, `RESEARCH_INSTITUTION`, `HOSPITAL`, `HEALTH_SYSTEM`, `NONPROFIT`, `NGO`, `FOUNDATION`, `FEDERAL_AGENCY`, `STATE_AGENCY`, `LOCAL_GOVERNMENT`, `PUBLIC_INSTITUTION`, `NATIONAL_LAB`, and `OTHER_EMPLOYER` plus compatibility categories already present in the platform.

### Authoritative dataset loaders

`app.jobs.organization_datasets` provides explicit normalization for:

- SEC company metadata → public companies / CIK identity
- NCES/IPEDS → U.S. colleges and universities / UNITID identity
- CMS hospital data → hospitals / provider identity
- IRS EO BMF/TEOS-style rows → nonprofits / EIN identity
- reviewed government directories → federal/state/local government organization identity

These loaders normalize public organization datasets; they do not automatically assert a careers URL or permission to crawl every resulting domain.

Use:

```bash
uv run --project services/api python -m scripts.import_organizations \
  --file <dataset.csv> \
  --dataset-type sec|ipeds|cms|irs|government
```

`--dry-run` validates without writing.

## Source discovery and ATS classification

Organization records can be queued for asynchronous career-source discovery through the existing PostgreSQL outbox → SQS source-worker flow. Discovery remains bounded by safe URL validation, SSRF defenses, robots/access-policy evaluation, response/page budgets and redirect limits.

Known ATS/provider fingerprint detection includes Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Workable, iCIMS, Oracle Recruiting, SuccessFactors, Jobvite, UKG, BambooHR, JazzHR, Recruitee, Teamtailor, Pinpoint, Comeet, Personio, Rippling, ADP, Paylocity, Dayforce, Taleo, PageUp, PeopleAdmin, Cornerstone and GovernmentJobs/NEOGOV.

Detection does not imply a dedicated API adapter. Providers without a reviewed dedicated public connector remain on the bounded employer-career path.

## Direct/public source implementations

Source-tested repository paths exist for:

- ApplyAI first-party employer jobs
- Greenhouse public Job Board
- Lever public postings
- Ashby public job board
- SmartRecruiters public postings
- USAJOBS official Search API, requiring issued API key/user-agent configuration
- ReliefWeb official jobs API, requiring configured/approved app name
- permitted employer career pages / JSON-LD

Live verification is separately measured by staging acceptance.

## Authorized/licensed feed contract

`app.jobs.partner_feed.PartnerFeedConnector` provides a generic contracted-feed path for:

- JSON
- JSONL
- CSV
- XML
- RSS
- Atom

It requires an explicitly registered feed URL, source identity and provider key, preserves provenance, supports configurable field mapping and uses the same safe public-fetch controls. `AUTHORIZED_AGGREGATOR_FEED`, `JSON_FEED` and `XML_FEED` source registry entries can use this contract.

This is an integration contract for authorized/licensed supply. It is not an anonymous marketplace scraper.

## Provider policy

`app.jobs.source_capabilities` is the operational provider-policy registry. Provider records expose:

- access mode
- implementation status
- credential requirement
- partnership requirement
- robots policy
- rate-limit policy
- pagination strategy
- delta support
- closure support
- trust level
- whether automated ingestion is permitted by ApplyAI policy
- reason/notes
- last reviewed timestamp

Major marketplaces such as Indeed, LinkedIn, Dice, Monster, ZipRecruiter, Glassdoor, CareerBuilder, Wellfound, Built In, HigherEdJobs, Handshake, Idealist and Devex remain partnership/authorized-feed candidates. ApplyAI does not implement CAPTCHA bypass, authenticated-session bypass, anti-bot evasion, proxy rotation to defeat blocking or private-API circumvention.

## Canonical job integrity

The existing authority-aware ingestion pipeline remains the canonicalization path. It preserves:

- source observations
- raw payload hash/provenance
- source/company/job identity
- canonical application URL
- employer requisition identity
- cross-source dedup evidence
- field-level provenance
- source authority
- closure/reopen evidence

Lower-authority observations cannot silently replace higher-authority employer-origin canonical content.

## Source completeness

Runtime source evidence now records one of:

- `FULL_SNAPSHOT`
- `PAGINATED_FULL_SNAPSHOT`
- `DELTA`
- `PARTIAL`
- `TRUNCATED`
- `UNKNOWN_COMPLETENESS`

Failed record processing downgrades observed completeness to `PARTIAL`. Generic employer career extraction and non-authoritative partner feeds remain non-authoritative for absence-based closure. Only full snapshot classes should be treated as closure authority.

Latest completeness evidence is stored with the source registry runtime configuration instead of pretending a partial crawl was complete.

## Scheduling and scale

The scheduler retains:

- adaptive refresh intervals
- quiet-source 1.25× compatibility cadence
- daily-or-longer empty-source backoff
- bounded exponential failure backoff
- deterministic sharding
- database leases / skip-locked claims

A PostgreSQL scheduler benchmark now measures 1,000, 10,000 and 50,000 synthetic due sources. It records claim throughput, batch latency, duplicate leases and second-worker conflicts. The artifact is explicitly labeled `SYNTHETIC_SCALE_EVIDENCE`; it is not a live-employer count.

The existing PostgreSQL job-search benchmark remains the measured search gate at 10K, 50K and 250K synthetic jobs.

## Catalog quality

`app.jobs.quality` exposes measured values for:

- organizations and organization-type coverage
- organizations with domains/career sites/detected ATS
- source totals, enabled/healthy/blocked/failing and provider distribution
- raw postings and canonical active/closed/stale jobs
- new/updated/closed/reopened jobs
- cross-source canonical jobs and orphan source observations
- apply URL validity
- salary/location coverage
- freshness buckets
- source-authority distribution
- ingestion p50/p95
- source failure rate
- measured worker/network/cost observations where instrumented

Unmeasured metrics remain `null` rather than being invented.

## Operator control plane

`/api/v1/internal/job-supply` now exposes consolidated operator endpoints for:

- overview/quality
- provider policy
- organizations
- sources/source details
- ingestion runs/failures
- dedup review
- source enable/disable/refresh/reclassification
- provider reclassification
- queued organization discovery
- dedup approve/reject review state

The existing operator-only `/admin` UI surfaces job-supply health, source controls, organization discovery and provider-policy status without exposing the internal API token to the browser.

## Acceptance command

Run:

```bash
pnpm job-supply:acceptance
```

The command reads actual database/runtime evidence. It deliberately returns `BLOCKED_EXTERNAL_CONFIGURATION` when a real organization universe, active real sources, successful real-source runs or real canonical jobs are absent. It does not convert deterministic seed data or synthetic benchmarks into live-source evidence.

For a non-blocking diagnostic report:

```bash
pnpm job-supply:acceptance:report
```

## What is still external/runtime work

The repository does not fabricate these outcomes:

- a reviewed real 50K organization dataset being physically loaded
- live USAJOBS/ReliefWeb credentials
- marketplace contracts/licensed feeds
- active staging source workers and queues
- measured real job counts/freshness/apply-link validity from staging
- representative real-source staging acceptance
- production verification

Those are runtime/provider dependencies. When configured, the repository now has an explicit acceptance command and operator surfaces to measure them.
