# Rezumite capability-donor dossier

Tracking issue: #87

## Source identity

- Primary Reddit intake: https://www.reddit.com/r/SideProject/s/raKDV87O9o
- Resolved post: https://www.reddit.com/r/SideProject/comments/1x2iqqu/i_made_a_web_app_that_turns_your_cv_into_a/
- Product named by author: Rezumite — https://www.rezumite.com/
- Canonical destination: ApplyAI

This is a clean-room capability donor. It does not justify a standalone product or repository because ApplyAI already owns candidate profile, portfolio, resume ingestion, Resume Share, proof-of-work, career evidence and public-sharing concerns.

## Observed behavior

Public founder posts/comments establish the following behavior:

1. User uploads a resume PDF.
2. An LLM reads both resume content and layout to preserve role/bullet associations.
3. The resume is normalized into structured experience, skills, education, projects and related facts.
4. The extraction prompt is intended to copy facts rather than invent or embellish them.
5. The same pass can create bounded derivative copy such as a headline or short introduction.
6. Hand-authored templates consume the same structured data, so the user can switch templates without re-entering information.
7. A selected portfolio is published under a user-specific subdomain.
8. Publicly disclosed donor stack: Next.js/Vercel, Clerk, Neon and Claude. These are observations only and are not ApplyAI implementation requirements.

Public failure/feedback evidence:

- one Rezumite tester reported a failed resume upload;
- a closely adjacent resume-to-portfolio product received feedback that users could not find an obvious Update Resume control;
- the same adjacent product received feedback that users expected Change Theme in the customization flow;
- adjacent products validate demand for public URLs, custom domains, project/media proof, analytics and grounded recruiter Q&A, but those are later-phase opportunities rather than first-slice requirements.

## Existing ApplyAI baseline

The current ApplyAI release-candidate portfolio already renders candidate-controlled profile evidence and exposes Resume Share separately. It emphasizes verified evidence and does not invent career claims. The missing capability is a low-friction, explicitly publishable public Career Site generated from the existing evidence base.

## Clean-room boundary

We may independently reproduce publicly observable workflow semantics.

We must not copy donor source code, prompts, templates, visual design, branding, copy, assets, private APIs or hidden implementation. Competitor stack choices are evidence, not design instructions. ApplyAI keeps its existing canonical architecture and security model.

## Product thesis

Add an evidence-preserving public Career Site generator to ApplyAI:

> verified resume/profile -> review structured facts -> choose an original ApplyAI theme -> preview exact public state -> explicit publish -> stable public URL -> later content/theme revisions through explicit republish.

The output should be a professional portfolio, not a literal HTML copy of the resume.

## Capability decisions

### MATCH

- PDF resume ingestion
- structured experience / education / skills / projects
- one canonical profile feeding multiple original themes
- rapid preview
- stable public URL
- post-generation editing
- theme switching without re-entry

### IMPROVE

- explicit candidate approval before publishing anything
- provenance for factual fields and generated derivative copy
- generated copy cannot add unsupported facts
- field-level visibility controls
- update-resume diff review instead of silent overwrite
- revoke/unpublish and noindex controls
- deterministic slug collision handling
- durable publication/revision history
- accessible, mobile-safe, print-friendly themes
- parse/publish failures preserve the current published revision

### NEW — later releases

- role-specific portfolio variants over one evidence graph
- proof-of-work cards using ApplyAI evidence
- custom domains after the base publish flow is certified
- privacy-safe analytics
- citation-grounded recruiter Q&A after separate factuality certification

### OMIT — first release

- donor branding or visual/template cloning
- custom domains
- recruiter identity inference
- opaque scores
- autonomous outreach/booking
- portfolio chat agent
- billing

# 9A Shipping Contract

Implementation is prohibited until this contract is accepted as the gate.

## Golden path

1. Authenticated candidate has a verified ApplyAI profile/resume.
2. Candidate opens Career Site builder.
3. System materializes a versioned `CareerSiteDraft` from canonical candidate evidence.
4. Candidate reviews facts and bounded generated derivative copy.
5. Candidate chooses one original ApplyAI theme.
6. Preview renders the exact draft revision that would be published.
7. Candidate chooses a unique slug and explicitly publishes.
8. System creates an immutable publication snapshot.
9. Anonymous browser loads the public URL without reading private mutable candidate data.
10. Later edits or theme changes create a new draft and require explicit republish.
11. Unpublish invalidates anonymous access.

## Negative paths

The first release must fail closed for:

- malformed, encrypted, empty or oversized PDFs;
- parser/LLM timeout or invalid structured output;
- resume text that looks like prompt instructions — it remains untrusted document content;
- generated copy that introduces unsupported factual claims;
- concurrent slug collisions;
- cross-candidate draft/publication access;
- anonymous access to unpublished/private fields;
- update-resume parse failures mutating the current publication;
- partial publish writes becoming externally visible;
- failed unpublish/revoke semantics;
- renderer/theme failure corrupting canonical profile data;
- stale drafts reintroducing deleted/private fields after republish.

## Contract outline

```text
CareerSiteDraft(
  id,
  candidate_id,
  source_profile_revision,
  theme_id,
  slug_candidate,
  content_json,
  visibility_json,
  status,
  created_at,
  updated_at
)

CareerSitePublication(
  id,
  candidate_id,
  slug,
  draft_revision,
  content_snapshot,
  visibility_snapshot,
  theme_id,
  published_at,
  revoked_at
)

GeneratedCopy(
  field,
  text,
  source_evidence_ids,
  factual_claims_added=false,
  model_receipt
)

CareerSitePublishReceipt(
  candidate_id,
  draft_id,
  publication_id,
  slug,
  exact_content_hash,
  exact_theme_version,
  timestamp
)
```

## Acceptance criteria

- verified facts are preserved exactly or changed only in presentation;
- generated headline/intro cannot introduce employers, dates, skills, metrics, credentials, projects or outcomes absent from evidence;
- public rendering reads the immutable publication snapshot rather than the mutable private profile;
- same draft plus same theme version produces deterministic public content;
- publish/unpublish are idempotent and auditable;
- normal anonymous rendering does not depend on an authenticated API call;
- first-party themes pass accessibility, mobile and overflow checks;
- exact-head browser UAT proves create -> preview -> publish -> anonymous view -> edit/theme switch -> republish -> unpublish;
- local test success cannot be promoted to preview, production or shipped status without higher-level receipts.

## Bounded implementation plan

### Slice 1 — contract and persistence

Add versioned draft/publication models, candidate ownership, slug reservation, publish/unpublish state machine and focused negative tests. No public-template parity or launch claim.

### Slice 2 — builder and preview

Reuse existing ApplyAI resume/profile evidence, add explicit review UI, one original theme and exact-draft preview.

### Slice 3 — anonymous renderer

Add public slug route backed only by immutable publication snapshots, with privacy/revoke/isolation tests.

### Slice 4 — resume refresh and theme switching

Add obvious Update Resume and Change Theme actions, reviewable diff, no silent overwrite.

### Slice 5 — certification

Exact-head CI, restart/replay, preview deployment, real anonymous-browser UAT, cross-candidate negatives, then production certification.

## Status boundary

Current status: **SPECIFIED / NOT BUILDING**.

ApplyAI already has multiple active donor/release branches. Under the portfolio WIP policy this dossier must not create another implementation stream until a BUILDING slot opens.

When WIP allows, the only authorized next slice is **Slice 1**. Custom domains, analytics, recruiter agents and additional theme work remain out of scope until the core publish contract is independently verified.