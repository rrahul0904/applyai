# Implementation Status

Updated: 2026-08-06

Statuses are restricted to `COMPLETE`, `PARTIAL`, `NOT STARTED`, and `BLOCKED`.
`COMPLETE` means source plus the applicable repository validation gate. External services are never
marked complete merely because their Terraform/workflow source exists.

| Capability | Status | Evidence / boundary |
|---|---|---|
| Core architecture | COMPLETE | Next.js App Router + Clerk; FastAPI modular monolith; PostgreSQL/Alembic; private S3; SQS; Vercel/AWS target preserved. No Redis/OpenSearch/Kafka/Kubernetes/microservice split. |
| Candidate authorization | COMPLETE | Candidate profile, resume, saved-job, application, note and career-intelligence APIs are owner scoped; deterministic two-user coverage exists for the established Candidate MVP. |
| Resume upload durability | COMPLETE | Upload intent -> presigned PUT -> S3 HEAD verification -> `ResumeVersion + task_outbox`; direct S3 browser path in durable environments. |
| Resume processing | COMPLETE | Versioning, transactional outbox, SQS lease heartbeat, idempotent attempts, candidate confirmation/provenance and DLQ operator path exist. |
| Candidate profile/onboarding | COMPLETE | Profile, experience, education, skills, target roles, preferences, onboarding state and manual fallback are implemented. |
| Job search/saved jobs/applications | COMPLETE | PostgreSQL FTS/filters/cursors, job detail, saved jobs and application status/events/notes are implemented with N+1 regression protection. |
| Multi-source job-data source | COMPLETE | Greenhouse/Lever/Ashby/structured-source architecture, source registry, durable dispatch, authority/provenance, dedup, freshness, closure evidence, URL verification and quality metrics exist. Real provider scale remains staging evidence. |
| OpenAPI contract discipline | PARTIAL | Public Career Memory/V2 endpoints are typed and generated client synchronization is automated during PR #12 development. The temporary sync workflow must be removed and exact-head drift CI must finish green before this returns to COMPLETE. |
| Database migrations | PARTIAL | Career Intelligence V2 and Career Memory Alembic revisions are source controlled. Exact-head zero-to-head and migration-drift CI must finish green before this returns to COMPLETE. |
| Candidate MVP browser acceptance | COMPLETE | Existing deterministic browser -> Next.js -> FastAPI -> real PostgreSQL journey covers onboarding, resume review/confirm, search, save, application/status/note persistence, relogin and Candidate B isolation. This is repository CI proof, not real Clerk/AWS proof. |
| Career Intelligence V1 | COMPLETE | Explainable six-factor prioritization, evidence-locked tailoring, application assistant/readiness, persistence reload and demo captures are merged on `main`. V1 remains a deterministic compatibility/baseline layer. |
| First-class Career Intelligence V2 domain | PARTIAL | `AIJobRun`, versioned `AIArtifact`, `CareerMatch`, tailoring/revisions, cover letters, application-question drafts, feedback and migrations are implemented on PR #12; exact-head CI pending. |
| Verified Career Memory | PARTIAL | Candidate-owned achievements/projects/metrics/responsibilities/certifications/leadership/interview-feedback/goals plus CRUD/summary and AI evidence inclusion are implemented on PR #12; exact-head CI pending. |
| Durable AI queue runtime | PARTIAL | AI task outbox, dedicated SQS/DLQ routing, queue-aware claim filtering, AI worker heartbeat/retry, transient-vs-terminal failure handling and deterministic CI provider are implemented; exact-head CI/staging proof pending. |
| Structured model-provider boundary | PARTIAL | Server-side provider abstraction, strict JSON-schema output, Pydantic validation, exact evidence-reference validation, provider/model/prompt/schema/latency/token/configured-cost telemetry and secret boundary are implemented. No real external model invocation is claimed yet. |
| Hybrid matching V2 | PARTIAL | Deterministic V1 baseline plus persisted 65/35 hybrid score, strengths/gaps/risks/actions and candidate-scoped match reads are implemented; real model calibration/evaluation remains staging/product evidence. |
| Resume Intelligence V2 | PARTIAL | Evidence-locked structured revisions, evidence refs, risk flags, confidence, candidate decision/edit text and artifact versioning are implemented; real model acceptance pending. |
| Application Copilot V2 | PARTIAL | First-class reviewable cover letter, question drafts, recruiter outreach and strategy artifact implemented; external submission remains intentionally outside scope. |
| Interview preparation V2 | PARTIAL | Evidence-grounded role questions, rationale, answer outlines, employer questions and gap plan implemented; real model acceptance pending. |
| Candidate Career workspace | PARTIAL | Real job-detail V2 actions, durable-run polling, hybrid score/artifact previews and `/career` Career Memory/recent-artifact workspace are implemented; exact-head web/Playwright validation pending. |
| AI quality/evaluation telemetry | PARTIAL | Run success/failure, latency, token/configured-cost, artifact verification and candidate feedback metrics plus regression tests are implemented; real model observations remain unavailable until staging. |
| CI definition | COMPLETE | Lint, typecheck, Vitest, production build, OpenAPI, Alembic, API tests, Docker, Terraform, Playwright, CloudFormation and workflow validation gates are source controlled. |
| Terraform candidate/source staging | COMPLETE | Networking, ALB, ECS/Fargate, ECR, Aurora, private S3, resume/source SQS/DLQ, IAM, EventBridge and CloudWatch source have validated previously. Real deployment remains separate. |
| Terraform AI staging source | PARTIAL | Dedicated AI queue/DLQ, AI worker, universal queue-aware outbox, conditional Secrets Manager credential access, logs and alarms are implemented on PR #12; exact-head Terraform validation pending. |
| GitHub -> AWS V2 release/verification | PARTIAL | V2 release now activates candidate/source/AI runtimes after the migration gate; V2 verification checks AI services/queues/logs/alarms/private networking. Workflow static validation and real AWS execution remain pending. |
| AWS bootstrap source | COMPLETE | CloudFormation bootstrap creates/reuses GitHub OIDC trust, private/versioned state and staging deploy role; no long-lived AWS key is required for normal deployment workflows. |
| Vercel/Clerk/operator templates | COMPLETE | Vercel/API templates plus GitHub/Terraform examples define staging values without committing credentials; Career Intelligence provider/model/Secrets Manager ARN are documented. |
| Real AWS/Vercel/Clerk staging deployment | BLOCKED | Requires actual staging account/environment, OIDC outputs, ACM/DNS, Clerk app, Vercel project/domain and reviewed source set. No real resources are claimed deployed. |
| Real-service Candidate MVP acceptance | BLOCKED | Must prove real Clerk -> Vercel -> ECS -> Aurora and browser -> S3 -> outbox -> resume SQS -> worker plus failure recovery and Candidate A/B isolation. |
| Real multi-source provider acceptance | BLOCKED | Must execute reviewed Greenhouse/Lever/Ashby set, freshness/dedup/closure/failure recovery and measured throughput/cost in staging. |
| Real model-provider acceptance | BLOCKED | Requires reviewed model credential/model and real AI outbox -> SQS -> worker -> provider -> validated artifact runs, retries/DLQ, evidence/schema failure injection and measured token/latency/cost observations. |
| Production infrastructure | PARTIAL | Promotion/recovery guidance exists; production Terraform remains intentionally gated by real staging acceptance, recovery drills and measured capacity/security decisions. |
| Native mobile | NOT STARTED | Intentionally outside the current Candidate/Career Intelligence milestone. |
| Employer platform | NOT STARTED | Intentionally outside the current Candidate/Career Intelligence milestone. |
| Billing | NOT STARTED | Intentionally outside the current Candidate/Career Intelligence milestone. |
| Auto-apply/external submission | NOT STARTED | Intentionally separate; current product prepares/reviews materials but does not submit external forms or send messages autonomously. |

