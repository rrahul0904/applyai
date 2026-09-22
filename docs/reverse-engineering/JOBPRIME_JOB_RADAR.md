# JobPrime -> ApplyAI Job Radar reverse-engineering contract

Status: reverse engineering started (2026-09-22)
Source: https://jobprime.vercel.app/
Canonical destination: ApplyAI (`/jobs`, `/matches`, alerts, Career Intelligence)

## Product decision

JobPrime is a capability donor, not a new standalone product. Its useful surface is the autonomous discovery loop: a candidate confirms a resume-derived search profile, the system fans out across multiple job queries, normalizes and filters listings, ranks them, explains the strongest matches, returns direct application links, and can repeat that scan on a schedule.

ApplyAI already owns canonical jobs, candidate preferences, deterministic Career Intelligence, durable AI jobs, saved searches, alerts, application handoff and billing. The implementation below therefore extends those boundaries rather than duplicating a second job marketplace.

## Evidence boundary

### Publicly observed / creator-described behavior

The public product and creator descriptions support the following behaviors:

- resume upload -> structured candidate/profile extraction -> confirmation;
- multi-query job discovery using job-search provider data;
- deterministic pre-filtering/scoring before expensive model ranking;
- role/title, skills, experience and location signals, with compensation as an additional boost/normalization input;
- bulk model ranking with structured output validation;
- progress visibility while a scan is running;
- direct handoff to the original employer/provider application URL rather than hosting the application itself;
- recurring delivery of selected matches;
- scan/rate limits and a free-trial concept.

Public descriptions are not fully version-consistent: scan breadth and result counts vary (for example, daily aggregate claims versus per-run claims, and top-10 delivery versus top-5-per-query descriptions). ApplyAI must therefore treat query count, provider breadth and top-K as configuration, not copied constants.

### Not verified from upstream source

No public JobPrime source repository was identified in this pass. Exact database schema, prompts, model-key racing implementation, cron expressions, production quotas, provider contracts and internal scoring blend are therefore **not** treated as source truth. The contracts below are a clean-room reconstruction adapted to ApplyAI.

## Target end-to-end flow

1. Candidate opens Job Radar and chooses an existing ApplyAI resume/profile.
2. ApplyAI derives a `JobSearchProfile` from verified resume/profile evidence.
3. Candidate confirms or edits target titles, skills, experience level, preferred locations/work mode and compensation floor.
4. Validator identifies weak/missing search fields and asks only targeted follow-up questions.
5. Query planner produces a configurable bounded set of search queries from target titles + skills + location/work mode.
6. A provider adapter executes bounded concurrent searches. Initial adapter can target JSearch/RapidAPI, but the domain contract must remain provider-neutral.
7. Results are normalized into canonical ApplyAI jobs, deduplicated, freshness-filtered and checked for a valid public handoff URL.
8. Cheap deterministic scoring runs first. The observed JobPrime-style baseline can be represented as configurable weights around role/title fit, skill fit, experience fit and location fit, with compensation handled as a bounded boost/constraint rather than an opaque hiring-probability score.
9. Only the shortlist is sent to the existing ApplyAI AI task/provider boundary for bulk reranking/explanations with strict structured-output validation and evidence references.
10. Matches are persisted with score breakdowns, rank, reasons, scan provenance and candidate state.
11. The web UI streams scan progress and renders new matches as they become available.
12. Candidate may save, dismiss or open the original application link. Third-party applications remain an explicit external handoff.
13. If Job Radar is enabled, a durable scheduled task repeats the scan in the candidate's timezone, suppresses already-delivered postings and emits the configured top-K through the notification channel.
14. Feedback (`save`, `dismiss`, `opened`, `applied`) becomes calibration/evaluation data; it does not silently rewrite scoring weights in production.

## Domain model

### `job_search_profiles`

- `id`
- `candidate_id`
- `resume_version_id`
- `target_titles[]`
- `skills[]`
- `years_experience`
- `seniority_preferences[]`
- `preferred_locations[]`
- `remote_policy`
- `salary_min`
- `salary_currency`
- `query_hints`
- `confirmed_at`
- `created_at`, `updated_at`

### `job_scans`

- `id`
- `candidate_id`
- `profile_id`
- `status` (`queued|running|completed|partial|failed`)
- `query_plan_json`
- `provider_set_json`
- `jobs_seen`
- `jobs_after_filter`
- `jobs_ranked`
- `started_at`, `completed_at`
- `error_code`, `error_detail`

