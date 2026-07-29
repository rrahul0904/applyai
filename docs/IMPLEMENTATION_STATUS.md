# Implementation Status

Updated: 2026-07-28

Statuses are restricted to COMPLETE, PARTIAL, NOT STARTED, and BLOCKED.

| Capability | Status | Evidence | Missing | Tests / verification |
|---|---|---|---|---|
| Repository architecture correction | COMPLETE | Official Next.js App Router web application; FastAPI service; PostgreSQL/Alembic architecture preserved | None for architecture-correction scope | Previously reported production web build |
| Source-control safety | COMPLETE | `docs/CURRENT_REPOSITORY_STATE.md`; changes continued on existing PR branch; no destructive cleanup | Local-only untracked state is outside remote repository visibility | Repository audit documented |
| Canonical PostgreSQL model | COMPLETE | Existing SQLAlchemy/Alembic foundation covers candidate, resume, job/source, saved job, application, event, and notes domains | Future fields require explicit migrations | Existing migration tests |
| Database migrations | COMPLETE | Two Alembic revisions with downgrade paths; current Candidate MVP changes require no schema change | Production release automation | CI migration job defined; GitHub runner currently fails before exposing steps/logs |
| Clerk authentication code | PARTIAL | Next Clerk integration; FastAPI RS256/JWKS verifier; internal Clerk subject → UUID mapping; guarded dev auth | Real Clerk production configuration and live integration verification | Existing auth-provider tests; live Clerk test pending |
| Candidate authorization | COMPLETE | Owner-scoped profile, resume, saved-job, application, and note access | Integration verification with live Clerk | Existing cross-user API tests |
| Candidate profile | PARTIAL | Authenticated GET/PUT; experience, education, skills, target roles, location/work mode, compensation; new `/profile` editor | Build/browser verification; certifications/projects remain absent because schema does not support them | Existing backend profile tests; frontend tests pending |
| Candidate onboarding | PARTIAL | Persisted stage machine; optional resume path; resume-processing state; profile review; target roles; location; work preferences; compensation; review; backend completion eligibility | Playwright acceptance test and production auth verification | New backend onboarding tests committed; CI execution blocked |
| Object storage | PARTIAL | Local and S3 providers; private opaque key structure; binary resume content excluded from PostgreSQL | Production bucket/IAM/signed access integration; malware scanning | In-memory storage exercised in backend tests |
| Resume upload | PARTIAL | PDF/DOCX validation, size/empty checks, storage persistence, queue event, new `/resume` UI | Production S3 integration; deliberate master-resume versioning behavior | Existing resume authorization/upload tests; browser test pending |
| Resume parsing | PARTIAL | Deterministic PDF/DOCX extraction; review/failure states; production SQS requirement; dedicated SQS worker; API only runs inline parser in memory-queue development mode | Deploy worker, configure SQS redrive/DLQ, integration-test retries and idempotency | Worker/config guardrail tests committed; CI execution blocked |
| Canonical job model | COMPLETE | Companies, aliases, sources, raw postings, canonical jobs, locations, compensation, skills, versions/status | Production ingestion behavior | Existing schema/migration coverage |
| Connector contract | COMPLETE | Connector/provider boundary and deterministic development connector exist | None for interface scope | Connector code coverage expanding |
| Real job ingestion | PARTIAL | Public Greenhouse Job Board connector, deterministic normalization, raw provenance, board health, configured ingestion runner | Production scheduling, company-resolution improvements, cross-source deduplication, explicit freshness/stale lifecycle | Greenhouse MockTransport tests committed; CI execution blocked |
| Job search API | PARTIAL | PostgreSQL provider, structured filters, URL-backed web filters, bounded cursor pagination | Query-plan/performance validation; eliminate N+1 assembly | Existing job API tests; performance tests pending |
| Job detail | PARTIAL | Canonical API plus new `/jobs/[id]` UI with provenance, requirements, skills, save, and application action | Build/browser verification | API coverage exists; frontend test pending |
| Saved jobs | PARTIAL | Save/list/unsave with composite ownership; new `/saved` UI | Browser persistence/E2E verification | Existing API coverage; frontend test pending |
| Applications | PARTIAL | Create/list/detail/status; duplicate prevention; immutable events; notes CRUD; new list/detail workspace | Remove list job-detail fan-out; browser persistence/E2E verification | Existing backend application tests; frontend test pending |
| Candidate settings | PARTIAL | New `/settings` route exposes only real account/profile/preferences/privacy state | Notification settings remain hidden until implemented | Frontend verification pending |
| Candidate web | PARTIAL | Landing/auth entry, shell, dashboard, onboarding, jobs, detail, saved, applications, resume, profile, settings | Successful build/lint on latest head, browser acceptance, accessibility pass | CI definition committed; runner currently fails before steps/logs are available |
| End-to-end vertical slice | PARTIAL | Required source-controlled screens/APIs now exist; production queue/worker boundary implemented | Playwright journey; live Clerk/S3/SQS integration | Playwright NOT STARTED |
| Search provider | PARTIAL | PostgreSQL provider with structured filters and canonical job query | Measured FTS relevance/performance; production job corpus | Job search API tests only |
| CI | BLOCKED | `.github/workflows/ci.yml` defines web lint/build plus PostgreSQL migrations/backend tests; workflow runs are created | GitHub Actions jobs currently terminate as failure before exposing steps or logs, so application verification cannot be claimed | Latest observed run failed at runner/execution layer with no available job steps/log blob |
| Matching | NOT STARTED | Architecture documented only | All matching implementation and evaluation | None |
| AI tools | NOT STARTED | Safety/task architecture documented | Implementation intentionally deferred | None |
| Mobile | NOT STARTED | UX/platform plan documented | Expo application | None |
| Employer product | NOT STARTED | Organization schema only | All workflows | None |
| Admin product | NOT STARTED | No implementation | All workflows | None |
| Production infrastructure | PARTIAL | Local PostgreSQL, S3 provider, real SQS provider selection, dedicated resume worker, Vercel/AWS deployment plan, CI definition | Staging/prod resources, IAM, SQS/DLQ, ECS worker/API deployment, monitoring, secrets | Deployment verification pending |

## Candidate MVP status

**PARTIAL**

The candidate-facing source code covers the intended MVP workflow and the production resume execution boundary is now implemented in code. The milestone cannot be marked COMPLETE until the latest web build/lint, backend tests/migrations, Playwright persistence journey, accessibility validation, live authentication/storage/queue integration, and production deployment checks are verified.
