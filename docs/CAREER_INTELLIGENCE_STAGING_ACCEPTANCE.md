# Career Intelligence V2 — Staging Acceptance

Updated: 2026-08-06

This runbook is the evidence gate between repository/source completion and any claim that Career
Intelligence works with real staging services. Do not mark this gate complete from local tests,
deterministic CI, screenshots, Terraform validation or an infrastructure apply alone.

## Prerequisites

The staging environment must already have:

- dedicated non-production AWS account/environment;
- GitHub `staging` environment and OIDC deploy-role values;
- ACM certificate and API DNS;
- Clerk staging application;
- Vercel staging project/domain;
- Aurora/S3/resume SQS/source SQS infrastructure;
- small reviewed ATS source set;
- AI SQS/DLQ, AI worker and universal outbox resources;
- reviewed AI provider/model configuration;
- provider API key stored in AWS Secrets Manager;
- `OPENAI_API_KEY_SECRET_ARN` set to the secret ARN only, never the key value.

If the provider remains `deterministic`, infrastructure behavior may be smoke-tested but **real model
acceptance has not happened**.

## Release gate

Run `ApplyAI Staging Release V2` with the exact full source SHA contained in `main`.

Required evidence:

```text
source SHA
immutable ECR image URI + digest
migration task definition + task ARN
migration exit code 0
AI provider/model configuration
resume/source/AI service desired counts
/health success
/ready success
source/AI queue reachability
```

A migration failure must prevent service activation.

## Infrastructure verification

Run `ApplyAI Staging Verification V2`.

Capture the successful workflow URL/run ID and verify:

- API and ALB targets healthy;
- all enabled ECS services stable;
- tasks run in private application subnets without public IPs;
- enabled runtime services use the same immutable image;
- resume/source/AI queues and DLQs have SQS-managed encryption;
- redrive policies point to the correct DLQs;
- resume S3 is private, versioned and encrypted;
- Aurora is available, encrypted, backed up and not publicly accessible;
- AI/source log groups and alarms exist;
- source dispatcher state matches the requested setting.

## Candidate A acceptance

Use a real staging Clerk account created only for acceptance.

1. sign in through the Vercel staging application;
2. complete/verify candidate profile;
3. upload one non-sensitive synthetic acceptance resume through the direct S3 path;
4. verify extraction review/confirmation;
5. add at least two Career Memory facts through `/career`;
6. open one real ingested staging job;
7. run all four Career Intelligence actions:
   - Analyze fit;
   - Tailor resume;
   - Prepare application;
   - Prepare interview;
8. confirm queued/processing state can survive browser refresh;
9. confirm final artifacts reload from PostgreSQL;
10. review/edit at least one generated artifact and submit candidate feedback.

Record only synthetic acceptance identifiers; never paste resume text or provider credentials into the
acceptance report.

## Durable AI-path evidence

For each task type, prove:

```text
HTTP task creation
 -> AIJobRun QUEUED
 -> task_outbox event
 -> universal outbox publish
 -> AI SQS message
 -> AI worker PROCESSING
 -> provider invocation
 -> strict schema validation
 -> evidence-reference validation
 -> AIArtifact/domain materialization
 -> AIJobRun COMPLETED
 -> browser polling/reload
```

Record:

- task type;
- sanitized `AIJobRun.id`;
- final status;
- provider/model;
- prompt/schema version;
- attempt count;
- latency;
- input/output token counts returned by provider;
- configured cost estimate;
- artifact type/version;
- evidence-reference count.

Do not record model API keys, auth tokens or full resume/application bodies.

## Evidence-lock acceptance

Use a synthetic resume where one attractive job requirement is deliberately absent.

The task must:

- identify the missing requirement as a gap or uncertainty;
- not claim the candidate has that skill/metric/responsibility;
- reference only evidence keys present in the server-generated catalog;
- fail rather than materialize if an injected test response uses an unknown evidence key.

Confirm the failed run stores a sanitized terminal error code and no invalid artifact is created.

## Transient provider failure injection

In a controlled non-production provider/test configuration, force one retryable provider failure such
as a synthetic transport/429/5xx response.

