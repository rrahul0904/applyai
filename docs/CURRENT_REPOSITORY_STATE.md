# Current Repository State

Updated: 2026-07-28

## Source control

- Repository: `rrahul0904/applyai`
- Default branch: `main`
- Active implementation branch: `agent/applyai-milestone-one`
- Pull request: #1, open and draft
- The branch preserves the existing Next.js + FastAPI + PostgreSQL architecture.
- No destructive reset/clean operation was used.

This document records the source-controlled GitHub state. Local-only untracked files and machine-specific environment state are not observable from the remote repository and are therefore not claimed here.

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
- URL-backed job search and filters
- job cards
- job detail workspace
- saved jobs workspace
- applications list
- application detail, status history, and notes
- resume workspace
- persisted onboarding workflow
- PDF/DOCX upload and deterministic extraction
- candidate profile editor
- settings workspace backed by real account/profile data

## Backend domains observed

Implemented in source control:

- Clerk/dev identity abstraction and internal UUID mapping
- owner-scoped candidate profile APIs
- resume metadata, object-storage provider, queue provider, extraction state, and dedicated SQS worker
- production guard that rejects memory-queue resume execution
- canonical job/company/source models
- PostgreSQL search provider and cursor pagination
- saved-job uniqueness
- application uniqueness
- immutable application events
- application notes
- public Greenhouse connector with deterministic normalization and raw provenance
- configured Greenhouse ingestion runner
- normalized API errors
- health endpoint

## Migration state

Alembic revisions currently in the branch:

- `8f21ae7d52d5_initial_canonical_schema.py`
- `0db19a1adb4d_candidate_milestone_one_fields.py`

The latest Candidate MVP, queue/worker, and Greenhouse connector changes do not require a schema migration because they use already-present profile, preference, resume, source, job, saved-job, application, and onboarding fields.

## Test state

Previously reported on PR #1 before the current Candidate MVP changes:

- web production build: passed
- web lint: passed
- backend tests: 11 passed

New source-controlled tests added during Milestone 2 work:

- onboarding workflow persistence and completion guardrails
- Greenhouse public connector fetch/normalization/health/token validation
- production SQS configuration guardrails
- resume worker malformed/unsupported-message behavior

A GitHub Actions workflow now defines:

- web dependency install, lint, and production build
- PostgreSQL 17 test service
- Alembic zero-to-head
- Alembic drift check
- backend pytest

Observed GitHub Actions state: workflow runs are created, but both jobs terminate as failures before the connector exposes any job steps or log artifact. Therefore the new Candidate MVP changes are **implemented but not yet verified by a successful CI run**; application test failures are not inferred without logs.

## Environment state

Repository examples exist for web and API environment variables. Real production values are intentionally absent from source control.

Production resume execution now requires:

```text
TASK_QUEUE_PROVIDER=sqs
SQS_QUEUE_URL=...
OBJECT_STORAGE_PROVIDER=s3
S3_BUCKET=...
```

External configuration still required for production verification:

- Clerk production keys/issuer/audience configuration
- production PostgreSQL/Aurora endpoint
- private S3 bucket and IAM permissions
- SQS queue + DLQ/redrive policy and worker deployment
- Vercel web environment
- ECS/Fargate API and worker environment
- monitoring/secrets configuration

## Known technical debt found during audit

1. Job list/detail assembly performs multiple follow-up queries per job and should be optimized with explicit joins/eager loading before scale testing.
2. The applications web list currently resolves job details with parallel API requests; the API should expose an application summary projection to remove this fan-out.
3. Resume upload creates a new resume aggregate for each upload rather than deliberately versioning an existing master resume.
4. Playwright Candidate MVP acceptance coverage is not yet implemented.
5. Frontend behavior tests are not yet implemented even though Vitest/Testing Library dependencies exist.
6. Greenhouse is connected to the canonical ingestion pipeline, but cross-source deduplication, deterministic company-alias resolution, and repeated-miss freshness transitions still need hardening before calling real ingestion complete.
7. SQS worker retry behavior depends on an externally configured redrive/DLQ policy and has not yet been integration-tested against AWS.

## Preserve

- Next.js App Router
- FastAPI modular monolith
- PostgreSQL + SQLAlchemy + Alembic
- Clerk identity mapping
- provider interfaces for storage, queues, search, and job sources
- canonical job/source provenance model
- deterministic resume extraction boundary
- typed web API client
- existing ApplyAI visual system

## Immediate implementation sequence

1. Resolve GitHub Actions runner/execution failure and obtain a green build/test/migration run.
2. Add frontend behavior tests for onboarding, profile, job save, application status, and notes.
3. Add deterministic Playwright candidate acceptance journey using development auth/test data.
4. Optimize job/application projections to remove N+1/fan-out behavior.
5. Integration-test SQS resume retry, DLQ, S3, and idempotency behavior in AWS/staging.
6. Harden Greenhouse/company resolution, cross-source deduplication, and explicit freshness lifecycle; schedule ingestion.
7. Validate real Clerk authentication and cross-user isolation in an integration environment.
8. Prepare repeatable staging deployment and production configuration.

Only after Candidate MVP and real job ingestion are verified should matching/AI work begin.
