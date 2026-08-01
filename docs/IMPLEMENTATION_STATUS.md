# Implementation Status

Updated: 2026-07-30

Statuses are restricted to COMPLETE, PARTIAL, NOT STARTED, and BLOCKED.

| Capability | Status | Evidence / boundary |
|---|---|---|
| Frozen architecture | COMPLETE | Next.js App Router + Clerk; FastAPI modular monolith; PostgreSQL/Alembic; S3/SQS; Vercel/AWS target preserved. No Redis/OpenSearch/Kafka/Kubernetes/microservice split added. |
| Candidate authorization | COMPLETE | Candidate-owned profile, resume, saved-job, application and note APIs are owner-scoped; deterministic two-user coverage exists. |
| Resume upload durability | COMPLETE | Upload intent -> presigned PUT -> S3 HEAD verification -> `ResumeVersion + task_outbox` transaction; direct S3 browser path in durable environments. |
| Resume versioning | COMPLETE | One master resume per candidate, monotonic versions, migration-enforced uniqueness. |
| Transactional outbox | COMPLETE | Durable outbox, unique idempotency key, `FOR UPDATE SKIP LOCKED`, stale claim recovery and exponential retry. |
| Resume processing idempotency | COMPLETE | Parser-version uniqueness, persisted processing attempts, stale-attempt recovery and redelivery-safe terminal handling. |
| SQS worker lease behavior | COMPLETE | Configurable visibility timeout/heartbeat and processing timeout; PROCESSING is not acknowledged; failed messages remain eligible for retry/DLQ. |
| DLQ operator path | COMPLETE | Durable environments require a DLQ; SQS redrive is configured in Terraform; sanitized DLQ inspection command avoids printing resume bodies. |
| Resume confirmation/profile provenance | COMPLETE | Confirmation completes extraction/version and persists candidate-reviewed profile data as `USER_VERIFIED` in one transaction. |
| Candidate profile/onboarding source | COMPLETE | Profile, experience, education, skills, roles, location, work mode, compensation, onboarding state and manual fallback are implemented. |
| Job search | COMPLETE | PostgreSQL FTS, structured filters, stable cursor pagination and relevance ordering are implemented; the old rank/cursor source mismatch is resolved. |
| Saved jobs | COMPLETE | Ownership, save/unsave, UI and keyset pagination implemented. |
| Applications | COMPLETE | Create/detail/status/events/notes plus lightweight keyset-paginated list projection. |
| Greenhouse connector | COMPLETE | Public-board connector preserves source identity, source metadata/raw payload and normalized canonical data. |
| Greenhouse ingestion lifecycle | COMPLETE | Ingestion runs, savepoint isolation, repeat-fetch idempotency, changed-job propagation, multi-source freshness and ACTIVE -> UNKNOWN -> STALE recovery logic. |
| Deterministic deduplication | COMPLETE | Exact source/application/internal identity and strict company/title/location/description fingerprint; heuristic confidence does not claim certainty. |
| N+1 regression protection | COMPLETE | SQL statement-count scaling tests cover jobs, saved jobs and applications and require statement count not to grow with page row count. |
| OpenAPI contract consistency | COMPLETE | Generated frontend schema is committed and CI enforces no contract drift. |
| API container | COMPLETE | Non-root production Docker image exists and has built successfully in GitHub Actions. |
| Database migrations | COMPLETE | Alembic zero-to-head migration, current-head reporting and migration-drift checks execute in CI against PostgreSQL 17. |
| Candidate MVP Playwright | COMPLETE | Deterministic browser -> Next.js -> FastAPI -> real PostgreSQL journey covers onboarding, resume review/confirm, search, save, application/status/note persistence, relogin and Candidate B isolation. This is CI proof, not real Clerk/AWS proof. |
| CI definition | COMPLETE | Independent lint, typecheck, Vitest, production build, OpenAPI, Alembic, API tests, Docker build, Terraform validation and Playwright gates. |
| Terraform staging source | COMPLETE | `infra/staging` defines networking, ALB, ECS/Fargate, ECR, Aurora Serverless v2, private S3, SQS/DLQ, IAM, EventBridge and CloudWatch. Terraform 1.15.5 `fmt`, provider `init -backend=false`, and `validate` have executed successfully. AWS provider is pinned to validated release 6.55.0. |
| AWS bootstrap source | COMPLETE | CloudFormation bootstrap creates/reuses GitHub OIDC trust, private/versioned Terraform state and the staging deploy role; the pinned `cfn-lint` gate has executed successfully. |
| GitHub workflow static validation | PARTIAL | `actionlint` is source-controlled and identified shell-quality issues in the new deployment workflows; those findings were corrected and the latest gate must finish green before this row becomes COMPLETE. |
| GitHub -> AWS deployment automation | COMPLETE | OIDC-only preflight, foundation plan/apply, immutable release/migration/activation, rollback and deployed-infrastructure verification workflows are source-controlled. No static AWS keys are required. |
| Vercel/Clerk staging templates | COMPLETE | Vercel staging env example, GitHub environment manifest and staging runbook define exact external values without committing secrets. |
| Staging deployment | BLOCKED | Requires real AWS staging account, GitHub `staging` environment values, ACM/DNS, Clerk staging application and Vercel staging project. No real AWS resources are claimed deployed. |
| Real-service Candidate MVP acceptance | BLOCKED | Must prove real Clerk -> Vercel -> ECS -> Aurora plus browser -> S3 -> outbox -> SQS -> worker, failure recovery and two-user isolation in staging. |
| Production infrastructure | PARTIAL | Promotion checklist and production-safe deployment ordering are defined. Production Terraform is intentionally not created until real staging acceptance and recovery drills pass. |
| AI matching / embeddings | NOT STARTED | Intentionally gated behind Candidate MVP + staging verification. |
| Mobile | NOT STARTED | Intentionally outside this milestone. |
| Employer platform | NOT STARTED | Intentionally outside this milestone. |
| Billing | NOT STARTED | Intentionally outside this milestone. |
| Auto-apply | NOT STARTED | Intentionally outside this milestone. |

