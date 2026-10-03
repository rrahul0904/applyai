# Jev Job Search — reverse-engineering donor

## Source

- Reddit: https://www.reddit.com/r/SideProject/s/iBACIRmQvO
- Upstream repository: https://github.com/qbeka/jev-job-search
- ApplyAI destination: candidate-core / application automation

## Roadmap decision

This source is a capability donor for ApplyAI, not a new standalone product. ApplyAI already owns the candidate journey for job discovery, matching, tailored materials, application execution, tracking, and interview preparation. Creating another job-search repository would fragment the product and duplicate existing work.

## Product teardown

The useful product idea is not raw application volume. The source combines four distinct responsibilities:

1. deterministic rules for facts and hard constraints;
2. typed/probabilistic decisions for bounded uncertainty;
3. generative AI for free-text application materials;
4. browser automation with verification and explicit manual fallbacks.

The Reddit discussion also raises a useful product constraint: optimizing for a headline application count can look spammy and can reduce application quality. ApplyAI should optimize for ranked fit, candidate-approved facts, truthful execution evidence, and bounded throughput instead.

## Safety contract to preserve

The donor's strongest design constraint is its explicit human boundary. ApplyAI should not create accounts, bypass CAPTCHAs or verification codes, sign or make legal attestations for a candidate, silently invent facts, or call a submission successful without evidence.

## Gap found in ApplyAI

The existing ApplyAI browser worker already stops for CAPTCHA/security challenges, unverified documents, unmapped required fields, and missing controls. However, it previously selected the next/submit control immediately after filling. Candidate approval therefore did not prove that the employer form still contained the same values at click time.

## Phase 1 implementation

Branch: `feat/jev-verified-application-submit`

Implemented:

- browser read-back verification before every next/submit action;
- normalized comparison for text, select, checkbox, and radio controls;
- fail-closed `PRE_SUBMIT_VERIFICATION_FAILED` handoff on mismatch/unreadable values;
- explicit `LEGAL_ATTESTATION_REQUIRED` human handoff for certification/signature fields;
- terminal browser evidence containing `pre_submit_verified`, `verified_field_ids`, and per-page verification receipts;
- regression tests locking the ordering and human-only boundaries.

## Deliberately not copied

- application-count marketing as a primary product goal;
- autonomous CAPTCHA/security-challenge handling;
- automated signatures or legal attestations;
- silent generation of unsupported candidate facts;
- a separate job-search dashboard or duplicate repository.

## Next phases

1. Enforce the verification receipt server-side before accepting `SUBMITTED` or `CONFIRMED` browser completion.
2. Add typed routing (`AUTO`, `MANUAL`, `SKIP`) as an explicit execution contract rather than inferring it only from workflow state.
3. Add provider-specific browser fixtures for Greenhouse, Lever, Workday, Ashby, SmartRecruiters, iCIMS, and SuccessFactors.
4. Add browser-level negative tests for read-back mismatch, dynamic field mutation, multi-page forms, legal attestation, and security challenges.
5. Evaluate application-quality/ranking metrics separately from throughput.

## Tracker gate

Do not mark this donor `INTEGRATED` solely because this document or branch exists. Integration requires exact-head CI evidence and, where the changed runtime is deployed, deployment/runtime evidence. Until those gates are satisfied, the truthful status is `IMPLEMENTING`.
