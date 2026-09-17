---
applyai_fit: PREPARE
fit_scope: FULL
destination: prepare
---

# Hack2Hire capability map

## ApplyAI Fit

`PREPARE / FULL`. Company-oriented interview question intelligence, practice progress, preparation plans, community interview reports and referral mechanics directly strengthen ApplyAI's interview-preparation and candidate network stages.

## Why this qualifies

The observed product mechanics connect naturally to ApplyAI's verified candidate evidence, job requirements, existing interview engine and application pipeline. The useful behavior is not a cloned question bank; it is the workflow around provenance-backed interview intelligence, practice, moderation, readiness and candidate contribution.

## Candidate journey stages

Understand fit → learn skill gaps → prepare for interviews → practice/mock → measure readiness → manage career intelligence.

## Absorb into ApplyAI

- interview tracks for coding, SQL, system design, ML system design, OOD and behavioral preparation;
- company collections with frequency, confidence and recency metadata;
- durable candidate practice attempts and progress;
- job-specific preparation plans from job requirements plus verified candidate skills;
- staged hints, solution frameworks and follow-up prompts;
- candidate interview-report submissions with provenance/fingerprinting;
- operator moderation and explicit report-to-question evidence links;
- candidate community posts/replies/reactions;
- isolated code-execution provider boundary that fails closed when not configured;
- referral code/event/credit ledger and candidate referral workspace.

## Keep separate

- proprietary or copied competitor question banks, tutorials or solutions;
- private forum content;
- arbitrary code execution inside the ApplyAI web/API process;
- automatic promotion of community submissions into canonical interview evidence.

## Implementation destination

The existing `feature/interview-intelligence` implementation line: candidate interview-prep surfaces, FastAPI interview-intelligence/referral routes, provenance models, moderation UI, migrations and isolated execution provider boundary.

## Implementation status

`IMPLEMENTED ON BRANCH; CONSOLIDATION REQUIRED`. PR #41 contains the end-to-end implementation and repository tests but is currently diverged from newer `main`. It must be ported/rebased against current production code and re-certified before merge; this summary intentionally does not claim it is live production functionality yet.
