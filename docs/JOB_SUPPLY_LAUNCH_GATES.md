# ApplyAI Job Supply Launch Gates

Updated: 2026-08-08

These gates define when the real job catalog is ready for candidate use. Synthetic benchmarks prove architecture/scale behavior but do not satisfy live catalog gates.

## Evidence levels

```text
SOURCE_IMPLEMENTED
SOURCE_TESTED
RUNTIME_EVIDENCE_AVAILABLE
LIVE_PUBLIC_SOURCE_VERIFIED
LIVE_STAGING_VERIFIED
PRODUCTION_VERIFIED
```

Never promote an evidence level without the corresponding runtime proof.

## Gate 1 — Organization universe

Required evidence:

- legitimate public/licensed organization datasets loaded
- dataset provenance recorded
- invalid rows measured
- duplicate/external-ID conflicts measured
- organizations needing manual identity review measured

Report separately:

```text
organizations_total
organizations_with_domain
organizations_with_careers_url
organizations_with_detected_ats
organizations_with_active_source
organizations_with_live_jobs
```

There is no launch gate that treats `organizations_total` as equivalent to employer coverage.

## Gate 2 — Representative live provider coverage

Staging acceptance requires successful measured runs from the supported representative matrix:

- Greenhouse
- Lever
- Ashby
- SmartRecruiters
- USAJOBS
- ReliefWeb
- employer career-site / JSON-LD path

LinkedIn/Indeed are not required unless partner access has actually been granted.

## Gate 3 — Source health

Measure:

```text
sources_registered
sources_active
sources_healthy
sources_failed
429 rate
5xx rate
timeout rate
retry/DLQ recovery
```

Launch requires an operator-reviewed threshold based on staging measurements. Do not invent a percentage before real source behavior is known.

## Gate 4 — Catalog freshness

Measure canonical active jobs by latest verified source observation:

```text
<3h
<6h
<12h
<24h
>24h
```

Provider/source-specific expected cadence must be considered. A source intentionally scheduled daily is not automatically unhealthy because it is older than an hourly source.

## Gate 5 — Apply URL health

Measure:

```text
VALID
REDIRECTED
NOT_FOUND
GONE
BLOCKED
TIMEOUT
SERVER_ERROR
UNKNOWN
```

Candidate-facing active jobs should have a high verified-valid rate determined from real staging evidence. Transient errors must not trigger immediate closure.

## Gate 6 — Deduplication quality

Measure:

```text
raw observations
canonical jobs
cross-source canonical jobs
duplicate observations
dedup ratio
review-required candidates
false-merge findings from sampled review
missed-duplicate findings from sampled review
```

No fixed success percentage is asserted until representative live data is reviewed.

## Gate 7 — Closure and reopening safety

Acceptance must prove:

- transient provider failures do not close jobs
- `PARTIAL`, `TRUNCATED`, `DELTA` and `UNKNOWN_COMPLETENESS` do not create absence-based closure
- only `FULL_SNAPSHOT` and `PAGINATED_FULL_SNAPSHOT` can support authoritative absence evidence
- explicit provider closed state / verified 404 or 410 can contribute closure evidence
- reappearing jobs can reopen

## Gate 8 — Search performance

Repository evidence must continue to pass the PostgreSQL synthetic search benchmark through the approved scale gate (currently including 250K jobs).

Staging additionally records query latency against the real catalog for representative candidate searches, filters and pagination.

## Gate 9 — Scheduler / worker scale

Repository evidence must continue to pass PostgreSQL scheduler leasing benchmarks at:

```text
1,000 sources
10,000 sources
50,000 sources
```

These are `SYNTHETIC_SCALE_EVIDENCE` only.

Staging additionally measures worker throughput, queue depth and recovery with real configured sources using progressive activation:

```text
100
500
1,000
5,000
10,000+
```

Do not expand to the next tier if rate limits, queue recovery, provider health or database load are outside the operator-reviewed envelope.

## Gate 10 — Security

Required:

- SSRF protections remain enforced
- redirect-to-private-network protection remains enforced
- only permitted HTTP(S) public source URLs are fetched
- robots/source-policy restrictions are honored where applicable
- provider credentials are secret-managed
- no provider secret or candidate resume body appears in operational logs
- internal operator endpoints require the existing internal authorization boundary

## Gate 11 — Candidate isolation

Staging must prove Candidate A cannot access Candidate B:

- profile
- resume
- career memory
- matches
- applications
- artifacts
- notifications

Job catalog data may be shared/public according to source policy, but candidate-specific state remains isolated.

## Gate 12 — Staging acceptance command

Run:

```bash
pnpm job-supply:acceptance
```

Allowed diagnostic states:

```text
BLOCKED_EXTERNAL_CONFIGURATION
RUNTIME_EVIDENCE_AVAILABLE
PARTIAL_STAGING_ACCEPTANCE
PASS
```

Launch-ready staging requires `PASS` from the actual staging runtime. Do not change the command merely to force success.

## Marketplace partnership rule

LinkedIn, Indeed and other marketplace partnerships are parallel business-development tracks. They become launch requirements only if a launch decision explicitly depends on a capability granted by that provider.

An adapter existing in source control does not satisfy partnership, credential, storage-right or display-right gates.

## Final launch review

Record one evidence row per gate:

```text
gate
status
measured value/evidence
release commit
workflow/run identifier
operator reviewer
remaining blocker
```

The launch decision must be based on measured staging evidence, not intended architecture or synthetic inventory.