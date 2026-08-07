# ApplyAI Job Data Platform Scale & Quality Report

Updated: 2026-08-06

## Reporting rule

This document separates:

- **implemented source controls**;
- **automated verification evidence**;
- **synthetic PostgreSQL measurements**;
- **real AWS/provider staging evidence**.

No job count, throughput, deduplication rate, cloud cost, or supported scale is reported as measured
until an executable run produced the value. Career Intelligence status is tracked separately from
job-data scale so an AI feature does not manufacture evidence about provider/job scale.

## Architecture implemented

```text
EventBridge
    |
    v
bounded source dispatcher Fargate task
    |
    +-- PostgreSQL due-source query
    +-- source authority priority
    +-- in-flight lease ceiling
    +-- FOR UPDATE SKIP LOCKED
    +-- source lease + transactional outbox event
            |
            v
        source SQS
            |
            v
 dedicated source workers
    +-- SOURCE_INGEST
    +-- SOURCE_DISCOVERY
    +-- SOURCE_VERIFY
            |
            +-- registry adapter
            +-- canonical source authority
            +-- apply-link verification
            +-- closure evidence
            +-- measured run/cost observations
```

The resume and Career Intelligence queues remain separate. The application still uses one immutable
FastAPI image with role-specific commands rather than a premature microservice split.

## Implemented quality controls

### Source scheduling

- authority-based operational priority;
- minimum/default/maximum intervals;
- faster refresh for measured high-change/high-volume sources;
- slower refresh for stable/zero-volume sources;
- exponential failure slowdown bounded by configuration;
- source recovery returns to normal adaptive scheduling.

### Durable dispatch

- due source lease and `SOURCE_INGEST` outbox event are committed together;
- no direct DB-then-SQS gap;
- `FOR UPDATE SKIP LOCKED` prevents duplicate source claims;
- active lease count enforces a bounded in-flight ceiling;
- SQS redrive owns retry-to-DLQ behavior;
- source worker extends visibility during long runs.

Career Intelligence V2 adds a queue-aware publisher. Source events remain routed only to the source
queue and AI events only to the AI queue; specialized task families fail closed when their dedicated
queue is absent.

### Source authority and conflict resolution

Source priority currently ranks:

```text
EMPLOYER_DIRECT
OFFICIAL_ATS
EMPLOYER_CAREER_SITE
LICENSED_FEED
STRUCTURED_JOB_PAGE
THIRD_PARTY_SOURCE
UNVERIFIED
```

All legitimate source postings remain linked. Only the selected highest-authority fresh source may
mutate canonical candidate-facing fields. A recently fetched lower-authority copy does not
automatically overwrite an employer/official ATS source.

Field provenance records the selected source link and a value hash for:

- title;
- description;
- location/work mode;
- employment type;
- seniority;
- compensation;
- application URL.

### Closure evidence

Apply-link verification statuses:

```text
VALID
REDIRECTED
NOT_FOUND
FORBIDDEN
ERROR
UNKNOWN
```

One transient error never closes a job. Repeated configured 404/410 evidence may confirm one source
closed. The canonical job closes only when the existing multi-source lifecycle determines that all
linked sources support closure. A valid link reactivates the source/job.

### Raw payload retention

The cleanup task removes only old duplicate raw payloads and always retains the newest payload for
every posting source.

Current policy default:

```text
90 days
```

Compressed S3 archival remains deferred until measured PostgreSQL storage growth justifies the
additional lifecycle and retrieval complexity.

## Quality KPI service

Protected internal endpoints expose measured values:

```text
GET /api/v1/internal/job-quality/metrics
GET /api/v1/internal/job-quality/source-coverage
```

Available metrics include:

- active/total canonical jobs;
- source posting count and canonical/source ratio;
- new/updated/closed jobs per hour;
- duplicate, invalid and quarantine percentages;
- latest apply-URL validity;
- salary and location coverage;
- average verification age;
- p50/p95 ingestion duration;
- source failure rate;
- source coverage by provider;
- measured worker seconds, network bytes and source postings;
- estimated AWS cost only when an explicit measured observation supplies it.

A missing cost value is returned as `null`, not guessed.

