# ApplyAI Milestone 2 Candidate MVP Report

Updated: 2026-07-28

## Executive Summary

Milestone 2 work moved ApplyAI from a backend-heavy foundation to a source-controlled candidate journey that now includes persisted onboarding, resume review, profile editing, job detail, saved jobs, application tracking, notes, resume management, and settings.

The architecture was preserved. No matching, LLM, mobile, employer portal, billing, OpenSearch, Kafka, or Kubernetes scope was introduced.

Candidate MVP remains **PARTIAL** because the latest changes have not yet produced a successful CI run, Playwright acceptance coverage is not implemented, resume parsing still uses an in-process background path in addition to the queue boundary, real ATS ingestion is not implemented, and production Clerk/AWS/deployment configuration is external.

## Architecture Preserved

```text
Next.js App Router + React + TypeScript + Tailwind
                      ↓
                   FastAPI
                      ↓
PostgreSQL / SQLAlchemy / Alembic
      ↓              ↓             ↓
 candidate         jobs        applications
      ↓              ↓             ↓
  S3 boundary    search       immutable events
      ↓
 SQS boundary / future durable worker
```

Preserved decisions:

- Clerk identity with internal UUID user ownership
- FastAPI modular monolith
- PostgreSQL as system of record and current search engine
- S3-compatible resume storage
- SQS-compatible asynchronous task boundary
- deterministic development data separated by `data_origin`
- no AI/matching expansion before real candidate/job data is reliable

## Features Completed in Source Control

### Authentication

Preserved existing Clerk and guarded development authentication architecture.

No client-supplied user ID authorization was introduced by Milestone 2 changes.

### Onboarding

Added persisted candidate onboarding UI and hardened backend progression.

Stages now represented:

```text
ACCOUNT_CREATED
RESUME
RESUME_PROCESSING
PROFILE_REVIEW
TARGET_ROLES
LOCATION
WORK_PREFERENCES
COMPENSATION
REVIEW
COMPLETE
```

Resume processing is optional so a candidate may continue manually.

Backend completion now requires:

- a current title or headline
- at least one target role
- at least one work mode

Completion can no longer jump around the persisted workflow.

### Resume

Existing PDF/DOCX deterministic extraction was confirmed in code.

New candidate UI supports:

- upload
- processing state
- failure/manual fallback
- review-required state
- resume history display

### Profile

Added `/profile` editor for:

- current title
- headline
- summary
- years of experience
- experience records
- education records
- skills
- target roles
- preferred location
- work modes
- minimum compensation

Candidate edits are persisted through the existing profile API.

### Jobs

Added `/jobs/[id]` candidate job detail workspace.

Displays only source-backed data:

- title
- company
- location
- work mode
- employment type
- compensation
- posted/freshness dates
- description
- requirements
- skills
- source URL when present
- development-data indicator

Actions are real:

- save/unsave writes through saved-job API
- track application creates/reuses the canonical candidate/job application

### Saved Jobs

Added `/saved` using the existing authenticated saved-job API.

Includes loading, error, results, empty state, unsave, and navigation to job detail.

### Applications

Added `/applications` and `/applications/[id]`.

The application workspace supports:

- persisted current status
- immutable status-event timeline
- add private note
- delete private note
- navigation back to the canonical job

### Settings

Added `/settings` with only real backed functionality:

- account identity/status
- onboarding state
- target roles
- location/work-mode preferences
- privacy explanation
- link to edit candidate profile/preferences

No fake notification or discoverability controls were added.

## Frontend Changes

New components:

```text
components/onboarding-view.tsx
components/job-detail-view.tsx
components/saved-jobs-view.tsx
components/applications-view.tsx
components/application-detail-view.tsx
components/resume-view.tsx
components/profile-view.tsx
components/settings-view.tsx
```

New routes:

```text
/onboarding
/jobs/[id]
/saved
/applications
/applications/[id]
/resume
/profile
/settings
```

The existing candidate shell, dashboard, job search, job cards, shared UI primitives, and API client were preserved.

## Backend Changes

`services/api/app/api/onboarding.py` now contains:

- explicit stage order
- explicit legal forward transitions
- ability to revisit earlier steps
- optional resume-processing branch
- backend completion eligibility checks

## Database Changes

No new migration was required for this implementation slice.

Existing migrations:

```text
8f21ae7d52d5_initial_canonical_schema.py
0db19a1adb4d_candidate_milestone_one_fields.py
```

The new workflows use existing persisted fields and tables.

## Migrations

A GitHub Actions CI job was added to execute:

```bash
alembic upgrade head
alembic check
pytest
```

against PostgreSQL 17.

The workflow definition is committed, but no successful workflow result is currently available for the latest branch head, so migration verification is not claimed for this iteration.

## Authentication

Current source supports:

- Clerk web authentication
- JWT verification boundary in FastAPI
- development auth when explicitly enabled
- internal user UUID mapping
- owner-scoped candidate APIs

External/live verification remains required for production Clerk keys, issuer/audience values, and end-to-end login/logout behavior.

## Resume Pipeline

Current implementation path:

```text
upload
↓
private object storage provider
↓
ResumeVersion = QUEUED
↓
queue event
↓
in-process background parser (current development implementation)
↓
PROCESSING
↓
NEEDS_REVIEW or FAILED
↓
candidate review
↓
COMPLETED
```

