# ApplyAI Milestone 2.6 — Correctness, Durability, Ingestion Lifecycle & Verification Gate

Updated: 2026-07-29

## Executive Summary

Milestone 2.6 was executed as a correctness gate on PR #1 rather than a feature expansion.

The milestone began from resolved PR HEAD:

```text
44bbbbd43859d08645130b1007444ad5a7b11a0e
```

The branch has advanced through the source changes documented below. The final PR head necessarily changes when this report itself is committed; PR metadata is the canonical branch-tip reference.

No AI matching, embeddings, pgvector, native mobile, employer workflows, billing, OpenSearch, Kafka, Kubernetes, microservice split, or new ATS connector was added.

The principal P0 source changes are:

1. resume bytes no longer depend on the Next.js/Vercel BFF in durable environments;
2. a separate durable upload-intent record exists before the object is uploaded;
3. `ResumeVersion` and `RESUME_PARSE` outbox event are created together only after S3 verification;
4. task dispatch is a PostgreSQL transactional outbox with `SKIP LOCKED`, idempotency keys and retry/backoff;
5. one master resume per candidate is enforced and legacy duplicate masters are consolidated by migration;
6. resume processing is idempotent under at-least-once queue delivery and records attempts;
7. SQS visibility/heartbeat are configurable and PROCESSING redeliveries remain retryable;
8. extraction confirmation atomically completes resume state and persists candidate-reviewed profile data as USER_VERIFIED;
9. Greenhouse identity is board-scoped, freshness is refreshed on unchanged payloads, canonical changes propagate, miss-based lifecycle is run-health aware, and multi-source jobs are not downgraded by one missing source;
10. PostgreSQL search now includes lexical relevance ranking while retaining deterministic cursor behavior;
11. applications are bounded by keyset pagination;
12. database pool configuration, Clerk JWKS provider lifetime, and BFF path/body security are hardened;
13. frontend/backend regression source was expanded materially.

The current head has **not** been declared passing because no available execution environment has produced executable current-head test/build output.

---

## Scope Freeze

Preserved:

```text
Next.js App Router
React + TypeScript + Tailwind
Clerk
FastAPI + Pydantic
SQLAlchemy 2 + Alembic + Psycopg 3
PostgreSQL
private S3
SQS
Vercel + AWS deployment target
```

Not implemented:

```text
AI matching
embeddings
pgvector matching
resume AI rewriting
cover letters
interview AI
auto apply
iOS
Android
employer/recruiter portal
billing/payments
OpenSearch
Kafka
Kubernetes
new ATS connectors
```

---

## Repository Inspection

Milestone 2.6 began only after resolving PR #1 and inspecting the requested current-source areas:

```text
services/api/app/api/resumes.py
services/api/app/resumes/processor.py
services/api/app/workers/resume.py
services/api/app/core/queue.py
services/api/app/core/storage.py
services/api/app/jobs/pipeline.py
services/api/app/jobs/connectors.py
services/api/app/models.py
services/api/app/api/jobs.py
services/api/app/api/applications.py
services/api/app/core/auth.py
services/api/app/core/database.py
apps/web/app/api/backend/[...path]/route.ts
apps/web/components/onboarding-view.tsx
apps/web/lib/api/client.ts
.github/workflows/ci.yml
```

The documentation snapshot was not treated as proof of current source behavior.

---

## Resume Upload Architecture

### Previous risk

Durable upload previously behaved conceptually as:

```text
Browser
→ Next.js BFF
→ FastAPI
→ object storage
→ DB commit
→ queue send
```

This made Vercel/Next.js carry resume file bodies and allowed database success to precede queue publication.

### Current source

Durable staging/production path:

```text
Browser
  ↓ POST /resumes/upload-intents
FastAPI
  ↓ validates filename/extension/MIME/size/ownership intent
PostgreSQL
  ↓ durable ResumeUploadIntent with opaque storage key + preallocated version UUID
FastAPI
  ↓ short-lived object-specific presigned S3 PUT
Browser
  ↓ PUT directly
private S3
Browser
  ↓ POST /resumes/versions/{id}/upload-complete
FastAPI
  ↓ S3 HEAD
  ↓ verifies existence/size/content type/expiration/ownership
PostgreSQL transaction
  ├─ ResumeVersion → UPLOADED / QUEUED
  └─ TaskOutbox RESUME_PARSE with unique idempotency key
```

A `ResumeVersion` does not exist at direct-upload initiation. That row and its parse outbox event first appear together after successful storage verification.

Storage keys contain opaque UUIDs and do not contain candidate names or email addresses.

