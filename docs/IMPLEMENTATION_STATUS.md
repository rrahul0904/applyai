# Implementation Status

Updated: 2026-09-01

This file separates repository/source completion from real provider acceptance. A feature is not considered live merely because code, migrations, or tests exist.

Status vocabulary:

- `COMPLETE_SOURCE` — product/source behavior exists with applicable repository evidence.
- `VALIDATION_PENDING` — source exists but the exact current head has not completed all required gates.
- `EXTERNAL_ACCEPTANCE_PENDING` — source is ready, but real provider/runtime evidence is still required.
- `DEFERRED_BY_PRIVACY` — intentionally not built because it conflicts with ApplyAI privacy boundaries.
- `DEFERRED_BY_LEGAL_RISK` — intentionally not built because it would materially change the employment-decision risk profile.
- `DEFERRED_BY_COST` — intentionally not required for the strict `$0` launch.

## Current release topology

| Item | Status |
|---|---|
| PR #22 Career System | merged |
| PR #23 Recruiter Lens | merged |
| PR #24 Resume Share Intelligence | merged |
| PR #25 Candidate Entry | merged |
| PR #26 Production Activation | merged |
| PR #27 Lean Production release vehicle | open/draft until real Preview acceptance |
| PR #28 Reverse-engineering gap closure | stacked on PR #27 branch; exact-head validation required before merge |

## Candidate product

| Capability | Status | Boundary |
|---|---|---|
| Authentication / onboarding / ownership | COMPLETE_SOURCE | Clerk remains sole identity provider in production; real tenant acceptance is external. |
| Resume upload / processing / review / versioning | COMPLETE_SOURCE | Private storage and worker paths are source complete; live object-provider acceptance remains external. |
| Resume Studio | COMPLETE_SOURCE | Evidence-bound job-specific variants and review workflow exist. |
| Deterministic Resume Intelligence | VALIDATION_PENDING | New gap-closure feature; explainable checks only, no ATS/hiring probability. |
| Job search / filters / saves | COMPLETE_SOURCE | Real-source capable PostgreSQL platform. |
| Career Intelligence / Career Memory | COMPLETE_SOURCE | Deterministic baseline plus reviewed durable AI path; core product can operate with deterministic provider. |
| Career Navigation / skill gaps / market context | VALIDATION_PENDING | Uses verified candidate evidence and ApplyAI canonical jobs; market coverage caveats required. |
| Career System | COMPLETE_SOURCE | Unified per-job preparation workspace. |
| Recruiter Lens core | COMPLETE_SOURCE | Candidate self-assessment only. |
| Recruiter Lens modes / reusable criteria | VALIDATION_PENDING | Protected-characteristic criteria blocked; owner-scoped. |
| Recruiter Lens report print/share/revoke | VALIDATION_PENDING | High-entropy candidate-controlled report share; no viewer/company inference. |
| Applications / history / notes | COMPLETE_SOURCE | Candidate-owned command center and approval boundary. |
| Interview preparation | COMPLETE_SOURCE | Evidence-bound preparation artifacts. |
| Technical Interview Lab | VALIDATION_PENDING | Behavioral/technical/system-design/SQL/coding reasoning and attempt history; no arbitrary remote execution. |
| Network / recruiter follow-up | COMPLETE_SOURCE | Candidate-controlled outreach/follow-up workflow. |
| Resume Share Intelligence | COMPLETE_SOURCE | Privacy-first smart links and engagement analytics. |
| Resume Share session reports / trends | VALIDATION_PENDING | Anonymous owner-scoped visit sequence and 7/30/90-day trends. |
| Public candidate portfolio | VALIDATION_PENDING | Explicit opt-in `/u/{slug}`, themes/projects/field visibility, publish/unpublish. |
| Alerts / analytics / settings | COMPLETE_SOURCE | Candidate-owned persistence. |
| Data export / account deletion | COMPLETE_SOURCE | Application-side lifecycle support. |

## Reverse-engineering policy status

| Capability | Status | Decision |
|---|---|---|
| Websumes-inspired Resume Intelligence | VALIDATION_PENDING | Safe P0 source implemented. |
| Websumes-inspired Career Navigation | VALIDATION_PENDING | Safe P0 source implemented. |
| Websumes-inspired Portfolio Identity | VALIDATION_PENDING | Safe P0 source implemented. |
| Websumes-inspired Market Intelligence | VALIDATION_PENDING | Safe P0 source implemented with corpus caveats. |
| JAN-inspired candidate Recruiter Lens | COMPLETE_SOURCE | Candidate preparation only. |
| JAN-inspired modes / reusable criteria | VALIDATION_PENDING | Safe P1 source implemented. |
| JAN-inspired candidate report/share | VALIDATION_PENDING | Safe P1 source implemented with candidate control/revoke. |
| JAN employer ranking / advancement / rejection | DEFERRED_BY_LEGAL_RISK | Do not build in candidate ApplyAI. |
| ResumeShareIQ-inspired smart links | COMPLETE_SOURCE | Privacy-first implementation. |
| ResumeShareIQ-inspired anonymous sessions/trends | VALIDATION_PENDING | Safe P1 source implemented. |
| IP/company/named-viewer inference | DEFERRED_BY_PRIVACY | Do not build. |
| Arbitrary remote coding sandbox | DEFERRED_BY_COST | Not required for `$0` launch; do not weaken sandbox security. |
| QR / print-intent / section-depth / recruiter contact | P2 | Useful enhancements, not release blockers. |

