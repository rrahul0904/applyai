# ApplyAI Job Data Platform — AWS Staging Validation

## Purpose

This is the real-services gate after Prompt 1, Prompt 2 and Prompt 3 source verification.

Passing local/CI fixtures does not prove:

- public provider availability;
- AWS network access;
- SQS retry/redrive behavior;
- ECS worker recovery;
- Aurora throughput;
- CloudWatch signal quality;
- real cost per refresh;
- real closure latency.

## Required GitHub staging variables

Existing deployment variables remain required. Add these public identifier arrays:

```text
GREENHOUSE_BOARD_TOKENS=["reviewed-board-1"]
LEVER_SITE_NAMES=["reviewed-site-1"]
ASHBY_BOARD_NAMES=["reviewed-board-1"]
```

Use JSON arrays. Start with no more than five per provider. These are public ATS identifiers, not credentials.

Do not store:

- AWS access keys;
- Clerk secret keys;
- private ATS tokens;
- passwords;
- authenticated/private endpoint URLs.

GitHub OIDC and RDS-managed credentials remain the deployment path.

## Deployment sequence

```text
1. Apply dormant Terraform foundation
2. Run ApplyAI Staging Release V2
   - immutable image
   - Alembic gate
   - API = 1
   - resume worker = 1
   - source worker = 1
   - outbox = 1
   - dispatcher disabled initially
3. Run ApplyAI Staging Verification V2
4. Run ApplyAI Staging Source Bootstrap
5. Manually dispatch one source batch
6. Inspect results/metrics/logs
7. Enable EventBridge dispatcher
8. Run failure/recovery drills
```

Do not enable the periodic dispatcher before a single reviewed batch succeeds.

## Initial source set

Recommended maximum first proof:

```text
5 Greenhouse boards
5 Lever sites
5 Ashby boards
```

Select employers with ordinary public career boards. Avoid enormous/high-change boards in the first run.

Record for every source:

- company;
- provider;
- public board/site identity;
- review date;
- why access is legitimate/public;
- expected approximate posting count;
- operator who enabled it.

## Source registration

Run:

```text
ApplyAI Staging Source Bootstrap
```

This launches a private one-shot ECS task using Aurora’s managed secret. It registers only the reviewed GitHub environment arrays and caps each provider at five.

It deliberately does not:

- expose the internal API token;
- store provider identifiers in Terraform state;
- begin ingestion directly;
- bypass provider access restrictions.

## Manual first dispatch

Before enabling EventBridge, run the dispatcher task once from ECS or temporarily invoke the dispatcher command in a one-shot task:

```bash
uv run python -m app.jobs.dispatcher
```

Expected durable path:

```text
PostgreSQL due source claim
  + source lease
  + SOURCE_INGEST outbox event
        ↓ commit
outbox publisher
        ↓
dedicated source SQS
        ↓
source worker
        ↓
provider fetch / normalize / validate / dedup
        ↓
Aurora canonical jobs + source links + run metrics
```

## Required proof matrix

For each provider type, prove:

### Initial ingest

- run COMPLETED;
- valid records linked to canonical jobs;
- invalid records retained but non-searchable;
- source health HEALTHY;
- source queue returns to zero;
- source DLQ remains zero.

### Identical ingest

- no duplicate canonical jobs;
- no duplicate source links;
- no unnecessary JobVersion rows;
- `last_seen_at` advances;
- adaptive interval is recorded.

### Material change

Use a naturally changed or controlled fixture source when possible.

Prove:

- authoritative source updates canonical fields;
- JobVersion is created once;
- field provenance points to the selected source;
- lower-authority copies do not overwrite official ATS data.

### Disappearance and recovery

Prove completed source runs only:

```text
ACTIVE -> UNKNOWN -> STALE
```

Then restore/reobserve the posting:

```text
UNKNOWN/STALE -> ACTIVE
```

Failed or partial runs must not count as missing evidence.