Development may retain multipart upload against local storage. The local path still commits version + outbox together before any queue publication.

### Remaining verification

- real private S3 bucket;
- real bucket CORS for the staging web origin;
- presigned PUT behavior with browser headers;
- IAM scope;
- abandoned/expired intent cleanup operations.

---

## Transactional Outbox

Added generic `task_outbox` fields:

```text
id
event_type
aggregate_type
aggregate_id
payload
idempotency_key UNIQUE
status
attempt_count
available_at
locked_at
lock_owner
published_at
last_error
created_at
```

Publisher behavior:

```text
PENDING
→ FOR UPDATE SKIP LOCKED claim
→ CLAIMED
→ SQS publish
→ PUBLISHED
```

Failure behavior:

```text
publish failure
→ attempt_count + 1
→ PENDING
→ exponential available_at
→ preserve ResumeVersion + S3 object
```

Stale claimed rows become claimable again after the configured lock timeout.

An outbox idempotency key prevents duplicate logical rows. A crash after SQS accepts a message but before PostgreSQL records `PUBLISHED` can still create a duplicate delivery; this is intentionally handled by worker idempotency rather than pretending SQS + PostgreSQL provide a distributed transaction.

---

## Resume Domain Versioning

Chosen domain:

```text
one candidate master Resume
        ↓
ResumeVersion 1
ResumeVersion 2
ResumeVersion 3
...
```

Implemented source invariants:

- at most one `is_master=true` Resume per candidate through a partial unique PostgreSQL index;
- replacement upload increments version under a master-resume row lock;
- concurrent creation uses a database uniqueness guard as final protection;
- storage object keys include candidate/master/version UUIDs;
- migration consolidates legacy duplicate master Resume rows before the unique index is created;
- legacy version numbers are temporarily made collision-safe, moved to the canonical master, and then renumbered chronologically.

---

## Resume Extraction / Confirmation

Processing state:

```text
QUEUED
→ PROCESSING
→ NEEDS_REVIEW
→ candidate confirmation
→ COMPLETED
```

Failure:

```text
PROCESSING
→ FAILED
→ later retry may reuse the same extraction identity
```

Candidate confirmation now performs one transaction containing:

```text
profile/preferences save
experience save
education save
skills save
ResumeExtraction → COMPLETED
ResumeVersion → COMPLETED
```

Candidate-reviewed profile-child provenance is normalized to:

```text
USER_VERIFIED
```

Resume-derived onboarding calls the confirmation API. Manual onboarding continues to use ordinary profile persistence.

The profile-review screen also restores persisted extraction data after browser refresh.

---

## Processing Idempotency

Added:

```text
ResumeProcessingAttempt
- resume_version_id
- parser_version
- attempt_number
- status
- started_at
- completed_at
- error_code
```

Integrity:

- unique extraction per `resume_version_id + parser_version`;
- unique processing-attempt number per version/parser;
- terminal review/completed state is not processed again;
- active attempts are lease-protected;
- stale PROCESSING attempts can be abandoned and retried;
- failure reuses the extraction identity rather than creating duplicate successful rows;
- verified/completed profile state is not overwritten by parser redelivery.

The migration first consolidates any existing duplicate extraction rows before adding the uniqueness constraint.

---

## SQS Worker Lease

Configuration is no longer tied to a hard-coded 120-second receive assumption.

Environment-driven controls include:

```text
SQS_VISIBILITY_TIMEOUT_SECONDS
SQS_VISIBILITY_HEARTBEAT_SECONDS
SQS_WAIT_TIME_SECONDS
```

The heartbeat extends message visibility while work runs.

Acknowledgement policy:

```text
NEEDS_REVIEW → ACK
COMPLETED    → ACK
FAILED       → no ACK
PROCESSING   → no ACK
unexpected   → no ACK
```

`PROCESSING` is deliberately not acknowledged. A previous delivery may have died after persisting PROCESSING; retaining the message lets the database processing lease age out and recover.

DLQ redrive and max receive count remain AWS queue configuration and must be validated in staging.

An explicit hard parser execution timeout remains an operational follow-up; heartbeat + stale attempt recovery are implemented, but no unsupported claim is made that Python document parsing is forcibly terminated after a fixed duration.

---

## Greenhouse Source Identity

Source-company identity:

```text
CompanySource.source_name = GREENHOUSE
CompanySource.external_company_id = board_token
```

Job source identity:

```text
external_job_id = {board_token}:{greenhouse_post_id}
```

Preserved source metadata includes:

```text
board token
Greenhouse post ID
internal_job_id when present
source/apply URL
Greenhouse updated_at
fetched_at
raw payload
```

This removes cross-board post-ID collision risk.

---

## Greenhouse Last-Seen Semantics

Freshness is updated before identical-payload early return.

For the same posting fetched again:

```text
JobSource.first_seen_at → unchanged
Job.first_seen_at       → unchanged
JobSource.last_seen_at  → advances
Job.last_seen_at        → advances
raw posting count       → unchanged
JobVersion count        → unchanged
```

Transport-only `_applyai_fetched_at` is excluded from the material payload hash.

---

## Changed Job Propagation

Canonical change detection covers:

```text
title
description
primary location
work mode
employment type when source knows it
seniority when source knows it
posted time when available
compensation when provided
skills when provided
requirements when provided
```

When canonical material changes:

- canonical fields update;
- search document/vector refresh;
- monotonically numbered `JobVersion` is added;
- raw source payload is retained.

Source URL is updated independently on `JobSource`.

An ingestion result is `updated` only when canonical material changed; a source-only payload change is not falsely reported as a canonical update.

---

## Freshness Lifecycle

Current canonical statuses used by ingestion:

```text
ACTIVE
UNKNOWN
STALE
CLOSED
```

Rules:

```text
seen on healthy complete run
→ ACTIVE, miss_count=0, last_seen advances

missed after configurable threshold
→ UNKNOWN

missed across configurable stale threshold
→ STALE

confirmed unavailable by every linked source
→ CLOSED
```

Important safety properties:

- connector fetch failure does not increment misses;
- partial per-post ingestion failure does not apply negative board freshness;
- absence from one healthy board never immediately closes a job;
- canonical state is evaluated across all source links;
- one still-fresh linked source keeps a deduplicated canonical job ACTIVE;
- `CLOSED` requires explicit source evidence (`confirmed_closed`), not title matching or a single missing run.

Greenhouse list ingestion currently provides absence evidence but not a production source-confirmation mechanism that sets `confirmed_closed`; therefore CLOSED is represented safely but real provider-confirmed closure remains PARTIAL until that policy/integration exists.

---

## Ingestion Runs

Added `job_ingestion_runs` with:

```text
connector
source_company
started_at
completed_at
status
fetched
created
updated
unchanged
failed
stale
closed
```

A failed board fetch records a FAILED run and leaves existing job freshness unchanged.

A run with normalization/record failures is PARTIAL and does not apply negative freshness evidence.

Duration is derivable from timestamps but a dedicated duration metric is not persisted.

---

## Deduplication

Source identity and canonical dedup are separate.

Priority:

1. exact source identity;
2. exact application URL;
3. board-scoped Greenhouse `internal_job_id`;
4. same canonical company + normalized title + primary location + description fingerprint;
5. otherwise create a new canonical job.

The strict heuristic path stores:

```text
dedup_reason = COMPANY_TITLE_LOCATION_DESCRIPTION
dedup_confidence = 0.8500
```

It is not labeled perfect confidence.

Title alone is never a deduplication key.

---

## Search Consistency

PostgreSQL remains the only search engine.

Canonical ingestion refreshes one search document from:

```text
title
company
description
skills
requirements
```

and updates `search_vector` atomically within the database transaction.

A PostgreSQL trigger provides a lower-level fallback when title/description are mutated outside the ingestion service.

Regression source checks that a changed description becomes searchable.

---

## Search Relevance

Keyword search now uses:

```text
ts_rank_cd(search_vector, websearch_to_tsquery(...))
```

Ordering:

```text
lexical rank DESC
coalesce(posted_at, first_seen_at) DESC
job UUID DESC
```

Rank is cast to a stable numeric precision.

Cursor continuation keeps the existing `at + id` public cursor. For keyword search the query obtains the cursor row's rank inside PostgreSQL, then applies rank/recency/UUID keyset continuation.

Structured location/work-mode/compensation filters use `EXISTS` rather than multiplicative joins.

No semantic search, embeddings, pgvector, or OpenSearch was introduced.

---

## Application Pagination

`GET /api/v1/applications` now returns:

```text
items[]
next_cursor
returned
```

Keyset order:

```text
updated_at DESC
id DESC
```

Bound:

```text
1 <= limit <= 50
```

Each item includes only list data plus lightweight job title/company/location.

Events and private notes remain detail-only.

The web application uses infinite paging. Dashboard consumes the page contract through a separate cache key and no longer assumes the endpoint returns an unbounded array.

---

## Database Connection Configuration