Canonical coverage documents:

- `docs/REVERSE_ENGINEERING_COVERAGE_AUDIT.md`
- `docs/reverse-engineering-feature-matrix.json`

## Job-data platform

| Area | Status | Evidence boundary |
|---|---|---|
| Provider-neutral source registry / adapters | COMPLETE_SOURCE | Greenhouse, Lever, Ashby and additional reviewed/configured source paths use canonical adapter/provenance architecture. |
| Raw posting preservation / validation | COMPLETE_SOURCE | Provider payload/provenance retained, invalid records kept out of searchable canonical jobs. |
| Canonical dedup / source authority | COMPLETE_SOURCE | Employer-origin evidence retains higher authority than broad coverage sources. |
| Freshness / closure safety | COMPLETE_SOURCE | Partial/failed runs do not create false absence closure evidence. |
| Scheduling / PostgreSQL leases | COMPLETE_SOURCE | Bounded due-source scheduling and `SKIP LOCKED` lease semantics. |
| Source health / operator control plane | COMPLETE_SOURCE | Internal source/run/quality controls exist. |
| Search/source scale gates | COMPLETE_SOURCE | Synthetic scale evidence only; not live inventory proof. |
| Open Jobs production inventory | EXTERNAL_ACCEPTANCE_PENDING | Requires real production database/worker run and measured canonical counts. |

## Durable runtime

| Area | Status | Evidence boundary |
|---|---|---|
| Transactional outbox | COMPLETE_SOURCE | First durable commit boundary. |
| PostgreSQL durable task queue | COMPLETE_SOURCE | Idempotency, leases, heartbeat, retry/backoff, dead/cancel/recovery. |
| Resume/source/AI/agent routing | COMPLETE_SOURCE | Explicit task families; unknown tasks fail closed. |
| Governed agent runtime | COMPLETE_SOURCE | Registry, durable runs/artifacts/tool calls/approvals/budgets and deterministic acceptance exist. |
| Live provider agent execution | EXTERNAL_ACCEPTANCE_PENDING | Requires real provider/runtime evidence. |

## Security / privacy

| Area | Status |
|---|---|
| Candidate ownership / user isolation | COMPLETE_SOURCE + new gap regression coverage pending exact-head CI |
| Resume parser bounds / malformed file handling | COMPLETE_SOURCE |
| Private object storage abstraction | COMPLETE_SOURCE |
| SSRF / redirect / response-size controls for public import | COMPLETE_SOURCE |
| Production CORS fail-closed | COMPLETE_SOURCE |
| Resume Share raw IP persistence | DEFERRED_BY_PRIVACY |
| Cross-link fingerprinting / company inference | DEFERRED_BY_PRIVACY |
| Recruiter Lens protected-characteristic criteria | blocked by source validation |
| Candidate evidence fabrication | prohibited by product policy and evidence validation |
| CAPTCHA/login/anti-bot bypass | prohibited |

## `$0` launch constraint

Mandatory initial infrastructure cost target:

```text
$0.00/month
```

The application must not silently enable paid infrastructure, paid AI, paid monitoring, paid email, paid queues, or automatic upgrades. Core product behavior must remain available with `AI_PROVIDER=deterministic`. Infrastructure may be simplified/substituted when required to preserve the zero-cost invariant, while Clerk remains the identity provider and PostgreSQL semantics/SQLAlchemy/Alembic remain canonical.

## Exact-head repository gate

After every source-changing commit require applicable:

```text
web lint
web typecheck
web tests
Next.js production build
API tests
Alembic zero-to-head
Alembic metadata drift
OpenAPI drift
API production image
Candidate Playwright journey
Lean Production Validation
Local Clean-room Certification
Job Search Scale
Job Supply Scheduler Scale
Agent Runtime Tests
Agent Runtime Scale
Demo Capture
GitHub Workflow Validation
optional AWS profile validation
```

Do not promote `VALIDATION_PENDING` gap features to `COMPLETE_SOURCE` until the exact current PR #28 head is green.

## Live production status

`LIVE_PRODUCTION_VERIFIED = false` until all of the following are demonstrated against real infrastructure:

- real Clerk signup/signin/JWT/logout-login;
- real persistent PostgreSQL migrations/data;
- real private object storage upload/read/delete acceptance;
- real job ingestion into the production database;
- dedicated ApplyAI Vercel Preview;
- complete Preview candidate journey;
- merge PR #28 into the PR #27 release branch after exact-head green;
- exact PR #27 gates;
- merge PR #27 to `main` only after Preview acceptance;
- exact-main gates;
- Vercel Production;
- complete Production candidate journey and production-health review.

Source completion must never be reported as live-provider or production verification.