### Multi-source canonical job

Create/identify one posting represented by two legitimate sources.

Prove:

- one canonical job;
- two source links;
- higher-authority source remains primary;
- one missing source does not stale/close the job while another stays fresh.

### Apply URL verification

Prove:

- valid/redirected URL result;
- one temporary failure does not close;
- repeated controlled 404/410 evidence can confirm one source closed;
- canonical job closes only when all linked source evidence supports it;
- a valid URL again reactivates the job.

Never submit an application during validation.

### Queue and worker recovery

1. Stop source workers with messages visible.
2. Confirm messages remain in SQS.
3. Restore workers.
4. Confirm processing resumes idempotently.
5. Force one controlled repeat failure until DLQ.
6. Inspect only sanitized identifiers.
7. Redrive after fixing the condition.

### Dispatcher idempotency

Run overlapping dispatcher tasks.

Prove:

- `FOR UPDATE SKIP LOCKED` prevents duplicate claims;
- one active lease per source;
- max-inflight ceiling applies backpressure;
- expired lease can be reclaimed after worker loss.

## Observability proof

CloudWatch should expose:

- source queue depth;
- oldest source message;
- source DLQ count;
- source task failures;
- source worker logs;
- source/run IDs;
- provider;
- duration;
- fetched/valid/invalid/created/updated/unchanged/dedup/closed counts.

Logs must not contain:

- access credentials;
- authorization headers;
- full HTML pages;
- full descriptions in routine logs;
- candidate resumes;
- operator tokens.

## Quality API evidence

Using the separately configured internal operator token, record outputs from:

```text
GET /api/v1/internal/job-quality/metrics
GET /api/v1/internal/job-quality/source-coverage
```

Capture:

- canonical/source ratio;
- invalid/quarantine rate;
- apply URL validity;
- salary/location coverage;
- average verification age;
- p50/p95 ingestion duration;
- source failure rate;
- provider coverage;
- measured worker seconds and source postings.

Do not convert worker seconds into a dollar estimate until actual AWS runtime pricing/usage is attached to the observation.

## Cost measurement

For each controlled source batch record:

- number of sources;
- source postings fetched;
- canonical jobs created/changed;
- ECS source-worker runtime;
- dispatcher runtime;
- Aurora change in storage/connections/ACU behavior;
- SQS requests;
- NAT data processing/transfer;
- CloudWatch log ingestion;
- database growth.

Then calculate from billed/observed usage:

```text
cost per source refresh
cost per 1,000 source postings
cost per 1,000 active canonical jobs
```

Do not extrapolate to one million jobs from fixtures alone.

## Scale progression

Advance only when the previous step remains healthy for repeated cycles:

```text
15 reviewed sources
50 sources
500 sources
5,000 sources
```

At each step review:

- queue age;
- worker utilization;
- DB pool/connection pressure;
- ingestion p95;
- failure rate;
- duplicate/invalid rates;
- stale/closure latency;
- cost telemetry.

## Rollback

Application rollback:

```text
ApplyAI Staging Rollback V2
```

This restores one existing immutable image across API/resume/source/outbox task definitions.

Database schema remains roll-forward only. Do not automatically run Alembic downgrade.

For source incidents:

1. disable EventBridge dispatcher;
2. set source-worker desired count as appropriate;
3. disable/block affected registry sources;
4. preserve queue/DLQ evidence;
5. correct forward;
6. redrive controlled messages.

## Exit criteria

Real multi-source staging is COMPLETE only when:

- reviewed Greenhouse/Lever/Ashby runs succeed;
- repeat ingestion is idempotent;
- freshness/recovery works;
- authority/dedup works across sources;
- SQS retry/DLQ/redrive works;
- worker restart and expired-lease recovery work;
- apply-link evidence works without application submission;
- metrics/logs are complete and PII-safe;
- backup/restore and application rollback are rehearsed;
- actual cost observations are recorded.

Until then, AI matching remains blocked.
