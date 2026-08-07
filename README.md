# ApplyAI

ApplyAI is a candidate career platform for verified career memory, public-job discovery,
explainable opportunity prioritization, evidence-grounded application preparation and durable
job-search history.

The repository keeps candidate facts, job/source facts, deterministic product signals and model
inference separate. ApplyAI prepares and reviews career/application material; it does not claim a
hiring probability or pretend that an external application/message was submitted.

## Architecture

```text
Vercel
  Next.js App Router + Clerk
             |
             | HTTPS
             v
AWS ALB -> ECS/Fargate FastAPI
                |
                +-> Aurora PostgreSQL
                +-> private S3 resume storage
                +-> PostgreSQL transactional outbox
                              |
                              v
                    queue-aware publisher
                     /         |          \
                    v          v           v
              resume SQS   source SQS    AI SQS
                  |            |            |
                  v            v            v
            resume worker  source worker   AI worker
                  |            |            |
                 DLQ          DLQ          DLQ

EventBridge -> bounded source dispatcher
CloudWatch  -> logs + alarms
```

Repository layout:

```text
apps/web/               Next.js candidate web
services/api/           FastAPI modular monolith + workers
infra/bootstrap/        one-time AWS/GitHub OIDC bootstrap
infra/staging/          staging Terraform including candidate/source/AI runtimes
docs/                   architecture, status, deployment and recovery runbooks
compose.yaml             local PostgreSQL
```

## Candidate product

The authenticated workspace includes:

```text
/dashboard
/jobs
/jobs/[id]
/career
/saved
/applications
/resume
/profile
/settings
```

`/jobs/[id]` contains Career Intelligence V2 actions for fit analysis, resume tailoring,
application preparation and interview preparation. `/career` stores verified Career Memory and
shows durable AI artifacts.

The historical `/beta` route remains useful regression/demo evidence for V1 compatibility; the
real product capabilities now live in the normal candidate workspace.

## Career Intelligence

### Deterministic V1 baseline

The merged V1 engine is deterministic and explainable. It evaluates target-role alignment,
verified skill alignment, location/work-mode fit, compensation fit, seniority and freshness. It is
retained as an auditable baseline rather than replaced by an opaque model score.

### V2 durable intelligence

V2 introduces first-class persistence:

```text
AIJobRun
AIArtifact
CareerMatch
ResumeTailoring
ResumeTailoringRevision
CoverLetter
ApplicationQuestionDraft
CandidateAIArtifactFeedback
CandidateCareerFact
```

Supported server-owned tasks:

```text
AI_DEEP_MATCH
AI_RESUME_TAILOR
AI_APPLICATION_COPILOT
AI_INTERVIEW_PREP
```

Every task uses a server-generated evidence catalog. Structured output must pass Pydantic/JSON
schema validation and every factual candidate claim must reference known evidence before an
artifact is persisted.

Local/CI use a deterministic evidence-safe provider. Reviewed staging/production may use the
server-side structured model provider with credentials injected only into the AI worker through
secret storage.

See [`docs/CAREER_INTELLIGENCE_V2.md`](docs/CAREER_INTELLIGENCE_V2.md).

## Career Memory

Candidates can persist verified achievements, projects, measurable results, responsibilities,
certifications, leadership stories, interview feedback and career goals. Candidate-created facts
enter as `USER_VERIFIED`; model inference cannot silently become verified Career Memory.

Career Intelligence retrieves verified, non-archived Career Memory together with the candidate
profile/resume and canonical job evidence.

## Local development

Prerequisites:

- Node.js 22+
- pnpm 10+
- Python 3.12+
- uv
- PostgreSQL 17 or Docker

Setup:

```bash
docker compose up -d postgres
pnpm install
uv sync --system-certs --project services/api
```

Create the API test database once:

```bash
docker compose exec -T postgres createdb -U applyai applyai_test
```

Apply migrations:

```bash
cd services/api
DATABASE_URL=postgresql+psycopg://applyai:applyai@localhost:55432/applyai \
  uv run alembic upgrade head
```

Run web/API:

```bash
pnpm dev
pnpm dev:api
```

Development defaults to local resume storage, an in-memory queue and the deterministic Career
Intelligence provider. See `apps/web/.env.example` and `services/api/.env.example`.

## Durable resume lifecycle

Staging/production are fail-closed around the durable resume path:

```text
Browser
  -> FastAPI upload intent
  -> presigned private-S3 PUT
  -> FastAPI upload-complete / S3 HEAD verification
  -> PostgreSQL transaction
       ResumeVersion -> QUEUED
       task_outbox    -> RESUME_PARSE
  -> queue-aware outbox publisher
  -> resume SQS
  -> resume worker
  -> ResumeExtraction NEEDS_REVIEW
  -> candidate confirmation
  -> COMPLETED + USER_VERIFIED profile
```

Resume bytes bypass the Vercel BFF.

## Durable Career Intelligence lifecycle

```text
Candidate action
  -> server builds verified candidate/job evidence context
  -> PostgreSQL transaction
       AIJobRun -> QUEUED
       task_outbox -> AI_* task
  -> queue-aware outbox publisher
  -> AI SQS
  -> AI worker + provider
  -> strict schema validation
  -> exact evidence-reference validation
  -> versioned AIArtifact/domain row
  -> candidate review/feedback
```

