# Local Clean-room Certification

Updated: 2026-08-07

ApplyAI has a repository-owned clean-room gate for proving that a fresh checkout can install, migrate, seed, launch and exercise the non-deployment product without relying on hidden developer state.

## One command

From the repository root:

```bash
pnpm local:certify
```

The same command is executed by `.github/workflows/local-cleanroom.yml` on a fresh GitHub-hosted Ubuntu runner. A green workflow therefore proves that the repository can bootstrap from a pristine checkout under the documented prerequisites; it is not a guarantee about every possible host OS, Docker Desktop version, firewall, proxy or corporate endpoint policy on an individual workstation.

## Prerequisites

The command fails early if a required tool is missing.

```text
Docker + running Docker daemon
Node.js 22+
pnpm 10.x
Python 3.12+
uv
curl
```

The repository lockfiles remain authoritative. The certification performs locked dependency installation rather than relying on an existing `node_modules` or Python environment.

## Local services

The clean-room stack intentionally uses production-shaped local dependencies where that improves integration fidelity:

| Service | Local implementation | Port(s) | Purpose |
|---|---|---:|---|
| PostgreSQL | PostgreSQL 17 | 55432 | canonical application database |
| S3 + SQS | LocalStack 4.14 | 4566 | boto3 object storage, presigned PUTs, queues and DLQs |
| Email | Mailpit 1.30.6 | 1025 / 8025 | SMTP delivery plus captured-message inspection |
| Stripe schema sanity | official stripe-mock 0.202.0 | 12111 / 12112 | provider service/schema sanity only |
| Clerk/OpenAI/Stripe behavioral protocols | ApplyAI local provider mock | 8099 | RS256/JWKS, Responses/embeddings and stateful billing response fields used by ApplyAI |
| FastAPI | ApplyAI API | 8000 | application API during browser acceptance |
| Next.js | ApplyAI web | 3000 | browser product during acceptance |

The clean-room database name is always `applyai_cleanroom`. The script terminates connections to, drops and recreates **that database only**. It does not drop the normal `applyai` database.

Generated runtime values and diagnostic logs live under `.local/`, which is gitignored.

## Certification sequence

`pnpm local:certify` performs the following from a fresh repository state:

1. checks required local tools and minimum runtimes;
2. installs JavaScript dependencies with `pnpm install --frozen-lockfile`;
3. installs Python dependencies with locked `uv` resolution;
4. starts PostgreSQL, LocalStack, Mailpit and the official Stripe schema mock;
5. recreates `applyai_cleanroom`;
6. creates the LocalStack resume bucket, CORS policy, resume/source/AI queues and DLQs;
7. applies Alembic zero-to-head and verifies migration metadata drift;
8. runs the normal API suite in its isolated test configuration;
9. runs web lint, typecheck, unit/source tests, production build and OpenAPI drift;
10. recreates the clean-room database again so test-state cannot make product acceptance pass accidentally;
11. starts the local Clerk/OpenAI/Stripe behavioral protocol server;
12. reapplies migrations and seeds deterministic jobs;
13. creates a deterministic resume fixture;
14. executes local integration smoke checks;
15. starts the transactional outbox plus resume, source and AI workers;
16. installs Chromium if needed;
17. runs the complete Playwright clean-room suite against Next.js + FastAPI + PostgreSQL + LocalStack;
18. verifies the local provider server and all background processes remain alive after browser execution;
19. stops local certification services unless `KEEP_LOCAL_CERT_ENV=1` is set.

## Integration checks

### S3

The smoke gate uses the real `S3ObjectStorageProvider` with boto3 against LocalStack and proves:

- object PUT;
- HEAD metadata;
- GET content;
- DELETE;
- path-style local endpoint support;
- presigned PUT generation;
- HTTP upload through the presigned URL with server-side-encryption headers.

The browser journey then uses the S3-backed resume path rather than the local-file storage substitute.

### SQS, outbox and workers

The gate uses the real `SqsTaskQueue` and boto3 clients against LocalStack and proves send/receive/delete behavior. It also starts the normal:

```text
transactional outbox publisher
resume worker
source worker
AI worker
```

Queue families have separate local queues and DLQs. The worker processes must still be alive after the browser suite completes.

### Email

`EMAIL_PROVIDER=smtp` points the real ApplyAI email provider boundary at Mailpit. The smoke gate sends a message through SMTP and verifies it appears through the Mailpit message API. Engagement dispatch also respects candidate email preferences.

