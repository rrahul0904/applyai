# Current Repository State

Updated: 2026-07-30

## Source control

- Repository: `rrahul0904/applyai`
- Default branch: `main`
- Active implementation branch: `agent/applyai-milestone-one`
- Pull request: #1, open, draft, mergeable
- Frozen architecture: Next.js App Router + Clerk; FastAPI modular monolith; PostgreSQL/Alembic; private S3; SQS/DLQ; Vercel web + AWS backend
- No destructive repository cleanup/reset was used
- No AI matching, embeddings, mobile, employer platform, billing, auto-apply, Redis, OpenSearch, Kafka or Kubernetes was introduced

This document describes source-controlled and observed CI state. It does not claim that external AWS, Vercel, Clerk or DNS resources exist until they are actually provisioned.

## Candidate MVP source

Implemented:

- Clerk authentication boundary plus internal user UUID mapping
- owner-scoped candidate APIs
- persisted onboarding
- profile, experience, education, skills and preferences
- direct durable resume upload design
- deterministic PDF/DOCX extraction/review/confirmation
- one master resume + version history
- transactional task outbox
- SQS resume worker with visibility heartbeat and processing timeout
- DLQ/redrive configuration and sanitized inspection path
- PostgreSQL job search/filter/relevance/cursor pagination
- job detail
- saved jobs with keyset pagination
- applications with keyset pagination, status history and notes
- public Greenhouse connector
- ingestion-run health and failure isolation
- deterministic source/canonical deduplication
- repeat-fetch `last_seen_at` refresh
- changed-job propagation + `JobVersion`
- ACTIVE -> UNKNOWN -> STALE lifecycle and recovery
- multi-source freshness protection

## Verification source

The CI surface now includes:

```text
Web lint
Web typecheck
Web Vitest
Web production build
OpenAPI contract drift
API migration validation
API tests
API production Docker build
Staging Terraform validation
Candidate MVP Playwright
AWS bootstrap CloudFormation lint
```

GitHub-hosted runners are operational.

Observed executable evidence includes:

- web lint/typecheck/tests/build success on recent implementation heads;
- OpenAPI generation/drift success;
- backend tests success against PostgreSQL 17;
- Alembic zero-to-head + drift validation success;
- production API Docker build success;
- Candidate MVP Playwright success on a verified application head;
- Terraform 1.15.5 formatting success;
- AWS provider initialization with `-backend=false` success;
- `terraform validate` success for the staging HCL.

A later Playwright job was cancelled while installing Chromium because `cancel-in-progress` replaced an older run after another commit. That cancellation is not an application test failure.

The bootstrap CloudFormation template has its own pinned `cfn-lint` validation workflow. Treat the template as PARTIAL until that final lint execution is observed green.

## Performance guardrails

Implemented and tested in source:

- application list is a lightweight projection;
- saved jobs and applications use bounded keyset pagination;
- job list related data is batch-loaded;
- SQL statement-count regression tests compare one-row and multi-row list responses for jobs, saved jobs and applications and require statement counts not to grow with row count.

Production query plans and real corpus performance still belong to staging/load verification rather than source completion.

## Staging AWS package

`infra/staging` contains Terraform for:

```text
VPC / two AZs
public ALB subnets
private ECS/Fargate subnets
isolated Aurora subnets
single staging NAT gateway
HTTPS ALB
ECS cluster
FastAPI service
resume worker service
outbox publisher service
migration task
scheduled Greenhouse ingestion task
immutable ECR repository
Aurora PostgreSQL Serverless v2
RDS-managed database secret
private encrypted/versioned resume S3 bucket
SQS processing queue + DLQ/redrive
IAM task/execution/EventBridge roles
CloudWatch log groups
ALB/Aurora/SQS/DLQ alarms
```

The same production API image is reused with role-specific commands for API, worker, outbox, migration and ingestion tasks.

Aurora credentials are injected from the RDS-managed Secrets Manager secret as separate username/password fields. The application can compose the Psycopg connection URL at runtime, so a password-bearing database URL does not need to live in Terraform variables.

## One-time AWS bootstrap

`infra/bootstrap/applyai-staging-bootstrap.yaml` provides:

- encrypted/versioned/private Terraform-state S3 bucket;
- GitHub Actions OIDC provider creation or existing-provider reuse;
- GitHub `staging` environment-scoped deployment IAM role;
- no static AWS access-key requirement for normal staging workflows.

The bootstrap role is deliberately intended for a dedicated non-production account. Production gets a separate trust/state/account decision after staging acceptance.

## Deployment workflows

Manual workflows now exist for:

### `ApplyAI Staging Infrastructure`

- GitHub OIDC -> AWS
- validate required staging environment values
- initialize remote state
- Terraform validate/plan
- optionally apply the dormant foundation with API/worker/outbox = 0 and ingestion disabled

### `ApplyAI Staging Release`

- exact Git commit -> immutable ECR tag
- idempotent image reuse on workflow rerun
- one-shot Alembic Fargate migration task
- abort before service activation when migration fails
- Terraform service activation
- wait API/worker/outbox stability
- public HTTPS `/health` + `/ready`

### `ApplyAI Staging Rollback`

- verify requested immutable image exists
- reapply service task definitions through Terraform
- wait ECS stability
- verify health/readiness
- no Alembic downgrade; schema remains roll-forward

### `ApplyAI Staging Infrastructure Verification`

Checks real deployed AWS state for:

- ECS service availability
- ALB target health
- private/encrypted Aurora
- private/versioned/encrypted resume S3
- SQS/DLQ/redrive
- HTTPS health/readiness
- CloudWatch runtime log groups

## External staging values still required

Real staging is **BLOCKED** until these external pieces exist:

```text
AWS staging account
GitHub staging environment
AWS OIDC bootstrap outputs
ACM certificate
API DNS hostname
Clerk staging application
Vercel staging project/domain
small explicit Greenhouse board set
```

Templates:

- `infra/staging/github.environment.example`
- `apps/web/.env.staging.example`
- `infra/staging/terraform.tfvars.example`

Primary runbook:

- `docs/AWS_STAGING_DEPLOYMENT.md`

## Required real-service acceptance

After deployment, staging must prove:

```text
Clerk candidate login
 -> Vercel
 -> FastAPI/ECS
 -> Aurora

resume upload intent
 -> browser direct S3 PUT
 -> upload verification
 -> ResumeVersion + outbox transaction
 -> outbox publisher
 -> SQS
 -> resume worker
 -> extraction review
 -> confirmation
 -> USER_VERIFIED profile
```

Also required:

- deliberate outbox/SQS/worker failure and recovery;
- DLQ behavior/inspection;
- repeat/changed Greenhouse ingestion and freshness recovery;
- Candidate A/B resource isolation;
- CloudWatch logs/alarms without resume text/tokens/passwords;
- backup/recovery drills before production promotion.

## Production boundary

Production infrastructure remains **PARTIAL** by design. The production promotion checklist is in `docs/PRODUCTION_PROMOTION_CHECKLIST.md`.

Do not create production Terraform by mechanically copying staging. Production must intentionally choose deletion protection, final snapshots/PITR, capacity/HA, approval controls, alert routing and recovery requirements based on verified staging behavior.

Do not begin Milestone 3 / AI matching until Candidate MVP + ingestion + real staging verification pass.