### canonical `jobs`

Reuse the existing ApplyAI job entity. Provider ingestion should retain sufficient source provenance to deduplicate and to preserve the public application handoff:

- provider + provider job id
- canonical application URL
- title/company/location/work mode/employment type
- salary min/max/currency/period when evidenced
- posted timestamp when evidenced
- source payload/version/hash where policy permits
- first/last seen timestamps

### `job_matches`

Extend/reuse the existing Career Intelligence match artifact rather than create a parallel relevance system:

- scan id + canonical job id
- deterministic score + score breakdown
- optional AI rerank score/position
- final display rank
- evidence-bound match reasons
- candidate state (`new|saved|dismissed|opened|applied`)
- timestamps

### `job_radar_preferences`

- candidate id
- enabled
- cadence
- timezone
- local delivery time/window
- top-K
- notification channel(s)
- provider/query budget
- last successful scan/delivery timestamps

### `job_delivery_log`

- candidate id
- scan id
- channel
- selected match ids
- delivery state
- provider message id where available
- retry/error metadata
- sent timestamp

## Service contracts

Provider boundary:

```python
class JobProvider(Protocol):
    async def search(self, request: SearchRequest) -> list[NormalizedJobCandidate]: ...
```

Scoring boundary:

```python
class JobPreScorer(Protocol):
    def score(self, profile: JobSearchProfile, job: CanonicalJob) -> ScoreBreakdown: ...
```

AI rerank boundary must reuse ApplyAI's durable AI task/provider path so provider/model/prompt/schema/latency/token/cost provenance remains auditable.

Delivery boundary:

```python
class MatchDeliveryChannel(Protocol):
    async def deliver(self, candidate, matches, preferences) -> DeliveryResult: ...
```

Email/in-app can be the first supported channels. Telegram may be implemented later as an adapter; it is not required to clone the donor.

## Proposed API surface

- `POST /v1/job-radar/profiles/from-resume`
- `GET /v1/job-radar/profile`
- `PUT /v1/job-radar/profile`
- `POST /v1/job-radar/scans`
- `GET /v1/job-radar/scans/{scan_id}`
- `GET /v1/job-radar/scans/{scan_id}/events` (SSE or existing event transport)
- `GET /v1/job-radar/matches`
- `POST /v1/job-radar/matches/{match_id}/state`
- `GET /v1/job-radar/preferences`
- `PUT /v1/job-radar/preferences`

The scheduler/worker invokes the same application service used by `POST /scans`; no privileged second implementation path.

## Deterministic ranking contract

The donor description references a weighted local score dominated by title/role, then skills, experience and preferred location, with salary adjustments. In ApplyAI:

- keep all weights versioned configuration;
- retain a per-signal score breakdown;
- treat missing evidence explicitly rather than imputing positive fit;
- apply hard/soft location constraints before AI reranking;
- normalize compensation periods/currencies only when evidence supports the conversion;
- use freshness and duplicate suppression as separate product signals;
- do not present the score as probability of interview, offer or hiring.

The AI stage may reorder a bounded deterministic shortlist and produce concise evidence-bound explanations. It must not fabricate qualifications, salary or employer facts.

## Salary normalizer test matrix

Must cover at least:

- annual range (`$120k-$150k/year`);
- single annual number;
- hourly rate/range;
- monthly compensation;
- Indian LPA/CTC representations;
- currency symbols/codes;
- `from` / `up to` ranges;
- malformed, contradictory or absent salary;
- explicit preservation of unknown instead of invented estimates.

## Dedupe contract

Prefer provider job id when stable, then canonicalized application URL. A conservative fallback may use normalized company + title + location + posting-time bucket. Never collapse two postings solely because descriptions are semantically similar.

Across scheduled scans, already-delivered jobs stay suppressed unless the posting materially changes or the candidate explicitly resets the radar history.

## Realtime scan UX

`/jobs` and `/matches` should expose a Job Radar state without creating a parallel product shell:

- profile readiness / missing inputs;
- scan queued/running/completed/partial/failed;
- queries completed / total;
- normalized jobs seen and shortlisted;
- new matches streamed as durable scan artifacts become available;
- retry-safe refresh/reconnect;
- clear provider/error state instead of an endless spinner.

## Scheduling and delivery

Use ApplyAI's durable task/outbox worker architecture. Required properties:

