# Implementation Status

Updated: 2026-08-08

This file is the source-of-truth status for ApplyAI after platform completion.

Statuses are intentionally restricted to:

- `COMPLETE` — the product/source capability exists and has an applicable repository validation gate.
- `BLOCKED` — the remaining work requires a real external environment, provider account, secret, signing identity, store publication, licensed dataset/feed, or live operational evidence that cannot be fabricated from source control.

## Platform/source status

| Area | Status | Evidence boundary |
|---|---|---|
| Core candidate platform | COMPLETE | Candidate workflows, persistence, search, applications, resume, AI, employer/admin, billing, notifications and privacy source exist with repository gates. |
| Multi-source job-data platform | COMPLETE | Greenhouse/Lever/Ashby/SmartRecruiters, USAJOBS, ReliefWeb, permitted employer career/JSON-LD paths, authorized/licensed JSON/JSONL/CSV/XML/RSS/Atom feed contract, source registry, scheduling/leasing, source completeness, authority/provenance, dedup, freshness, closure evidence, URL verification and measured quality metrics exist. This does not claim live provider execution. |
| Organization universe and authoritative dataset ingestion | COMPLETE | Repeatable organization ingestion supports canonical domains, aliases, source-specific external IDs, review-safe identity resolution, dataset provenance and SEC, NCES/IPEDS, CMS hospital, IRS nonprofit and reviewed government directory loaders. The architecture can represent large organization universes; no live 50K employer count is claimed. |
| ATS/career-site discovery | COMPLETE | Discovery identifies Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable, iCIMS, Oracle, SuccessFactors, Jobvite, UKG, BambooHR, JazzHR, PageUp, PeopleAdmin, Cornerstone, GovernmentJobs/NEOGOV and additional reviewed fingerprints; unsupported board APIs use the bounded public structured-page path without bypassing access controls. |
| Provider access-policy registry | COMPLETE | Provider records expose access mode, implementation state, credential/partnership requirements, robots/rate-limit/pagination policy, closure/delta support, trust level and automated-ingestion permission. Major marketplaces remain partnership/authorized-feed gated rather than anonymous crawler targets. |
| Marketplace partner capability model | COMPLETE | Partner approval states and fail-closed contractual rights (`can_search`, ingest/store/redistribute/display/apply/post/update/close, retention, attribution) are source controlled. LinkedIn/Indeed readiness and blocker runbooks exist; no provider approval or data rights are claimed. |
| Job source completeness and closure safety | COMPLETE | Source runs distinguish full/paginated-full/delta/partial/truncated/unknown evidence; record failures downgrade a run to partial, and absence-based closure requires explicit full-snapshot authority rather than defaulting unknown connectors to complete. |
| Job-scale repository gate | COMPLETE | PostgreSQL benchmark workflow validates 10K, 50K and 250K synthetic job corpora. A separate PostgreSQL scheduler gate measures 1K, 10K and 50K synthetic source leases. Both are explicitly synthetic scale evidence, not live inventory. |
| Job-supply operator control plane | COMPLETE | Internal job-supply overview/providers/organizations/sources/runs/failures/dedup/quality APIs plus source controls, provider review overrides, organization discovery and the server-only `/admin` UI are implemented. Dedup review decisions do not silently merge canonical jobs. |
| Job-supply staging acceptance tooling | COMPLETE | `pnpm job-supply:acceptance` reads actual runtime/database evidence and fails closed as `BLOCKED_EXTERNAL_CONFIGURATION` when real organizations, active real sources, successful real runs or non-development canonical jobs are absent. It cannot turn deterministic/synthetic evidence into staging verification. |
| OpenAPI contract discipline | COMPLETE | Public APIs are typed, generated client contract is committed, the temporary generation workflow is removed, and exact-head drift validation is required. |
| Database migrations | COMPLETE | Alembic revisions cover Career Intelligence, Career Memory, platform-completion and global job-supply domains; zero-to-head and metadata drift validation are required. |
| Canonical browser acceptance | COMPLETE | Browser -> Next.js -> FastAPI -> PostgreSQL journey covers onboarding, resume review, search, save, application persistence, canonical platform workspaces, relogin and ownership isolation. |
| Fresh local clean-room reproducibility | COMPLETE | `pnpm local:certify` is executed by a dedicated fresh-checkout workflow: locked install, clean DB recreation, migrations, isolated API/web/OpenAPI gates, deterministic seed, local integrations, workers and browser acceptance. This does not guarantee every host-specific workstation configuration or live external provider acceptance. |
| Production-shaped local S3/SQS/SMTP integration | COMPLETE | LocalStack exercises the real boto3 S3/SQS code paths including presigned resume PUTs, separate queue families/DLQs and live outbox/workers; Mailpit exercises the real SMTP provider and captured delivery. |
| Local Clerk/OpenAI/Stripe protocol integration | COMPLETE | A controlled local provider server exercises the real Clerk RS256/JWKS verifier, real OpenAI Responses and embeddings clients, and Stripe checkout/portal request handling; ApplyAI separately verifies signed Stripe webhook persistence. These are local protocol tests, not live vendor-account acceptance. |
| Career Intelligence and AI platform source | COMPLETE | Career Intelligence, Career Memory, evidence-locked tailoring, AI queue/provider abstraction, semantic matching, evaluations and telemetry are source controlled and repository-tested. |
| Employer/recruiter platform | COMPLETE | Employer organizations, role membership, trust verification, job drafting/publishing/closure, canonical first-party listings, applicants, stages, ratings, notes and dashboard metrics are implemented. |
| Billing/subscriptions | COMPLETE | Free/Pro/Team entitlements, subscription/usage persistence, Stripe Checkout adapter, Billing Portal adapter, signed webhook processing and billing ledger are implemented. |
| Privacy/account lifecycle | COMPLETE | Machine-readable export, application-side deletion, anonymized referential tombstone and deleted-identity hash protection are implemented. |
| Operator/admin console | COMPLETE | Server-only operator boundary, platform metrics, employer verification/suspension, engagement dispatch, AI evaluation and global job-supply health/source/provider/organization controls are implemented. |
| Browser extension source | COMPLETE | Manifest V3 extension with only `activeTab` and `storage` hands the active public URL to ApplyAI's existing safe import workflow; source syntax/permission checks run in repository tests. |
| Native mobile source | COMPLETE | Expo/React Native candidate client with Clerk secure token handling and native Matches, Jobs, Applications, Alerts and Profile/Career Memory screens is source controlled; mobile TS/TSX source is compiled in repository tests. |
| Candidate web product consolidation | COMPLETE | Historical `/demo` and `/beta` entry points redirect to canonical `/dashboard` and `/matches`; the real candidate navigation exposes Matches, Resume Studio, Network, Analytics, Alerts, Billing and Career Intelligence. |
| Public pricing/settings | COMPLETE | Pricing surface, subscription controls, alert settings and privacy export/deletion controls are implemented. |
| CI and repository quality gates | COMPLETE | Web lint/typecheck/tests/build, mobile/extension source validation, API tests, Docker, Alembic, OpenAPI, Terraform, Playwright, CloudFormation/workflow validation, demo capture, clean-room certification, search-scale benchmarks and source-scheduler scale benchmarks are source controlled. |
| AWS staging infrastructure source | COMPLETE | VPC/ALB/ECS/Aurora/S3/ECR, resume/source/AI queues and DLQs, IAM, EventBridge, logs/alarms, migrations and worker services are source controlled and Terraform-validated. |
| AWS bootstrap source | COMPLETE | CloudFormation bootstrap creates/reuses GitHub OIDC trust, encrypted/versioned state and staging deployment role without long-lived normal deployment keys. |
| Staging release/rollback/verification automation | COMPLETE | Immutable-image release, migration gate, runtime activation, rollback and candidate/source/AI verification workflows are implemented and statically validated. |