### Clerk authentication protocol

The local provider server generates an ephemeral RSA key pair, serves a Clerk-shaped JWKS endpoint and issues a short-lived RS256 JWT. The smoke gate passes that token through the real `ClerkAuthProvider`, including issuer/JWKS/signature verification and claim extraction.

The browser journey intentionally uses ApplyAI's controlled development sign-in so it remains account-free and deterministic. The protocol smoke separately proves the production Clerk verification code path without claiming a real Clerk tenant was contacted.

### OpenAI protocol

The local provider server exposes Responses and embeddings endpoints. The smoke gate uses the real:

```text
OpenAIResponsesProvider
OpenAIEmbeddingProvider
```

and proves authorization headers, structured request/response handling, JSON output parsing, usage parsing and embedding-vector consumption. The normal browser clean-room journey keeps `AI_PROVIDER=deterministic` so it cannot spend tokens or depend on an external network.

This proves ApplyAI's OpenAI client/protocol integration against a controlled local double. It does **not** prove the behavior, availability, latency, token accounting or quality of a live OpenAI model.

### Stripe protocol

ApplyAI retains the official `stripe-mock` container as a basic provider/schema sanity dependency. Because that project is intentionally stateless, the behavioral local server supplies the small set of stateful response fields ApplyAI consumes for Checkout and Billing Portal sessions.

The smoke gate proves:

- checkout request construction;
- checkout-session response handling;
- signed webhook verification;
- persisted subscription transition to `PRO` / `STRIPE`;
- billing-ledger write path;
- Billing Portal request/response handling.

No real charge, customer or Stripe account is created.

## Browser coverage

The clean-room Playwright suite includes the full candidate persistence/isolation journey plus the product-completion journeys and a strict canonical-route sweep.

The sweep requires the requested route to remain the final pathname; a hidden redirect to onboarding or another fallback therefore fails the certificate.

Covered surfaces include:

```text
/
/pricing
/dashboard
/jobs
/jobs/[id]
/matches
/saved
/applications
/applications/[id]
/resume
/resume/studio
/career
/network
/analytics
/alerts
/billing
/profile
/settings
/import-job
/interview/[jobId]
/employer
/admin
```

Historical `/demo` and `/beta` entry points are also checked for their intended redirects into the canonical product.

## Diagnostics and keeping services running

On a local failure, inspect:

```text
.local/provider-mock.log
.local/outbox.log
.local/resume-worker.log
.local/source-worker.log
.local/ai-worker.log
apps/web/playwright-report/
apps/web/test-results/
```

To leave the Docker dependencies running after the command exits:

```bash
KEEP_LOCAL_CERT_ENV=1 pnpm local:certify
```

The application/provider processes started directly by the script are still terminated at script exit; the environment flag keeps the Docker dependencies available for manual inspection.

## What a green certificate proves

A green clean-room workflow proves, for the exact commit tested:

- a pristine checkout can install from repository lockfiles;
- database creation and zero-to-head migrations work without preexisting application state;
- the normal repository test/build/OpenAPI gates remain green;
- deterministic seeding works after a second clean database reset;
- production-shaped local S3/SQS/SMTP paths work;
- outbox and worker processes start and survive browser execution;
- Clerk JWT/JWKS verification code works against a protocol-faithful local issuer;
- OpenAI Responses and embeddings client code works against a protocol-faithful local endpoint;
- Stripe checkout/portal client handling and signed webhook persistence work against controlled local endpoints;
- canonical candidate/employer/operator web surfaces execute through real Next.js, FastAPI and PostgreSQL locally.

## What it deliberately does not prove

A green local certificate is **not** evidence that any external provider account or deployment has succeeded. These remain separate live acceptance gates:

```text
real Clerk tenant/session lifecycle
live OpenAI model and embedding behavior
real Stripe test/live account behavior
real AWS S3/SQS/ECS/Aurora networking and IAM
real SMTP/email or push provider delivery
Vercel/AWS deployment
mobile/browser-store signing and publication
```

Those gates require actual credentials/accounts and must never be inferred from emulator or protocol-mock success.

It also cannot guarantee an arbitrary developer laptop has no host-specific issue. On a machine that satisfies the prerequisites, `pnpm local:certify` is the authoritative local diagnostic: a failure is a real local certification failure to investigate rather than something the documentation should hide.