- candidate timezone aware;
- idempotency key per profile + intended schedule slot;
- bounded concurrency and provider quota accounting;
- retry/backoff for transient provider failure;
- partial-success status when one query/provider fails but useful matches exist;
- no duplicate notification for the same candidate/job/delivery campaign;
- a visible last-run/next-run state;
- user can pause Radar immediately.

## Rate limits / entitlements

Rate limits are product configuration, not donor constants. Enforce by authenticated candidate + entitlement, with an IP-abuse backstop. Do not rely on IP as the canonical quota identity.

Track provider request cost, AI request cost and jobs processed per scan so Free/Pro limits can be priced from real telemetry.

## Privacy and application boundary

- A scheduled radar requires explicit persistence of the confirmed search profile and delivery preferences.
- Retain only provider/job payload fields needed by ApplyAI policy and provider terms.
- Candidate can disable Radar and remove Radar preferences/history under the existing account-data controls.
- Third-party application action opens/records the public employer/provider handoff. It does not bypass login, CAPTCHA, anti-bot controls or private endpoints.
- No autonomous application submission is introduced by this donor.

## Observability

Per scan record:

- query count and per-query latency;
- provider success/failure/rate-limit counts;
- raw count -> deduped -> filtered -> pre-scored -> AI-ranked -> delivered funnel;
- AI provider/model/prompt/schema version and validation outcome;
- delivery success/failure;
- cost estimate where configured.

Quality dashboard/evals should monitor Precision@5/10, save/open/apply downstream rates, duplicate rate, unsupported explanation rate and stale-job rate without turning behavioral feedback into an unreviewed ranking mutation.

## Failure modes

- provider 429/5xx -> bounded retry/failover, preserve partial scan;
- malformed provider result -> reject only the malformed record when safe;
- AI timeout -> deterministic shortlist remains usable and scan is marked degraded/partial;
- invalid AI JSON/evidence -> validate/repair once, then fail closed to deterministic order;
- scheduler duplicate -> idempotency prevents duplicate scan/delivery;
- invalid/dead application URL -> hide direct-apply CTA and record quality issue;
- user changes resume/profile mid-scan -> scan remains pinned to its profile/version provenance.

## Implementation slices

### Phase A — repository implementation

1. Persist confirmed `JobSearchProfile` and `JobScan` contracts/migration.
2. Add provider abstraction and one reviewed provider adapter.
3. Add normalization, dedupe, salary parsing and deterministic pre-score with unit tests.
4. Add on-demand durable scan orchestration and match persistence.

### Phase B — candidate experience

1. Resume/profile -> search-profile confirmation UI.
2. Job Radar scan action and progress transport.
3. Match cards with evidence breakdown, salary/source/recency and direct-apply handoff.
4. Save/dismiss/open/applied feedback.

### Phase C — autonomous loop

1. Radar preferences and timezone-aware schedule.
2. Idempotent durable scheduled scans.
3. In-app/email digest; optional Telegram adapter later.
4. Delivery dedupe and quota/entitlement enforcement.

### Phase D — certification

1. Provider sandbox/live acceptance and quota evidence.
2. Hosted Postgres migration + worker scheduling evidence.
3. Browser/mobile UAT for profile -> scan -> match -> direct apply.
4. Failure injection for 429/5xx/AI malformed output/scheduler retry.
5. Evaluation report against the existing deterministic Career Intelligence baseline.

## Minimum acceptance criteria

- A confirmed profile can start a bounded multi-query scan.
- Provider results normalize into canonical jobs and dedupe deterministically.
- Every displayed score has a signal breakdown and source evidence.
- The AI layer can be disabled/fail without making the scan unusable.
- Progress is reconnect-safe and reflects durable state.
- Top-K and query breadth are configurable.
- Every third-party application CTA resolves to a public source URL and is an explicit handoff.
- Scheduled scans are timezone-aware, idempotent, pausable and suppress already-delivered jobs.
- Unit/integration tests cover provider failures, salary normalization, location rules, dedupe, structured AI validation, scheduler idempotency and delivery dedupe.
- Hosted/provider certification remains clearly separate from repository-complete behavior.

## Smallest truthful next implementation action

Implement **Phase A steps 1-3 only**: the persisted search-profile/scan contracts, a provider-neutral adapter with one concrete provider, and deterministic normalize/dedupe/salary/score logic with tests. Do not start scheduled delivery or model reranking until one on-demand scan is repository-tested end to end. This creates a useful vertical slice while preserving ApplyAI's existing architecture and avoids claiming JobPrime parity from documentation alone.
