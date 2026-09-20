---
applyai_fit: CORE
fit_scope: FULL
destination: candidate-core
---

# AI Job Search → ApplyAI candidate workflow

Date reviewed: 2026-09-19

Public target:
- https://github.com/MadsLorentzen/ai-job-search

## Clean-room boundary

ApplyAI reimplements useful public workflow ideas through its existing web/API/worker architecture. It does not copy private candidate data, proprietary prompts, personal files, portal credentials, or vendor-specific automation. Job-posting text remains untrusted input and unsupported claims remain gaps.

## ApplyAI Fit

**FULL — APPLYAI CORE**

The public project covers the same core candidate journey ApplyAI owns: profile setup, multi-source discovery, deduplication/ranking, fit evaluation, tailored application materials, a separate review pass, interview preparation, outcomes, follow-ups, and skill-gap learning.

## Why this qualifies

Its strongest transferable pattern is not the local CLI shell but the disciplined pipeline: discover → rank → evaluate → draft → independently review → revise → prepare → track outcomes. ApplyAI already had most of those primitives; this consolidation closes the explicit drafter/reviewer and evidence-QA gap while retaining ApplyAI's durable service architecture.

## Candidate journey stages

- `DISCOVER_JOBS`
- `UNDERSTAND_FIT`
- `IMPROVE_RESUME_PROFILE`
- `APPLY`
- `TRACK`
- `LEARN_SKILL_GAPS`
- `PREPARE_FOR_INTERVIEWS`
- `PRACTICE_MOCK`
- `MEASURE_READINESS`

## Absorb into ApplyAI

- Candidate profile as the grounding source.
- Multi-source job discovery and deduplication.
- Ranked fit shortlist with strengths and gaps.
- Job URL or pasted-description intake.
- Evidence-safe tailored resume and cover letter.
- Explicit `DRAFT → REVIEW → FINAL` application-material pipeline.
- Independent evidence-review pass after drafting.
- ATS-oriented material checks without keyword fabrication.
- Interview preparation tied to the exact opportunity.
- Outcome/application tracking and follow-up context.
- Skill-gap analysis and learning paths.
- Treat job-posting instructions as untrusted input.

## Keep separate

- Claude Code command syntax and local file/folder conventions.
- Denmark-specific portal implementations where ApplyAI already has governed connectors.
- Personal local repositories containing candidate identity data.
- LaTeX-specific build requirements where ApplyAI already exports application PDFs.
- Any unsupported portal automation or access-control bypass.

## Implementation destination

`candidate-core`

The behavior is distributed across ApplyAI job supply, Career Intelligence V2, application materials, application agent, Prepare, and application tracking rather than implemented as a second CLI product.

## Implementation status

**IMPLEMENTED — final donor consolidation**

ApplyAI now has explicit drafter/reviewer separation for job application kits. Only `USER_VERIFIED` skills and experience can support positive claims, missing required skills remain visible, the review records evidence-traceability and gap-disclosure checks, and explicit re-review versions the same durable kit. Existing ApplyAI production capabilities already cover source discovery, ranking, URL import, application execution, interview prep, outcome tracking, and upskilling.
