# Milestone 2.5 — Verification and Staging Report

Updated: 2026-07-29

## Executive Summary

Milestone 2.5 has started on PR #1 without redesigning the frozen ApplyAI architecture or adding AI matching, mobile, employer, billing, OpenSearch, Kafka, or Kubernetes scope.

This pass completed source-level hardening in four areas:

1. CI is split into independent observable jobs for web lint, web typecheck, web tests, web production build, API migration validation, and API tests.
2. Frontend Vitest coverage now exists for job detail/save/application creation, applications list rendering, application status/history/notes, and saved jobs.
3. Application/job list hot paths were changed to remove the known frontend API fan-out and reduce backend N+1 relation assembly.
4. API staging safety now includes `/ready`, exact credentialed CORS origin behavior, and fail-closed requirements for Clerk + S3 + SQS in staging/production.

The milestone is **not verified** and **not staging deployed**. The current blocker occurs before application commands execute: the available GitHub Actions runs create jobs but terminate with no exposed steps/logs, while this execution sandbox cannot resolve `github.com` for a clean checkout. No current-head test pass is claimed.

## Repository HEAD

Repository: `rrahul0904/applyai`

Branch: `agent/applyai-milestone-one`

PR: #1, open, draft, mergeable

Audited implementation head before the documentation-only status update: `a0bffc923301226d870341c57c8ffa28792c856f`

PR metadata at that point reported 57 commits and 126 changed files.

## CI Investigation

The previous CI definition grouped verification into two coarse jobs. Milestone 2.5 changed it to six independent jobs:

- Web lint
- Web typecheck
- Web tests
- Web production build
- API migration validation
- API tests

Pinned/runtime configuration now includes:

- Node 22.13.0
- pnpm 10.13.1
- Python 3.12.11
- PostgreSQL 17
- pnpm cache through `actions/setup-node`
- uv cache through `astral-sh/setup-uv`

Observed workflow run on implementation head `a0bffc923301226d870341c57c8ffa28792c856f`:

- Run: `30420175430`
- Conclusion: failure
- All six jobs were created
- All six jobs completed failure
- Connector-visible job steps: none
- Connector-visible logs: none

This is treated as a runner/account/execution-layer blocker, not proof that lint, tests, build, or migrations failed.

## Local Verification

A clean clone was attempted from the execution sandbox using the PR branch.

Result:

```text
fatal: unable to access 'https://github.com/rrahul0904/applyai.git/':
Could not resolve host: github.com
```

Because the sandbox cannot reach GitHub and no complete repository checkout is mounted locally, the required clean-environment commands cannot be executed honestly from this environment.

## Frontend Tests

Vitest configuration is now source-controlled in `apps/web/vitest.config.ts`.

New behavior tests cover:

- job detail rendering
- save-job mutation
- application creation from job detail
- application list summary rendering
- regression check preventing application-list job-detail fan-out
- application timeline rendering
- application status mutation
- application note creation/deletion
- saved-jobs empty state
- saved-jobs persisted results

Still missing:

- onboarding stage persistence/refresh behavior
- resume processing states and retry/manual fallback
- extraction review editing
- profile editor
- settings
- broader error/retry behavior

Execution result: **BLOCKED — tests are committed but the available runner does not execute steps.**

## Backend Tests

Existing backend coverage remains for authentication/authorization, profile, resume, jobs, applications, onboarding, Greenhouse, queue configuration, and worker behavior.

Milestone 2.5 added regression coverage for:

- lightweight application-list projection
- application-list owner isolation
- `/health`
- database-aware `/ready`
- staging S3 requirement
- production SQS requirement
- wildcard credentialed-CORS rejection
- valid durable production configuration

Execution result: **BLOCKED — current-head pytest has not run in an observable environment.**

## Playwright

Status: **NOT STARTED**

The dependency exists, but the deterministic Candidate MVP journey has not been added. It must not be called complete until the full logout/login persistence journey is implemented and executed.

## Performance

Completed source-level changes:

- `/applications` list no longer materializes events and notes for every row.
- `/applications` now returns a lightweight nested job summary needed by the list UI.
- `ApplicationsView` no longer performs `GET /jobs/{id}` for each application.
- job list company/location/compensation assembly is batch-loaded rather than fetched per job.
- saved-job job/company/location/compensation assembly is batch-loaded.
- saved-job list is explicitly bounded with a maximum limit.

