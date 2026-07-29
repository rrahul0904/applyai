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
S3 boundary     production object-storage provider
SQS boundary    production task-queue provider
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
- resume metadata, object-storage boundary, queue boundary, and extraction state
- canonical job/company/source models
- PostgreSQL search provider and cursor pagination
- saved-job uniqueness
- application uniqueness
- immutable application events
- application notes
- normalized API errors
- health endpoint

## Migration state

Alembic revisions currently in the branch:

- `8f21ae7d52d5_initial_canonical_schema.py`
- `0db19a1adb4d_candidate_milestone_one_fields.py`

The latest Candidate MVP UI/onboarding changes do not require a schema migration because they use already-present profile, preference, resume, job, saved-job, application, and onboarding fields.

## Test state

Previously reported on PR #1 before the current Candidate MVP changes:

- web production build: passed
- web lint: passed
- backend tests: 11 passed

New source-controlled verification added during Milestone 2 work:

- onboarding workflow tests
- `.github/workflows/ci.yml` for web lint/build and PostgreSQL migration/backend-test validation

The new CI workflow has been committed but no GitHub workflow result is currently available for the latest commit. Therefore the current Candidate MVP changes are **implemented but not yet verified by CI**.

## Environment state

Repository examples exist for web and API environment variables. Real production values are intentionally absent from source control.

External configuration still required for production verification:

- Clerk production keys/issuer/audience configuration
- production PostgreSQL/Aurora endpoint
- private S3 bucket and IAM permissions
- SQS queue + DLQ and worker deployment
- Vercel web environment
- ECS/Fargate API and worker environment
- monitoring/secrets configuration

## Known technical debt found during audit

1. Job list/detail assembly performs multiple follow-up queries per job and should be optimized with explicit joins/eager loading before scale testing.
2. The applications web list currently resolves job details with parallel API requests; the API should expose an application summary projection to remove this fan-out.
3. Resume parsing is currently also scheduled as an in-process FastAPI background task after queue publication. Production should move parsing exclusively to the durable worker path.
4. Resume upload creates a new resume aggregate for each upload rather than deliberately versioning an existing master resume.
5. Playwright Candidate MVP acceptance coverage is not yet implemented.
6. Frontend behavior tests are not yet implemented even though Vitest/Testing Library dependencies exist.
7. No legitimate live ATS connector has been completed; current seeded job data remains development-only.

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

1. Make CI execute and fix all lint/build/test failures.
2. Add frontend behavior tests for onboarding, profile, job save, application status, and notes.
3. Add deterministic Playwright candidate acceptance journey using development auth/test data.
4. Optimize job/application projections to remove N+1/fan-out behavior.
5. Finish durable SQS resume worker and idempotency behavior.
6. Implement one legitimate Greenhouse connector end to end with normalization, deduplication, provenance, and freshness.
7. Validate real Clerk authentication and cross-user isolation in an integration environment.
8. Prepare repeatable staging deployment and production configuration.

Only after Candidate MVP and real job ingestion are verified should matching/AI work begin.
