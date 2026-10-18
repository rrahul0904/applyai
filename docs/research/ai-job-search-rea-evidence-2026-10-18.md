# REA Intake — AI Job Search → ApplyAI

**Date:** 2026-10-18  
**LinkedIn evidence:** https://lnkd.in/p/gWfEZ9uv  
**Canonical upstream:** https://github.com/MadsLorentzen/ai-job-search  
**Inspected upstream revision:** 0f6480d32e59d7651d920a5ec6d78ede2f4113bf (master)  
**Upstream license:** MIT, Copyright (c) 2026 Mads Lorentzen. This first owned implementation is independently written, not a copy of upstream code. Include upstream notices if later reusing material.  
**Owned product:** rrahul0904/applyai; governance: https://github.com/rrahul0904/agent-work-os/issues/287; delivery issue: https://github.com/rrahul0904/applyai/issues/96.

## Classification and decision

**DONOR / EXTENSION TO EXISTING PRODUCT**. Do not create another job-search repo, scheduler or applicant database. ApplyAI already owns the user identity, verified candidate profile, job inventory, career scoring, resume studio, application command center, interview prep and approved third-party application handoffs. REA provides source/evidence extraction. Agent Work OS owns governance, policy, verification/replay receipts and Shipping OS gating. ApplyAI owns product and deployment.

**Lifecycle:** source verified → public capabilities inventoried → internal gap audited → first static verification component built and locally unit-tested → product integration / release still pending.

## Evidence inventory

| Source | Publicly supported behavior | Confidence and limitation |
|---|---|---|
| Upstream README.md and .claude/commands/setup.md | Import profile from CV/files, paste, or interview | Source/workflow confirmed; privacy of a live install not audited |
| Upstream .claude/commands/rank.md, add-portal.md, .agents/skills | Search several boards, normalize/dedupe, rank batches, build a portal adapter | Public design confirmed; no proof of US-scale commercial provider access |
| Upstream .claude/commands/apply.md | URL/pasted JD → fit evaluation → CV/cover → independent reviewer → revise → compile PDF → inspect → ATS text check | Instruction/workflow confirmed; effectiveness not measured |
| Upstream tools/verify_pdf.py | Extract text, inspect page counts, detect some PDF/ATS hazards | Source confirmed; not a universal ATS certification |
| Upstream .claude/commands/ | /interview, /outcome, /upskill, /expand, /html-report, /gmail-sync, /notion-sync, /add-template | Public workflow exists; live integrations not independently certified |
| Upstream SECURITY.md | Untrusted postings, local personal data, limited allowlist, no automatic send | Safeguards documented; instructions are not a sandbox |
| Original author’s LinkedIn/job-search story | 69 applications, 20 interviews, one accepted offer | Self-reported single-person result, not a measured success rate |

MIT license is evidenced by upstream LICENSE. Do not assume all third-party portals or dependencies share this license. Upstream itself cautions that automated LinkedIn guest endpoint usage conflicts with LinkedIn Terms; do not adapt it into commercial/bulk ApplyAI ingestion.

## Actual ApplyAI gap audit

| Area | Internal source evidence | Action |
|---|---|---|
| Profile/resume, matching, jobs, applications | ApplyAI README, existing APIs and model classes | Reuse, no duplication |
| Candidate-evidence application kit | services/api/app/api/application_materials.py and test_application_materials.py | Existing baseline |
| **Independent fresh-context critique** | _review_application_kit() performs deterministic same-process evidence checks, despite pipeline label REVIEW | **Gap**: distinct reviewer run, new context, immutable input, versioned findings and bounded revision |
| **PDF extraction / page audit** | _pdf_bytes produces PDF and tests assert magic/header; no durable extracted-text/page/visual release gate | **Gap**: static auditor in this branch, then wiring into artifact lifecycle |
| Job adapter extensibility | Existing Greenhouse, Lever, Ashby, SmartRecruiters and canonical job ingestion | Consider contracts/registry; prohibit auth/ToS bypass and preserve employer-origin authority |
| Interview accuracy and follow-up | Interview tools and application status state exist | Tie prep/outcomes to exact submitted CV/letter/posting snapshot, not latest mutable draft |
| Candidate-proposed email status reconciliation | Notifications exist but Gmail proposal loop not independently established | Optional, opt-in, approval-gated; do not silently write statuses |

