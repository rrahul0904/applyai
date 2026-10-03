---
applyai_fit: CORE
fit_scope: PARTIAL
destination: candidate-core
---

# Jev Job Search — reverse-engineering donor

## Source

- Reddit: https://www.reddit.com/r/SideProject/s/iBACIRmQvO
- Upstream repository: https://github.com/qbeka/jev-job-search
- ApplyAI destination: candidate-core / application automation

## ApplyAI Fit

**CORE / PARTIAL.** This is a capability donor for ApplyAI's existing application automation journey, not a new standalone job-search product.

## Why this qualifies

The useful product idea is not raw application volume. The source separates deterministic facts and hard constraints, typed/probabilistic bounded decisions, generative free-text work, and browser automation with read-back verification plus explicit manual fallbacks.

The Reddit discussion also raises a useful product constraint: optimizing for a headline application count can look spammy and can reduce application quality. ApplyAI should optimize for ranked fit, candidate-approved facts, truthful execution evidence, and bounded throughput instead.

The donor's strongest design constraint is its explicit human boundary. ApplyAI should not create accounts, bypass CAPTCHAs or verification codes, sign or make legal attestations for a candidate, silently invent facts, or call a submission successful without evidence.

The existing ApplyAI browser worker already stopped for CAPTCHA/security challenges, unverified documents, unmapped required fields, and missing controls. However, it previously selected the next/submit control immediately after filling, and the API accepted a terminal browser status without independently requiring a read-back receipt. Candidate approval therefore did not prove that the employer form still contained the same values at click time or that a reported terminal outcome had passed verification.

## Candidate journey stages

- `APPLY`
- `TRACK` through durable submission evidence and manual-handoff state
- `UNDERSTAND_FIT` as a later quality/ranking extension rather than a throughput target

## Absorb into ApplyAI

Phase 1 on branch `feat/jev-verified-application-submit` adds:

- browser read-back verification before every next/submit action;
- normalized comparison for text, select, checkbox, and radio controls;
- fail-closed `PRE_SUBMIT_VERIFICATION_FAILED` handoff on mismatch/unreadable values;
- explicit `LEGAL_ATTESTATION_REQUIRED` human handoff for certification/signature fields;
- terminal browser evidence containing `pre_submit_verified`, `verified_field_ids`, and per-page verification receipts;
- server-side rejection of `SUBMITTED` or `CONFIRMED` completion unless the browser supplies `pre_submit_verified=true`;
- route-order regression coverage proving the guarded completion endpoint is registered before the legacy completion endpoint;
- regression tests locking the ordering and human-only boundaries.

Follow-on slices:

1. Add typed routing (`AUTO`, `MANUAL`, `SKIP`) as an explicit execution contract rather than inferring it only from workflow state.
2. Add provider-specific browser fixtures for Greenhouse, Lever, Workday, Ashby, SmartRecruiters, iCIMS, and SuccessFactors.
3. Add browser-level negative tests for read-back mismatch, dynamic field mutation, multi-page forms, legal attestation, and security challenges.
4. Evaluate application-quality/ranking metrics separately from throughput.
5. Add bounded one-job-at-a-time pacing and per-provider rate controls where runtime evidence shows they are required.

## Keep separate

- application-count marketing as a primary product goal;
- autonomous CAPTCHA/security-challenge handling;
- automated signatures or legal attestations;
- silent generation of unsupported candidate facts;
- a separate job-search dashboard or duplicate repository.

## Implementation destination

`rrahul0904/applyai`, candidate-core application agent and browser worker. Reuse ApplyAI's existing candidate profile, answer memory, tailored-document, application execution, and tracking models rather than introducing a parallel store or service.

## Implementation status

`IMPLEMENTING`.

The Phase 1 repository slice now closes both sides of the verification contract: the worker verifies the employer form before navigation/submission, and the API refuses terminal success without that receipt. Do not mark this donor `INTEGRATED` solely because the document, branch, or PR exists. Integration still requires exact-head CI evidence and, because the changed path includes the browser worker, deployment/runtime evidence from the exact candidate SHA. Until those gates are satisfied, the truthful status remains `IMPLEMENTING`.