Production gap: parsing must move to the durable SQS worker path with bounded retries and DLQ behavior instead of relying on API-process background execution.

## Candidate Profile

The candidate profile is structured separately from extracted resume text and remains the canonical candidate representation.

Current provenance design distinguishes document-extracted data from candidate-verified edits.

## Job Search

Existing PostgreSQL search/filter/cursor API is preserved.

Candidate search state is URL-backed.

Performance debt remains in job result assembly because company/location/compensation are loaded through multiple follow-up queries per job.

## Saved Jobs

Saved jobs remain protected by composite candidate/job ownership.

The UI is now implemented but requires browser/E2E persistence verification before the domain is called complete.

## Application Tracking

Existing uniqueness prevents duplicate applications per candidate/job.

Status transitions append immutable events.

Notes are candidate/application scoped.

The new web list currently resolves job details using parallel API calls. A future application-summary API projection should remove this fan-out.

## Job Ingestion

Real ingestion remains **NOT STARTED**.

The next implementation should complete one legitimate Greenhouse connector before Lever or Ashby.

Required order:

```text
FETCH
RAW SOURCE RECORD
VALIDATE
NORMALIZE
RESOLVE COMPANY
DEDUPLICATE
CREATE/UPDATE CANONICAL JOB
LINK SOURCE
UPDATE FRESHNESS
SEARCH DOCUMENT
```

No unauthorized scraping should be introduced.

## Testing

Previously reported before these changes:

```text
web build: passed
web lint: passed
backend: 11 passed
```

New test code:

- persisted onboarding-stage test
- out-of-order transition rejection
- completion-minimum validation
- optional resume-processing transition

New CI workflow:

- web dependency install
- web lint
- web production build
- PostgreSQL 17 service
- API dependency install
- Alembic zero-to-head
- Alembic drift check
- backend pytest

Current verified count for the new branch head: **not available**.

No test number is invented in this report.

## Security

Preserved/implemented:

- authenticated candidate endpoints
- account-scoped profile/resume/saved-job/application/note ownership
- private resume storage boundary
- no raw S3 key exposure in normal resume responses
- file extension/content-type/size/empty validation
- normalized API errors
- no candidate data in development job records
- no AI-generated candidate facts

Remaining security work:

- live auth integration verification
- production S3/IAM validation
- malware scanning decision/implementation
- durable worker security/IAM
- rate-limit implementation/validation
- formal security test pass for IDOR, XSS, SSRF, log redaction, and upload edge cases

## Accessibility

The existing shared UI and new forms use semantic labels, buttons, headings, focus-visible styling, and reduced-motion support.

A formal keyboard/screen-reader/automated accessibility test has not yet been run; therefore accessibility is **PARTIAL**.

## Performance

Known issues to address before scale testing:

1. Job API list/detail data assembly issues follow-up SQL queries for related records.
2. Saved-job list uses per-record follow-up queries.
3. Application list UI performs parallel job-detail requests.
4. Application backend response construction loads events/notes per application.

Next step: replace these with explicit joined/eager-loaded projections and then measure query plans for the core APIs.

## Production Readiness

Added source-controlled CI definition.

Still required:

- first successful CI run on current branch
- frontend behavior tests
- Playwright Candidate MVP journey
- production Clerk integration
- private S3 integration
- durable SQS worker + DLQ
- legitimate real ATS ingestion
- staging Vercel/ECS/Aurora deployment
- CloudWatch/structured logging verification
- production secrets configuration

## Known Limitations

- Candidate MVP code is not yet CI-verified after the latest changes.
- Resume uploads are not deliberately versioned under an existing master resume aggregate.
- Resume parsing still has an API background-task execution path.
- Real ATS data is not present.
- Application list/job presentation needs a backend summary projection.
- Frontend test suite and Playwright acceptance test are not yet implemented.
- Production resources are not deployed/verified.

## Blocked Items

Blocked by external configuration/infrastructure:

- live Clerk production authentication
- AWS S3/SQS integration
- ECS/Fargate worker/API deployment
- Aurora production database
- Vercel production environment

Not externally blocked and should be implemented next:

- frontend tests
- Playwright
- query optimization
- durable worker code
- Greenhouse connector
- CI fixes until green

## Next Milestone

Milestone 2 must first be completed and verified.

After Candidate MVP + real job ingestion are complete, the planned next milestone is:

# APPLYAI MILESTONE 3 — JOB INTELLIGENCE & MATCHING

```text
Candidate Profile
        ↓
Candidate Representation

Job
        ↓
Job Representation

Hard Eligibility Filters
        ↓
Lexical Retrieval
        ↓
Semantic Retrieval
        ↓
Feature Ranking
        ↓
Explainable Match
```

Possible later technologies include pgvector, embeddings, reranking, feature scoring, and LLM assistance. None should be added before the Milestone 2 acceptance criteria pass.

## Status Matrix

```text
Candidate MVP: PARTIAL
Authentication: PARTIAL
Resume Pipeline: PARTIAL
Profile: PARTIAL
Job Search: PARTIAL
Real Job Ingestion: NOT STARTED
Applications: PARTIAL
Testing: PARTIAL
Production Deployment: BLOCKED
AI Matching: NOT STARTED
Mobile: NOT STARTED
Employer Platform: NOT STARTED
```