SQLAlchemy now accepts environment-configurable:

```text
DATABASE_POOL_SIZE
DATABASE_MAX_OVERFLOW
DATABASE_POOL_TIMEOUT_SECONDS
DATABASE_POOL_RECYCLE_SECONDS
```

`pool_pre_ping` remains enabled.

RDS Proxy is intentionally not mandatory. It should be evaluated when horizontally scaled API/worker connection pressure, failover, or connection churn justify the extra managed layer.

---

## Clerk Provider Lifetime

Production Clerk auth no longer creates a new JWKS client for every request.

The provider is cached by:

```text
JWKS URL
issuer
audience
```

`PyJWKClient` key caching remains compatible with refresh on an unseen key ID, preserving key rotation behavior.

Development authentication remains fail-closed in staging/production.

---

## OpenAPI Client Consistency

Added deterministic commands:

```text
pnpm openapi:export
pnpm openapi:generate
pnpm openapi:check
```

The exporter serializes `FastAPI.app.openapi()` and `openapi-typescript` owns the generated TypeScript schema.

Because no executable Node+Python runner is currently available, the generated schema has not been regenerated for the current head. Temporary Milestone 2.6 client shapes therefore remain and this area is PARTIAL.

No claim is made that OpenAPI drift currently passes.

`openapi-fetch` remains installed from the existing dependency set; it is not newly adopted by Milestone 2.6. Dependency cleanup/use should occur together with a successful frozen-lockfile regeneration rather than manually desynchronizing `package.json` and `pnpm-lock.yaml` without execution.

---

## BFF Security

The Next.js backend route now:

- accepts only safe alphanumeric/underscore/hyphen path segments;
- rejects dot/traversal, encoded separators and query-like path content;
- constructs destinations only under `/api/v1`;
- caps proxied non-direct-upload bodies at 1 MiB using declared and actual size;
- forwards only required content/auth headers;
- does not log Authorization or candidate payloads.

Durable resume bytes no longer pass through the BFF.

---

## Regression Test Source Added/Expanded

### Resume

```text
master resume replacement/versioning
database one-master invariant
direct upload intent
no ResumeVersion before completion
candidate ownership on completion
size mismatch blocks completion
expired intent blocks completion
atomic ResumeVersion + outbox after completion
idempotent completion
queue outage preserves resume/outbox
published outbox not reclaimed
outbox idempotency-key uniqueness
parser redelivery idempotency
failed parsing retriable
confirmation completes extraction/version
profile provenance becomes USER_VERIFIED
PROCESSING worker message remains retryable
visibility heartbeat configuration validation
```

### Greenhouse

```text
board-scoped source identity
preserved internal/source metadata
same posting twice
first_seen preserved
last_seen advances
no duplicate raw/version on identical material
changed canonical propagation
new JobVersion on canonical change
search refresh
CompanySource mapping
strict multi-signal dedup
non-perfect heuristic confidence
board failure does not stale
UNKNOWN → STALE → ACTIVE
multi-source fresh link keeps canonical ACTIVE
```

### Applications / Search

```text
bounded application limit
invalid cursor rejection
lightweight list projection
no events/notes in list
frontend cursor loading
no list job-detail fan-out
PostgreSQL lexical rank ordering
deterministic ranked second page
```

### Frontend

```text
onboarding extraction restore after refresh
resume-derived confirmation path
manual profile path
failed resume manual fallback
resume QUEUED/PROCESSING/NEEDS_REVIEW/FAILED/COMPLETED UX
profile read/edit/structured role+skill save
settings real-state/privacy behavior
direct S3 upload client sequence
development proxy fallback
direct PUT failure handling
BFF path guard
existing job/application/saved behavior suites retained
```

### Auth / Migration

```text
Clerk provider/JWKS reuse
cache isolation by Clerk configuration
staging dev-auth prohibition
Alembic head includes durability/upload tables
resume integrity indexes
application/outbox/source-link query indexes
```

---

# Verification Failure Report

## BLOCKER

### What failed

Current-head automated verification cannot be executed in the available environment.

Prior observable PR behavior showed all six GitHub Actions jobs created and then terminated without executable steps or job logs.

### Evidence available

The workflow definition contains independent:

```text
Web lint
Web typecheck
Web tests
Web production build
API migration validation
API tests
```

The available GitHub repository connector supports source/PR operations, but does not expose Actions account/repository configuration for hosted-runner policy, minutes, budget/spending, or organization policy.

The alternate execution sandbox cannot clone `github.com`, so it cannot serve as a clean checkout runner.

