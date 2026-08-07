# Career Intelligence V2

Updated: 2026-08-06

## Purpose

Career Intelligence V2 turns ApplyAI's deterministic Candidate MVP into a durable,
evidence-grounded career intelligence platform without weakening the existing factuality,
ownership, job-quality, or deployment boundaries.

The system intentionally keeps four things separate:

1. **verified candidate evidence** — profile, resume-confirmed facts and Career Memory;
2. **verified job/source evidence** — canonical job data plus source provenance;
3. **deterministic product signals** — the existing explainable V1 score and factors;
4. **model output** — reviewable inference that can never silently become verified fact.

A model recommendation is not a hiring probability. ApplyAI does not claim that an external
application, email or recruiter message was submitted merely because content was prepared.

## Candidate surfaces

Career Intelligence is part of the normal candidate application, not a screenshot-only demo.

- `/jobs/[id]` contains Analyze fit, Tailor resume, Prepare application and Prepare interview.
- `/career` is the verified Career Memory and recent-artifact workspace.
- queued durable work is polled until it becomes `COMPLETED` or `FAILED`.
- candidate review state persists independently of the transient browser session.

The historical `/beta` journey remains regression/demo evidence for V1 compatibility; it is no
longer the architectural home of Career Intelligence.

## Durable data model

First-class tables replace the V1 practice of treating generic application-answer rows as the
primary AI artifact store:

```text
AIJobRun
  -> AIArtifact
      -> ResumeTailoring -> ResumeTailoringRevision
      -> CoverLetter
      -> ApplicationQuestionDraft

CandidateCareerFact
CareerMatch
CandidateAIArtifactFeedback
```

`AIJobRun` records task, candidate/job/application ownership, provider, model, prompt version,
schema version, stable input hash, idempotency key, status, input/output JSON, evidence refs,
attempt count, latency, token counts, configured cost estimate and sanitized failure code.

`AIArtifact` provides immutable-version semantics across runs. A newly materialized artifact for
the same candidate/job/type supersedes the prior current version instead of overwriting history.

## Career Memory

`CandidateCareerFact` stores durable candidate evidence such as:

- achievements;
- projects;
- measurable results;
- responsibilities;
- certifications;
- leadership stories;
- interview feedback;
- career goals.

Candidate-created facts enter as `USER_VERIFIED`. A model cannot directly promote an inference
into Career Memory. Archived or unverified facts are excluded from the default AI evidence
context.

## Evidence context

Every AI task receives one JSON-safe context built from server-side persisted data:

```text
candidate
  profile
  target roles
  skills
  experiences
  preferences
  verified Career Memory

job
  title/company/description
  source URL
  locations/work mode
  skills
  requirements
  compensation

deterministic_match

evidence_catalog
```

Every factual model claim must reference exact keys in `evidence_catalog`. The runtime rejects
unknown or missing evidence references before materializing an artifact.

## Task types

Career Intelligence V2 currently supports:

```text
AI_DEEP_MATCH
AI_RESUME_TAILOR
AI_APPLICATION_COPILOT
AI_INTERVIEW_PREP
```

### Deep match

The V1 deterministic match remains the auditable baseline. V2 stores a hybrid score as:

```text
65% deterministic baseline + 35% model score
```

The output includes a prioritization decision, strengths, gaps, interview risks and recommended
actions. The score ranks candidate attention; it does not estimate employer response probability.

### Resume tailoring

Every proposed edit stores:

- original/source text;
- suggested text;
- reason;
- exact evidence references;
- risk flags;
- confidence;
- candidate decision and candidate-edited text.

The policy remains `EVIDENCE_LOCKED`. Unsupported employers, skills, metrics, duties, dates,
achievements or outcomes fail the contract rather than becoming resume content.

### Application copilot

Produces reviewable:

- cover-letter material;
- application-question drafts;
- recruiter outreach;
- strategy notes.

The artifact is preparation only. Candidate verification remains explicit and external form/email
submission is outside the current product boundary.

### Interview preparation

Produces role-specific likely questions, why each question matters, evidence-grounded answer
outlines, questions for the employer and a gap plan. It cannot manufacture a STAR story that the
candidate evidence does not support.

