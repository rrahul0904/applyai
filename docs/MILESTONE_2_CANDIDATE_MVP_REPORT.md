# ApplyAI Milestone 2 Candidate MVP Report

Updated: 2026-07-28

## Executive Summary

Milestone 2 has moved ApplyAI from a backend-heavy foundation to a source-controlled candidate workflow covering onboarding, resume review, profile editing, job detail, saved jobs, application tracking, notes, resume management, and settings.

This coding pass also completed two important infrastructure/data slices that were missing from the original PR:

- production resume execution now has a real SQS provider and dedicated worker boundary;
- the first legitimate real-job connector now exists for the public Greenhouse Job Board API, including deterministic tests and a configured ingestion runner.

The frozen architecture was preserved. No matching, LLM, mobile, employer portal, billing, OpenSearch, Kafka, or Kubernetes scope was introduced.

Candidate MVP remains **PARTIAL** because the current branch still lacks a successful latest build/test/migration run, Playwright acceptance coverage, frontend behavior tests, formal accessibility validation, and live Clerk/S3/SQS/staging verification. GitHub Actions runs are being created but currently terminate before the connector exposes executable steps or logs, so no application test failure is inferred from those runs.

## Architecture Preserved

```text
Next.js App Router + React + TypeScript + Tailwind
                      ↓
                   FastAPI
                      ↓
PostgreSQL / SQLAlchemy / Alembic
      ↓              ↓               ↓
 candidate         jobs          applications
      ↓              ↓               ↓
 private S3      PostgreSQL FTS   immutable events
      ↓
     SQS
      ↓
resume worker

public Greenhouse Job Board API
      ↓
connector → raw source → normalize → canonical job pipeline
```

Preserved principles:

- Clerk subject maps to internal UUID ownership.
- FastAPI remains a modular monolith.
- PostgreSQL remains the system of record and current search engine.
- Resume binary content stays outside PostgreSQL.
- Source provenance/raw job payloads are preserved.
- Development job data remains explicitly marked.
- AI/matching remains deferred until real candidate/job data is reliable.

## Completed in Source Control

### Authentication

Preserved existing Clerk and guarded development authentication architecture.

No client-supplied user ID authorization was introduced.

Production configuration still requires live Clerk verification.

### Onboarding

Implemented persisted onboarding stages:

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

Implemented:

- explicit legal forward transitions;
- resume-processing branch;
- manual/resume-less path;
- ability to revisit earlier persisted steps;
- backend completion eligibility.

Completion requires:

- current title or headline;
- at least one target role;
- at least one work mode.

### Resume

Existing deterministic PDF/DOCX extraction was retained and exposed through the candidate journey.

Candidate UI now supports:

- PDF/DOCX upload;
- queued/processing state;
- failure/manual fallback;
- review-required state;
- extracted profile review;
- resume history display.

### Profile

Added `/profile` editor for:

- current title;
- headline;
- summary;
- years of experience;
- experience;
- education;
- skills;
- target roles;
- preferred location;
- work modes;
- minimum compensation.

Candidate edits persist through the canonical profile API.

### Jobs

Added `/jobs/[id]` candidate job workspace.

Displays source-backed fields only:

- title;
- company;
- location;
- work mode;
- employment type;
- compensation;
- posted/freshness fields;
- description;
- requirements;
- skills;
- source URL when present;
- development-data indicator.

Real actions:

- save/unsave;
- create/reuse application;
- open application workspace.

### Saved Jobs

Added `/saved` backed by authenticated saved-job persistence.

Supports loading, error, empty, list, unsave, and job navigation states.

### Applications

Added:

```text
/applications
/applications/[id]
```

Supports:

- create/reuse canonical candidate/job application;
- current status;
- immutable event timeline;
- private notes;
- note deletion;
- navigation back to canonical job.

### Resume Workspace

Added `/resume` for upload/history/status and review/failure guidance.

### Settings

Added `/settings` exposing only backed behavior:

- account identity/status;
- onboarding state;
- job preferences;
- privacy explanation;
- profile/preferences edit path.

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

The existing shell, dashboard, job search, job cards, API client, and design system were preserved.

## Backend Changes

### Onboarding

`services/api/app/api/onboarding.py` now contains explicit workflow transitions and backend completion validation.

### Production Queue Boundary

`services/api/app/core/config.py` now supports:

```text
TASK_QUEUE_PROVIDER
SQS_QUEUE_URL
SQS_REGION
```

Production rejects the in-memory task queue.

`services/api/app/core/queue.py` now actually selects SQS when configured rather than always returning the development in-memory queue.

Standard and FIFO SQS queues are both supported; FIFO-only deduplication/group fields are sent only to FIFO queue URLs.

### Resume Worker

Added:

```text
services/api/app/workers/resume.py
```

Production flow:

```text
upload
↓
private S3 provider
↓
ResumeVersion = QUEUED
↓
SQS RESUME_PARSE event
↓
dedicated resume worker
↓
PROCESSING
↓
NEEDS_REVIEW or FAILED
↓
ack only successful/review-ready work
```

Failed parsing is left unacknowledged for SQS retry/redrive behavior. An external DLQ/redrive policy is still required and must be verified in staging.

The API schedules inline background parsing only when the configured queue is the development memory queue.

## Real Job Ingestion

Real ingestion is now **PARTIAL**, not NOT STARTED.

Added `GreenhouseJobBoardConnector` using Greenhouse's public Job Board GET endpoints.

Implemented connector behavior:

- explicit board token validation;
- board/company identity lookup;
- public job fetch with full content;
- raw source payload preservation;
- source data origin marker `GREENHOUSE_PUBLIC_API`;
- deterministic HTML-to-text description normalization;
- source job ID/title/application URL;
- primary/office location extraction;
- conservative work-mode inference only when source location text says remote/hybrid;
- unknown employment type/seniority rather than invented values;
- no fabricated salary/skills/requirements;
- connector health;
- checkpoint metadata.