## External/live activation status

| Area | Status | Remaining evidence |
|---|---|---|
| AWS/Vercel/Clerk staging deployment | BLOCKED | Create the real staging environment, OIDC outputs, ACM/DNS, Clerk app and Vercel project/domain, then run the release/verification workflows. |
| Real-service candidate acceptance | BLOCKED | Prove Clerk -> Vercel -> ECS -> Aurora and browser -> S3 -> outbox -> resume SQS -> worker, including candidate isolation and recovery drills. |
| Real organization-universe activation | BLOCKED | Load reviewed public/licensed organization datasets in staging, record measured row/domain/career-source counts and resolve identity-review conflicts. The loaders and operator workflow are source-complete. |
| Real ATS/provider acceptance | BLOCKED | Configure reviewed live sources/credentials and run `pnpm job-supply:acceptance`; measure real freshness, dedup, completeness, closure/reopen, apply URL health, throughput and cost. Repository tests/synthetic gates are not live-source evidence. |
| Marketplace partner/licensed-feed activation | BLOCKED | Obtain required provider contracts/approved feeds for any marketplace used directly. LinkedIn/Indeed remain fail-closed until partner approval, credentials and exact storage/display/redistribution rights are evidenced. |
| Live Clerk account acceptance | BLOCKED | Exercise real Clerk sign-up/sign-in/sign-out, issuer/JWKS rotation behavior and account lifecycle against a configured Clerk tenant. |
| Live OpenAI acceptance | BLOCKED | Execute the AI worker against the reviewed real provider/model and capture schema, latency, token, cost and evidence-lock telemetry. |
| Live Stripe acceptance | BLOCKED | Configure real products/prices/webhook secret and validate checkout, entitlement changes, portal, renewal/cancel and replay behavior. |
| Real email/push delivery | BLOCKED | Configure approved production providers and measure delivery/failure/bounce/opt-out behavior. |
| Production cloud deployment and recovery drills | BLOCKED | Promote only after staging acceptance, backup/restore/PITR, rollback and failure-injection evidence. |
| Native mobile signing/store release | BLOCKED | Requires Apple/Google signing identities and store submission/review. |
| Browser extension publication | BLOCKED | Requires browser-store publisher account and review. |

## Claim rule

`COMPLETE` above means repository/source completion at the stated evidence boundary. It must never be presented as live-provider, live-staging or production verification unless the corresponding runtime evidence has actually passed.