# REA-ApplyAI: SealApply donor intake (2026-10-19)

Status: RESEARCH + ISOLATED PROTOTYPE; NOT MERGED, NOT RELEASED, NOT DEPLOYED.
Owner: rrahul0904/applyai. REA governance: https://github.com/rrahul0904/agent-work-os/issues/306

## 1. Canonical source identity and evidence
- Reddit: https://www.reddit.com/r/saasbuild/comments/1x9p4k8/ (poster u/Dazzling-Shopping532; product promotional description).
- Official landing: https://sealapply.com/ (public first-party marketing claims and six-stage UI walkthrough).
- Developer demo URL mentioned elsewhere: https://demo.sealapply.com/ (not accessible to this inspection tool; NOT functionally tested).
- No authorized upstream source repository, private implementation, license grant, network trace, extension bundle, or real applicant test was established.
- The landing page displays both waitlist calls-to-action and a dashboard entry. Treat live general availability as unverified.
- Evidence levels used here: OBSERVED_PUBLIC (page/text), FOUNDER_CLAIM, EXISTING_OWNED_SOURCE, PROPOSED, NOT_VERIFIED.

## 2. Capability decomposition
| Capability | Donor evidence | ApplyAI source comparison | Next action |
|---|---|---|---|
| Paste/capture job | Reddit and landing; widget claimed | README documents safe public URL import and active-tab URL-only MV3 extension | Keep safe importer; add deliberate paste fallback and reviewed capture UX |
| Parsed structured role requirements | Landing structured job detail | README documents career matching and job import; no parity test | Add golden structured-description parsing fixtures |
| Explainable job score /100 | Landing role match with sub-scores | README documents explainable deterministic match baseline and evidence-bound reranker | Map skills/education/experience/projects without pretending score is ATS acceptance probability |
| Truthful resume tailoring | Landing constrained rewrites | README documents Resume Studio, version history and AI tailoring | Compare artifact provenance, human edit controls and missing-skills UI |
| Per-line accept/reject diff | Landing specifically shows side-by-side changes | Cannot verify exact per-line diff in owned runtime from README alone | Implement traceable change hunks on a controlled route |
| Cover letter and export | Landing PDF/HTML templates | README documents cover-letter artifacts and resume exports | Verify supported formats and role-bound provenance |
| Autofill of external application fields | Landing claims 10/12 demo fields filled; leaves two unanswered | Verified apps/extension/popup.js opens /import-job URL only | Separate opt-in candidate-reviewed form assistance; NEVER auto-submit |
| Local-first data, backup, restore | Landing and Reddit describe IndexedDB/exports | ApplyAI's canonical records are server-side PostgreSQL/R2 after authentication | Design optional local draft/cache with explicit sync, expiration and export rather than replacing server source of truth |
| Provider choice / low-cost path | Landing describes Puter, Gemini, NVIDIA, OpenRouter, OpenAI, Claude | README documents provider-abstracted durable AI processing | Only add reviewed provider adapters; disclose data egress, limits, token costs and BYOK key risk |
| Application tracker | Landing has saved/applied dates and links | README documents application command center | Reuse canonical state machine; avoid duplicate local/server application records |

## 3. Owned architecture (proposed; not upstream reverse-compiled)
1. Job intake: active-tab URL or user-pasted description -> explicit candidate click -> existing ApplyAI safe import pipeline or local pasted-text parser; keep public-URL SSRF/robots/redirect constraints.
2. Evidence: normalized JobRequirement objects with source text spans, employer identity, URL, capture time, confidence and verification state. No unsupported entity fabrication.
3. Match: existing deterministic Career Intelligence -> explanation groups (skills, work history, education, projects), displayed as candidate alignment only; optionally run a reviewed AI augmentor.
4. Resume: existing Resume Studio and revision ledger -> job-specific candidate evidence selection -> constrained rewrite suggestions -> per-hunk before/after review -> versioned export. Keep missing skill as missing, never invent work or achievements.
5. Cover letter: same verified source evidence; draft+edit+approve; publish PDF/HTML only if generation tests pass.
6. Browser form assist: optional activeTab/on-click scanner reports non-secret labels/type/autocomplete locally; deterministic field mapper (new inert prototype) -> candidate preview of proposed values -> explicit fill-selected action. File uploads, sensitive questions, CAPTCHA/auth and submit are manual boundaries.
7. Application: first-party existing approved submit route OR external handoff; capture explicit user confirmation/receipt before marking externally applied. No synthetic successful-application state.
8. Audit: store provenance and candidate approvals in canonical app records when enabled; never log unredacted sensitive field values or provider API keys.

