# Current Repository State

Updated: 2026-07-29

## Source control

- Repository: `rrahul0904/applyai`
- Default branch: `main`
- Active implementation branch: `agent/applyai-milestone-one`
- Pull request: #1, open, draft, mergeable
- Audited source snapshot immediately before this documentation update: `c17c105c906ad6a8e527bfba4351ced414821da2`
- PR metadata at that snapshot: 59 commits, 127 changed files
- Frozen architecture remains Next.js + FastAPI + PostgreSQL/Alembic + Clerk + S3/SQS + Vercel/AWS target
- No destructive reset/clean operation was used

This document records source-controlled GitHub state. Local-only files, workstation credentials, and external cloud configuration are not observable from the remote repository and are not claimed.

## Architecture observed

```text
apps/web        Next.js App Router candidate web application
services/api    FastAPI modular monolith
PostgreSQL      SQLAlchemy 2 + Alembic
S3 provider     production object storage
SQS provider    production task queue
resume worker   dedicated SQS consumer
job connectors  development seed + public Greenhouse Job Board API
docs            product, security, data, UX, deployment architecture
```

## Candidate experience observed

Implemented in source control:

- authenticated candidate shell
- dashboard
- persisted onboarding workflow
- PDF/DOCX resume upload and deterministic extraction
- manual onboarding fallback
- candidate profile editor
- experience, education, skills, roles, location, work mode, compensation
- URL-backed job search and filters
- job detail workspace
- saved jobs workspace
- applications list
- application detail, immutable status history, and private notes
- settings workspace backed by real account/profile data

## Backend domains observed

Implemented in source control:

- Clerk/dev identity abstraction and internal UUID mapping
- owner-scoped candidate profile/resume/saved-job/application/note APIs
- resume object-storage provider and queue provider
- dedicated SQS resume worker
- production/staging durable-provider guardrails
- canonical job/company/source models
- PostgreSQL search provider and cursor pagination
- saved-job uniqueness
- application uniqueness
- immutable application events
- application notes
- public Greenhouse connector with deterministic normalization and raw provenance
- configured Greenhouse ingestion runner
- normalized API errors
- `/health` liveness
- `/ready` database readiness

## Milestone 2.5 changes now present

### CI structure

`.github/workflows/ci.yml` now defines independent jobs:

- Web lint
- Web typecheck
- Web tests
- Web production build
- API migration validation
- API tests

Pinned/runtime choices:

- Node 22.13.0
- pnpm 10.13.1
- Python 3.12.11
- PostgreSQL 17

### Frontend behavior testing

Vitest is configured and source-controlled tests now cover:

- job detail rendering
- save-job mutation
- application creation from job detail
- application list rendering
- regression check against list-level job-detail API fan-out
- application timeline
- application status changes
- private-note creation/deletion
- saved-job empty and persisted states

These tests are not yet claimed passing because no available runner has executed them observably.

### Performance hardening

Completed in source:

- `/applications` list now returns a lightweight application + job summary projection
- list responses no longer load events/notes per application
- applications web list no longer requests job detail once per row
- job list company/location/compensation assembly is batch-loaded
- saved-job related rows are batch-loaded
- saved-job list is explicitly bounded

Still required:

- measured SQL query counts
- query-plan review
- measured browser request counts
- dashboard/profile/application-detail audit
- complete saved-list pagination strategy

### Runtime/staging safety

Completed in source:

- credentialed CORS uses exact `WEB_ORIGIN`
- wildcard credentialed CORS is rejected
- staging/production require Clerk auth configuration
- staging/production require HTTPS `WEB_ORIGIN`
- staging/production require S3 object storage
- staging/production require SQS task queue
- production development auth remains prohibited
- `.env.example` documents durable staging requirements

## Migration state

Alembic revisions currently in the branch:

- `8f21ae7d52d5_initial_canonical_schema.py`
- `0db19a1adb4d_candidate_milestone_one_fields.py`

The Milestone 2.5 changes in this pass use existing schema fields and do not add a migration.

## Current verification blocker

Clean local verification was attempted from the execution sandbox and failed before checkout:

```text
fatal: unable to access 'https://github.com/rrahul0904/applyai.git/':
Could not resolve host: github.com
```

The latest observed GitHub Actions run for implementation head `a0bffc923301226d870341c57c8ffa28792c856f` was `30420175430`.

All six jobs were created but completed failure with no connector-visible steps and no logs:

- Web lint
- Web typecheck
- Web tests
- Web production build
- API migration validation
- API tests

Therefore the current source is **implemented but not current-head verified**. No old test counts are reused.

## Environment state

Repository examples exist for web/API environment variables. Real staging/production values are intentionally absent from source control.

Staging/production API startup now requires durable values for at least:

```text
DATABASE_URL
AUTH_PROVIDER=clerk
CLERK_ISSUER
CLERK_JWKS_URL
OBJECT_STORAGE_PROVIDER=s3
S3_BUCKET
TASK_QUEUE_PROVIDER=sqs
SQS_QUEUE_URL
WEB_ORIGIN=https://...
```

External staging configuration still required:

- real Clerk environment
- real PostgreSQL/Aurora endpoint
- private S3 bucket + IAM
- SQS queue + DLQ/redrive policy
- ECS/Fargate API
- ECS/Fargate resume worker
- Vercel web deployment
- secrets/monitoring configuration

## Known technical debt

1. Playwright Candidate MVP journey is not implemented.
2. Onboarding/resume/profile/settings frontend behavior coverage is incomplete.
3. Greenhouse company resolution, multi-signal deduplication, repeated-ingestion idempotency/freshness, and scheduling remain incomplete.
4. Resume worker idempotency and DLQ behavior are not staging-tested.
5. S3/SQS/Clerk integrations are not staging-tested.
6. Accessibility/security acceptance execution remains pending.
7. Search/query performance is improved structurally but not measured yet.

## Immediate implementation sequence

1. Restore an executable clean verification environment and obtain observable current-head results.
2. Fix any real lint/typecheck/test/build/migration failures revealed there.
3. Finish onboarding/resume/profile/settings Vitest coverage.
4. Implement deterministic Playwright Candidate MVP logout/login persistence journey.
5. Complete measured query/request-count audit and remaining pagination work.
6. Harden Greenhouse company resolution, deduplication, idempotency, freshness, and ingestion health.
7. Validate S3/SQS/worker retry + DLQ + idempotency in staging.
8. Validate real Clerk authentication and two-user isolation in staging.
9. Deploy Vercel/AWS staging and run the full Candidate MVP smoke test.
10. Run security/accessibility/mobile-web acceptance and update the final report.

Do not begin matching/AI work until Candidate MVP + real ingestion + staging are verified.
