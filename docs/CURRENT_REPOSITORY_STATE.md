# Current Repository State

Updated: 2026-08-06

## Source control

- Repository: `rrahul0904/applyai`
- Default branch: `main`
- Active implementation branch: `agent/career-intelligence-v2-foundation`
- Pull request: #12, draft while exact-head validation completes
- Architecture: Next.js App Router + Clerk; FastAPI modular monolith; PostgreSQL/Alembic; private S3; dedicated resume/source/AI SQS queues; Vercel web + AWS ECS/Aurora backend
- No destructive repository cleanup/reset was used.
- No Redis, OpenSearch, Kafka, Kubernetes or premature microservice split was introduced.

This document describes source-controlled state. It does **not** claim external AWS, Vercel, Clerk,
DNS, ATS-provider or model-provider staging acceptance until those services are actually exercised.

## Candidate platform

Implemented:

- Clerk authentication boundary and internal user mapping;
- owner-scoped candidate APIs;
- persisted onboarding;
- profile, experience, education, skills and preferences;
- direct private-S3 resume upload design;
- deterministic PDF/DOCX extraction/review/confirmation;
- one master resume plus version history;
- transactional task outbox;
- resume SQS worker with visibility heartbeat, timeout, retry and DLQ behavior;
- PostgreSQL job search/filter/relevance/cursor pagination;
- job detail, saved jobs and applications;
- application status history and notes;
- deterministic Candidate A/B isolation coverage;
- real candidate workspace routes for dashboard, jobs, resume, profile, applications, saved jobs,
  settings and Career Intelligence.

## Job-data platform

Implemented source includes:

- Greenhouse, Lever, Ashby and generic structured-page adapter architecture;
- career-site discovery and ATS detection;
- source registry and canonical authority;
- durable dispatcher/outbox/source SQS/source workers;
- source leasing with `FOR UPDATE SKIP LOCKED`;
- raw payload/provenance retention;
- canonicalization and deterministic deduplication;
- field-level source authority/conflict rules;
- repeat-fetch idempotency and material-change propagation;
- source freshness and closure evidence;
- apply-URL verification;
- protected quality metrics;
- PostgreSQL benchmark workflow for 10K/50K/250K synthetic corpus sizes;
- dedicated source queue/DLQ and CloudWatch alarms.

Synthetic/load results and real provider throughput are evidence only after the exact workflows run.

## Career Intelligence V1

Merged on `main` and retained as the deterministic baseline/compatibility layer:

- six-factor explainable 100-point opportunity prioritization;
- strengths, gaps and realistic fit risks;
- evidence-locked resume wording;
- candidate approve/reject behavior;
- cover-letter and common application-answer preparation;
- application readiness state;
- persisted browser reload journey;
- explicit boundary that ApplyAI prepares but does not externally submit an application.

## Career Intelligence V2

Implemented on PR #12:

```text
Verified profile/resume/Career Memory
          +
canonical job/source evidence
          +
deterministic V1 factors
          |
          v
server evidence catalog
          |
          v
AIJobRun + transactional outbox
          |
          v
AI SQS -> AI worker -> provider
          |
          v
strict schema + evidence validation
          |
          v
versioned AIArtifact/domain rows
          |
          v
candidate review + quality feedback
```

First-class persistence:

- `AIJobRun`;
- `AIArtifact`;
- `CareerMatch`;
- `ResumeTailoring` / `ResumeTailoringRevision`;
- `CoverLetter`;
- `ApplicationQuestionDraft`;
- `CandidateAIArtifactFeedback`;
- `CandidateCareerFact`.

Current V2 task types:

- `AI_DEEP_MATCH`;
- `AI_RESUME_TAILOR`;
- `AI_APPLICATION_COPILOT`;
- `AI_INTERVIEW_PREP`.

Candidate product integration:

- Career Intelligence V2 actions are on real `/jobs/[id]` pages;
- durable queued work is polled until completion/failure;
- `/career` provides verified Career Memory and recent AI artifact visibility;
- `/beta` remains compatibility/demo evidence rather than the architectural product surface.

Provider architecture:

- deterministic evidence-safe provider for local/CI;
- server-side structured Responses provider for reviewed staging/production use;
- strict JSON/Pydantic output validation;
- exact evidence-reference validation;
- transient provider errors remain retryable; terminal/schema/evidence failures fail closed;
- provider/model/prompt/schema/latency/token/configured-cost/outcome telemetry is persisted when
  available.