## 4. Proposed contracts
- JobEvidence: job_id, source_url, captured_at, canonical_job_id?, original_description_hash, fields[], confidence, evidence_spans[].
- MatchBreakdown: job_id, resume_version_id, dimension_scores[], supported[], partial[], missing[], evidence_refs[], score_version; never a hiring probability.
- ResumeRewriteHunk: hunk_id, revision_id, source_fact_refs[], original, proposal, reason, decision[pending/accepted/rejected], schema_version.
- FormFieldDescriptor (local-only): type, label, ariaLabel, placeholder, name, id, autocomplete; strip page values, password inputs, auth tokens and nearby non-form document text.
- FormFillSuggestion: field_key, candidate_verified_value_ref, confidence, reason, review_status; sensitive and unknown -> manual; no writes until an explicit user gesture.
- ApplicationAttempt: canonical_job_id, candidate_approved_at?, site_origin, handoff_started_at?, external_submitted_at? only with candidate/user receipt, result_status, failure_reason.

## 5. Threat and privacy boundaries
- Treat job descriptions, job-site DOM and resumes as untrusted inputs; defend against prompt injection into providers and UI.
- One-page temporary activeTab access only after candidate click. No broad host permissions, no background scraping, no silent applications, no employer-login/CAPTCHA/anti-bot circumvention.
- No contact, protected-category, authorization, salary-expectation, birthdate or identity data to an AI service by default. A variable placeholder is not sufficient proof of zero data egress; evaluate each network request and vendor separately.
- API keys, if BYOK is offered, need appropriate storage, disclosure and provider scopes; never place long-lived backend keys in distributed client code.
- Local browser data is not a durable backup by itself. Provide explicit export/import and optional encrypted sync with user-facing failure/retention messages; do not silently delete unsubmitted jobs.
- Cross-origin injection stays disabled until threat review. Browser extension never calls form.submit(), requestSubmit(), or clicks submit buttons.
- No copying any upstream CSS, illustrations, brand, text, code or unlicensed assets. Implement only generic independently specified behavior.

## 6. Staged delivery plan and objective acceptance
### P0: inspect + contracts (this branch)
- [x] Identify product and cite public source.
- [x] Route to existing ApplyAI repo; governance issue opened.
- [x] Inspect owned README, extension manifest/popup, lean architecture and release checklist.
- [x] Add isolated deterministic form field mapping prototype with Node built-in unit tests.
- [ ] Independently review candidate form-field policy and multiple locale/ATS fixtures.
### P1: candidate UX integration
- [ ] Add job-description paste + parsed evidence review to existing import job screen.
- [ ] Expose explanation breakdown and missing/verified skills based on supported facts.
- [ ] Add per-hunk resume edit preview, accept/reject and safe undo with immutable source references.
- [ ] Verify PDF/HTML and cover-letter export with structural/ATS readability tests.
### P2: opt-in extension workflow
- [ ] Build explicit local page scanner behind activeTab; no persistent host permissions.
- [ ] Redact form values and secrets; propose field mapping and confidence.
- [ ] Candidate reviews each proposed value; fill only selected non-sensitive fields after a second explicit click.
- [ ] Test synthetic fixtures for simple native forms and simulated Greenhouse/Lever/Ashby/Workday field patterns. No claim about live site integration absent a recorded, permitted acceptance run.
- [ ] Stop for unknown fields, auth challenge, CAPTCHA, attachment, ambiguous select, validation failure, or unexpected navigation.
- [ ] External submission remains manual; capture explicit receipt and avoid false applied state.
### P3: retention, providers, release
- [ ] Optional encrypted local draft/backup with import-export conflict handling.
- [ ] Provider policy, price/quotas and consent tests; do not promise unlimited free model usage.
- [ ] Mobile web fallback: paste/open job, draft/review; do not claim desktop extension behavior on mobile.
- [ ] Accessibility, privacy, abuse, Playwright synthetic flows, exact-head CI, local clean-room and live provider acceptance.
- [ ] Merge/deploy only after review, certification and existing LIVE_PREVIEW_VERIFIED/LIVE_PRODUCTION_VERIFIED gates; preserve current first-party approval contract.

## 7. Reproduction and verification receipts
- Existing extension inspected: apps/extension/manifest.json and apps/extension/popup.js; permissions activeTab, storage; popup performs URL handoff only.
- New pure prototype: apps/extension/form-assist/field-map.mjs.
- Test command (Node >=22): node --test apps/extension/form-assist/field-map.test.mjs.
- Initial local run: 5 tests passed (2026-10-19), including passwords, hidden fields, file uploads, eligibility/sensitive questions, unknowns and review-needed suggestions.
- Code is **not wired to the manifest, scanner, live UI or deployment**; these remain planned and require testing.
- Public demo not inspectable in the current environment, so no unverified real browser interactions, feature parity, latency or compatibility assertions.

## 8. Completion definition
Only call this capability shipped when candidate can paste or capture a posting; see evidence-linked fit; generate a truthful editable resume and cover letter; review each proposed rewrite; export; click an opt-in action to inspect fields on a permitted external application page; approve filled known fields; complete unknown/sensitive fields personally; submit personally on third-party sites; and track the confirmed result. Every flow needs exact-SHA test receipts and no unverified vendor promises.