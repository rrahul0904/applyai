# ApplyAI Reverse-Engineering Coverage Audit

Updated: 2026-09-01

## Purpose

This document is the conservative source-of-truth for reverse-engineering coverage. A route, README claim, or schema alone is not enough for `COMPLETE`: code, ownership/authorization, usable UI where applicable, and repository validation must exist. Live-provider behavior remains `EXTERNAL_ACCEPTANCE_PENDING` until exercised against real infrastructure.

## Product boundary

ApplyAI is an original candidate career platform. Public product behavior from Websumes, JAN Screening, ResumeShareIQ, and the original ApplyAI Candidate MVP / Job Source Platform specifications is used only as problem-space inspiration. ApplyAI does not copy private APIs, source code, prompts, proprietary scoring, assets, or protected text.

Hard product exclusions remain:

- employer-side automatic candidate ranking, advancement, or rejection;
- hiring/interview probability claims;
- protected-class criteria in candidate self-assessment;
- raw-IP persistence, company inference from IP, cross-link fingerprinting, or named-viewer guessing;
- CAPTCHA/login/anti-bot bypass;
- fabricated candidate evidence;
- mandatory paid infrastructure for the initial launch.

## Executive coverage

| Area | Status | Evidence / decision |
|---|---|---|
| Candidate MVP | COMPLETE (source) | Canonical account → onboarding → resume → profile → jobs → save/application → relogin workflow is repository implemented; live provider acceptance remains separate. |
| Job Source Platform V1 | COMPLETE (source) | Registry, adapters, normalization, provenance, dedup, freshness, scheduling/leasing, health, operator APIs and scale gates exist. |
| Websumes-inspired Resume Intelligence | COMPLETE (source) | Existing Resume Studio plus deterministic readiness checks added on gap-closure branch. |
| Websumes-inspired Career Navigation | COMPLETE (source) | Candidate career navigation uses verified candidate context plus canonical active-job evidence; role/skill/market outputs include coverage caveats. |
| Websumes-inspired Portfolio Identity | COMPLETE (source) | Explicit opt-in `/u/{slug}` portfolio, project showcase, themes, field visibility and publish/unpublish controls are implemented. |
| Websumes-inspired Market Intelligence | COMPLETE (source) | Candidate-side corpus-derived metrics are implemented with sample-size/freshness/coverage caveats. |
| JAN-inspired Recruiter Lens core | COMPLETE (source) | Evidence-bound criteria, statuses, concerns, questions and readiness tier remain candidate-side. |
| Recruiter Lens modes / reusable candidate criteria | COMPLETE (source) | DEFAULT_RECRUITER / STRICT_MUST_HAVE / HIRING_MANAGER / TECHNICAL / CUSTOM plus candidate-owned criteria sets exist. |
| Recruiter Lens candidate report/share | COMPLETE (source) | Candidate can print or create a high-entropy private report link for the chosen perspective and revoke it; public report is noindex and has no named-viewer/company inference. |
| JAN employer bulk screening / applicant ranking | DEFERRED_BY_LEGAL_RISK | Intentionally excluded from candidate ApplyAI. |
| ResumeShareIQ-inspired smart links | COMPLETE (source) | Smart links, dwell/scroll/click/copy/download/return metrics, timeline, CSV and bounded notifications exist. |
| Resume Share anonymous session report / trends | COMPLETE (source) | Privacy-safe anonymous session sequence and 7/30/90-day trend APIs added. |
| Resume Share company/named viewer inference | DEFERRED_BY_PRIVACY | Intentionally excluded. |
| Technical Interview Lab | COMPLETE (source foundation) | Job-specific behavioral/technical/system-design/SQL/coding practice, answer workspace, notes and attempt history exist; secure arbitrary remote code execution is separately deferred. |
| Secure remote coding sandbox | DEFERRED_BY_COST | A hardened multi-language execution sandbox would add operational/security cost; not required for zero-cost launch. |
| Live production acceptance | EXTERNAL_ACCEPTANCE_PENDING | Requires real Clerk, Vercel, backend/database, private object storage, real job ingestion and persistent candidate journey. |

## Candidate MVP evidence checklist

Source-complete canonical capabilities:

- account and Clerk identity boundary;
- onboarding and candidate-owned profile;
- experience, education, skills and preferences;
- private resume upload, processing, review and versioning;
- Resume Studio / job-specific variants;
- job search, filters, detail, saved jobs and saved searches;
- Career Intelligence and Career Memory;
- Recruiter Lens;
- applications, history, notes and candidate-approval boundary;
- interview preparation;
- network/recruiter contacts and follow-up workflow;
- alerts, analytics, settings, export and deletion;
- Resume Share Intelligence;
- logout/login persistence in canonical browser acceptance.

Provider-backed production proof is not inferred from these source capabilities.

## Websumes-inspired coverage

### Resume Intelligence — COMPLETE (source)

ApplyAI already had parsing, reviewed evidence, Resume Studio and job-specific variants. The gap branch adds deterministic explainable checks for parseability/readiness, section/evidence coverage and unsupported-claim risk without presenting an opaque ATS or hiring probability.

### Career Navigation — COMPLETE (source)

The gap branch adds a dedicated career-navigation workspace using verified candidate context and ApplyAI's own real canonical job corpus. Outputs are framed as adjacent/preparation directions, not deterministic career destiny.

### Portfolio Identity — COMPLETE (source)

Implemented:

- explicit opt-in candidate portfolio;
- unique slug and collision handling;
- publish/unpublish;
- field-level visibility;
- project showcase;
- original Professional / Minimal / Technical / Portfolio themes;
- indexing preference;
- public `/u/{slug}` view;
- no implicit raw-resume exposure.

