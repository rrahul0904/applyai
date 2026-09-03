# Current Repository State

Updated: 2026-08-31

## Source control

- Repository: `rrahul0904/applyai`
- Default branch: `main`
- Current integrated main before Lean Production: `10d64358e7faa4328ca1f0765e3f224e23fa0321`
- Merged product stack: PR #22 Career System, #23 Recruiter Lens, #24 Resume Share Intelligence, #25 Candidate Entry, #26 Production Activation.
- Final lean-production release vehicle: PR #27, branch `agent/lean-production-wave-1`, base `main`.
- PR #27 remains draft until real Preview acceptance passes.

The first production launch architecture is now:

```text
Vercel / Next.js + Clerk
        ↓
Railway / FastAPI
        ↓
Railway PostgreSQL
        ├─ canonical product data
        └─ TaskOutbox → postgres_tasks → Railway worker

Cloudflare R2 → private résumé/document objects
```

AWS remains source-controlled and validated as an optional scale/enterprise profile. It is not a launch prerequisite.

## Candidate product

Canonical authenticated candidate routes include:

```text
/dashboard
/matches
/jobs
/jobs/[id]
/saved
/applications
/applications/[id]
/resume
/resume/studio
/resume/signals
/career
/interview/[jobId]
/network
/analytics
/alerts
/profile
/billing
/settings
/import-job
```

Core candidate capabilities now include:

- Clerk-backed identity mapping and owner-scoped APIs;
- branded sign-in/sign-up and onboarding;
- Career Memory and candidate-reviewed profile evidence;
- private résumé upload, parsing, review and versioning;
- Resume Studio and job-specific variants;
- real-source capable PostgreSQL job search, filters and saved jobs;
- explainable deterministic Career Intelligence;
- candidate-side Recruiter Lens with `SUPPORTED`, `PARTIAL` and `NOT_EVIDENCED` criteria;
- unified Career System per job;
- application command center;
- candidate-approved external submission boundary;
- evidence-bound application/interview copilots;
- recruiter/referral outreach and follow-up;
- privacy-preserving Resume Share Intelligence;
- notification inbox and candidate analytics;
- account export and application-side deletion.

The first-value dashboard is organized around:

```text
Next Best Action
Jobs For You
Career Readiness
Active Opportunities
```

Readiness and Recruiter Lens are candidate preparation signals, not employer scores or hiring probabilities.

## Career Intelligence and AI

Career Intelligence V1 remains the deterministic, explainable baseline. Durable V2 uses:

```text
verified candidate/job evidence
        ↓
AIJobRun + transactional outbox
        ↓
durable queue
        ↓
worker → reviewed model provider
        ↓
strict schema + evidence-reference validation
        ↓
versioned artifact + candidate review
```

Lean production routes durable work through PostgreSQL. The optional AWS profile can continue routing the same task families through SQS.

Supported AI task families include deep match, résumé tailoring, application copilot and interview preparation. AI is not allowed to invent candidate facts.

## Lean durable queue

PR #27 adds the production Postgres worker path:

```text
TaskOutbox
    ↓
postgres_tasks
    ↓
Railway worker
```

Queue semantics include:

- unique idempotency keys;
- `FOR UPDATE SKIP LOCKED` claims;
- concurrent worker safety;
- lease owner/expiry and heartbeat;
- expired-lease recovery;
- bounded exponential retry;
- `RETRY_WAIT` and `DEAD` states;
- cancellation;
- explicit task-family routing;
- unknown task types fail closed and visibly.

Production task families are résumé, source ingestion, AI and agent runtime.

## Resume storage and Resume Share Intelligence

Lean production uses Cloudflare R2 through the existing S3-compatible storage adapter. The bucket is required to remain private; R2 credentials are server-side only and direct-upload response headers are provider-owned.

AWS S3 retains `AES256` support. R2 uses `S3_SERVER_SIDE_ENCRYPTION=none` because the AWS-specific PutObject SSE header is not used for the R2 mode.

Resume Share Intelligence remains privacy preserving:

