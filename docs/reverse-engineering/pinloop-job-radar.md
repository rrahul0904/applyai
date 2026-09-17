# Pinloop → ApplyAI Job Radar

Status: IMPLEMENTING
ApplyAI fit: CORE (partial absorption)
Source: https://www.reddit.com/r/AgentsOfAI/s/TMzCnSDrbt
Reference CLI: https://github.com/pinloop-ai/pinloop-cli

## What Pinloop demonstrates

Pinloop packages a job-search loop for coding agents:

1. Pull newly available jobs from a large, frequently refreshed supply.
2. Keep candidate resume/preferences available as judgment context.
3. Judge postings in batches rather than requiring a human to inspect each role.
4. Persist a verdict plus reasoning.
5. Put the strongest fits into a small list for the candidate to review.
6. Support unattended/scheduled routines for recurring review.

The public CLI is MIT licensed. The CLI talks to Pinloop's hosted service; that hosted backend and its job corpus are not part of the open-source CLI license and are not an implementation dependency for ApplyAI.

## ApplyAI capability map

ApplyAI already owns the majority of the required primitives:

- Global job supply, provenance, deduplication, source policy, URL health, and closure evidence.
- Candidate profile, preferences, resume extraction, and verified career memory.
- Semantic matching.
- Career Intelligence V2 deterministic + AI deep-match scoring.
- Explainable match factors/evidence.
- Idempotent AI runs, outbox dispatch, workers, cost/latency tracking, and artifacts.
- Candidate recommendations and job-detail workflows.

Therefore this reverse-engineering slice does **not** clone Pinloop's CLI, hosted API, or external job corpus.

## Capabilities to absorb

### 1. Fresh-job radar

Continuously focus candidate attention on jobs first seen or posted recently, rather than forcing a full-corpus browse.

ApplyAI implementation: `GET /api/v1/career-v2/radar`.

### 2. Batch judgment loop

Select recent active jobs that do not yet have an `applyai-hybrid-fit-v2` match for the current candidate and enqueue deep-match runs through the existing Career V2 runtime.

ApplyAI implementation: `POST /api/v1/career-v2/radar/refresh`.

### 3. High-signal queue

Classify judged jobs into candidate-facing radar buckets:

- `TOP_MATCH`: Career V2 decision is `APPLY_NOW` or `STRONG`.
- `WATCH`: decision is `CONSIDER`.
- `PENDING_JUDGMENT`: recent role has not yet been judged.
- `LOW_PRIORITY`: current Career V2 evidence does not justify promotion.

### 4. Reason preservation

Reuse Career V2 factor explanations and evidence instead of producing a second opaque score.

### 5. Candidate surface

Expose Radar directly on the existing `/matches` experience with a manual refresh action and periodic page-level refresh. Existing semantic/Career V2 recommendations remain intact below Radar.

## Explicitly not copied

- Pinloop's CLI command grammar and agent guide.
- Pinloop authentication, billing, or hosted account model.
- Pinloop's private/hosted job database.
- Any assumption that a model score predicts hiring outcomes.
- A second crawler or separate matching engine that would duplicate ApplyAI's existing platform.

## Current implementation boundary

This first slice deliberately uses existing `jobs`, `career_matches`, and `ai_job_runs` data, so it requires no schema migration. It supports on-demand batch refresh and periodic browser refresh.

A future slice can add a durable scheduler/watch policy and transition history (for example, when a role entered or left `TOP_MATCH`) after the current API/UI behavior is validated in CI and preview. That should reuse the governed agent runtime rather than introduce a separate scheduler.

## Files

- `services/api/app/api/career_radar.py`
- `services/api/tests/test_career_radar.py`
- `services/api/scripts/register_pinloop_research.py`
- `apps/web/lib/api/client.ts`
- `apps/web/components/recommended-jobs-view.tsx`
