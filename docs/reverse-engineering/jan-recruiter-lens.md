---
applyai_fit: INTELLIGENCE
fit_scope: FULL
destination: career-intelligence
---

# JAN / Job Applicant Navigator → Recruiter Lens

Date reviewed: 2026-09-19

Public targets:
- https://janscreening.com/
- https://app.janscreening.com/terms

## Clean-room boundary

ApplyAI reproduces useful observable screening-assistance behavior through its own candidate-facing Recruiter Lens. It does not copy JAN source code, private prompts, customer data, proprietary scoring weights, protected-class data, or autonomous hiring decisions.

## ApplyAI Fit

**FULL — APPLYAI INTELLIGENCE**

JAN's evidence-first screening model is useful to candidates when inverted into a recruiter-perspective lens: show how verified candidate evidence maps to role criteria, where support is partial or absent, and what a recruiter may reasonably probe in an interview.

## Why this qualifies

The behavior strengthens `UNDERSTAND_FIT`, interview preparation, and career intelligence without pretending to know an employer's private ATS score or hiring decision. Public JAN material describes user-defined criteria, explained scoring, blind-first review, evidence-backed reasoning, and criteria-specific interview questions while keeping final judgment with a human.

## Candidate journey stages

- `UNDERSTAND_FIT` — see criteria-level evidence and gaps.
- `PREPARE_FOR_INTERVIEWS` — turn partial or unsupported criteria into honest probe questions.
- `MEASURE_READINESS` — distinguish supported, partial, and not-evidenced requirements.
- `CAREER_INTELLIGENCE` — understand a screening perspective without claiming hiring probability.

## Absorb into ApplyAI

- Criteria-driven recruiter-perspective review.
- Evidence-first explanations rather than keyword-only matching.
- Criteria-level support states.
- Overall 0–100 screening lens for prioritization, not hiring probability.
- Confidence and concern signals.
- Gap-derived interview questions.
- Candidate evidence provenance and identity isolation.
- Human-decision boundary.

## Keep separate

- Bulk employer resume ingestion and recruiter workflow.
- Automated rejection/advancement of real candidates.
- Protected-class criteria or identity-based ranking.
- Proprietary JAN prompts, weights, customer data, or ATS integrations.
- Any claim that ApplyAI knows the employer's actual private screening score.

## Implementation destination

`career-intelligence`

Implemented through ApplyAI Recruiter Lens and the existing verified candidate/job evidence model.

## Implementation status

**INTEGRATED — repository implementation**

Recruiter Lens is already merged into ApplyAI. It produces evidence-backed criteria assessment, support/partial/not-evidenced distinctions, concerns, confidence, and interview probes without making hiring decisions or exposing protected attributes.
