# ApplyAI Global Job Supply — Current State

Updated: 2026-08-08

## Scope

This document records the repository-side implementation state of the Global Real Job Supply Platform. It deliberately separates source implementation from live-provider acceptance. A connector or policy record is not evidence that a third-party marketplace permits anonymous crawling or that a live feed has been activated.

## Existing platform reused

ApplyAI already had a normalized job domain, PostgreSQL search, source registry/run tracking, Greenhouse/Lever/Ashby adapters, company career-site discovery, JSON-LD extraction, safe public URL fetching, robots/access-policy checks, SSRF protections, provenance, freshness/closure evidence, SQS/outbox workers, candidate URL import, and search-scale benchmarks. The global-supply work extends these capabilities rather than replacing them.

## Global-supply additions

### Provider capability and policy registry

`app.jobs.source_capabilities` defines explicit access modes:

- `DIRECT_PUBLIC_API`
- `AUTHORIZED_FEED`
- `PUBLIC_ATS`
- `PUBLIC_STRUCTURED_PAGE`
- `EMPLOYER_CAREER_SITE`
- `FIRST_PARTY_APPLYAI`
- `PARTNERSHIP_REQUIRED`
- `BLOCKED_BY_POLICY`
- `UNSUPPORTED`

Implementation status is tracked independently as:

- `SOURCE_IMPLEMENTED`
- `LIVE_PUBLIC_SOURCE_VERIFIED`
- `PARTNERSHIP_REQUIRED`
- `BLOCKED_BY_PROVIDER_POLICY`
- `NOT_YET_SUPPORTED`

This prevents technical discoverability from being treated as permission to crawl.

### Direct/public sources implemented in source

- ApplyAI first-party employer jobs
- Greenhouse public Job Board API
- Lever public postings API
- Ashby public job-board API
- SmartRecruiters public posting path
- USAJOBS official Search API (requires issued API key/user-agent configuration)
- ReliefWeb official jobs API (requires configured app name)
- bounded employer career-site/JSON-LD extraction for permitted public pages

### Marketplace policy classification

Major marketplaces including Indeed, LinkedIn, Dice, Monster, ZipRecruiter, Glassdoor, CareerBuilder, SimplyHired, Wellfound, Built In, HigherEdJobs, Handshake, Idealist and Devex are represented conservatively as partnership/authorized-feed candidates unless a documented public source is available and reviewed. The platform does not implement CAPTCHA, authentication, anti-bot, robots or rate-limit bypasses.

### Organization universe

`app.jobs.organization_universe` provides normalized organization ingestion from CSV, JSON and JSONL, with:

- canonical name and domain normalization
- aliases
- organization type
- industry
- country/region
- size band
- source priority
- careers URL
- ATS provider
- dataset provenance
- conflict-to-review behavior rather than unsafe merging

The model supports companies, startups, universities, colleges, research institutes, hospitals, health systems, nonprofits, NGOs, foundations, government/public institutions and national laboratories.

### Discovery and source registration

Organization records can feed asynchronous career-page discovery. The existing ATS detector is extended to recognize additional provider fingerprints while unsupported providers are routed through the safe generic career-site path rather than assumed to have private APIs.

### Source authority and deduplication

Source trust is explicit. ApplyAI first-party and employer-origin sources outrank authorized aggregators and candidate imports. Cross-source dedup review retains source observations/provenance instead of discarding duplicate evidence.

### Adaptive scheduling and sharding

The global-supply layer adds source priority, adaptive refresh intervals, progressive backoff and deterministic source sharding. The intended operating model is high-frequency refresh for high-change sources, normal 6–12 hour refresh for ordinary sources, daily refresh for low-volume sources, and longer backoff for repeatedly empty/failing sources.

### Public feed connectors

USAJOBS and ReliefWeb connectors expose checkpoint/health behavior and avoid claiming an authoritative snapshot when configured paging limits prevent exhaustion of the source.

### Operator/API surface

Internal job-supply endpoints and scripts provide source registration, organization import/discovery/synchronization, provider capability seeding and dedup review support.

## CLI / operator entry points

Representative commands include:

```bash
uv run --project services/api python -m scripts.import_organizations --file <organizations.csv>
uv run --project services/api python -m scripts.seed_job_source_capabilities
uv run --project services/api python -m scripts.register_public_job_sources
uv run --project services/api python -m scripts.discover_job_sources
uv run --project services/api python -m scripts.sync_job_sources
uv run --project services/api python -m scripts.build_job_dedup_candidates
```

See each script's `--help` output for exact options and required credentials.

## Scale design

The repository targets a representation capacity of 50,000+ organizations and a path toward 1M+ active jobs / 10M+ historical observations. Synthetic benchmark tooling measures organization validation, scheduling and shard distribution. Existing PostgreSQL search benchmarking remains the evidence gate for search scale; synthetic CPU-only scheduling benchmarks must not be described as proof of production database throughput.

## Source-safety rules

The implementation must not:

- bypass `robots.txt` or source access policy
- solve or evade CAPTCHA
- bypass authentication/paywalls
- rotate proxies to defeat blocking
- spoof private sessions/cookies
- reverse engineer authenticated private APIs for ingestion
- ignore `Retry-After`, 429 responses or provider throttling

Blocked/disallowed sources must remain explicit operational states.

## Status boundary

### SOURCE IMPLEMENTED

Repository code exists and must pass the applicable exact-head CI/tests.

### LIVE PUBLIC SOURCE VERIFIED

Requires successful staging execution against a real public/authorized source with captured metrics. Source code alone is insufficient.

### PARTNERSHIP REQUIRED

A provider requires licensed/partner access for the desired ingestion path. ApplyAI should prefer the original employer ATS/career page until such access is contracted.

### BLOCKED BY PROVIDER POLICY

Automated access is explicitly disallowed for the attempted path. The source must not be bypassed.

### NOT YET SUPPORTED

No production-grade adapter/path has been implemented and reviewed.

## Remaining non-source-control work

- load a reviewed real organization universe (large public/licensed datasets are intentionally not fabricated or committed)
- provide real USAJOBS/ReliefWeb credentials/configuration where required
- activate staging source schedules and workers
- measure live source job counts, freshness, dedup, closure and provider error behavior
- obtain any desired marketplace partnerships/licensed feeds

Those are activation/acceptance tasks, not a reason to fabricate source support in code.
