---
applyai_fit: CORE
fit_scope: PARTIAL
destination: candidate-career-intelligence
---

# RE-370 — Workmark capability-donor research

Date reviewed: 2026-10-01 (America/New_York)

Public targets:
- https://www.reddit.com/r/IMadeThis/comments/1wv75s1/i_made_a_resum%C3%A9_that_finds_work_for_you_for_cs/
- https://www.workmark.org/
- https://www.workmark.org/how-it-works
- https://www.workmark.org/levels
- https://www.workmark.org/business
- https://www.workmark.org/privacy

## Clean-room boundary

This summary records publicly observable product behavior and first-party claims. It does not infer or copy private Workmark source code, prompts, model weights, database schema, ranking logic, production scale, or hiring-outcome accuracy. The ApplyAI implementation is independently authored and deliberately exposes deterministic evidence receipts rather than claiming Workmark parity.

## Research findings

The Reddit launch describes Workmark as a CS-student / entry-level career product that connects GitHub, derives skills from work already built, creates a roadmap, and matches users to jobs, internships, hackathons, fellowships, open-source work, events, and student perks. At review time the launch post had zero comments, so there was no direct community feedback to incorporate.

Workmark's first-party pages describe a loop of user-selected repositories, proof-based skill records, evidence depth, skill gaps, guided projects, opportunity matching, and an opt-in employer view. Its public methodology says repository evidence can include manifests/build files, import relationships, commit dates/authorship, and tests, while its public copy says source-code bodies are not read/stored. Its level model distinguishes evidence depth and reserves later confirmation-style levels for stronger collaborator/dependency evidence.

The privacy page describes GitHub as an external source after authorization and repository selection and names service providers, but these disclosures are not evidence of Workmark's private implementation architecture.

Public comparator repositories reviewed during the market scan included SkillSync, campus-opportunity-recommender, KaushalSetu, and CodeMeet. They reinforce a broader market pattern around GitHub/CV evidence, skill-gap analysis, explainable matching, and project-based recruiting. The capability donor selected for ApplyAI is specifically the proof-of-work → evidence depth → role gap → guided next-build loop.

## ApplyAI Fit

**PARTIAL — CORE CANDIDATE CAREER INTELLIGENCE**

ApplyAI already owns candidate portfolio, Career Intelligence, job matching, opportunity ingestion, employer workflows, privacy/export, and evidence-aware application/resume surfaces. Rebuilding Workmark as a second standalone career platform would duplicate those systems. The useful donor capability is the missing GitHub proof-of-work loop that can strengthen ApplyAI's existing evidence model.

## Why this qualifies

The donor behavior converts evidence a candidate already controls into attributable career signals, makes missing evidence explicit, and recommends a bounded next project rather than inventing experience. That directly improves ApplyAI's evidence-first portfolio and preparation journey while preserving candidate agency and a human hiring-decision boundary.

## Candidate journey stages

- `BUILD_PROFILE` — connect selected work and retain repository-level evidence receipts.
- `MEASURE_READINESS` — compare observed signals with a transparent target-role checklist.
- `BUILD_EVIDENCE` — turn an unmet evidence area into a scoped next-build brief.
- `MATCH_OPPORTUNITIES` — later use candidate-approved proof signals as one explainable input to existing ApplyAI matching.
- `PRESENT_EVIDENCE` — later expose candidate-controlled proof to portfolio/employer surfaces with consent and dispute controls.

## Absorb into ApplyAI

- User-controlled GitHub repository evidence.
- Deterministic, attributable skill signals.
- Evidence-depth recurrence across repositories.
- Transparent target-role gaps.
- Guided next-build recommendations with acceptance criteria.
- Evidence receipts that can feed existing portfolio and Career Intelligence surfaces.
- Candidate-controlled publication / employer exposure in a later phase.
- Dispute and evidence-review controls in a later phase.

## Keep separate

- Workmark branding and proprietary implementation.
- Any hidden or reverse-engineered private scoring formula.
- Opaque candidate ranking or hiring probability.
- Unsupported proficiency claims.
- Automatic application behavior.
- A duplicate job marketplace or duplicate employer product.
- Claims of Workmark parity, production scale, or hiring-outcome accuracy.

## Implementation destination

`candidate-career-intelligence`

Phase A is implemented as a public ApplyAI Proof of Work Lab at `/proof-of-work`, backed by `/api/proof-of-work/github` and a deterministic evidence library. The next integration destination is the existing candidate portfolio and matching data model after private-repository consent and evidence persistence are designed.

## Implementation status

**PHASE A PROTOTYPE IMPLEMENTED — exact-head preview runtime verified; repository-wide gates still being evaluated**

Phase A:
- accepts a public GitHub username plus target role;
- scans at most six recent owned, non-fork, non-archived public repositories;
- reads repository metadata and root artifact names only;
- derives deterministic signals for languages, testing, CI/CD, containers, data/migrations, infrastructure and build markers;
- aggregates recurrence as `Observed`, `Repeated`, or `Sustained` evidence depth;
- exposes the exact repositories supporting each signal;
- compares evidence with a transparent role checklist;
- turns the first unmet area into one bounded next-build recommendation with acceptance criteria;
- does not write to GitHub and does not produce an opaque hiring/proficiency score;
- includes focused deterministic tests.

Issue: #81
PR: #82
Feature branch: `reverse/workmark-proof-of-work`

The first exact-head preview successfully rendered `/proof-of-work` and returned a live HTTP 200 GitHub evidence report from the API. Repository-wide security audits currently also report dependency advisories that pre-existed this Phase A feature and are tracked separately from the donor slice.

## Phase B gaps

- Read-only GitHub App / OAuth with candidate-controlled private repository selection.
- Stronger commit/authorship/test/CI receipts without reading arbitrary source bodies.
- Persisted candidate consent, evidence challenges, and revocation.
- Integration into the canonical ApplyAI portfolio and Career Intelligence stores.
- Guided project task verification and completion receipts.
- Existing ApplyAI opportunity matching using evidence as an explainable input.
- Candidate-controlled employer exposure.
- Evaluation/calibration for false-positive and false-negative evidence signals.
