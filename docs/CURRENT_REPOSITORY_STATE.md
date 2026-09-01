# Current Repository State

Updated: 2026-09-01

## Source control

- Repository: `rrahul0904/applyai`
- Default branch: `main`
- Product PRs #22–#26 are merged into `main`.
- Final lean-production release vehicle: PR #27, `agent/lean-production-wave-1` → `main`.
- Reverse-engineering gap closure: PR #28, `agent/reverse-engineering-gap-closure` → `agent/lean-production-wave-1`.
- PR #28 must pass exact-head validation before being merged into the PR #27 release branch.
- PR #27 remains draft until real Preview/provider acceptance passes.

## Launch architecture

```text
Vercel / Next.js + Clerk
        ↓
FastAPI backend
        ↓
PostgreSQL
        ├─ canonical product data
        └─ TaskOutbox → durable PostgreSQL task queue

Private S3-compatible object storage → résumé/document objects
```

The public product target remains Vercel. Backend/provider choices must preserve the hard `$0 required monthly infrastructure` launch constraint; no mandatory paid provider is allowed without explicit approval. AWS remains an optional future scale/enterprise profile, not a launch prerequisite.

## Candidate product

Canonical candidate surfaces include:

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
/career/navigation
/portfolio
/interview/[jobId]
/network
/analytics
/alerts
/profile
/billing
/settings
/import-job
```

Public candidate-controlled surfaces on the gap-closure branch include:

```text
/u/{candidate-slug}
/recruiter-report/{token}
/r/{resume-share-token}
```

Core capabilities include:

- Clerk-backed identity mapping and owner-scoped APIs;
- branded sign-in/sign-up and onboarding;
- candidate-reviewed profile evidence and Career Memory;
- private résumé upload, parsing, review and versioning;
- Resume Studio and job-specific variants;
- deterministic resume-intelligence checks;
- real-source capable PostgreSQL job search, filters and saved jobs;
- explainable Career Intelligence;
- unified Career System per job;
- candidate-side Recruiter Lens;
- Recruiter Lens modes and candidate-owned reusable criteria;
- candidate-controlled print/private-share/revoke Recruiter Lens reports;
- application command center and candidate-approved external submission boundary;
- evidence-bound application/interview preparation;
- Technical Interview Lab for behavioral, technical, system-design, SQL and coding reasoning practice;
- recruiter/referral outreach and follow-up;
- opt-in public portfolio with themes, projects and field-level visibility;
- career role navigation, skill-gap and canonical-job market intelligence;
- privacy-preserving Resume Share Intelligence;
- anonymous Resume Share session reports and 7/30/90-day trends;
- notification inbox and candidate analytics;
- account export and application-side deletion.

Readiness metrics are candidate preparation signals, never employer scores or hiring probabilities.

## Reverse-engineering coverage

Canonical audit files:

- `docs/REVERSE_ENGINEERING_COVERAGE_AUDIT.md`
- `docs/reverse-engineering-feature-matrix.json`

Safe P0/P1 gaps are source-implemented on PR #28. Deliberate exclusions remain explicit:

- employer bulk candidate ranking/automatic advancement/rejection → `DEFERRED_BY_LEGAL_RISK`;
- raw-IP/company/named-viewer inference and fingerprinting → `DEFERRED_BY_PRIVACY`;
- arbitrary remote coding sandbox → `DEFERRED_BY_COST` for the `$0` launch;
- QR, print-intent tracking, section-level engagement and recruiter contact form → P2, not release blockers.

Source completion is not promoted to validated completion until exact-head CI is green.

## Career Intelligence and durable work

Career Intelligence V1 remains deterministic and explainable. Durable V2 uses verified candidate/job evidence, transactional outbox persistence, durable task delivery, strict schema/evidence-reference validation and candidate review. Lean production uses PostgreSQL durable tasks; the optional AWS profile can route the same task families through SQS.

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
- unknown task types fail closed.

## Resume and sharing privacy

Private storage credentials remain server-side. Raw private storage URLs are never exposed by Resume Share or portfolio/report surfaces.

Resume Share remains privacy preserving:

- no raw IP persistence;
- no cross-link browser fingerprinting;
- no company identity inference;
- no named viewer guessing;
- engagement is not hiring probability;
- first human view creates one viewed notification;
- first observed return creates one returned notification;
- later repeated views remain analytics-only;
- new session-detail and trend APIs remain owner-scoped.

Recruiter Lens report shares are candidate-created, high-entropy, noindex, revocable, and explicitly do not perform viewer identity/company inference.

## Job-data platform

Source support and architecture include ApplyAI first-party jobs, Greenhouse, Lever, Ashby, SmartRecruiters, configured government/public sources, bounded permitted employer structured pages, authorized/licensed feeds and Open Jobs discovery coverage.

Employer-origin sources remain higher authority than broad coverage sources. Open Jobs does not receive absence-based closure authority. Source registry, leases, health, provenance, deduplication, freshness, URL verification and operator controls remain canonical.

Real production job counts still require an actual production database/source run. Synthetic and source-network acceptance are not interchangeable with live production inventory.

## Repository validation

Required release evidence includes:

```text
Web lint / typecheck / unit tests / Next.js production build
API tests
Alembic zero-to-head + zero metadata drift
OpenAPI drift
API production container
Candidate Playwright journey
Local clean-room certification
Lean Production Validation
Postgres queue concurrency / lease / retry / cancellation tests
job search/source scheduler scale gates
agent runtime tests / scale gate
demo capture
GitHub workflow validation
AWS optional-profile validation
```

PR #28 additionally includes dedicated ownership/privacy regression coverage for portfolio projects, Recruiter Lens criteria, Recruiter Lens report shares, Technical Interview Lab attempts and Resume Share session/trend data.

Do not reuse a historical PASS after a source-changing commit.

## Live-provider boundary

Repository/source work and live deployment evidence are intentionally separate.

The final live gate still requires actual evidence for:

```text
real Clerk signup/signin/JWT
real database migrations/persistence
real private object storage
real job ingestion
Vercel ApplyAI Preview
complete Preview candidate journey
merge PR #28 into PR #27 release branch
exact PR #27 CI
merge PR #27 to main
exact-main CI
Vercel Production
complete Production candidate journey
```

Optional Stripe, Resend, paid AI, analytics/monitoring and browser auto-submit must remain disabled or safely feature-gated when they would violate the `$0` launch constraint.

`LIVE_PRODUCTION_VERIFIED` may be reported only after the complete persistent candidate journey passes against real Production infrastructure.