## Provider boundary

`BaseAIProvider` isolates model transport from product persistence and safety logic.

### Deterministic provider

Used by local development and CI. It is a predictable evidence-safe test/baseline provider and is
not represented to candidates or operators as an LLM.

### OpenAI Responses provider

The production-capable provider uses server-side HTTP only and requests strict JSON-schema
output. Provider credentials are never placed in browser configuration, task payloads, Terraform
plain-text variables, model context or logs.

OpenAI transient transport, 429 and 5xx failures remain retryable. Schema/evidence violations and
non-retryable provider responses fail closed.

Model name, reasoning level and cost coefficients are configuration, so a reviewed deployment can
change them without changing persistence contracts.

## Queue and worker architecture

```text
Candidate/API
   |
   v
PostgreSQL transaction
  AIJobRun + task_outbox
   |
   v
queue-aware outbox publisher
   |
   +--> resume SQS
   +--> source SQS
   +--> AI SQS
             |
             v
          AI worker
             |
             +--> provider
             +--> strict Pydantic/JSON schema
             +--> evidence validation
             +--> materialization
```

Specialized source and AI task types fail closed when their dedicated queue is missing. The
publisher filters claims by routable task family so multiple publishers cannot accidentally put an
AI task onto the resume queue.

AI SQS uses visibility heartbeat, retry and DLQ behavior. A transient model failure is not
acknowledged; terminal validated failures are persisted and acknowledged so poison messages do not
loop forever.

## Staging architecture

Terraform adds:

- AI SQS queue and DLQ/redrive;
- AI ECS/Fargate worker;
- queue-aware universal outbox service;
- least-privilege SQS IAM;
- conditional Secrets Manager access for the model credential;
- AI queue depth, age and DLQ alarms;
- dedicated CloudWatch log groups.

The V2 staging release performs migration first, then can activate resume, source and Career
Intelligence runtimes from the same immutable API image. V2 verification checks AI service desired
state, private networking, queue encryption/redrive, log groups and alarms.

A real OpenAI model invocation is **not** claimed by source validation. It requires an actual
staging deployment with a reviewed credential and explicit acceptance run.

## Quality and cost telemetry

Protected internal metrics expose measured values only:

```text
GET /api/v1/internal/ai-quality/metrics
```

Metrics include:

- total/completed/failed runs;
- success/failure rates;
- status/task/provider counts;
- average measured latency;
- input/output token totals when supplied by the provider;
- configured cost estimate when token usage is available;
- artifact candidate-verification rate;
- accepted/edited/rejected feedback rates;
- provider/model/task/status breakdown.

The deterministic CI provider produces zero model tokens and zero model cost rather than inventing
usage.

## Acceptance gates

### Repository/source gate

Required on the exact candidate head:

```text
web lint
web typecheck
web unit tests
Next.js production build
OpenAPI drift
API tests
Alembic zero-to-head and drift check
API container build
Terraform fmt/init/validate
workflow static validation
Candidate MVP Playwright
functional candidate workspace Playwright
Career Intelligence browser regression
```

### Real staging gate

Source completion does not satisfy this gate. Staging must prove:

1. real Clerk candidate login through Vercel to ECS/Aurora;
2. real S3 resume path and resume SQS worker;
3. source dispatcher/source worker and provider lifecycle;
4. AI outbox -> AI SQS -> AI worker -> reviewed provider -> artifact;
5. one successful model invocation for each enabled V2 task type;
6. model/schema/evidence failure behavior;
7. 429/5xx retry and DLQ/redrive behavior;
8. Candidate A/B isolation for Career Memory, runs, matches and artifacts;
9. CloudWatch logs contain no resume bodies, model credentials or auth tokens;
10. measured latency/token/cost observations;
11. rollback/recovery and database restore drills.

Until those external resources and credentials exist, real-service acceptance remains `BLOCKED`
regardless of repository CI status.

## Deferred product boundaries

The following are intentionally separate milestones:

- automatic external application submission;
- employer/recruiter product;
- billing;
- native iOS/Android applications;
- autonomous messaging on the candidate's behalf.

They must not be smuggled into Career Intelligence by calling content preparation "auto-apply".
