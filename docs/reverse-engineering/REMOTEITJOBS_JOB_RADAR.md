---
applyai_fit: CORE
fit_scope: PARTIAL
destination: candidate-core
source_type: public-product-clean-room
---

# RemoteITJobs.net -> ApplyAI Job Radar reverse-engineering contract

Status: research/donor contract started (2026-09-23)
Source: https://www.reddit.com/r/SideProject/s/Q2cMWN2sfq
Product: https://remoteitjobs.net/
Canonical destination: ApplyAI Job Radar / candidate-core
Related implementation: issue #75 and branch `reverse/applyai-jobprime-radar`

## ApplyAI Fit

RemoteITJobs.net is a capability donor, not a standalone ApplyAI product. Its strongest reusable ideas are the ingestion/normalization pipeline, remote-work eligibility taxonomy, faceted discovery model, public-source application handoff, and search-engine/AI-discovery-friendly landing pages.

This donor should extend the existing JobPrime/Job Radar implementation instead of creating a parallel job store, matching engine, scheduler, or application workflow.

## Why this qualifies

RemoteITJobs is relevant to ApplyAI only as a clean-room capability donor for canonical job ingestion, remote-eligibility evidence, conservative deduplication, and public application handoff. It does not justify a second job marketplace, scheduler, ranking runtime, or application engine.

## Publicly observed behavior

The creator describes the product as a remote IT-job aggregator that:

- pulls jobs from multiple sources;
- cleans and normalizes the listings;
- exposes filtering/search by tech stack, remote type, location restrictions, and employment type;
- uses Next.js + NestJS + Postgres;
- reports roughly 900 active users / 1.1k sessions over seven days, with about 90% attributed to an "AI Assistant" GA4 channel. Treat these traffic figures as creator-reported, not independently audited.

The public product currently exposes a large remote-job catalog and names Remotive, RemoteOK, Himalayas, and Greenhouse as sources. It states that imports are normalized across titles, companies, tags, and locations and that duplicate postings are reduced before display.

Observed discovery dimensions include:

- keyword/company/technology search;
- category;
- tag / technology / seniority;
- country;
- worldwide vs country-restricted remote;
- employment type;
- salary when supplied by the source;
- freshness / posted timestamp.

Job detail pages preserve the original-source application handoff rather than hosting the application workflow.

## Absorb into ApplyAI

The existing JobPrime donor already establishes persisted JobSearchProfile/JobScan, provider-neutral ingestion, normalization, dedupe, salary handling, deterministic scoring, and one durable on-demand scan.

RemoteITJobs adds concrete requirements that should be absorbed into that slice:

1. **Remote eligibility as first-class evidence**
   - normalized remote type;
   - explicit worldwide vs country/region-restricted remote;
   - eligible countries/regions when evidenced;
   - timezone/payroll constraints only when source evidence exists;
   - unknown remains unknown rather than being inferred.

2. **Source provenance**
   - source/provider name;
   - provider job id;
   - canonical listing URL;
   - public application URL;
   - first/last seen;
   - source posted timestamp when evidenced;
   - source payload/hash only where provider terms permit retention.

3. **Facet-ready normalization**
   - category;
   - technology/tags;
   - employment type;
   - country/region;
   - seniority;
   - compensation;
   - freshness.

4. **Conservative cross-source dedupe**
   - stable provider id first;
   - canonicalized source/application URL second;
   - guarded company + title + location + posting-time fallback;
   - retain source aliases/provenance for merged observations.

5. **Direct application boundary**
   - candidate opens the verified public employer/provider application URL;
   - no anti-bot bypass, CAPTCHA bypass, hidden API use, or autonomous submission is introduced by this donor.

6. **Discovery/SEO surface**
   - stable indexable landing pages for validated categories, technologies, and locations;
   - canonical URLs and deduplicated metadata;
   - avoid generating thin or unsupported pages from arbitrary tags;
   - search/AI discoverability is a distribution surface, not a relevance signal.

## Candidate journey stages

- `DISCOVER_JOBS` — improve canonical remote-job discovery and evidence quality.
- `UNDERSTAND_FIT` — expose remote eligibility, compensation, freshness, and provenance as explicit signals.
- `APPLY` — preserve the verified public employer/provider handoff URL; no application submission is added.

## Implementation destination

`candidate-core` — extend the existing ApplyAI Job Radar/canonical job contracts only. No separate RemoteITJobs runtime or product shell is introduced.

## Proposed canonical job additions

Where not already present, the canonical job/search-result contract should be able to represent:

- `remote_type`: `fully_remote | hybrid | onsite | unknown`
- `remote_scope`: `worldwide | country_restricted | region_restricted | unknown`
- `eligible_countries[]`
- `eligible_regions[]`
- `employment_type`
- `seniority[]`
- `tags[]`
- `salary_min`, `salary_max`, `salary_currency`, `salary_period`
- `source_posted_at`
- `first_seen_at`, `last_seen_at`
- `source_name`, `source_job_id`, `source_url`, `application_url`
- `source_aliases[]` or equivalent provenance for deduped multi-source observations

Do not add fields solely because the donor UI exposes a facet; reuse existing ApplyAI fields when semantics already match.

## Provider architecture

The existing provider-neutral boundary remains correct:

```python
class JobProvider(Protocol):
    async def search(self, request: SearchRequest) -> list[NormalizedJobCandidate]: ...
```

RemoteITJobs suggests testing the boundary against both:

- aggregator-style APIs/feeds; and
- company ATS sources such as Greenhouse.

Each adapter must declare its own rate limits, terms constraints, pagination/freshness behavior, stable identifier strategy, and which fields are authoritative vs inferred.

No scraping implementation should be added for a source unless its public terms and technical access path are reviewed.

## Normalization contract

For every imported job:

1. preserve source identity/provenance;
2. canonicalize URLs without destroying application parameters needed for the handoff;
3. normalize whitespace/casing for matching while preserving display text;
4. map employment type/category/seniority through reviewed dictionaries;
5. parse salary only from explicit evidence;
6. normalize remote scope separately from ordinary location;
7. retain source posting time separately from ingestion time;
8. reject or quarantine malformed records rather than fabricating missing fields;
9. emit deterministic dedupe keys with reason/evidence.

## Candidate search implications

A candidate profile should be able to express:

- target titles and skills;
- preferred countries/regions;
- whether worldwide remote is acceptable;
- whether country-restricted remote is acceptable;
- employment type preferences;
- compensation floor with currency;
- recency preference.

Hard eligibility filters should run before deterministic fit ranking when the source provides enough evidence. If eligibility is unknown, the result can remain visible with an explicit uncertainty flag rather than being silently excluded or treated as eligible.

## SEO / AI-discovery lesson

The public product has indexable routes around job categories, technologies/tags, countries, and individual job pages. The creator also reports a large share of recent traffic attributed by GA4 to AI-assistant referrals.

ApplyAI can borrow the architecture, not the traffic claim:

- expose durable public pages only for approved, evidenced job-taxonomy combinations;
- include canonical metadata and structured job data where appropriate;
- keep candidate-private match/ranking state out of public pages;
- never optimize ranking for "AI referral traffic";
- measure referral source separately from job quality/conversion.

## Clean-room boundary

This work reconstructs public behavior and contracts only. We do not have RemoteITJobs source code, private APIs, ingestion credentials, database schema, dedupe implementation, ranking logic, analytics configuration, or provider agreements.

The creator's stack statement (Next.js + NestJS + Postgres) is an observed implementation choice, not a requirement for ApplyAI.

## Smallest implementation delta

Do **not** create a new scheduler or AI reranker.

Extend the existing JobPrime Phase A slice with tests and contracts for:

1. `remote_scope` + evidenced eligible-country/region normalization;
2. source/application provenance;
3. cross-source alias-aware dedupe;
4. employment/seniority/tag facet normalization;
5. one ATS-style fixture plus one aggregator-style fixture flowing through the existing on-demand scan;
6. assertions that hard remote eligibility executes before deterministic fit scoring;
7. explicit unknown-state behavior for salary, remote scope, and source timestamps.

## Repository acceptance evidence

The next repository-certified checkpoint should capture:

- migration/domain diff for any new normalized fields;
- deterministic fixtures for at least two source shapes;
- before/after normalization snapshots;
- dedupe evidence showing why two source records were merged or kept separate;
- remote-eligibility test matrix;
- application URL provenance/handoff tests;
- one on-demand scan persistence result using the existing durable task/outbox path;
- exact-head unit/integration test results.

## Keep separate

- live Remotive/RemoteOK/Himalayas/Greenhouse credentials or API certification;
- permission to scrape any source;
- production provider quotas;
- hosted scheduler execution;
- AI reranking;
- autonomous applications;
- RemoteITJobs traffic reproducibility;
- production SEO performance.

## Implementation status

**DOCUMENTED ONLY — NOT IMPLEMENTED IN THIS SLICE.**

This file remains a clean-room donor contract. PR #76's implemented repository slice is the JobPrime Phase A on-demand Job Radar path; the RemoteITJobs-specific remote-eligibility/facet delta remains future work.

## Next action

Use issue #75 / PR #76 as the implementation vehicle. Keep the JobPrime Phase A architecture, add the RemoteITJobs normalization/remote-eligibility/provenance test delta, and certify one bounded on-demand scan before scheduled delivery or AI reranking.