Contact delivery is not considered complete merely because `contact_enabled` exists; a public contact form remains a P2 enhancement unless implemented with rate limiting and abuse controls.

### Market Intelligence — COMPLETE (source)

The gap branch derives candidate-side market indicators only from ApplyAI's canonical job dataset and avoids claiming complete labor-market coverage. Salary is used only when explicit source compensation exists.

## JAN-inspired Recruiter Lens

### COMPLETE (source)

- job-derived criteria;
- SUPPORTED / PARTIAL / NOT_EVIDENCED states;
- evidence snippets;
- deterministic score/tier;
- concerns;
- gap-driven interview questions;
- candidate-side disclaimer;
- identity/protected-field exclusion;
- selectable assessment modes;
- candidate-owned reusable criteria sets;
- print-friendly candidate report;
- candidate-created high-entropy private report link;
- candidate revocation of report links;
- noindex public report page;
- no named-viewer or company-identity inference on report shares.

### DO NOT BUILD

- bulk candidate upload/ranking;
- ATS applicant ranking;
- automatic advancement/rejection;
- candidate-pool ranking;
- employer hiring recommendations.

These remain `DEFERRED_BY_LEGAL_RISK`.

## ResumeShareIQ-inspired coverage

### COMPLETE (source)

Existing platform plus gap branch provide:

- high-entropy candidate-owned links;
- role/application/channel context;
- expiry, revoke/reactivate/delete and download controls;
- public privacy disclosure and noindex behavior;
- no raw storage URL exposure;
- anonymous per-link sessions;
- bot filtering;
- view, dwell, scroll, click, copy and download events;
- returning-view metrics;
- engagement bands and timeline;
- CSV export;
- bounded first-view / first-return / first-download notifications;
- privacy-safe session sequence reports;
- 7 / 30 / 90 day trend comparisons.

### PARTIAL / P2

- true section-level HTML portfolio engagement is not yet evidenced;
- PDF page heatmaps are explicitly unavailable unless technically observable;
- print intent, QR sharing and public-view theme controls are useful P2 parity items, not launch blockers;
- candidate opt-in recruiter contact form is P2 until abuse/rate-limit controls exist.

### DEFERRED_BY_PRIVACY

- raw IP persistence;
- company detection from IP;
- named-viewer inference;
- cross-link identity graphs;
- third-party fingerprinting;
- hidden tracking.

## Technical Interview Lab

The gap branch adds a lightweight zero-cost practice foundation for:

- behavioral;
- technical;
- system design;
- SQL;
- coding questions;
- answer workspace;
- notes;
- attempt history;
- self-review.

This source foundation satisfies the safe P1 interview-practice requirement. It intentionally does not create unsafe arbitrary remote code execution. Secure sandboxed execution remains `DEFERRED_BY_COST` until a hardened zero-cost mechanism is proven.

## Job Source Platform V1

The repository source covers the original required architecture: source registry, provider-neutral connectors, `RawJobPosting`, Greenhouse/Lever/Ashby, validation, provenance, canonical dedup, freshness, source runs, scheduler, PostgreSQL leases, retries, source health, internal operator APIs, indexes/migrations and scale gates. Additional source types must still be described according to actual implementation state rather than enum presence.

Authority remains conceptually:

1. ApplyAI first-party / employer-direct;
2. official ATS / employer-origin source;
3. employer structured career page;
4. authorized feed;
5. broad discovery/coverage such as Open Jobs.

## Product engineering audit status

Already represented in source/repository gates:

- authentication and candidate ownership;
- user isolation tests in canonical platform flows;
- dedicated gap-closure ownership tests for portfolio projects, criteria sets, interview attempts and Resume Share insights;
- Recruiter Lens report-share owner/revocation regression tests;
- resume parser bounds/security;
- private storage abstraction;
- transactional outbox and durable queue semantics;
- idempotency, leases, retry/dead/cancel recovery;
- job provenance/freshness/closure safety;
- SSRF/redirect/response-size controls for public import paths;
- CORS fail-closed production configuration;
- public share token entropy and privacy boundaries;
- export/deletion lifecycle;
- deterministic/local provider substitutes;
- lint/typecheck/build/API/Alembic/OpenAPI/Playwright/scale/clean-room gates.

Gap-closure source completion is promoted to validated source completion only after exact-head CI passes.

## Priority decisions

### P0 — implemented on gap branch

- opt-in public candidate portfolio;
- portfolio projects/privacy controls;
- career navigation;
- skill-gap / market intelligence;
- deterministic resume intelligence.

### P1 — implemented on gap branch

- Recruiter Lens modes;
- candidate-owned reusable criteria;
- candidate-controlled Recruiter Lens report/print/share/revoke;
- Technical Interview Lab foundation;
- Resume Share anonymous session detail;
- Resume Share trends.

### P2 — useful but not production blockers

- QR sharing;
- print-intent signal;
- section-level public portfolio engagement where technically reliable;
- public resume/portfolio theme refinements;
- recruiter contact form with rate limiting and abuse controls.

### P3

Low-value visual parity and competitor-specific presentation details. Document rather than delay launch.

### DO_NOT_BUILD

Privacy-invasive viewer identity inference and employer-side automated candidate decisioning.

## Live production boundary

`CORE_REVERSE_ENGINEERING_COMPLETE` and `SAFE_HIGH_VALUE_GAPS_COMPLETE` are source-level claims only after exact-head validation. `LIVE_PRODUCTION_ACCEPTANCE` remains false until the real deployed Vercel candidate journey passes with real Clerk identity, durable database, private object storage, real job data and persistence.
