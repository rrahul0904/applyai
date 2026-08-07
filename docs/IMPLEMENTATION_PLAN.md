# Implementation Plan

Updated: 2026-08-06

This plan distinguishes **repository/source completion** from **real external-service acceptance**.
Passing CI does not prove that AWS, Vercel, Clerk, public ATS providers or an external model have
been exercised in a real staging environment.

## Milestones 0–3 — Candidate and job-data foundation

Status: **SOURCE IMPLEMENTED**

### Milestone 0 — Architecture correction

- Next.js App Router candidate web.
- FastAPI modular monolith.
- PostgreSQL/Alembic canonical persistence.
- Clerk identity/ownership boundary.
- storage, queue, search and connector interfaces.
- source-controlled CI and deployment architecture.

### Milestone 1 — Authenticated onboarding

- candidate identity mapping;
- owner-scoped APIs;
- resume-less and resume-upload onboarding;
- direct private-S3 upload design;
- transactional outbox -> SQS -> resume worker;
- deterministic PDF/DOCX extraction, provenance review and confirmation;
- one master resume with version history.

### Milestone 2 — Candidate workflow

- PostgreSQL job search/filter/relevance/cursor pagination;
- job detail;
- save/unsave;
- application creation, status history and notes;
- persisted return-session browser acceptance;
- Candidate A/B ownership isolation.

### Milestone 3 — Multi-source job-data platform

- Greenhouse, Lever, Ashby and structured public-source architecture;
- source registry, scheduling, leasing and durable dispatch;
- canonicalization, deduplication and field provenance;
- source authority/conflict resolution;
- apply-URL verification and closure evidence;
- ACTIVE -> UNKNOWN -> STALE/closure lifecycle;
- source quality metrics and scale benchmark workflow;
- dedicated source queue/DLQ/worker/outbox infrastructure.

Real provider-scale measurements remain staging/benchmark evidence, not source claims.

## Milestone 4 — Career Intelligence V1

Status: **COMPLETE ON MAIN**

- deterministic explainable opportunity prioritization;
- six-factor 100-point baseline;
- evidence-locked resume wording;
- candidate approve/reject flow;
- cover-letter and common application-answer preparation;
- application package readiness;
- persisted browser reload journey;
- screenshots/demo artifact;
- clear boundary that ApplyAI prepares but does not externally submit applications.

V1 is retained as a compatibility/baseline layer rather than deleted.

## Milestone 5 — Career Intelligence V2

Status: **IMPLEMENTED ON PR #12; EXACT-HEAD VALIDATION REQUIRED BEFORE MERGE**

### 5A — First-class AI domain

- `AIJobRun`;
- versioned `AIArtifact`;
- `CareerMatch`;
- `ResumeTailoring` / revisions;
- `CoverLetter`;
- `ApplicationQuestionDraft`;
- candidate artifact feedback.

### 5B — Verified Career Memory

- candidate-owned facts for achievements, projects, metrics, responsibilities, certifications,
  leadership stories, interview feedback and career goals;
- explicit `USER_VERIFIED` provenance;
- archive/review behavior;
- inclusion in the AI evidence catalog.

### 5C — Durable AI runtime

- four server-owned task types;
- transactional outbox creation;
- dedicated AI SQS/DLQ routing;
- visibility heartbeat and retry behavior;
- deterministic CI provider;
- production-capable structured model-provider abstraction;
- strict JSON schema plus Pydantic validation;
- exact evidence-reference validation;
- model/prompt/schema/latency/token/configured-cost telemetry;
- transient-vs-terminal failure handling.

### 5D — Hybrid matching and copilots

- deterministic baseline retained;
- hybrid persisted match;
- evidence-grounded deep fit analysis;
- evidence-locked resume tailoring;
- application copilot;
- interview preparation;
- artifact version/supersession;
- candidate review persistence.

### 5E — Candidate product integration

- V2 actions on real `/jobs/[id]` pages;
- asynchronous polling for durable staging work;
- `/career` Career Memory workspace;
- recent artifact visibility;
- existing `/beta` reduced to compatibility/demo evidence rather than the architectural product
  surface.

### 5F — Evaluation and observability

- measured run success/failure;
- provider/task/model breakdown;
- latency/token/configured-cost telemetry;
- artifact verification rate;
- accepted/edited/rejected feedback rates;
- AI queue depth/age/DLQ alarms;
- protected operator metrics.

### 5G — Staging runtime source

- AI SQS + DLQ/redrive;
- AI Fargate worker;
- queue-aware universal outbox publisher;
- least-privilege IAM;
- conditional Secrets Manager access for provider credentials;
- release activation after migration gate;
- infrastructure verification for AI services/queues/logs/alarms.

## Milestone 6 — Real staging acceptance

Status: **BLOCKED BY EXTERNAL ENVIRONMENT**

Required before production promotion:

1. provision the real dedicated staging AWS environment;
2. configure GitHub `staging` environment and OIDC outputs;
3. issue/attach ACM certificate and API DNS;
4. configure the real Clerk staging application;
5. configure the Vercel staging project/domain;
6. approve a small explicit Greenhouse/Lever/Ashby source set;
7. run Candidate A/B browser acceptance against real services;
8. run direct S3 -> outbox -> resume SQS -> worker acceptance;
9. run source queue/provider freshness/dedup/closure acceptance;
10. configure a reviewed AI provider credential and model;
11. execute each Career Intelligence V2 task through AI SQS/worker;
12. inject transient model/worker failures and prove retry/DLQ/redrive;
13. prove evidence/schema failures fail closed;
14. verify no resume/model credential/auth-token leakage in logs;
15. record real latency/token/cost observations;
16. execute rollback and database backup/restore drills.

No repository change can honestly mark this milestone complete without those external resources.

## Milestone 7 — Production promotion

Status: **GATED**

Only after staging acceptance:

- production account/state/trust boundary;
- deletion protection and final-snapshot/PITR policy;
- production capacity/HA decisions based on measurements;
- alert routing and operational ownership;
- reviewed AI provider/model/cost budgets;
- staged rollout/rollback policy;
- privacy/security review;
- production domain and Clerk configuration.

## Later product milestones

Not part of the current Candidate/Career Intelligence completion gate:

- native iOS/Android;
- employer/recruiter platform;
- billing;
- autonomous external messaging;
- auto-apply/external form submission.

These remain separate because they materially change product permissions, risk and operating model.
