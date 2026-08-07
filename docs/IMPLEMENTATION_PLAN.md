# Implementation Plan

Updated: 2026-08-07

ApplyAI's repository/source implementation plan is complete. The remaining plan contains only real deployment, external-provider, signing, distribution and operational-evidence gates.

## Completed source milestones

### Milestone 0 — Core architecture

Status: **COMPLETE**

- Next.js App Router web product;
- FastAPI modular monolith;
- PostgreSQL/Alembic canonical persistence;
- Clerk identity and owner-scoping boundary;
- private object storage and durable queue abstractions;
- source-controlled CI and AWS/Vercel deployment architecture.

### Milestone 1 — Candidate onboarding and durable resume

Status: **COMPLETE**

- authenticated candidate mapping;
- profile/experience/education/skills/preferences;
- resume-less and resume-upload onboarding;
- private direct-S3 upload architecture;
- transactional outbox -> resume SQS -> worker;
- PDF/DOCX extraction/review/confirmation;
- one master resume plus version history and processing provenance.

### Milestone 2 — Candidate workflow

Status: **COMPLETE**

- job search/filter/relevance/cursor pagination;
- saved jobs and saved searches;
- application command center;
- statuses/events/notes;
- candidate analytics;
- notifications/reminders;
- network/recruiter contacts;
- account privacy/export/deletion;
- canonical browser acceptance and ownership isolation.

### Milestone 3 — Job-data platform

Status: **COMPLETE**

- Greenhouse/Lever/Ashby dedicated adapters;
- bounded public structured-page import;
- ATS discovery for major recognized career systems;
- source registry/scheduling/leasing;
- canonicalization/dedup/provenance/authority;
- apply-URL verification and closure evidence;
- quality metrics;
- source queue/DLQ/worker/outbox infrastructure;
- 10K/50K/250K PostgreSQL benchmark gate.

### Milestone 4 — Career Intelligence V1

Status: **COMPLETE**

- deterministic explainable ranking baseline;
- evidence-locked resume wording;
- candidate review decisions;
- cover-letter/application-answer preparation;
- readiness state and persisted browser workflow.

### Milestone 5 — Career Intelligence V2

Status: **COMPLETE**

- first-class AI runs/artifacts/matches/tailoring/cover-letter/question/feedback persistence;
- verified Career Memory;
- dedicated AI queue/DLQ/worker/outbox;
- structured provider abstraction;
- strict schema/evidence validation;
- retry/fail-closed behavior;
- prompt/model/schema/token/latency/configured-cost telemetry;
- hybrid matching;
- canonical Career Intelligence product integration.

### Milestone 6 — Candidate Product Completion

Status: **COMPLETE**

- AI Matches;
- semantic embedding reranking;
- Resume Studio;
- Application Command Center;
- Interview Copilot/practice;
- Alerts and saved searches;
- networking/follow-up workspace;
- company intelligence;
- candidate analytics;
- public pricing, subscription and privacy controls;
- `/demo` and `/beta` consolidated into canonical product routes.

### Milestone 7 — Employer Platform

Status: **COMPLETE**

- employer organizations and memberships;
- operator verification/suspension;
- employer job drafting/publishing/closure;
- first-party jobs in the canonical candidate marketplace;
- first-party applicant pipeline;
- stages, ratings, recruiter notes and dashboard metrics.

### Milestone 8 — Application Submission Orchestration

Status: **COMPLETE**

- explicit candidate review/approval boundary;
- direct submission for verified first-party ApplyAI employers;
- recorded external handoff for third-party employers;
- no employer authentication, CAPTCHA or anti-bot circumvention.

### Milestone 9 — Billing and Entitlements

Status: **COMPLETE**

- Free/Pro/Team plans and usage entitlements;
- subscription persistence;
- Stripe Checkout adapter;
- Stripe Billing Portal adapter;
- signed Stripe webhook lifecycle;
- billing ledger and candidate billing UI.

### Milestone 10 — Engagement, Operations and AI Evaluation

Status: **COMPLETE**

- notification preferences and inbox;
- saved-search job alerts;
- interview/recruiter follow-up dispatch;
- operator console and employer trust controls;
- runtime AI quality telemetry;
- golden evaluation datasets;
- ranking/evidence metrics and baseline-vs-candidate A/B comparison.

### Milestone 11 — Native Mobile and Browser Extension Source

Status: **COMPLETE**

- Expo/React Native mobile source with Clerk secure token handling;
- native Matches, Jobs, Applications, Alerts and Profile/Career Memory;
- Manifest V3 browser extension with permission-minimal public-job URL handoff;
- repository tests compile mobile TS/TSX and validate extension source/permissions.

### Milestone 12 — Infrastructure and Release Source

Status: **COMPLETE**

- AWS staging Terraform for candidate/source/AI runtime;
- CloudFormation OIDC/state bootstrap;
- immutable-image release;
- migration gate;
- rollback/recovery automation;
- infrastructure verification;
- provider/environment templates;
- production-promotion and recovery runbooks.

## Remaining external execution milestones

### Real staging activation

Status: **BLOCKED**

Requires real AWS/Vercel/Clerk/DNS/ACM resources and GitHub staging environment configuration. Then execute the existing preflight, infrastructure, release and verification workflows.

### Real candidate and worker acceptance

Status: **BLOCKED**

Prove against real services:

```text
Clerk -> Vercel -> FastAPI/ECS -> Aurora
browser -> private S3 -> outbox -> resume SQS -> worker
source dispatcher -> source SQS -> provider lifecycle
AI outbox -> AI SQS -> AI worker -> reviewed model -> validated artifact
```

Also prove Candidate A/B isolation, retries, DLQ/redrive, safe logs and rollback/recovery.

### Live model/embedding acceptance

Status: **BLOCKED**

Configure the reviewed OpenAI secret/model/embedding model in the real AI runtime and measure quality, latency, token usage and cost. Inject retryable and terminal failures and prove the existing safety boundaries.

### Live billing acceptance

Status: **BLOCKED**

Configure the real Stripe account, prices and webhook secret, then exercise Checkout, Billing Portal, signed webhooks, cancellation and entitlement transitions.

### Real notification delivery

Status: **BLOCKED**

Choose/configure email and push providers and prove delivery, preferences, opt-out and failure handling. Durable notification generation/inbox state is already complete.

### Production cloud promotion

Status: **BLOCKED**

Promote only after staging evidence determines final account/state/trust boundaries, capacity, HA, WAF/rate limiting, alert routing, provider budgets, backup/PITR and rollback approvals.

### Production recovery drills

Status: **BLOCKED**

Execute backup/restore, PITR, worker/DLQ recovery, rollback and incident drills against real infrastructure.

### Native app distribution

Status: **BLOCKED**

Configure Apple/Google developer accounts, signing/EAS credentials, native builds, App Store/Play Store review and publication.

### Browser-extension distribution

Status: **BLOCKED**

Package, sign and publish through the selected browser extension stores.

### External identity deletion

Status: **BLOCKED**

ApplyAI application-side personal-data deletion is implemented. Revoking/deleting the external Clerk identity must be completed through the configured identity provider.

## Completion rule

Source capabilities are complete when they exist in the repository and pass the applicable exact-head gate. External milestones remain blocked until genuine environment/provider/distribution evidence exists; repository source is never used to fabricate that evidence.