Added configured runner:

```bash
cd services/api
uv run python -m app.jobs.ingest
```

with:

```text
GREENHOUSE_BOARD_TOKENS=["company-board-token"]
```

Remaining before real ingestion is COMPLETE:

- scheduled production execution;
- deterministic company alias resolution;
- stronger cross-source deduplication;
- explicit repeated-miss freshness/stale transitions;
- production-scale ingestion tests/metrics.

## Database Changes

No new migration was required during this coding pass.

Existing migrations remain:

```text
8f21ae7d52d5_initial_canonical_schema.py
0db19a1adb4d_candidate_milestone_one_fields.py
```

Current changes use existing persisted candidate, resume, job/source, application, and onboarding structures.

## Testing Added

Existing PR #1 reported before these changes:

```text
web build: passed
web lint: passed
backend: 11 passed
```

Those counts apply to the earlier PR head only.

New backend test source now covers:

- onboarding stage persistence;
- out-of-order onboarding rejection;
- onboarding completion minimums;
- optional resume-processing path;
- Greenhouse fetch/normalization;
- Greenhouse health/token validation;
- production SQS requirement;
- required SQS queue URL;
- supported production SQS configuration;
- resume worker malformed/unsupported-message behavior.

A CI workflow now defines:

```text
web install
web lint
web production build
PostgreSQL 17
API dependency install
Alembic zero-to-head
Alembic drift check
backend pytest
```

### Current verification result

GitHub Actions workflow runs are created on the branch, but the observed jobs currently terminate as failures before job steps/log artifacts are exposed through the GitHub integration. Therefore:

```text
backend latest passed count: NOT VERIFIED
frontend latest passed count: NOT VERIFIED
Playwright: NOT STARTED
```

No test count is invented.

## Security

Implemented/preserved:

- authenticated candidate endpoints;
- owner-scoped candidate resources;
- protected application notes;
- private object-storage boundary;
- no raw storage key in normal resume API responses;
- resume file extension/content-type/size/empty validation;
- production rejects development auth;
- production now rejects in-memory resume queue execution;
- SQS task payload contains opaque IDs, not resume contents;
- no resume content is intentionally logged;
- Greenhouse integration uses public API reads rather than access-control bypass/scraping;
- no AI-generated candidate facts.

Remaining:

- live Clerk integration test;
- production S3/IAM verification;
- SQS IAM + DLQ/redrive verification;
- malware-scanning decision/implementation;
- rate limiting;
- formal IDOR/XSS/SSRF/log-redaction/upload security pass.

## Accessibility

Shared/new UI uses semantic labels, headings, buttons, visible focus styling, and reduced-motion support.

Formal keyboard, screen-reader, and automated accessibility verification is still pending.

## Performance

Known performance debt:

1. job list/detail assembly performs follow-up related-record queries;
2. saved-job assembly performs per-job related queries;
3. applications web list performs parallel job-detail API calls;
4. application backend response assembly loads events/notes per application.

Next performance slice should build joined/eager-loaded summary projections and measure query plans for core endpoints.

## Production Readiness

Improved in this pass:

- source-controlled CI workflow;
- production SQS selection;
- production memory-queue guard;
- independent resume worker;
- SQS FIFO/standard handling;
- SQS configuration examples;
- Greenhouse production connector boundary;
- Greenhouse configured ingestion runner;
- README operational commands.

Still required:

- successful CI run on current head;
- frontend behavior tests;
- Playwright candidate persistence journey;
- live Clerk integration;
- private S3 integration;
- real SQS + DLQ/redrive integration;
- scheduled Greenhouse ingestion/freshness lifecycle;
- Vercel/ECS/Aurora staging deployment;
- structured logging/CloudWatch verification;
- secrets/IAM validation.

## Known Limitations

- Current Candidate MVP source has not yet passed a latest-head CI run.
- Resume uploads create a new resume aggregate instead of deliberately versioning the existing master resume.
- Greenhouse ingestion is functional at connector/runner level but freshness and cross-source dedup still need hardening.
- Application list/job presentation needs a backend summary projection.
- Frontend behavior tests and Playwright are not yet implemented.
- Production resources are not deployed/verified.

## Blocked by External Configuration / Platform

- GitHub Actions currently terminates jobs before usable step/log evidence is available.
- Clerk production credentials/configuration.
- AWS S3 bucket/IAM.
- AWS SQS queue/DLQ/IAM.
- ECS/Fargate API/worker resources.
- Aurora production database.
- Vercel production environment.

## Next Engineering Sequence

1. Resolve CI runner/execution failure and obtain green lint/build/migrations/backend tests.
2. Add frontend behavior tests.
3. Add Playwright Candidate MVP persistence journey.
4. Remove job/application N+1/fan-out behavior.
5. Stage-test S3/SQS resume worker retries, idempotency, and DLQ.
6. Harden Greenhouse company resolution, deduplication, freshness, scheduling, and metrics.
7. Verify real Clerk authentication/isolation.
8. Deploy and validate staging.

Only then should Milestone 3 matching begin.

## Next Milestone

# APPLYAI MILESTONE 3 — JOB INTELLIGENCE & MATCHING

Not implemented yet.

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

## Status Matrix

```text
Candidate MVP: PARTIAL
Authentication: PARTIAL
Resume Pipeline: PARTIAL
Profile: PARTIAL
Job Search: PARTIAL
Real Job Ingestion: PARTIAL
Applications: PARTIAL
Testing: BLOCKED
Production Deployment: BLOCKED
AI Matching: NOT STARTED
Mobile: NOT STARTED
Employer Platform: NOT STARTED
```