Career Intelligence V2 has a separate protected `/api/v1/internal/ai-quality/metrics` surface for
model/task quality and configured model-cost observations. Those AI metrics do not substitute for
job ingestion/source-scale measurements.

## PostgreSQL benchmark methodology

`services/api/scripts/benchmark_job_search.py` creates synthetic non-production rows at one explicit
size:

```text
10,000
50,000
250,000
```

It runs `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` for:

- PostgreSQL full-text keyword search;
- location filtering;
- remote filtering;
- salary filtering;
- keyset pagination;
- saved-job list shape;
- job detail shape.

Workflow:

```text
.github/workflows/job-search-benchmark.yml
```

Pull requests run the 10K benchmark. The 50K and 250K sizes are manual gates and must not be
described as passing until those exact workflows complete.

## Executed benchmark evidence

### 10,000 synthetic jobs

Status: **NOT YET RECORDED IN THIS REPORT**

The source workflow exists. Record the exact run/artifact only after the final source-changing head
has completed; do not reuse a superseded PR run as the final scale claim.

### 50,000 synthetic jobs

Status: **NOT STARTED / NOT RECORDED**

### 250,000 synthetic jobs

Status: **NOT STARTED / NOT RECORDED**

## Partitioning decision

Status: **DEFERRED**

No current measured query requires table partitioning. The likely future candidates are raw payload
history, ingestion runs and job versions, but partitioning will not be added merely because
million-row scale is planned.

## AWS staging configuration

Terraform includes:

- dedicated source queue + source DLQ;
- source visibility/redrive controls;
- source worker task definition/service;
- bounded dispatcher EventBridge task;
- source queue depth/age/DLQ alarms;
- source-worker failure metric/alarm;
- V2 release/rollback/verification workflows;
- zero desired-count dormant foundation by default.

Career Intelligence V2 additionally introduces a separate AI queue/DLQ and worker; it does not
share source-worker throughput or source quality metrics.

## Real staging rollout gate

Start with an explicit reviewed set:

```text
5 Greenhouse boards
5 Lever sites
5 Ashby boards
```

Then prove:

- first ingest;
- identical ingest;
- material posting change;
- posting disappearance;
- failed/partial source safety;
- source recovery;
- cross-provider canonical deduplication;
- source queue DLQ and redrive;
- worker restart/lease recovery;
- repeat dispatcher run;
- apply URL verification and repeated closure evidence;
- CloudWatch alarms/log correlation;
- cost per source refresh and per 1,000 postings.

Only then increase gradually:

```text
50 sources
500 sources
5,000 sources
```

## Current status

| Area | Status | Evidence / limitation |
|---|---|---|
| Multi-source platform source | COMPLETE | Source registry/dispatcher/workers/authority/provenance/freshness/quality architecture is implemented; exact final PR head must retain green CI. |
| Career discovery source | COMPLETE | Public career-site discovery/ATS detection/import architecture exists; live provider staging remains external. |
| Source/quality infrastructure | COMPLETE | Dedicated source queue/DLQ/worker/dispatcher and quality controls are source controlled; real AWS execution remains external. |
| 10K PostgreSQL benchmark | NOT YET RECORDED | PR workflow exists; final exact-head result/artifact must be recorded before claiming pass here. |
| 50K PostgreSQL benchmark | NOT STARTED | Manual evidence gate. |
| 250K PostgreSQL benchmark | NOT STARTED | Manual evidence gate. |
| Real AWS multi-source staging | BLOCKED | Requires AWS/Clerk/Vercel staging resources and a reviewed provider list. |
| Million verified canonical jobs | NOT STARTED | No manufactured job counts. |
| Career Intelligence V1 | COMPLETE | Merged deterministic explainable matching/tailoring/application-assistant baseline. |
| Career Intelligence V2 | PARTIAL | Active PR #12 implements durable model runtime, verified Career Memory, hybrid matching and candidate copilots. Exact-head CI and real provider staging acceptance remain separate gates. |

## Reporting boundary

Do not use this job-data report to claim that Career Intelligence has validated source scale, and do
not use AI source completion to claim that 50K/250K job-search benchmarks or real provider staging
have run. Each evidence category must remain independently reproducible.
