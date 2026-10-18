# ScoutWand donor -> ApplyAI applicant-controlled local application helper

Governance: https://github.com/rrahul0904/agent-work-os/issues/290  
Snapshot 2026-10-18. Sources: https://www.reddit.com/r/IMadeThis/comments/1x9eqce/ , https://www.scoutwand.com/  
Decision: **DONOR / EXISTING_PRODUCT_EXTENSION** to ApplyAI, never a separate ScoutWand clone.

## Publicly observed / advertised behavior
- Windows/macOS desktop download.
- User gives desired jobs + locations and optionally CV; claims LinkedIn, Indeed and InfoJobs search and fit-ranked listing suggestions.
- Opens supported listing in integrated browser and populates fields (name/location/phone etc) from local CV; user must review and click Apply.
- Paid signed-license mechanism with offline checks between renewals is claimed; local storage of CV, form data and sessions is claimed; device key/email/license and daily counter are sent to service.
- Free allowance 5 listings per day. Monthly plan €10.99, two devices.
- Critical vendor disclosure: browser automation may violate target site's Terms of Service and may lead to account restrictions. This is a *first-class product/legal constraint*, not a challenge to bypass.

## Owned ApplyAI baseline
Read the repo's README and use the existing lean architecture: Next.js candidate web + Expo RN mobile + MV3 browser extension; Railway FastAPI + PostgreSQL + durable Postgres task queue + Cloudflare R2. Existing candidate job discovery, profile, resume studio, import, applications and tracking are relevant; do not create a shadow job database/account system. Existing application-kit QA and user approval should precede field reuse. Platform support claims only after actual packaging tests.

## Scope: Guided Apply desktop/extension contract
```text
candidate opt-in
   -> local profile vault / minimal authorized credentials
   -> permitted job source (company feed or explicitly supported board)
   -> normalize + dedupe canonical job URL -> score with evidence
   -> job detail + tailored and reviewed CV/application kit
   -> open user-navigated authorized page
   -> extract visible form labels (no hidden credentials)
   -> map verified profile facts to each field
   -> preview JSON diff and provenance/confidence
   -> user clicks "Fill" for supported fields
   -> applicant reviews + manually submits on target site
   -> applicant explicitly marks applied / optional consented tracker sync
```

### Neutral contracts proposed (clean room)
- `JobSourceCapability`: source_id, allowed_data_access_modes, robots_tos_review, authorization_scope, domain_allowlist, provenance, read_budget.
- `LocalApplicantProfile`: schema_version, values, source_document_hash, last_reviewed_at, expiry, consent policy. Persistent on device; sensitive raw values not logged/uploaded without specific consent.
- `FieldSuggestion`: field_locator_stable_id, display_label, target_type, proposed_value_ref, evidence_ref, confidence, requires_user_input, sensitive_class, abstain_reason.
- `FillPlan`: job_id, origin, form_fingerprint, suggestions, missing_fields, warnings, user_approval_timestamp, expiration.
- `ApplicationDraftReceipt`: job_id, fingerprint, kit_version, fields_filled_count, fields_abstained_count, explicit_review_event; NEVER represents submitted unless user confirms verified result.
- `PermissionPolicy`: per-domain allowlist, read/form-fill-only, no form submission capability and no bypass.
No static output or logs may contain real applicant name/contact/resume contents.

## Competitive check and differentiation
Simplify Copilot publicly advertises broad ATS autofill, resume matching and application tracking; Teal competes on resume tailoring and application organization. Build a better trust and reasoning loop: evidence-locked answer mapping, privacy-safe vault, domain-by-domain compatibility receipts, annotated abstentions, credential isolation, manual application handoff and outcomes.

## Work packages
- P0: code audit across `apps/extension`, `services/api` and local stack; inspect existing job capture/autofill to avoid duplicate features.
- P0: classify approved job source methods and third-party terms; block unsupported scraping/login automation in product policy.
- P0: offline synthetic form corpus (simple, multi-step, checkboxes, dropdown, upload, language/locale variants, unusual field names, missing and high-stakes optional fields).
- P0: deterministic form identification and field suggestions; prefer stable semantics/labels not brittle positional selectors.
- P0: reviewed, candidate-approved preview of every field before local fill. Leave EEO, disability, work authorization, salary and other sensitive fields blank by default unless the user explicitly confirms per field.
- P1: optional user-approved local desktop companion (Tauri/Electron selection only after test and security assessment) for Windows/macOS. Mobile remains job discovery/tracking; do not advertise mobile browser autofill without capability evidence.
- P1: retry-once-on-navigation, visual mismatch warning and safe abort on form drift.
- P1: portable match results + consented tracking in existing ApplyAI; integration tests for job matching and resume artifact QA.
- P2: signed offline-capability tokens if needed, without copying ScoutWand licensing structure; exact public policy, local encrypted storage with key rotation/revocation/clear all.

## Strict disallowed behaviors
NO autonomous final job-application submission. NO CAPTCHA bypass, bot-detection evasion, login credential collection, private-page scraping without access, bulk unauthorized actions or identity misrepresentation. Third-party ToS must be reviewed before any adapter goes beyond user-controlled manual navigation.

## Acceptance/QA
1. On 100 diverse synthetic authorized sample forms, precision/coverage quantified; no silent wrong field placements. Threshold must be approved before deployment.
2. All sensitive fields default to abstain without specific confirmation; no use of AI to invent qualifications/work eligibility.
3. Fail closed if origin shifts, form fingerprint mismatches, login is prompted or unsupported ATS behavior appears.
4. No code path auto-clicks final Apply/Submit; E2E enforcement test.
5. CV/profile plaintext excluded from server requests, analytics, crash logs and CI fixtures; consent and redaction tests.
6. One application cannot be duplicated by retries; idempotent linkage to existing canonical job and kit hash.
7. Manual submission receipt never asserts success based merely on a click.
8. Windows/macOS signature/notarization, browser permissions, local storage security, accessibility, offline mode and rollback require actual receipts.
9. Exact-SHA CI suite + UI/E2E and provider acceptance; then candidate opt-in staged release only after owner approval.
10. REA evidence -> implementation diff -> replay/compare -> Shipping OS gates explicitly documented.

## Current gate
Public source and owner routing completed; auth/binary inspection and UI screenshot evidence unavailable; implementation/tests/production parity not completed. Competitor code/assets presumed proprietary absent a verified license.
