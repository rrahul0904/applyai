---
applyai_fit: INFRASTRUCTURE
fit_scope: PARTIAL
destination: platform-infrastructure
---

# Camouflet Skills / Terum Skills / Claude Skills Evaluation

Date reviewed: 2026-09-17

Public targets:
- https://www.reddit.com/r/claudeskills/s/Aeu7i3iWZj
- https://github.com/ryanliu-terum/terum-skills

## Clean-room boundary

This summary records publicly observable behavior and open-source architectural evidence. ApplyAI should reproduce only the useful behavior through its own product model and existing governed runtime. The generic skill marketplace, desktop library, branding, and unrelated team-distribution UX are not ApplyAI product requirements.

## ApplyAI Fit

**PARTIAL — APPLYAI INFRASTRUCTURE**

The Camouflet Skills thread maps to the public Terum Skills evaluation work. It is not a candidate-facing ApplyAI feature by itself. Its evaluation and certification mechanics qualify because they can measure whether ApplyAI agents, prompts, skills, and career workflows improve rather than regress.

## Why this qualifies

The relevant behavior is controlled baseline-versus-candidate evaluation with repeatable checks, regression detection, provenance, content-bound receipts, trigger precision/recall, cost/latency evidence, and explicit release verdicts. Those capabilities strengthen ApplyAI's governed agent runtime and can certify changes to resume, job-ranking, interview, application, and career-intelligence workflows.

## Candidate journey stages

- `MEASURE_READINESS` — indirect platform support: the same evidence discipline can certify readiness-scoring and preparation agents.
- All candidate stages benefit indirectly when their supporting agent behavior is regression-tested before release.

## Absorb into ApplyAI

- Agent/skill A/B evaluation.
- Baseline-versus-candidate testing.
- Regression detection.
- Immutable evaluation receipts tied to exact evaluated content/version.
- Provenance for engine, model, dataset, and run configuration.
- Trigger precision and recall.
- Cost and latency measurements.
- PASS / NEUTRAL / FAIL release gates.
- Shareable internal evaluation evidence for operator review.

## Keep separate

- Generic Claude skill marketplace.
- Generic desktop skill library.
- General-purpose team skill distribution.
- Camouflet/Terum-specific branding and generic skill-library UI.
- Any behavior that does not improve ApplyAI's candidate journey or platform quality.

## Implementation destination

`platform-infrastructure`

The first ApplyAI destination is the existing governed-agent and AI-evaluation layer. The reverse-engineering registry itself records this decision and keeps the non-ApplyAI boundary explicit.

## Implementation status

**INTEGRATED — repository implementation**

This slice implements the ApplyAI Fit registry and deterministic classifier plus the Terum-inspired baseline/candidate release evaluator. The evaluator records content-bound immutable receipts, regression verdicts, trigger precision/recall, cost and latency deltas, provenance, execution completeness, and a fail-closed release gate for partial or regressing runs.

Repository tests certify the deterministic scoring contract once CI passes. A live hosted run against production agents/models remains a separate release-evidence boundary and must not be inferred from repository code alone.