Required behavior:

1. worker does not delete the SQS message;
2. `AIJobRun` returns to `QUEUED` with sanitized transient error state;
3. message becomes visible after the lease/retry window;
4. a subsequent successful invocation increments `attempt_count` and completes;
5. no duplicate current artifact is created for the same run/type.

## DLQ/redrive acceptance

Force repeated retryable failure beyond the configured receive count.

Verify:

- source message leaves the AI queue after SQS redrive threshold;
- AI DLQ contains the message;
- AI DLQ alarm enters the expected alarm state;
- operator inspection can identify task/run identifiers without printing candidate content;
- after the root cause is corrected, a controlled redrive/retry can complete or be safely abandoned.

Record queue message counts/IDs only; do not copy request/model content into the report.

## Candidate B isolation

Create a second real staging Clerk acceptance account.

Candidate B must receive `404`/owner-scoped behavior when attempting to access Candidate A:

- Career Memory fact ID;
- AI run ID;
- hybrid match;
- AI artifact;
- resume tailoring/revision;
- cover letter/question draft;
- application.

Also verify Candidate B's `/career` and artifact lists contain only Candidate B records.

## Log-safety review

Inspect the staging CloudWatch groups for:

```text
/api
/worker
/source-worker
/source-dispatcher
/ai-worker
/outbox-v3
```

Search for and confirm absence of:

- provider API key/value;
- Clerk JWTs;
- `Authorization` header values;
- complete resume bodies;
- full cover letters/application answers;
- database passwords/URLs containing passwords;
- raw SQS bodies containing candidate evidence.

Operational logs may include sanitized IDs, task type, status, provider/model, timing and failure code.

## Quality telemetry acceptance

Call the protected internal AI quality endpoint with the staging operator token:

```text
GET /api/v1/internal/ai-quality/metrics?window_hours=24
```

Verify the result matches observed staging activity:

- completed/failed run counts;
- provider/task/model breakdown;
- nonzero latency for real model calls;
- provider token counts when returned;
- configured cost estimate derived from returned usage;
- candidate artifact verification rate;
- feedback counts.

Do not infer a missing provider usage field. Missing evidence stays missing/zero according to the
service contract.

## Source and job-quality acceptance

Career Intelligence acceptance is invalid if it is run only against fabricated production-like job
rows. For the selected staging job, verify its source provenance and apply URL through the existing
job-data quality/ingestion tooling.

Separately complete the source lifecycle acceptance documented in the job-data runbooks:
identical fetch, material update, disappearance, failed/partial fetch, recovery, dedup and closure
evidence.

## Recovery acceptance

Before production promotion:

1. perform application-image rollback using the immutable previous image path;
2. confirm schema remains roll-forward compatible;
3. run an Aurora backup/restore drill to a non-production recovery target;
4. verify restored Career Memory, AI runs/artifacts, applications and resume metadata;
5. verify private S3 resume versions remain accessible to the recovered application using the
   documented recovery process.

## Acceptance record

A complete acceptance record should contain:

```text
Date/time
Source SHA
Image digest
GitHub release run ID
GitHub verification run ID
Vercel deployment identifier
Clerk staging tenant identifier (non-secret)
Reviewed ATS source identifiers
AI provider/model
Candidate A/B synthetic acceptance IDs
Four sanitized AIJobRun IDs + outcomes
Failure-injection run IDs
DLQ/redrive evidence
Quality-metrics snapshot
Rollback run ID
Backup/restore evidence
Known limitations / follow-up issues
Final go/no-go decision
```

## Exit criteria

Career Intelligence real-service staging may be marked `COMPLETE` only when all of the following are
true:

- all four task types complete through the real durable AI path;
- evidence/schema safeguards are proven by failure injection;
- transient retry and DLQ/redrive are proven;
- Candidate A/B isolation is proven;
- logs pass secret/content safety review;
- real provider latency/token/cost evidence is recorded;
- source/job provenance for the acceptance job is verified;
- rollback and database recovery drills pass.

Anything less remains `PARTIAL` or `BLOCKED`; repository CI is not a substitute for this record.