Transient provider transport/429/5xx failures stay retryable and eligible for DLQ/redrive.
Terminal provider, schema or evidence failures fail closed and are persisted as failures rather than
silently producing application content.

Useful worker/operator commands:

```bash
cd services/api
uv run python -m app.core.outbox
uv run python -m app.workers.resume
uv run python -m app.workers.ai
uv run python -m app.ops.dlq --limit 10
```

## Public job-data platform

ApplyAI supports a multi-source architecture around reviewed public employer/ATS sources including
Greenhouse, Lever, Ashby and structured public pages. Source scheduling, leases, authority,
provenance, deduplication, freshness, apply-link verification and closure evidence are server-owned.

Source work uses a dedicated source SQS/DLQ and worker path. Failed/partial source runs do not create
negative freshness evidence merely because a request failed.

## Candidate E2E

The deterministic Playwright journey runs real Next.js + FastAPI + PostgreSQL while CI may use
controlled substitutes for external auth/storage/queue dependencies. It covers Candidate A
onboarding/resume/search/save/application/status/note/relogin persistence and Candidate B isolation.

```bash
uv run --project services/api python services/api/scripts/create_e2e_resume.py /tmp/applyai-e2e-resume.docx
E2E_RESUME_PATH=/tmp/applyai-e2e-resume.docx pnpm test:e2e
```

Real staging must replace the controlled substitutes with Clerk, S3, SQS/DLQ, ECS workers and the
reviewed external providers.

## AI quality telemetry

Protected internal metrics report measured values only:

```text
GET /api/v1/internal/ai-quality/metrics
```

They include run success/failure, latency, provider/task/model breakdown, token usage when supplied,
configured cost estimates, artifact candidate-verification rate and accepted/edited/rejected
feedback. The deterministic CI provider reports zero model tokens/cost rather than inventing usage.

## Production API image

API, resume/source/AI workers, outbox publishers, migration and source-dispatch tasks reuse the same
immutable production image with role-specific commands:

```bash
docker build -t applyai-api:local services/api
```

The image runs as a non-root user. Staging releases tag ECR images with the full Git commit SHA.

## AWS staging deployment package

Start here:

- [`infra/bootstrap/README.md`](infra/bootstrap/README.md) — one-time AWS state/OIDC bootstrap
- [`infra/staging/README.md`](infra/staging/README.md) — Terraform stack
- [`docs/AWS_STAGING_DEPLOYMENT.md`](docs/AWS_STAGING_DEPLOYMENT.md) — operator runbook
- [`docs/PRODUCTION_PROMOTION_CHECKLIST.md`](docs/PRODUCTION_PROMOTION_CHECKLIST.md) — production gate
- [`infra/staging/github.environment.example`](infra/staging/github.environment.example) — GitHub `staging` environment values
- [`infra/staging/terraform.tfvars.example`](infra/staging/terraform.tfvars.example) — dormant foundation example
- [`apps/web/.env.staging.example`](apps/web/.env.staging.example) — Vercel/Clerk staging template

V2 release ordering is migration-first:

```text
1. CloudFormation bootstrap: Terraform state + GitHub OIDC role
2. GitHub staging environment + ACM/DNS/Clerk/Vercel prerequisites
3. dormant Terraform foundation
4. immutable API image
5. exact-image Alembic Fargate migration
6. activate candidate/source/AI services
7. verify ECS/private networking/S3/Aurora/queues/DLQs/logs/alarms
8. real Candidate/source/model acceptance and failure injection
9. rollback + backup/restore drills
```

Normal deployment workflows use GitHub OIDC and require no long-lived AWS access keys. The model API
key is represented only by a Secrets Manager ARN in deployment configuration and is injected into
the AI worker when the reviewed provider is enabled.

## Validation

Application/runtime gates:

```bash
pnpm lint
pnpm --dir apps/web typecheck
pnpm test:web
pnpm build
pnpm openapi:check
pnpm test:e2e

docker build -t applyai-api:ci services/api

cd services/api
uv run alembic upgrade head
uv run alembic check
uv run pytest
```

Infrastructure/source gates:

```bash
terraform -chdir=infra/staging fmt -check -recursive
terraform -chdir=infra/staging init -backend=false
terraform -chdir=infra/staging validate

cfn-lint infra/bootstrap/applyai-staging-bootstrap.yaml
actionlint
```

Do not reuse a historical PASS for a newer source-changing head. Current source status and external
boundaries are recorded in [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) and
[`docs/CURRENT_REPOSITORY_STATE.md`](docs/CURRENT_REPOSITORY_STATE.md).

## Honest external boundary

Repository CI can prove source behavior and deterministic integration. It cannot prove that a real
AWS staging account, Vercel project, Clerk application, public provider set or external model
credential has been exercised. Those remain explicit staging acceptance gates until the real
workflows execute successfully.

Native mobile, employer workflows, billing, autonomous messaging and auto-apply/external submission
are intentionally separate later product milestones.
