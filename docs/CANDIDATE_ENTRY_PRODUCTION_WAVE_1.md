# ApplyAI Candidate Entry + Production Activation Wave 1

## Mission

Make the first five minutes of ApplyAI feel like a trustworthy, premium candidate workspace and establish the production architecture boundary for the next activation phase.

This wave does not rewrite the existing backend, replace Clerk, or migrate the database. It improves the candidate entry experience while documenting the lean production stack we should activate next.

## Candidate entry experience

### Product goal

A signed-out candidate should immediately understand:

1. ApplyAI is a candidate-controlled career workspace, not an automatic hiring decision tool.
2. Resume and career evidence stay private by default.
3. AI-generated claims remain evidence-bound.
4. Every opportunity can move through one connected workflow: job discovery -> recruiter fit -> evidence strengthening -> application preparation -> interview preparation.
5. New candidates should enter onboarding after account creation; returning candidates should return to the dashboard.

### Routes

- `/sign-in/[[...sign-in]]` — dedicated Clerk sign-in surface
- `/sign-up/[[...sign-up]]` — dedicated Clerk sign-up surface
- signed-in visitors to either route redirect to `/dashboard`
- signed-out protected candidate routes redirect to `/sign-in`
- signed-out onboarding redirects to `/sign-in?redirect_url=/onboarding`
- sign-up fallback destination is `/onboarding`
- sign-in fallback destination is `/dashboard`

### Visual direction

- warm neutral background
- deep green/ink interaction color
- restrained typography and spacing
- no gradients or generic AI neon styling
- left side explains the candidate workflow and safety model
- right side contains the Clerk authentication surface
- mobile collapses to a single-column layout

## Recommended production stack

### Product surfaces

| Layer | Technology | Decision |
| --- | --- | --- |
| Candidate web | Next.js 16 App Router + React 19 + TypeScript | Keep |
| Web hosting/CDN | Vercel | Activate |
| Candidate identity | Clerk | Keep and activate real tenant |
| Candidate mobile | Expo / React Native | Keep |
| Browser capture | Manifest V3 extension | Keep |

### Application backend

| Layer | Technology | Decision |
| --- | --- | --- |
| API | FastAPI / Python 3.12 | Keep |
| Architecture | Modular monolith | Keep |
| ORM | SQLAlchemy 2 | Keep |
| Migrations | Alembic | Keep |
| API contract | OpenAPI generated TypeScript client | Keep |

### Data

| Layer | Initial production choice | Scale path |
| --- | --- | --- |
| PostgreSQL | Dedicated Supabase Postgres project | Aurora Postgres only when operational evidence justifies it |
| Vector search | pgvector in Postgres | Dedicated search/vector system only after measured need |
| Text search | PostgreSQL FTS | Typesense/OpenSearch only after measured need |
| Resume/object storage | S3-compatible private bucket | AWS S3 canonical at scale; Cloudflare R2 is acceptable for a lean deployment if worker/storage semantics stay compatible |

Important: Supabase is recommended as managed PostgreSQL only. Clerk remains the identity provider. Do not add Supabase Auth alongside Clerk.

The existing SQLAlchemy/Alembic data layer should connect to Supabase through `DATABASE_URL`; application code should not be rewritten around the Supabase client SDK.

### Background work and browser execution

| Workload | Technology |
| --- | --- |
| Transaction boundary | PostgreSQL transactional outbox |
| Durable queue | AWS SQS |
| Job ingestion | Python source workers |
| Resume processing | Python resume worker |
| AI jobs | Python AI worker |
| Browser application execution | Playwright worker in ECS/Fargate or another long-running container runtime |
| Scheduling | EventBridge / bounded source dispatcher |

Do not run the Playwright application executor as a short-lived Vercel Function.

### AI

- provider abstraction already present in ApplyAI
- OpenAI as primary reviewed provider initially
- Anthropic optional behind the same provider boundary
- deterministic/evidence-bound product scoring remains separate from LLM output
- no model may create unsupported candidate evidence

### SaaS operations

| Capability | Recommended provider |
| --- | --- |
| Billing | Stripe |
| Transactional email | Resend |
| Product analytics | PostHog |
| Error monitoring | Sentry |
| Tracing | OpenTelemetry |
| CI/CD | GitHub Actions |
| Infrastructure | Terraform for cloud resources |

## Production activation order

1. Merge the stacked Career System, Recruiter Lens, Resume Share Intelligence, and Candidate Entry waves in dependency order.
2. Create the dedicated `applyai` Vercel project and deploy Preview.
3. Create a dedicated ApplyAI Supabase project; do not reuse an unrelated project.
4. Apply the existing Alembic schema to that Postgres database and require zero migration drift.
5. Configure a real Clerk tenant and verify signup -> onboarding -> API -> database -> logout -> login.
6. Activate real object storage and resume processing.
7. Load reviewed organization datasets and activate the first real job sources.
8. Run live job-supply acceptance and measure freshness, dedup, apply-link validity, failures, and cost.
9. Activate AI provider and candidate Career Intelligence acceptance.
10. Activate the Playwright application worker only after the preceding candidate journey is stable.

## Explicit non-goals for this wave

- no Supabase Auth
- no database migration to Supabase in source code yet
- no rewrite to serverless-only backend
- no employer-side JAN candidate ranking
- no automatic application submission without candidate approval
- no public portfolio publishing
- no production deployment claim without real external evidence

## Definition of done

- custom sign-in and sign-up routes exist
- signed-out candidate routes use the branded sign-in path
- sign-up returns to onboarding
- returning sign-in returns to dashboard
- the auth surface is responsive and accessible
- web lint/typecheck/tests/build are green on the exact head
- existing API/migration/OpenAPI/Playwright gates remain green