Still required:

- measured SQL query counts
- measured client request counts
- `EXPLAIN`/query-plan review for representative search filters
- dashboard request audit
- application-detail/profile request audit
- full saved-job pagination strategy

## Database Query Review

Known hot paths addressed:

```text
/applications
/jobs
/jobs/saved
```

Application list changed from:

```text
applications
+ events per application
+ notes per application
+ job detail request per application
```

to a dedicated list projection containing only:

```text
application id/status/timestamps
job id/title/company/location
```

Job search and saved jobs now batch-load related company/location/compensation rows.

No speculative indexes were added in this pass because real query plans have not yet been measured.

## Resume Architecture

Source-controlled architecture remains:

```text
API
→ object storage provider
→ task queue provider
→ dedicated resume worker
→ deterministic parser
→ extraction/review state
```

Staging/production configuration now fails closed unless S3 and SQS are selected.

## S3 Validation

Status: **PARTIAL / staging validation BLOCKED**

Implemented in code:

- S3 provider
- opaque storage-key architecture
- server-side AES256 encryption on upload
- staging/production requires `OBJECT_STORAGE_PROVIDER=s3`
- staging/production requires `S3_BUCKET`

Not proven:

- real private staging bucket
- IAM least privilege
- API upload to real S3
- worker retrieval from real S3
- object privacy inspection
- failed-transaction cleanup behavior

## SQS Validation

Status: **PARTIAL / staging validation BLOCKED**

Implemented in code:

- memory/SQS provider selection
- production/staging requires SQS
- queue URL required for SQS provider
- standard/FIFO publishing behavior
- dedicated resume worker

Not proven:

- real staging publish/receive
- visibility timeout
- max receive count
- redrive policy
- DLQ behavior

## Worker Validation

Status: **PARTIAL**

Implemented:

- dedicated worker module
- malformed-message retry behavior
- unsupported-message handling
- processing through configured storage provider
- success/review-ready acknowledgement behavior

Missing:

- real SQS execution
- redelivery idempotency proof
- worker timeout/resource validation
- structured end-to-end correlation across API → queue → worker

## DLQ Validation

Status: **BLOCKED**

Requires real staging SQS queue + DLQ + redrive policy. No DLQ success claim is made.

## Greenhouse Connector

Status: **PARTIAL**

Implemented before this pass:

- public Greenhouse Job Board fetch
- board/company lookup
- published job retrieval
- raw payload preservation
- deterministic normalization
- provenance
- health checks
- configured ingestion runner
- connector tests

This pass did not change Greenhouse ingestion because clean current-head verification is blocked earlier in the milestone sequence.

## Company Resolution

Status: **PARTIAL**

Canonical company, alias, and source tables exist, but Greenhouse ingestion still needs deterministic source-backed company resolution hardening and explicit tests before acceptance.

## Deduplication

Status: **PARTIAL**

Current canonicalization is not yet sufficient for the Milestone 2.5 multi-signal acceptance definition. Required follow-up includes source/external ID, company identity, apply URL, normalized title/location, description fingerprint, and conservative ambiguity handling.

## Freshness

Status: **PARTIAL**

Existing job/source models contain first/last seen and status foundations, but repeated-miss thresholds, last-verified behavior, stale transitions, and close transitions still require implementation and tests.

## Authentication

Status: **PARTIAL**

Source-level hardening completed:

- production development-auth rejection retained
- staging/production now require Clerk provider
- staging/production require Clerk issuer + JWKS URL
- staging/production require HTTPS web origin
- wildcard credentialed CORS is rejected

Still required:

- real Clerk staging sign-up/login/logout
- email verification behavior if enabled
- Google sign-in if enabled
- session refresh/expiry
- FastAPI bearer-token smoke test
- two-user cross-resource staging authorization test

## Security

Completed source-level controls include owner-scoped APIs, upload validation, normalized API errors, credentialed CORS restriction, production dev-auth rejection, and durable-environment fail-closed configuration.

Still required as executed acceptance checks:

- IDOR
- cross-user UUID access
- invalid/expired JWT
- malicious filename
- S3 privacy
- log leakage
- SQL injection regression review
- XSS/browser behavior