## Verified source gates

GitHub-hosted runners are operational. Executable runs have demonstrated the application/infrastructure source gates rather than merely creating jobs. Verified evidence includes:

```text
Web lint
Web typecheck
Vitest
Next.js production build
OpenAPI contract drift
API tests
Alembic migration validation
API production Docker build
Terraform fmt
Terraform provider initialization
Terraform validate
CloudFormation cfn-lint
```

The Candidate MVP Playwright journey has also completed successfully on a verified application head. One later Playwright execution was cancelled during Chromium installation only because `cancel-in-progress` superseded that older run with a newer commit; it was not a test assertion failure.

Do not reuse those results as evidence for a future source-changing head. Each deployment candidate must pass its own required checks.

## Deployment package

The staging deployment package now contains:

```text
infra/bootstrap/
  applyai-staging-bootstrap.yaml
  README.md

infra/staging/
  backend.tf
  versions.tf
  variables.tf
  network.tf
  data.tf
  compute.tf
  observability.tf
  outputs.tf
  terraform.tfvars.example
  github.environment.example
  README.md

.github/workflows/
  ci.yml
  bootstrap-validation.yml
  workflow-validation.yml
  staging-preflight.yml
  staging-infra.yml
  staging-deploy.yml
  staging-rollback.yml
  staging-verify.yml

apps/web/.env.staging.example
docs/AWS_STAGING_DEPLOYMENT.md
docs/PRODUCTION_PROMOTION_CHECKLIST.md
```

## Candidate MVP status

**PARTIAL**

The application and deployment source are ready for the real-service phase, but the milestone remains PARTIAL until AWS/Clerk/Vercel staging exists and the real Candidate MVP, queue/outbox failure recovery, Greenhouse lifecycle, observability and recovery acceptance gates are executed successfully.

Do not begin Milestone 3 / AI matching until that staging gate is verified.