## Target architecture

~~~text
Candidate verified evidence + canonical job posting/source
  → baseline explainable match and candidate job choice
  → durable drafter task: immutable resume + cover letter + evidence matrix
  → SEPARATE fresh-context reviewer (no shared scratchpad, distinct run ID)
  → deterministic factual/requirement evidence review
  → bounded revision and disagreement logging
  → versioned export and SHA-256 of exact generated PDF bytes
  → static PDF preflight + rendered visual inspection
  → candidate preview/edit/approval
  → first-party intake or tracked external employer handoff
  → submitted-version archive + downstream interview/outcome/follow-up
~~~

Use existing AIJobRun/AIArtifact, transactional outbox, PostgreSQL worker and candidate auth. Save reviewer run identity, input SHA, model/schema version, verified evidence refs, verdict, revisions, token/cost measurements and failure reasons. Do not label a same-process deterministic check as independent agent review. Job descriptions are untrusted *data*, never tool instructions. Model outputs cannot authorize writes or profile fact changes.

## New first executable slice

- services/api/app/ai/application_pdf_audit.py: independent, read-only static document verification using ApplyAI’s existing pypdf dependency. Checks PDF validity/size, parseability/encryption, resume <=2 pages, cover letter <=1 page, extractable text, name/email presence, verified phrases and non-ASCII year ranges.
- services/api/tests/test_application_pdf_audit.py: 6 isolated offline unit tests, with pass and negative cases (overflow, absent evidence, corrupt file, size, kind validation).
- Emits SHA-256, verdict and named check results without raw candidate text or contact details. **visual_inspection is explicitly NOT_PERFORMED**; text extraction does not prove rendering or ATS acceptance.
- Local authoring-environment test: 6 passed. It is *not yet connected to existing PDF download/application readiness endpoints*, and full CI has not been run against this GitHub branch at this point.

## Phased release checklist

### P0 — Research and safe prototype
- [x] Resolve original source and inspect exact upstream SHA and MIT license.
- [x] Map donor into existing ApplyAI repo, not a clone.
- [x] Identify deterministic reviewer and missing PDF-release-check gaps.
- [x] Build offline, non-PII PDF preflight and tests; establish governance/work issues.
- [ ] Branch exact-head CI and repository integration confirmation.

### P1 — Real independent review
- [ ] Versioned review request/result schema (evidence refs, immutable source hashes, structured issues).
- [ ] Fresh-context reviewer as a distinct durable task with no drafter scratchpad access.
- [ ] Bounded iterations, disagreement/evidence conflict tests, fail-closed provider errors and cost ceilings.
- [ ] Candidate edit/approval persisted independently from model verdict.

### P2 — Candidate document release
- [ ] Attach preflight result to exact exported bytes, and fail closed on mismatched SHA/page/text errors.
- [ ] Render and inspect pages for clipping, font glyphs, reading order, layout and overflow.
- [ ] Show actionable findings in Resume Studio, web and mobile.
- [ ] Templates as sandboxed build jobs; no arbitrary model-generated commands.

### P3 — Discovery and experience integration
- [ ] One reviewed source capability contract for search/detail, normalization, authority, robots and ToS.
- [ ] Distinguish unreachable jobs from positively closed jobs; respect fetch quotas and source precedence.
- [ ] Persist submitted CV/letter/posting snapshot for accurate later interview stage coaching.
- [ ] Optional Gmail outcome suggestions only with consent, message provenance and candidate approval.

### P4 — Certification and shipping
- [ ] Golden factual-grounding and reviewer-independence evals; fake evidence and prompt-injection tests.
- [ ] DB/auth/privacy, API, worker failure/retry, DOC/PDF fidelity and browser/mobile UAT.
- [ ] Quality measures: unsupported-claim rate, PDF text/page/visual defect rate, review revisions, document version consistency, cost/latency, failed-runs recovery.
- [ ] External job-board provider acceptance and explicit deployment receipts/URL.
- [ ] Shipping OS approval before merge/release. No claim of production feature parity without this evidence.

## Smallest next owned action

Wire the PDF auditor into versioned generated document artifacts and candidate preview, and make document readiness fail closed when the PDF hash or quality checks disagree. In parallel define a distinct fresh-context reviewer invocation. Avoid adding a new pipeline, database, or automated third-party submission path.