### Root cause

**Unknown external execution/configuration condition.**

It would be dishonest to label the cause as Actions disabled, minutes exhausted, budget exhausted, or policy denial without access to those controls/logs.

### What was attempted

- inspected the CI workflow rather than rewriting it;
- confirmed the workflow already defines separated observable jobs;
- inspected repository permissions available through the connector;
- continued source/test correctness work independently, as required by Milestone 2.6;
- added reproducible OpenAPI export/check commands for when execution returns.

### What remains

Run the exact current branch head in an environment that can execute:

```text
pnpm install --frozen-lockfile
pnpm lint
pnpm --dir apps/web typecheck
pnpm test:web
pnpm build
pnpm openapi:check

cd services/api
uv sync --group dev --locked
alembic upgrade head
alembic current
alembic check
pytest
```

Then fix actual errors from real output.

### External dependency

Access to a functioning GitHub-hosted/self-hosted runner or another clean checkout environment, plus visibility into any account/repository Actions restrictions if GitHub continues failing before steps.

---

## Required Test Report

No historical numbers are reused.

```text
Backend:
BLOCKED — current head not executed

Frontend:
BLOCKED — current head not executed

Playwright:
BLOCKED — deterministic executable environment unavailable

Build:
BLOCKED — current head not executed

Lint:
BLOCKED — current head not executed

Typecheck:
BLOCKED — current head not executed

Alembic upgrade/check:
BLOCKED — current head not executed

OpenAPI drift:
BLOCKED — current head not executed
```

---

## Current Status

```text
Candidate MVP:                 PARTIAL
Authentication:                PARTIAL
Resume Upload Architecture:    PARTIAL
Resume Pipeline:               PARTIAL
Resume Versioning:             PARTIAL
Transactional Outbox:          PARTIAL
Worker Idempotency:            PARTIAL
Worker Visibility/Lease:       PARTIAL
Profile:                       PARTIAL
Job Search:                    PARTIAL
Saved Jobs:                    PARTIAL
Applications:                  PARTIAL
Greenhouse Ingestion:          PARTIAL
Company Resolution:            PARTIAL
Source Identity:               PARTIAL
Deduplication:                 PARTIAL
Changed-Job Propagation:       PARTIAL
Freshness:                     PARTIAL
Search Consistency:            PARTIAL
Search Relevance:              PARTIAL
Frontend Testing:              PARTIAL
Backend Testing:               BLOCKED
OpenAPI Consistency:           PARTIAL
Playwright:                    BLOCKED
S3:                            PARTIAL
SQS:                           PARTIAL
Worker:                        PARTIAL
CI Definition:                 COMPLETE
CI Execution:                  BLOCKED
Staging Deployment:            BLOCKED
Production Deployment:         BLOCKED

AI Matching:                   NOT STARTED
Mobile:                        NOT STARTED
Employer Platform:             NOT STARTED
Billing:                       NOT STARTED
```

---

## Known Issues / Follow-up Before Staging

1. Execute all current-head checks and resolve concrete failures.
2. Regenerate OpenAPI TypeScript and remove temporary manual M2.6 client declarations.
3. Prove S3 direct PUT/CORS/object metadata against the real private staging bucket.
4. Deploy/verify the outbox publisher independently from API/worker.
5. Configure and prove SQS visibility, heartbeat, maxReceiveCount and DLQ redrive.
6. Decide and implement an explicit Greenhouse/provider confirmation path before using CLOSED automatically; absence alone remains UNKNOWN/STALE.
7. Run concurrency stress for simultaneous master-resume completions and ingestion/version creation.
8. Establish a hard parser-timeout strategy if operational evidence shows document parsing can exceed acceptable worker limits.
9. Run real Clerk two-user IDOR/isolation verification.
10. Run measured SQL/API request-count review, security, accessibility, and responsive QA.
11. Implement/run Playwright Candidate journey only once deterministic execution is available.

---

## Staging Gate

Staging deployment remains intentionally blocked.

Do not deploy merely because source code exists. The gate requires executed evidence for:

```text
lint
typecheck
frontend tests
production build
Alembic upgrade/check
backend tests
OpenAPI drift
```

Then staging must prove:

```text
real Clerk
real PostgreSQL
private S3 direct upload
TaskOutbox publisher
real SQS
resume worker + visibility heartbeat
retry + DLQ
Greenhouse ingest/search
candidate persistence journey
```

Only after those checks may the Candidate MVP move toward `STAGING VERIFIED`.

Milestone 3 / AI matching remains blocked by design until this durability gate is verified.
