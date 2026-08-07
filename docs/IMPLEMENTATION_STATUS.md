# Implementation Status

Updated: 2026-08-07

This file is the source-of-truth status for ApplyAI after platform completion.

Statuses are intentionally restricted to:

- `COMPLETE` — the product/source capability exists and has an applicable repository validation gate.
- `BLOCKED` — the remaining work requires a real external environment, provider account, secret, signing identity, store publication, or live operational evidence that cannot be fabricated from source control.

## Platform/source status

| Capability | Status | Evidence / boundary |
|---|---|---|
| Core architecture | COMPLETE | Next.js App Router + Clerk; FastAPI modular monolith; PostgreSQL/Alembic; private S3; SQS; Vercel/AWS target. No unnecessary Redis/OpenSearch/Kafka/Kubernetes/microservice split. |
| Candidate authorization and isolation | COMPLETE | Candidate profile, resume, saved-job, application, note, Career Memory and Career Intelligence APIs are owner scoped; deterministic multi-user browser/API coverage exists. |
| Candidate onboarding/profile | COMPLETE | Identity mapping, onboarding state, profile, experience, education, skills, target roles, work-mode/location/compensation preferences and resume-less fallback are implemented. |
| Resume upload and processing durability | COMPLETE | Upload intent -> presigned S3 PUT -> object verification -> `ResumeVersion + task_outbox`; versioning, idempotent processing attempts, heartbeat/retry/DLQ and candidate confirmation/provenance exist. |
| Resume Studio | COMPLETE | Candidate-owned job-specific resume variants, editable content, revisions, review/final states, verified-evidence attachment and TXT/HTML export are implemented. |
| Job search and detail | COMPLETE | PostgreSQL FTS, filters, stable cursors, detail, provenance, saved jobs, company intelligence and N+1 regression protection are implemented. |
| Saved searches and job alerts | COMPLETE | Saved-search persistence, thresholds, alert preferences, notification creation and candidate inbox/read state are implemented. |
| Multi-source job-data platform | COMPLETE | Greenhouse/Lever/Ashby adapters, structured public-page import, source registry, scheduling/leasing, authority/provenance, dedup, freshness, closure evidence, URL verification and quality metrics exist. |
| ATS/career-site discovery | COMPLETE | Discovery identifies Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, iCIMS, Oracle and SuccessFactors; unsupported board APIs use the bounded public structured-page path without bypassing access controls. |
| Job-scale repository gate | COMPLETE | PostgreSQL benchmark workflow validates 10K, 50K and 250K synthetic job corpora on the completion head. |
| OpenAPI contract discipline | COMPLETE | Public APIs are typed, generated client contract is committed, the temporary generation workflow is removed, and exact-head drift validation passes. |
| Database migrations | COMPLETE | Alembic revisions cover Career Intelligence, Career Memory and platform-completion domains; zero-to-head and metadata drift validation pass. |
| Canonical browser acceptance | COMPLETE | Browser -> Next.js -> FastAPI -> PostgreSQL journey covers onboarding, resume review, search, save, application persistence, canonical platform workspaces, relogin and ownership isolation. |
| Fresh local clean-room reproducibility | COMPLETE | `pnpm local:certify` is executed by a dedicated fresh-checkout workflow and has passed from a pristine GitHub-hosted Ubuntu runner: locked install, clean DB recreation, migrations, isolated API/web/OpenAPI gates, deterministic seed, local integrations, workers and browser acceptance. This does not guarantee every host-specific workstation configuration. |
| Production-shaped local S3/SQS/SMTP integration | COMPLETE | LocalStack exercises the real boto3 S3/SQS code paths including presigned resume PUTs, separate queue families/DLQs and live outbox/workers; Mailpit exercises the real SMTP provider and captured delivery. |
| Local Clerk/OpenAI/Stripe protocol integration | COMPLETE | A controlled local provider server exercises the real Clerk RS256/JWKS verifier, real OpenAI Responses and embeddings clients, and Stripe checkout/portal request handling; ApplyAI separately verifies signed Stripe webhook persistence. These are local protocol tests, not live vendor-account acceptance. |
| Career Intelligence V1 baseline | COMPLETE | Deterministic six-factor explainable prioritization, evidence-locked tailoring and application-readiness baseline remain supported. |
| Career Intelligence V2 domain | COMPLETE | `AIJobRun`, versioned `AIArtifact`, `CareerMatch`, tailoring/revisions, cover letters, application-question drafts, feedback and durable persistence are implemented. |
| Verified Career Memory | COMPLETE | Candidate-owned verified achievements, projects, metrics, responsibilities, certifications, leadership stories, interview feedback and goals have CRUD/summary/archive/provenance behavior and AI evidence inclusion. |
| Durable AI queue runtime | COMPLETE | Dedicated AI task family, transactional outbox, AI SQS/DLQ routing, queue-aware claims, worker heartbeat/retry and transient-vs-terminal error behavior are implemented. |
| Structured model-provider boundary | COMPLETE | Deterministic CI provider plus server-side OpenAI structured provider, JSON/Pydantic schema validation, exact evidence-reference validation and provider/model/prompt/schema/token/latency/configured-cost telemetry exist. |
| Hybrid matching | COMPLETE | Explainable deterministic baseline plus persisted hybrid Career Intelligence matching is implemented. |
| Semantic matching | COMPLETE | Provider-abstracted embedding reranker with deterministic local CI execution and optional server-side OpenAI embedding provider is implemented. |
| AI Matches product | COMPLETE | Canonical `/matches` surface combines semantic opportunity ranking with Career Intelligence factors and clear non-probability language. |
| Resume Intelligence | COMPLETE | Evidence-locked structured revisions, evidence references, risk flags, confidence, candidate decisions/edits and artifact versioning are implemented. |
| Application Copilot | COMPLETE | Reviewable cover letters, application-question drafts, recruiter/outreach strategy artifacts and candidate verification are implemented. |
| Application Command Center | COMPLETE | Status/events, notes, resume/interview/network links, reviewed submission controls and activity history are consolidated per application. |
| Application submission orchestration | COMPLETE | Candidate approval is mandatory. Verified first-party ApplyAI employers support direct submission; third-party roles use a recorded external handoff. No CAPTCHA/authentication/anti-bot bypass is attempted. |
| Interview Copilot and practice | COMPLETE | Evidence-grounded interview preparation plus durable practice sessions, responses, feedback and readiness scoring are implemented. |
| Career/network contacts | COMPLETE | Recruiter/hiring-manager/referral contacts, relationship notes and follow-up dates are implemented. |
| Candidate analytics | COMPLETE | Application funnel, saved jobs, resume variants, interview practice, contacts, notification and candidate-event aggregates are implemented. |
| Company intelligence | COMPLETE | Evidence-backed company/job-market signals are derived from currently known public/first-party job postings with explicit provenance disclaimers. |
| Notifications and reminders | COMPLETE | Notification preferences, inbox/read state, saved-search job alerts, interview reminders and recruiter follow-up dispatch are implemented. |
| AI quality/evaluation | COMPLETE | Runtime telemetry plus golden ranking/evidence datasets, Precision@5/10, reciprocal rank, evidence-support rate, unsupported-reference count and baseline-vs-candidate comparison are implemented. |
| Employer/recruiter platform | COMPLETE | Employer organizations, role membership, trust verification, job drafting/publishing/closure, canonical first-party listings, applicants, stages, ratings, notes and dashboard metrics are implemented. |
| Billing/subscriptions | COMPLETE | Free/Pro/Team entitlements, subscription/usage persistence, Stripe Checkout adapter, Billing Portal adapter, signed webhook processing and billing ledger are implemented. |
| Privacy/account lifecycle | COMPLETE | Machine-readable export, application-side deletion, anonymized referential tombstone and deleted-identity hash protection are implemented. |
| Operator/admin console | COMPLETE | Server-only operator boundary, platform metrics, employer verification/suspension, engagement dispatch and AI evaluation visibility are implemented. |
| Browser extension source | COMPLETE | Manifest V3 extension with only `activeTab` and `storage` hands the active public URL to ApplyAI's existing safe import workflow; source syntax/permission checks run in repository tests. |
| Native mobile source | COMPLETE | Expo/React Native candidate client with Clerk secure token handling and native Matches, Jobs, Applications, Alerts and Profile/Career Memory screens is source controlled; mobile TS/TSX source is compiled in repository tests. |
| Candidate web product consolidation | COMPLETE | Historical `/demo` and `/beta` entry points redirect to canonical `/dashboard` and `/matches`; the real candidate navigation exposes Matches, Resume Studio, Network, Analytics, Alerts, Billing and Career Intelligence. |
| Public pricing/settings | COMPLETE | Pricing surface, subscription controls, alert settings and privacy export/deletion controls are implemented. |
| CI and repository quality gates | COMPLETE | Web lint/typecheck/tests/build, mobile/extension source validation, API tests, Docker, Alembic, OpenAPI, Terraform, Playwright, CloudFormation/workflow validation, demo capture, clean-room certification and scale benchmarks are source controlled. |
| AWS staging infrastructure source | COMPLETE | VPC/ALB/ECS/Aurora/S3/ECR, resume/source/AI queues and DLQs, IAM, EventBridge, logs/alarms, migrations and worker services are source controlled and Terraform-validated. |
| AWS bootstrap source | COMPLETE | CloudFormation bootstrap creates/reuses GitHub OIDC trust, encrypted/versioned state and staging deployment role without long-lived normal deployment keys. |
| Staging release/rollback/verification automation | COMPLETE | Immutable-image release, migration gate, runtime activation, rollback and candidate/source/AI verification workflows are implemented and statically validated. |
| Provider/environment configuration templates | COMPLETE | API/web/mobile/Terraform/GitHub examples define Clerk, AWS, OpenAI, Stripe, ATS, operator and mobile values without committing credentials. |
| Production promotion architecture/runbooks | COMPLETE | Promotion, rollback, recovery, privacy/security, backup/PITR and capacity decision gates are documented. Production resource activation remains a deployment activity. |