## Current PR #12 acceptance gate

Before PR #12 is eligible to merge, the exact candidate head must pass:

```text
Web lint
Web typecheck
Web unit tests
Next.js production build
OpenAPI contract drift
API tests
Alembic zero-to-head + drift validation
API production Docker build
Terraform fmt/init/validate
GitHub workflow static validation
Candidate MVP Playwright
applicable Career Intelligence/browser regression
```

Cancelled runs caused only by `cancel-in-progress` superseding an older source head are not failures,
but they are also not proof for the final head.

## Real staging acceptance after merge

Real staging must separately prove:

```text
Clerk -> Vercel -> FastAPI/ECS -> Aurora
browser -> private S3 -> outbox -> resume SQS -> worker
source dispatcher -> source SQS -> adapters -> canonical job lifecycle
AI outbox -> AI SQS -> AI worker -> reviewed provider -> validated artifact
```

It must also prove Candidate A/B ownership, queue/DLQ recovery, model transient retry, terminal
schema/evidence failure behavior, safe logs, provider/source measurements, rollback and database
backup/restore. These gates remain `BLOCKED` until the external environment exists.

## Source-of-truth rule

Do not use the older statement “AI matching is not started.” Career Intelligence V1 is already on
`main`, and V2 is the active PR. Use this file, `CURRENT_REPOSITORY_STATE.md`, and
`CAREER_INTELLIGENCE_V2.md` together; never reuse a historical PASS for a newer source-changing
head.