See `docs/CAREER_INTELLIGENCE_V2.md`.

## Queue architecture

Task families are separated:

```text
resume task_outbox -> resume SQS -> resume worker
source task_outbox -> source SQS -> source worker
AI task_outbox     -> AI SQS     -> AI worker
```

The queue-aware outbox publisher claims only task families it can route. Specialized source/AI
routing fails closed when the dedicated queue is absent, preventing accidental delivery onto the
resume queue.

## Verification source

The repository CI surface includes:

```text
Web lint
Web typecheck
Web Vitest
Next.js production build
OpenAPI contract drift
API migration validation
API tests
API production Docker build
Staging Terraform validation
Candidate MVP Playwright
AWS bootstrap CloudFormation lint
GitHub workflow static validation
Job-search PostgreSQL benchmark workflow
```

Exact-head results must be taken from the current PR/head; older green results are not reused as
proof after source changes.

## Staging AWS package

Terraform now contains:

```text
VPC / two AZs
public ALB subnets
private ECS/Fargate subnets
isolated Aurora subnets
single staging NAT gateway
HTTPS ALB
ECS cluster
FastAPI service
resume worker
source worker
AI worker
queue-aware outbox services
migration task
source dispatcher task/EventBridge schedule
immutable ECR repository
Aurora PostgreSQL Serverless v2
RDS-managed database secret
private encrypted/versioned resume S3
resume SQS + DLQ
source SQS + DLQ
AI SQS + DLQ
IAM roles/policies
CloudWatch logs and alarms
```

The same immutable API image is reused with role-specific commands. The external model API key is
injected only into the AI worker through Secrets Manager when the reviewed provider is enabled.

## V2 deployment workflows

`ApplyAI Staging Release V2` performs:

1. exact source/immutable image resolution;
2. Alembic migration gate;
3. candidate/source/AI runtime activation;
4. ECS stability checks;
5. HTTPS health/readiness;
6. source/AI queue reachability and service-state verification.

`ApplyAI Staging Verification V2` verifies:

- healthy ALB/API;
- private ECS networking;
- candidate/source/AI service desired state;
- immutable-image consistency;
- resume/source/AI SQS encryption and redrive;
- private/versioned/encrypted resume S3;
- encrypted/private/backed-up Aurora;
- source dispatcher state;
- source/AI log groups and alarms.

## External staging blockers

Real staging remains **BLOCKED** until the actual environment values/resources exist:

```text
AWS staging account
GitHub staging environment + OIDC bootstrap outputs
ACM certificate + API DNS
Clerk staging application
Vercel staging project/domain
reviewed public ATS provider set
reviewed model provider credential/model
```

Templates now include Career Intelligence values without committing credentials:

- `services/api/.env.example`;
- `infra/staging/github.environment.example`;
- `infra/staging/terraform.tfvars.example`;
- `apps/web/.env.staging.example`.

## Required real-service acceptance

Real staging must still prove:

- Clerk -> Vercel -> FastAPI/ECS -> Aurora candidate authentication;
- direct browser S3 upload -> outbox -> resume SQS -> resume worker;
- source dispatcher -> source SQS -> provider adapters -> freshness/dedup/closure recovery;
- AI outbox -> AI SQS -> AI worker -> reviewed provider -> validated artifact;
- all four V2 task types through the durable AI path;
- Candidate A/B isolation for Career Memory, runs, matches and artifacts;
- worker/provider failure retry and DLQ/redrive;
- model schema/evidence failure behavior;
- CloudWatch logs without resume bodies, API keys, auth tokens or unsafe model payloads;
- measured latency/token/cost observations;
- rollback and backup/restore drills.

No repository-only change can honestly mark those external gates complete.

## Production boundary

Production infrastructure remains intentionally gated by staging evidence. Do not mechanically copy
staging Terraform into production. Production must explicitly choose account/state/trust boundary,
delete protection, final snapshots/PITR, HA/capacity, alert routing, model/cost budgets, approvals,
rollback and privacy/security requirements based on measured staging behavior.

Native mobile, employer platform, billing, autonomous messaging and auto-apply remain separate future
product milestones.