## Deployment and external-runtime gates

| External gate | Status | What must happen in the real environment |
|---|---|---|
| AWS/Vercel/Clerk staging deployment | BLOCKED | Create the real staging environment, OIDC outputs, ACM/DNS, Clerk app and Vercel project/domain, then run the release/verification workflows. |
| Real-service candidate acceptance | BLOCKED | Prove Clerk -> Vercel -> ECS -> Aurora and browser -> S3 -> outbox -> resume SQS -> worker, including candidate isolation and recovery drills. |
| Real ATS/provider acceptance | BLOCKED | Run reviewed public providers in staging and measure freshness, dedup, closure recovery, throughput and cost. |
| Live Clerk account acceptance | BLOCKED | Exercise real Clerk sign-up/sign-in/sign-out, issuer/JWKS rotation behavior and account lifecycle against a configured Clerk tenant. Local RS256/JWKS protocol verification is already certified separately. |
| Live OpenAI acceptance | BLOCKED | Inject the reviewed secret/model, execute AI/embedding paths, measure latency/tokens/cost, and prove retry/DLQ/schema/evidence-failure behavior. Local Responses/embedding protocol integration is already certified separately. |
| Live Stripe acceptance | BLOCKED | Configure the real Stripe account, price IDs and webhook secret, then exercise checkout, portal and signed webhook lifecycle. Local request/response/webhook integration is already certified separately. |
| Real email/push delivery | BLOCKED | Select/configure delivery providers and prove notification delivery, opt-out and failure handling. Local SMTP delivery through Mailpit is already certified. |
| Production cloud deployment | BLOCKED | Promote only after staging evidence and measured capacity/security/recovery decisions. |
| Production backup/restore and failure drills | BLOCKED | Execute PITR/restore, rollback, queue recovery and incident drills against real infrastructure. |
| Native mobile signing/store release | BLOCKED | Configure Apple/Google developer identities, signing/EAS credentials, native builds and App Store/Play Store publication. |
| Browser-extension store publication | BLOCKED | Package/sign and publish through the selected browser stores. |
| External identity-provider deletion | BLOCKED | Application-side personal data deletion is implemented; deleting/revoking the corresponding Clerk identity must be performed through the configured identity provider. |

## Exact-head validation rule

A source-changing head is complete only after the applicable exact-head gates pass. Historical green runs are not reused after source changes.

Current platform-completion validation includes:

```text
Web lint
Web typecheck
Web unit/source tests
Next.js production build
API tests
Alembic zero-to-head + drift validation
OpenAPI client drift
API production Docker build
Terraform validation
Candidate browser journey
Demo capture
Fresh local clean-room certification
GitHub workflow validation
AWS bootstrap validation
10K / 50K / 250K PostgreSQL search benchmark
```

Real environment acceptance is deliberately separate and remains `BLOCKED` until genuine external evidence exists.
