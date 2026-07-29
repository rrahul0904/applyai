# Implementation Status

Updated: 2026-07-29

Statuses are restricted to COMPLETE, PARTIAL, NOT STARTED, and BLOCKED.

| Capability | Status | Evidence | Missing | Tests / verification |
|---|---|---|---|---|
| Repository architecture correction | COMPLETE | Official Next.js App Router web application; FastAPI service; PostgreSQL/Alembic architecture preserved | None for architecture-correction scope | Architecture audit documented |
| Source-control safety | COMPLETE | `docs/CURRENT_REPOSITORY_STATE.md`; changes continued on existing PR branch; no destructive cleanup | Local-only untracked state is outside remote repository visibility | Repository audit documented |
| Canonical PostgreSQL model | COMPLETE | Existing SQLAlchemy/Alembic foundation covers candidate, resume, job/source, saved job, application, event, and notes domains | Future fields require explicit migrations | Existing migration tests are source-controlled; current-head execution is blocked |
| Database migrations | COMPLETE | Two Alembic revisions with downgrade paths; current Candidate MVP changes require no schema change | Production release automation | CI now has an independent PostgreSQL 17 migration-validation job; runner fails before steps execute |
| Clerk authentication code | PARTIAL | Next Clerk integration; FastAPI RS256/JWKS verifier; internal Clerk subject → UUID mapping; guarded dev auth; staging/production fail closed without Clerk config | Real Clerk staging configuration and live integration verification | Existing auth-provider tests; live Clerk test pending |
| Candidate authorization | COMPLETE | Owner-scoped profile, resume, saved-job, application, and note access | Live Clerk integration verification | Existing cross-user API tests |
| Candidate profile | PARTIAL | Authenticated GET/PUT; experience, education, skills, target roles, location/work mode, compensation; `/profile` editor | Current-head browser verification; certifications/projects remain absent because schema does not support them | Backend coverage exists; profile frontend behavior coverage still pending |
| Candidate onboarding | PARTIAL | Persisted stage machine; optional resume path; resume-processing state; profile review; target roles; location; work preferences; compensation; review; backend completion eligibility | Playwright acceptance test and real Clerk staging verification | Backend onboarding tests committed; current-head execution blocked |
| Object storage | PARTIAL | Local and S3 providers; private opaque key structure; server-side AES256 upload; staging/production now require S3 configuration | Real staging bucket/IAM integration, object privacy proof, transaction cleanup validation, malware scanning decision | In-memory provider used in backend tests; AWS integration pending |
| Resume upload | PARTIAL | PDF/DOCX validation, size/empty checks, storage persistence, queue event, `/resume` UI | Real S3 integration; deliberate master-resume versioning behavior | Existing API coverage; browser test pending |
| Resume parsing | PARTIAL | Deterministic PDF/DOCX extraction; review/failure states; production SQS requirement; dedicated SQS worker; API only runs inline parser in memory-queue development mode | Deploy worker, configure SQS redrive/DLQ, integration-test retry/idempotency | Worker/config guardrail tests committed; current-head execution blocked |
| Canonical job model | COMPLETE | Companies, aliases, company sources, job sources, raw postings, canonical jobs, locations, compensation, skills, versions/status | Production ingestion behavior | Existing schema/migration coverage |
| Connector contract | COMPLETE | Connector/provider boundary and deterministic development connector exist | None for interface scope | Connector code coverage expanding |
| Real job ingestion | PARTIAL | Public Greenhouse Job Board connector, deterministic normalization, raw provenance, board health, configured ingestion runner | Company-source resolution hardening, multi-signal deduplication, repeated-ingestion freshness lifecycle, scheduling, staging verification | Greenhouse MockTransport tests committed; current-head execution blocked |
| Job search API | PARTIAL | PostgreSQL provider, structured filters, URL-backed web filters, bounded cursor pagination; company/location/compensation list assembly is now batch-loaded rather than per-job | Query-plan/request-count validation, relevance measurement, production corpus validation | Existing API tests; performance execution pending |
| Job detail | PARTIAL | Canonical API plus `/jobs/[id]` UI with provenance, requirements, skills, save, and application action | Current-head browser verification | New job-detail behavior tests committed but not executed by available runner |
| Saved jobs | PARTIAL | Save/list/unsave with composite ownership; `/saved` UI; related job rows batch-loaded; list is explicitly bounded | Full pagination strategy and logout/login persistence E2E | New saved-jobs behavior tests committed but not executed by available runner |
| Applications | PARTIAL | Create/detail/status; duplicate prevention; immutable events; notes CRUD; list now returns a lightweight job summary projection; frontend job-detail fan-out removed | Browser persistence/E2E verification and measured query/request counts | Backend summary/isolation regression coverage plus frontend list/detail/status/note tests committed; runner blocked |
| Candidate settings | PARTIAL | `/settings` exposes only real account/profile/preferences/privacy state | Notification settings intentionally remain hidden until implemented; browser verification pending | Frontend verification pending |
| Candidate web | PARTIAL | Landing/auth entry, shell, dashboard, onboarding, jobs, detail, saved, applications, resume, profile, settings | Successful current-head lint/typecheck/tests/build, full browser acceptance, accessibility pass | CI definition committed; runner fails before steps/logs are available |
| Frontend behavior testing | PARTIAL | Vitest configured; tests now cover job detail/save/apply, applications list projection, application timeline/status/notes, and saved jobs | Onboarding, resume states, manual fallback, profile editor, settings, broader error/retry coverage | Test execution BLOCKED by runner/local-network environment |
| End-to-end vertical slice | PARTIAL | Required source-controlled screens/APIs exist; production queue/worker boundary implemented | Playwright journey; live Clerk/S3/SQS integration | Playwright NOT STARTED |
| Playwright Candidate MVP | NOT STARTED | Playwright dependency is present | Deterministic auth + full logout/login persistence journey | None |
| Search provider | PARTIAL | PostgreSQL provider with structured filters and canonical job query | Measured FTS relevance/performance; production job corpus | Job search API tests only |
| API health/readiness | COMPLETE | `/health` provides liveness; `/ready` performs a database dependency probe without exposing internals | Staging deployment proof | Health/readiness regression test committed; current-head execution blocked |
| Runtime configuration safety | COMPLETE | Credentialed CORS rejects wildcard origin; staging/production require HTTPS web origin, Clerk, S3, and SQS; production dev auth remains prohibited | Real environment values intentionally external | Configuration guardrail tests committed; current-head execution blocked |
| CI | BLOCKED | Six independent jobs now exist: web lint, typecheck, tests, build, API migrations, API tests; versions pinned; PostgreSQL 17; safe pnpm/uv caching | GitHub Actions runner/account execution must start jobs and expose steps/logs | Latest observed run `30420175430` completed failure with `steps=None` and no logs for all six jobs |
| Staging deployment | BLOCKED | Fail-closed staging configuration and target architecture are source-controlled | Real Vercel/AWS/Clerk resources, credentials, DNS/origins, S3, SQS/DLQ, ECS API/worker, Aurora/PostgreSQL | No staging smoke test can be claimed |
| Matching | NOT STARTED | Architecture documented only | All matching implementation and evaluation | None |
| AI tools | NOT STARTED | Safety/task architecture documented | Implementation intentionally deferred | None |
| Mobile | NOT STARTED | UX/platform plan documented | Native application intentionally outside current milestone | None |
| Employer product | NOT STARTED | Organization schema only | All workflows | None |
| Admin product | NOT STARTED | No implementation | All workflows | None |
| Production infrastructure | PARTIAL | S3 provider, real SQS provider selection, dedicated resume worker, explicit readiness, fail-closed durable-environment configuration, Vercel/AWS deployment plan | Production resources, IAM, SQS/DLQ, ECS worker/API deployment, monitoring, secrets, backups, alerts, approval | Deployment verification pending |

## Candidate MVP status

**PARTIAL**

The candidate-facing source code now covers the intended MVP workflow, frontend behavior testing has begun, the application/job list fan-out and N+1 hot paths have been reduced, and staging configuration fails closed instead of silently using development providers. The milestone cannot be marked COMPLETE until the current head actually passes lint, typecheck, frontend tests, backend tests, Alembic validation, production build, Playwright, live Clerk/S3/SQS/worker validation, accessibility/security checks, and a real staging smoke test.
