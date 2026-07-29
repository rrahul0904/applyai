# Implementation Status

Statuses are restricted to COMPLETE, PARTIAL, NOT STARTED, and BLOCKED.

| Capability | Status | Evidence | Missing | Tests |
|---|---|---|---|---|
| Repository architecture correction | COMPLETE | Official Next app; FastAPI service; D1/Vinext code removed | None for correction scope | Web production build |
| Canonical PostgreSQL model | COMPLETE | 33 SQLAlchemy/Alembic tables covering required foundation domains | Future domain fields will use new migrations | Zero-to-head, rollback, forward, drift |
| Database migrations | COMPLETE | Initial Alembic revision with explicit downgrade | Production release automation | Migration head test |
| Clerk authentication code | PARTIAL | Next Clerk integration; FastAPI RS256/JWKS verifier; internal UUID mapping | Real keys, issuer/JWKS, Google enablement, live sign-in | Auth dependency exercised through overrides |
| Candidate authorization | COMPLETE | Owner-scoped profile, resume, saved-job, and application queries | Notes/documents routes are not exposed yet | Cross-user profile, resume, application tests |
| Candidate profile | PARTIAL | Authenticated GET/PUT with preferences and target roles | Candidate web form and full experience/education/skills editing | Write/read, isolation, invalid input |
| Candidate onboarding | NOT STARTED | Architecture and persistence fields defined | Workflow UI, resume-less path, completion transition | None |
| Object storage | PARTIAL | Local and S3 providers; secure key shape; storage key omitted | Production S3 configuration, signed flows, integration test | In-memory provider upload test |
| Resume upload | PARTIAL | Validation, object persistence, metadata, queued processing state | Candidate UI, download, malware scan, production S3 config | Metadata, type validation, owner isolation |
| Resume parsing | NOT STARTED | Queue task and extraction table exist | Worker, PDF/DOCX parser, failures, provenance review | None |
| Canonical job model | COMPLETE | Companies, sources, raw postings, canonical jobs, locations, compensation, skills, versions/status | Dedup service logic | Migration/schema test |
| Connector contract | COMPLETE | Fetch/normalize/checkpoint/health interface and development connector | Pipeline runner | Import/compile validation |
| Real job ingestion | NOT STARTED | Provider boundary exists | One legitimate live connector and pipeline | None |
| Job search API | PARTIAL | Canonical DB search and structured filters | PostgreSQL FTS ranking, pagination, full filter set, web URL UI | Job list/detail test |
| Job detail | PARTIAL | Canonical job, company, location, salary provenance, requirements, skills, source | Web detail screen | Detail API test |
| Saved jobs | PARTIAL | Save, list, unsave with authenticated composite ownership | Web screens and browser-session test | End-to-end API test |
| Applications | PARTIAL | Create/list/detail/status plus immutable event history | Notes/documents APIs and web workspace | Creation, event history, cross-user mutation |
| Candidate web | PARTIAL | Public auth entry and authenticated foundation workspace | Onboarding, jobs, detail, save, applications UI | Production build |
| End-to-end vertical slice | BLOCKED | Foundation APIs and schema exist | Clerk credentials, candidate UI, resume parser, seeded ingestion | E2E not yet written |
| Search provider | PARTIAL | PostgreSQL provider interface and filters | FTS, pgvector, performance tests | Job search API test |
| Matching | NOT STARTED | Architecture documented | All matching prerequisites | None |
| AI tools | NOT STARTED | Safety/task architecture documented | Implementation intentionally deferred | None |
| Mobile | NOT STARTED | UX/platform plan documented | Expo application | None |
| Employer product | NOT STARTED | Organization schema only | All workflows | None |
| Admin product | NOT STARTED | No implementation | All workflows | None |
| Infrastructure | PARTIAL | Local PostgreSQL, Vercel/AWS deployment plan, provider boundaries | Terraform, CI/CD, staging/prod resources | Local migration/build validation |