## Accessibility

Status: **PARTIAL**

Source already uses labels, semantic controls, focus-visible styles, and responsive layouts in many candidate surfaces. Formal keyboard/screen-reader/contrast/reduced-motion acceptance has not been executed.

## Staging Infrastructure

Status: **BLOCKED**

Target remains:

```text
Vercel Next.js
→ ECS/Fargate FastAPI
→ Aurora/PostgreSQL
→ S3
→ SQS
→ ECS resume worker
→ Clerk
```

Repository configuration now rejects development providers in staging, but the real external resources/credentials are not available in this execution environment.

## Staging Smoke Test

Status: **BLOCKED — NOT EXECUTED**

No claim is made for real Clerk, S3, SQS, worker, Greenhouse, persistence, logout/login, or DLQ behavior in staging.

## Known Issues

1. GitHub Actions jobs terminate before exposed steps/logs.
2. Clean local checkout is blocked by sandbox DNS/network access to GitHub.
3. Playwright Candidate MVP journey is not implemented.
4. Greenhouse company resolution/dedup/freshness remains incomplete.
5. Real S3/SQS/DLQ/worker/Clerk staging integration is unavailable.
6. Full performance measurements are not available yet.
7. Accessibility/security acceptance execution remains pending.

## Production Blockers

- current-head automated verification
- staging environment
- staging smoke test
- real Clerk verification
- S3/IAM proof
- SQS/DLQ/redrive proof
- ECS API/worker deployment
- Aurora/PostgreSQL deployment
- monitoring/alerting/backups/secrets
- deployment approval

Production readiness is **not** claimed.

## Test Report

No old test counts are reused.

```text
Backend:    BLOCKED — current-head pytest not executed by available runner
Frontend:   BLOCKED — current-head Vitest not executed by available runner
Playwright: NOT STARTED

Build:      BLOCKED — job created but no steps/logs exposed
Lint:       BLOCKED — job created but no steps/logs exposed
Typecheck:  BLOCKED — job created but no steps/logs exposed
Alembic:    BLOCKED — job created but no steps/logs exposed
```

## BLOCKER

What failed:

Current-head clean automated verification cannot execute in the available environments.

Evidence:

- GitHub Actions run `30420175430` created six independent jobs, all ending failure with no exposed steps/logs.
- Clean sandbox clone failed because `github.com` could not be resolved.

Root cause:

The exact GitHub Actions account/runner cause is not visible through the connected API. The local sandbox has no usable GitHub network/DNS path.

What was attempted:

- restructured CI into independent jobs
- pinned Node/pnpm/Python versions
- added safe dependency caching
- kept PostgreSQL 17 service
- triggered current-head workflows repeatedly through branch commits
- inspected run/job metadata
- attempted clean branch clone from the execution sandbox

What remains:

Run the current head in an environment where either GitHub-hosted Actions starts normally or a complete clean repository checkout can execute commands.

External dependency:

GitHub Actions runner/account availability or another clean execution environment with repository network access.

## Required Final Status

```text
Candidate MVP:          PARTIAL
Authentication:         PARTIAL
Resume Pipeline:        PARTIAL
Profile:                PARTIAL
Job Search:             PARTIAL
Saved Jobs:             PARTIAL
Applications:           PARTIAL
Greenhouse Ingestion:   PARTIAL
Deduplication:           PARTIAL
Freshness:               PARTIAL
Frontend Testing:       PARTIAL / EXECUTION BLOCKED
Backend Testing:        BLOCKED
Playwright:              NOT STARTED
S3:                      PARTIAL / STAGING BLOCKED
SQS:                     PARTIAL / STAGING BLOCKED
Worker:                  PARTIAL / STAGING BLOCKED
CI:                      BLOCKED
Staging Deployment:      BLOCKED
Production Deployment:   BLOCKED

AI Matching:             NOT STARTED
Mobile:                  NOT STARTED
Employer Platform:       NOT STARTED
```

## Next Milestone

Do not begin Milestone 3 yet.

The next executable work remains Milestone 2.5 verification: obtain an executing clean runner, fix any real failures it exposes, complete frontend tests + Playwright, then harden Greenhouse and validate Clerk/S3/SQS/worker behavior in staging before matching work begins.