- no raw IP persistence;
- no cross-link browser fingerprinting;
- no inferred company identity from IP;
- engagement is not hiring probability;
- first human view creates one `RESUME_SHARE_VIEWED` notification;
- first observed return creates one `RESUME_SHARE_RETURNED` notification;
- later repeat views remain analytics-only rather than generating notification spam.

## Job-data platform

Implemented source support includes:

- ApplyAI first-party jobs;
- Greenhouse;
- Lever;
- Ashby;
- SmartRecruiters;
- USAJOBS where credentials are configured;
- ReliefWeb where configuration is available;
- bounded permitted employer career-page/JSON-LD import;
- authorized/licensed feeds;
- Open Jobs public CC0 discovery coverage.

Open Jobs uses bounded manifest/group ingestion and is deliberately lower authority than employer-origin sources. It does not get absence-based closure authority.

The real-network Open Jobs source was previously acceptance-tested. Real canonical production job counts still require a live production PostgreSQL database/source worker run.

Initial production inventory is gated by:

```bash
pnpm job-supply:initial-acceptance
```

The mature multi-source gate remains:

```bash
pnpm job-supply:acceptance
```

and is not weakened for launch.

## Deployment profiles

### Lean launch

```text
DEPLOYMENT_PROFILE=lean
DATABASE_URL=<Railway Postgres>
TASK_QUEUE_PROVIDER=postgres
OBJECT_STORAGE_PROVIDER=s3
S3_ENDPOINT_URL=<Cloudflare R2 endpoint>
AUTH_PROVIDER=clerk
WEB_ORIGIN=<Vercel production origin>
```

### Optional AWS scale profile

The repository continues to contain and validate:

```text
VPC / private networking
ALB
ECS/Fargate
Aurora PostgreSQL Serverless v2
ECR
private S3
resume/source/AI/agent SQS queues and DLQs
EventBridge source dispatch
CloudWatch
Terraform + bootstrap CloudFormation
```

No AWS credential is required to start the lean API/worker path.

## Repository validation

The final release gate includes:

```text
Web lint / typecheck / unit tests / Next.js production build
API tests
Alembic zero-to-head + zero metadata drift
OpenAPI generated-client drift
API production container
Candidate Playwright journey
Local clean-room certification
Lean Production Validation
Postgres queue concurrency / lease / retry / cancellation tests
R2/AWS storage compatibility tests
Open Jobs live-source acceptance
Job Search Scale Benchmark
Job Supply Scheduler Scale Benchmark
Agent runtime tests / scale benchmark
Demo capture
GitHub workflow validation
AWS Terraform/bootstrap validation
```

Exact-head evidence is required after every source-changing commit.

## Current live-provider boundary

Repository-side launch support is implemented, but the currently connected tool environment does not expose authorized Railway, Cloudflare R2 or Clerk integrations/credentials.

The connected Vercel team also does not yet contain a dedicated `applyai` project. The repository Preview workflow is ready to create/configure it, but its preflight has confirmed these required GitHub Actions values are currently absent:

```text
VERCEL_TOKEN
APPLYAI_VERCEL_API_URL
APPLYAI_VERCEL_CLERK_PUBLISHABLE_KEY
APPLYAI_VERCEL_CLERK_SECRET_KEY
```

Accordingly, the following remain `BLOCKED_EXTERNAL_CONFIGURATION` rather than falsely marked live:

```text
Railway project/PostgreSQL/API/worker
Cloudflare R2 private bucket + live acceptance
Clerk real signup/signin/JWT acceptance
Vercel ApplyAI Preview
real Open Jobs insertion into production PostgreSQL
complete real Preview candidate journey
PR #27 merge / final production deployment
```

See:

- `DEPLOYMENT.md`
- `docs/RAILWAY_DEPLOYMENT.md`
- `docs/R2_STORAGE.md`
- `docs/PRODUCTION_RELEASE_CHECKLIST.md`
- `docs/PRODUCTION_RUNBOOK.md`

`LIVE_PRODUCTION_VERIFIED` is allowed only after the complete persistent candidate journey passes against real Production infrastructure.
