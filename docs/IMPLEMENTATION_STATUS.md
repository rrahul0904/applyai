# Implementation Status

Updated: 2026-07-28

Statuses are restricted to COMPLETE, PARTIAL, NOT STARTED, and BLOCKED.

| Capability | Status | Evidence | Missing | Tests / verification |
|---|---|---|---|---|
| Repository architecture correction | COMPLETE | Official Next.js App Router web application; FastAPI service; PostgreSQL/Alembic architecture preserved | None for architecture-correction scope | Previously reported production web build |
| Source-control safety | COMPLETE | `docs/CURRENT_REPOSITORY_STATE.md`; changes continued on existing PR branch; no destructive cleanup | Local-only untracked state is outside remote repository visibility | Repository audit documented |
| Canonical PostgreSQL model | COMPLETE | Existing SQLAlchemy/Alembic foundation covers candidate, resume, job/source, saved job, application, event, and notes domains | Future fields require explicit migrations | Existing migration tests |
| Database migrations | COMPLETE | Two Alembic revisions with downgrade paths; Candidate MVP UI changes require no schema change | Production release automation | CI migration validation added; latest run pending |
| Clerk authentication code | PARTIAL | Next Clerk integration; FastAPI RS256/JWKS verifier; internal Clerk subject → UUID mapping; guarded dev auth | Real Clerk production configuration and live integration verification | Existing auth-provider tests; live Clerk test pending |
| Candidate authorization | COMPLETE | Owner-scoped profile, resume, saved-job, application, and note access | Integration verification with live Clerk | Existing cross-user API tests |
| Candidate profile | PARTIAL | Authenticated GET/PUT; experience, education, skills, target roles, location/work mode, compensation; new `/profile` editor | Build/browser verification; certifications/projects remain absent because schema does not support them | Existing backend profile tests; frontend tests pending |
| Candidate onboarding | PARTIAL | Persisted stage machine; optional resume path; resume-processing state; profile review; target roles; location; work preferences; compensation; review; backend completion eligibility | Playwright acceptance test and production auth verification | New backend onboarding tests committed; CI result pending |
| Object storage | PARTIAL | Local and S3 providers; private opaque key structure; binary resume content excluded from PostgreSQL | Production bucket/IAM/signed access integration; malware scanning | In-memory storage exercised in backend tests |
| Resume upload | PARTIAL | PDF/DOCX validation, size/empty checks, storage persistence, queue event, new `/resume` UI | Production S3 integration; deliberate master-resume versioning behavior | Existing resume authorization/upload tests; browser test pending |
| Resume parsing | PARTIAL | Deterministic PDF/DOCX text extraction, structured extraction, failure/review states, provenance; onboarding review UI | Durable ECS/SQS worker must replace in-process background execution; retry/DLQ integration | Parser path exists; dedicated worker/integration tests pending |
| Canonical job model | COMPLETE | Companies, aliases, sources, raw postings, canonical jobs, locations, compensation, skills, versions/status | Production ingestion behavior | Existing schema/migration coverage |
| Connector contract | COMPLETE | Connector/provider boundary and deterministic development connector exist | None for interface scope | Import/compile coverage only |
| Real job ingestion | NOT STARTED | Domain/provider foundation only | Complete one legitimate Greenhouse connector, normalization, deduplication, freshness | None |
| Job search API | PARTIAL | PostgreSQL provider, structured filters, URL-backed web filters, bounded cursor pagination | Query-plan/performance validation; eliminate N+1 assembly | Existing job API tests; performance tests pending |
| Job detail | PARTIAL | Canonical API plus new `/jobs/[id]` UI with provenance, requirements, skills, save, and application action | Build/browser verification | API coverage exists; frontend test pending |
| Saved jobs | PARTIAL | Save/list/unsave with composite ownership; new `/saved` UI | Browser persistence/E2E verification | Existing API coverage; frontend test pending |
| Applications | PARTIAL | Create/list/detail/status; duplicate prevention; immutable events; notes CRUD; new list/detail workspace | Remove list job-detail fan-out; browser persistence/E2E verification | Existing backend application tests; frontend test pending |
| Candidate settings | PARTIAL | New `/settings` route exposes only real account/profile/preferences/privacy state | Notification settings remain hidden until implemented | Frontend verification pending |
| Candidate web | PARTIAL | Landing/auth entry, shell, dashboard, onboarding, jobs, detail, saved, applications, resume, profile, settings | CI build result, browser acceptance, accessibility pass | New CI workflow committed; result pending |
| End-to-end vertical slice | PARTIAL | Required source-controlled screens/APIs now exist for the Candidate MVP journey | Playwright journey; durable resume worker; real auth integration | Playwright NOT STARTED |
| Search provider | PARTIAL | PostgreSQL provider with structured filters and canonical job query | Measured FTS relevance/performance; production job corpus | Job search API tests only |
| CI | PARTIAL | `.github/workflows/ci.yml` added for web lint/build plus PostgreSQL migrations/backend tests | First successful workflow run; frontend tests/Playwright stages | No workflow result currently available |
| Matching | NOT STARTED | Architecture documented only | All matching implementation and evaluation | None |
| AI tools | NOT STARTED | Safety/task architecture documented | Implementation intentionally deferred | None |
| Mobile | NOT STARTED | UX/platform plan documented | Expo application | None |
| Employer product | NOT STARTED | Organization schema only | All workflows | None |
| Admin product | NOT STARTED | No implementation | All workflows | None |
| Production infrastructure | PARTIAL | Local PostgreSQL, provider boundaries, Vercel/AWS deployment plan, CI definition | Staging/prod resources, secrets, S3/SQS integration, ECS worker/API deployment, monitoring | Deployment verification pending |

## Candidate MVP status

**PARTIAL**

The candidate-facing source code now covers the intended workflow, but the milestone cannot be marked COMPLETE until the latest web build/lint, backend tests/migrations, Playwright persistence journey, accessibility validation, and production authentication/storage/queue integrations are verified.
