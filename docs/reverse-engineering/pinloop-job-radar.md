---
applyai_fit: CORE
fit_scope: PARTIAL
destination: candidate-core
---

# Pinloop → ApplyAI Job Radar

Date reviewed: 2026-09-17

Public targets:
- https://www.reddit.com/r/AgentsOfAI/s/TMzCnSDrbt
- https://github.com/pinloop-ai/pinloop-cli

## Clean-room boundary

Pinloop is used as a public behavioral and architectural reference. ApplyAI should reproduce only the useful candidate workflow through ApplyAI's own job supply, candidate evidence, matching engine, AI runtime, and UI. The standalone CLI shell, Pinloop-hosted backend, authentication/billing model, private job corpus, command grammar, and product branding remain separate.

The public Pinloop CLI is MIT licensed, while the hosted service and job corpus are not an implementation dependency for ApplyAI.

## ApplyAI Fit

**PARTIAL — APPLYAI CORE**

The qualifying idea is the agent-first job-search loop: repeatedly surface fresh jobs, judge them against candidate context, preserve an explainable verdict, and reduce a large search surface into a small high-signal queue. That directly strengthens ApplyAI's `DISCOVER_JOBS`, `UNDERSTAND_FIT`, and career-intelligence journey.

ApplyAI already owns the deeper primitives: governed job supply and provenance, semantic matching, Career Intelligence V2, verified career memory, idempotent AI runs, worker/outbox execution, and the candidate recommendation workspace. The correct integration is therefore a Radar layer, not a Pinloop clone.

## Why this qualifies

The capability addresses a core candidate problem: job supply is abundant, but attention is scarce. A recurring judgment loop can identify newly discovered roles that deserve review before the candidate manually scrolls through the broader corpus.

Pinloop also demonstrates two useful trust patterns that fit ApplyAI's evidence-first design:

- verdicts behave as an ordered threshold rather than an unexplained binary decision;
- filtered or deprioritized items retain an explicit reason/coverage trail instead of silently disappearing.

ApplyAI should preserve those principles while retaining its richer Career V2 score, factors, confidence, and evidence rather than reducing decisions to Pinloop's four-word verdict vocabulary.

## Candidate journey stages

- `DISCOVER_JOBS` — prioritize newly posted or newly discovered active roles.
- `UNDERSTAND_FIT` — judge fresh roles against verified profile, preferences, skills, experience, and career-memory evidence.
- `CAREER_INTELLIGENCE` — maintain a high-signal queue with reasons, fit bands, confidence, and refresh state.
- `APPLY` — promote strong-fit roles into the existing ApplyAI job-detail, resume-tailoring, application-copilot, and interview-prep flow without auto-claiming hiring likelihood.

## Absorb into ApplyAI

- Fresh-job Radar over the existing global job supply.
- Batch judgment of recent active jobs that do not yet have a current Career V2 match for the candidate.
- Reuse of the existing `AI_DEEP_MATCH` task, idempotent AI-run model, outbox, and worker runtime.
- High-signal Radar buckets:
  - `TOP_MATCH` for Career V2 `APPLY_NOW` / `STRONG` decisions.
  - `WATCH` for `CONSIDER`.
  - `PENDING_JUDGMENT` for fresh roles not yet evaluated.
  - `LOW_PRIORITY` for current evidence that does not justify promotion.
- Explainable reasons derived from existing Career V2 factors/evidence.
- Coverage counts so candidates can see what is promoted, waiting, watched, or deprioritized.
- Candidate-facing Radar controls and promoted fresh roles on the existing `/matches` experience.
- Periodic page-level refresh without replacing the established semantic + Career V2 recommendation list.

## Keep separate

- Pinloop's standalone CLI shell and command syntax.
- Pinloop-hosted API, authentication, billing, plans, and account model.
- Pinloop's private/hosted job database or any dependency on it.
- A second ApplyAI crawler, job corpus, matching engine, or AI runtime.
- Any implication that an ApplyAI fit score predicts interview selection, offer probability, or hiring outcomes.
- Durable unattended schedules/watches until they are implemented through ApplyAI's governed agent runtime and certified separately.

## Implementation destination

`candidate-core`

Repository implementation targets:

- `services/api/app/api/career_radar.py`
- `services/api/tests/test_career_radar.py`
- `services/api/scripts/register_pinloop_research.py`
- `apps/web/lib/api/client.ts`
- `apps/web/components/recommended-jobs-view.tsx`

The implementation is intentionally migration-free for this slice. Radar derives from existing `jobs`, `career_matches`, and `ai_job_runs` state.

## Implementation status

**IMPLEMENTED IN DRAFT PR — certification pending**

Current repository behavior includes:

- `GET /api/v1/career-v2/radar` for recent active jobs, current Career V2 judgments, Radar buckets, counts, and explainable reasons.
- `POST /api/v1/career-v2/radar/refresh` to select recent active jobs without a current `applyai-hybrid-fit-v2` row and queue existing `AI_DEEP_MATCH` runs.
- ApplyAI Job Radar on `/matches`, with fresh-role counts, manual judgment refresh, periodic page refresh, and a compact top/pending queue above the existing recommendations.
- Backend tests for fresh unmatched-job judgment and skip-already-judged behavior.
- An idempotent reverse-engineering registry script that records the source, ApplyAI fit, qualifying/excluded capabilities, and implementation target.

Repository CI and preview/browser evidence remain certification boundaries. This document does not claim that the draft PR is merge-ready until those checks pass.

A bounded follow-on can add governed unattended schedules/watches and durable transition history such as when a job enters or leaves `TOP_MATCH`. Those capabilities are explicitly not claimed by this slice.
