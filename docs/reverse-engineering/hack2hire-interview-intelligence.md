---
applyai_fit: PREPARE
fit_scope: PARTIAL
destination: prepare
---

# Hack2Hire-style interview intelligence

## ApplyAI Fit

**APPLYAI — PREPARE / PARTIAL.** The question intelligence, company patterns, evidence provenance, coaching and candidate-reporting behaviors belong in ApplyAI; arbitrary execution infrastructure and unrelated referral growth do not.

## Why this qualifies

Candidates benefit from evidence-backed company collections, recurring question patterns, track and difficulty filters, recency/confidence, staged hints, durable practice progress and job-specific preparation plans. Those behaviors improve preparation without changing ApplyAI's core application workflow.

## Candidate journey stages

- understand fit
- prepare for interviews
- practice/mock
- measure readiness
- manage career intelligence

## Absorb into ApplyAI

- question bank across Coding, SQL, System Design, ML System Design, OOD and Behavioral tracks
- company collections with frequency, recency and confidence evidence
- durable question attempts and progress
- staged coaching/hints
- candidate interview-experience reports with fingerprinting, moderation and provenance
- operator moderation using the existing operator-or-internal authorization boundary
- evidence links that recompute aggregates from remaining evidence so unlinking is reversible
- candidate community discussion around interview experience

## Keep separate

- arbitrary local code execution in the ApplyAI API process
- embedded SQL execution
- a dedicated execution product; use the existing Rigor/external isolated execution boundary when configured
- referral-credit growth mechanics, which do not materially strengthen the candidate journey
- copied proprietary question banks or unlicensed source content

## Implementation destination

Add an Interview Intelligence layer alongside ApplyAI Prepare, reuse the existing mock interview/readiness stack for execution and scoring, and expose operator moderation through the existing admin authorization model.

## Implementation status

**INTEGRATING.** The older experimental PR #41 is not being merged wholesale. Its qualifying behavior is being reimplemented against current `main`, with its open authorization, moderation, aggregate-reversal and execution-boundary review issues resolved by design.