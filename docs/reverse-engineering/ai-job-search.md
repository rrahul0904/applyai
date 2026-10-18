---
applyai_fit: CORE
fit_scope: FULL
destination: candidate-core
---

# AI Job Search → ApplyAI candidate workflow

Date reviewed: 2026-09-19; re-audited: 2026-10-18

Public target:
- https://github.com/MadsLorentzen/ai-job-search
- https://lnkd.in/p/gWfEZ9uv (2026-10-18 LinkedIn share)
- Exact re-audit upstream master SHA: 0f6480d32e59d7651d920a5ec6d78ede2f4113bf (MIT)

## Clean-room boundary

ApplyAI reimplements useful public workflow ideas through its existing web/API/worker architecture. It does not copy private candidate data, proprietary prompts, personal files, portal credentials, or vendor-specific automation. Job-posting text remains untrusted input and unsupported claims remain gaps.

## ApplyAI Fit

**FULL — APPLYAI CORE**

The public project covers the same core candidate journey ApplyAI owns: profile setup, multi-source discovery, deduplication/ranking, fit evaluation, tailored application materials, a separate review pass, interview preparation, outcomes, follow-ups, and skill-gap learning.

## Why this qualifies

Its strongest transferable pattern is not the local CLI shell but the disciplined pipeline: discover → rank → evaluate → draft → independently review → revise → prepare → track outcomes. ApplyAI already had most of those primitives, but an October 2026 source audit found a remaining difference: its application-kit REVIEW stage is a deterministic in-process evidence check, not an independent fresh-context agent. Static PDF text/page verification is not integrated into the export gate. These are implementation gaps, not completed donor parity.

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
- Independent, fresh-context reviewer pass after drafting (**required enhancement; not yet implemented**).
- ATS-oriented evidence-safe material checks without keyword fabrication; add an explicit exported-PDF extraction/page/visual quality gate (**required enhancement**).
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

**PARTIAL — canonical candidate journeys exist; independent reviewer and exported PDF release QA NOT certified.**

The September 2026 summary previously described this donor as fully implemented. Source-level re-audit on 2026-10-18 found:

- Existing ApplyAI application kit does produce a tailored resume/cover letter, applies only USER_VERIFIED experience and skills to positive claims, discloses missing required skills and persists a deterministic gap/provenance review.
- The deterministic checker is called applyai-evidence-review-v1 in services/api/app/api/application_materials.py, but it is invoked in the same process on the drafted content. The label DRAFT -> REVIEW -> FINAL does **not** establish an isolated second AI context.
- Existing PDF export is tested for basic PDF bytes, not a durable ATS text-extraction, page count, rendered visual or version-bound release gate.
- New read-only application PDF audit has been developed on branch rea/ai-job-search-quality-gates-20261018, with six isolated offline tests passing in the authoring environment. It is **not yet wired into the application APIs** and does not claim visual inspection or universal ATS compatibility.
- The authenticated candidate application approval and third-party handoff policies remain required. No autonomous bulk portal scraping or third-party application submission is inferred from this donor.

Evidence ledger and step-by-step roadmap: [October 18 REA research audit](../research/ai-job-search-rea-evidence-2026-10-18.md).

Canonical governance: [Agent Work OS #287](https://github.com/rrahul0904/agent-work-os/issues/287).
Implementation tracking: [ApplyAI #96](https://github.com/rrahul0904/applyai/issues/96).

Do not mark donor parity or production release complete until an independent reviewer task, exact exported-document QA integration, full CI/UAT, source-provider acceptance and Shipping OS deployment receipts are independently verified.
