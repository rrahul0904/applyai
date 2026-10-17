---
applyai_fit: INTELLIGENCE
fit_scope: FULL
destination: career-intelligence
---

# MarketTruth donor → evidence-backed HR rubric intelligence

## Source

- User-supplied Reddit share: https://www.reddit.com/r/SideProject/s/1tUJ434SE2
- Resolved public thread: https://www.reddit.com/r/SideProject/comments/1x7zofr/for_sale_struggling_in_this_job_market_i_built_an/
- Research snapshot: 2026-10-17 ET
- Product name used by the Reddit author: **MarketTruth**
- Live product URL: **not publicly identified in the source snapshot**; the author asks interested buyers to DM for a live link.
- Public source repository/license: **not identified**.

Important disambiguation: public search also surfaces an unrelated trading/market-analysis product using the MarketTruth name/domain. Do not conflate that product, its terms, architecture, or behavior with this career/resume donor.

## Evidence classification

### OBSERVED / SOURCE-REPORTED

The Reddit author describes a completed career tool built after dissatisfaction with generic keyword-oriented resume tools. Publicly reported behavior/architecture includes:

- candidate resume audit against live ATS/job-feed evidence;
- a point-factor-inspired HR evaluation lens centered on technical know-how, problem-solving scope, and business accountability;
- resume improvement and interview preparation as downstream workflows;
- React + Vite frontend;
- Cloudflare Pages/Workers edge hosting/proxy;
- Gemini free-tier model usage with claimed ability to swap providers;
- PDF parsing in the browser;
- application tracking in browser `localStorage`;
- no database in the disclosed implementation;
- self-reported improvement in interview volume after using the tool on the author's own search;
- codebase is being offered for sale.

The interview-improvement claim is creator-reported anecdotal evidence, not independently verified causal evidence.

### INFERRED

A useful implementation of the observed workflow requires independent contracts for:

- target-role/job snapshot;
- candidate evidence inventory;
- configurable competency/rubric dimensions;
- evidence-to-dimension mapping;
- gap/coverage assessment;
- resume rewrite proposals tied to evidence;
- interview preparation tied to the same role gaps;
- versioned model/rubric/job/profile identity.

These are our architecture requirements, not claims about the donor's hidden implementation.

### UNKNOWN

Do not guess:

- donor prompt text or rubric formula;
- exact point weights, thresholds, leveling bands, or proprietary HR methodology;
- exact ATS/feed providers;
- whether job feeds are accessed through licensed APIs, public endpoints, scraping, or another mechanism;
- exact PDF parser/library;
- exact Gemini model/version;
- production privacy/security behavior beyond the author's public claims;
- actual code quality, test coverage, availability, latency, or user base;
- the live product URL unless independently resolved;
- revenue, retention, conversion lift, or causal interview impact.

## Clean-room boundary

Treat this target as a **behavior/capability donor only** unless a specific public source artifact and license are later identified.

Allowed:

- public product claims and workflows as requirements evidence;
- independently authored generic job-evaluation/rubric concepts;
- public/authorized ATS job sources already governed by ApplyAI;
- independently authored schemas, UX, prompts, tests, scoring logic, and evaluation fixtures.

Do not copy or reconstruct:

- proprietary source code;
- private prompts;
- private APIs;
- hidden rubric weights/formulas;
- branding, copy, UI assets, or trade dress;
- proprietary commercial job-evaluation frameworks or vendor formulas.

The owned rubric must use generic, independently authored terminology and configurable dimensions. It must not present itself as Korn Ferry/Hay/Mercer or any other proprietary job-evaluation system unless a separately licensed integration is intentionally added.

## ApplyAI Fit

**Classification: `INTELLIGENCE / FULL` with a secondary `PREPARE` consumer.**

Canonical implementation repository: `rrahul0904/applyai`.

This is **not** a standalone MarketTruth clone and **not** a reason to expand `rrahul0904/resumeshareiq` into another career product.

ApplyAI already owns the surrounding candidate journey:

`Discover jobs → understand fit → improve resume/profile → apply → track → learn skill gaps → prepare for interviews → practice/mock → measure readiness → manage career intelligence`

The donor adds one meaningful capability gap: a transparent, evidence-backed **role-scope and accountability assessment** that evaluates the level and quality of candidate evidence rather than merely keyword overlap.

## Why this qualifies

The target directly strengthens three existing ApplyAI workflows:

1. **Career Intelligence / job fit** — explain why a candidate appears below/at/above a target role across meaningful role dimensions.
2. **Resume Studio** — turn identified evidence gaps into bounded, factual rewrite proposals without inventing seniority, scope, skills, metrics, or business impact.
3. **Interview preparation** — convert weak/unclear rubric dimensions into targeted evidence-recall and practice questions.

Existing ApplyAI donor work already covers factuality/FactLock, one-page tailoring, public portfolio, recruiter intelligence, interview intelligence, and job-source ingestion. This donor should extend those capabilities rather than create parallel stores or workflows.

## Candidate journey stages

Primary:

- understand fit;
- improve resume/profile;
- learn skill gaps;
- prepare for interviews;
- measure readiness;
- manage career intelligence.

Secondary:

- application tracking may consume the assessment as context, but this donor does not own application-state truth;
- Job Radar may produce the target job snapshot, but this donor does not own job ingestion.

## Product thesis

Build **Evidence-backed Career Rubric Intelligence** inside ApplyAI:

> Take an exact candidate evidence revision and an exact target job revision; evaluate them against a transparent, versioned role rubric; show what is supported, weak, missing, contradictory, or unknown; then generate factual resume/interview actions whose claims remain bound to evidence.

This is intentionally different from a generic ATS percentage score.

The user should be able to answer:

- What does this role actually demand beyond keywords?
- Which parts of my history prove those demands?
- Where is my evidence weak versus simply absent from the resume?
- Am I demonstrating the scope expected at this seniority?
- What should I rewrite, clarify, or prepare to discuss in an interview?
- Which conclusions are evidence-backed versus model inference?

## MATCH / IMPROVE / NEW / OMIT

### MATCH

- resume/PDF ingestion;
- target-role/job comparison;
- job-source/ATS evidence;
- AI-assisted assessment;
- resume improvement recommendations;
- interview preparation;
- provider-swappable model seam;
- fast candidate-facing workflow.

### IMPROVE

- replace one opaque ATS score with dimension-level evidence and uncertainty;
- preserve exact job-posting revision/source provenance;
- preserve exact candidate evidence/profile revision;
- make every dimension cite evidence or explicitly say `insufficient_evidence`;
- separate `OBSERVED`, `DERIVED`, `INFERRED`, `UNKNOWN`, and `VERIFIED` assertions;
- deterministic factuality checks run after model classification/rewrite;
- model output cannot increase candidate scope/seniority without evidence;
- source changes invalidate stale assessments;
- generated resume text becomes a proposal, never silent canonical mutation;
- interview-prep questions point to the role requirement and the candidate evidence/gap that caused them;
- provider/model/rubric/schema version is captured in receipts;
- local parsing/privacy is an optional capability, not a claim that browser `localStorage` is sufficient for ApplyAI's canonical data/security model;
- no claim of universal ATS compatibility or interview-rate uplift without independent measurement.

### NEW owned concepts

Prefer reuse of existing ApplyAI profile, evidence, FactLock, job, and interview entities. Add only missing semantics:

- `career-rubric/v1`
- `career-rubric-dimension/v1`
- `rubric-assessment/v1`
- `rubric-dimension-result/v1`
- `rubric-gap/v1`
- `career-assessment-receipt/v1`

Potential generic independently-authored dimension set:

1. **Functional / technical knowledge** — depth and breadth required for the work.
2. **Problem complexity** — ambiguity, novelty, and difficulty of problems handled.
3. **Decision scope / autonomy** — independence, judgment, and decision rights evidenced.
4. **Business accountability / impact** — responsibility for outcomes, reliability, cost, revenue, risk, customers, or operational results where evidenced.
5. **Leadership / influence** — people leadership, technical leadership, cross-functional influence, mentoring, or stakeholder span where evidenced.
6. **Scale / operating context** — data/system/team/geography/customer/financial scale only when explicitly supported.
7. **Role-level consistency** — whether title/scope/ownership evidence coheres with the target seniority.

No proprietary point weights are assumed. Dimensions/weights may be configurable by role family after independent evaluation.

### OMIT / DEFER

- donor branding/name/UI;
- copied rubric prompts/weights/formulas;
- a new standalone resume product;
- a second application tracker;
- a second resume database;
- claims that a rubric predicts hiring decisions;
- automated hiring/rejection decisions;
- recruiter-side candidate ranking as an employment decision system;
- opaque personality/psychometric inference;
- scraping gated ATS pages or bypassing anti-bot/access controls;
- custom proprietary HR framework emulation;
- billing/pricing experiments from the donor;
- localStorage as the authoritative ApplyAI data layer.

## Core contract sketch

### `career-rubric/v1`

- rubric id/version;
- role family / applicability;
- dimension definitions;
- optional dimension weights with provenance;
- scoring/banding method;
- required evidence policy;
- uncertainty policy;
- creation/review metadata;
- deterministic rubric digest.

### `rubric-assessment/v1`

Bind exact:

- candidate/profile/evidence revision;
- target job id + source snapshot/revision;
- rubric digest;
- provider/model/prompt/schema version if a model is used;
- dimension results;
- overall summary that cannot be stronger than dimension evidence;
- limitations/unknowns;
- deterministic assessment identity/digest.

### `rubric-dimension-result/v1`

For each dimension:

- dimension id;
- target expectation;
- candidate evidence ids;
- evidence coverage: `strong | partial | weak | absent | unknown`;
- fit state: `above | aligned | below | unknown` only when evidence permits;
- confidence;
- evidence-backed rationale;
- unsupported/inferred claims separated from verified facts;
- suggested candidate action;
- generated rewrite/interview references, if any.

### `rubric-gap/v1`

- exact assessment/dimension;
- gap type: `missing_evidence | weak_specificity | scope_gap | requirement_gap | contradiction | unknown`;
- requirement/source refs;
- candidate evidence refs;
- remediation class: `resume_clarification | evidence_collection | skill_development | interview_prep | no_action`;
- severity/confidence;
- no fabricated remedy claim.

### `career-assessment-receipt/v1`

- exact input digests;
- assessment/rubric versions;
- deterministic validation results;
- FactLock/factuality receipt refs;
- model/provider metadata when used;
- timing/cost facts when available;
- output digest;
- terminal status: `complete | partial | insufficient_evidence | failed | stale`.

## First vertical slice

Start with one role family and synthetic fixtures. Do not start with broad UI or live provider automation.

Suggested Phase A fixture: **Senior Data Engineer / Data Architect**, because ApplyAI can exercise technical depth, ambiguity, autonomy, business accountability, cross-functional influence, and scale without proprietary assessment content.

Flow:

1. load synthetic candidate evidence fixture;
2. load synthetic target job snapshot;
3. apply independently authored `career-rubric/v1`;
4. compute deterministic evidence coverage per dimension;
5. optionally call a model only for bounded classification/explanation;
6. validate all model claims against candidate/job evidence;
7. emit dimension results + gaps + receipt;
8. produce two bounded outputs:
   - resume clarification/rewrite proposals;
   - interview-prep questions tied to gaps;
9. run negative/adversarial fixtures;
10. preserve exact receipts for replay.

## Deterministic baseline before model scoring

The first slice should not depend entirely on an LLM score.

Baseline signals may include:

- exact/normalized skill and domain evidence;
- chronology/duration facts already verified by ApplyAI;
- action/ownership language recognized from candidate evidence without fabricating scope;
- explicit scale/metric evidence only when present;
- target requirement extraction with source spans;
- evidence specificity/coverage counts;
- contradiction/missing-field detection.

A model can classify nuanced evidence, but the final output must remain bounded by source spans and deterministic factuality checks.

## Required negative / recovery tests

- candidate employer/title/date cannot be changed by assessment or rewrite;
- metric absent from source evidence cannot appear in generated rewrite;
- technology absent from evidence cannot be added as candidate experience;
- target job changes after assessment -> prior assessment becomes stale;
- candidate profile/evidence revision changes -> stale assessment cannot drive new application package without recomputation;
- “senior” in the target title alone cannot manufacture leadership/autonomy evidence;
- broad responsibility language with no scope detail remains `weak/unknown`, not confidently aligned;
- model says `above` but evidence policy cannot support it -> deterministic validator downgrades/rejects;
- model output cites nonexistent evidence id -> fail;
- prompt-injection-like text inside resume/JD remains untrusted document content;
- malformed/empty/encrypted PDF extraction cannot produce a successful assessment;
- provider timeout/invalid JSON leaves deterministic baseline available and marks model portion partial/failed;
- Candidate A cannot access Candidate B assessment/evidence;
- interview question must identify the rubric gap/requirement that caused it;
- same canonical candidate/job/rubric inputs produce the same deterministic baseline and assessment identity;
- local-only parsing mode makes no outbound AI call unless the candidate explicitly invokes an AI-enabled step;
- assessment cannot become an automatic employer hiring/rejection decision.

## Evaluation plan

Build a labeled synthetic benchmark before candidate-facing score claims:

- clear alignment fixtures;
- clear scope-gap fixtures;
- missing-evidence fixtures;
- ambiguous seniority fixtures;
- contradictory requirement/evidence fixtures;
- keyword-rich but accountability-poor resume fixture;
- strong accountability evidence with low keyword overlap fixture;
- adversarial unsupported-metric/skill generation fixtures.

Measure:

- evidence-link precision;
- unsupported-claim rate (target: zero accepted unsupported claims);
- dimension classification accuracy against reviewed fixture labels;
- unknown calibration;
- stale-input invalidation correctness;
- deterministic baseline replay;
- model-to-model/provider drift separately from baseline correctness.

Do not publish a candidate-facing numerical score until the banding/weighting model has an independently reviewed evaluation set and is shown to add value beyond a transparent dimension summary.

## Integration points

### Career Intelligence

Primary owner of the assessment/read model. Job Radar provides normalized job evidence; assessment adds role-depth/scope interpretation.

### Resume Studio / FactLock

Consume `rubric-gap` outputs to create reviewable rewrite proposals. Existing factuality gates remain authoritative; rubric intelligence cannot bypass them.

### Interview Prep

Create targeted questions from assessment gaps, e.g. “give a concrete example showing autonomous ownership at X scope,” tied to exact job/candidate evidence. Existing interview-practice/evaluation architecture remains canonical.

### Application workflow

May display the current assessment and its freshness. It must not auto-submit or change application state based solely on rubric score.

### Resume Share / Career Site

May later surface candidate-approved evidence/proof cards, but raw assessment weaknesses are private by default and must never leak to public portfolio routes.

## Privacy / security posture

The donor's browser parsing/localStorage design is useful as a privacy pattern but should not replace ApplyAI's existing identity, authorization, persistence, deletion, and audit controls.

Potential later local-first option:

- parse PDF locally;
- show extraction preview before upload;
- allow candidate to keep selected sensitive drafts local;
- send only explicitly approved bounded evidence to a selected model/provider;
- retain clear provider/network disclosure.

Canonical cloud data must still follow ApplyAI tenancy, authorization, deletion, retention, and security contracts.

## Absorb into ApplyAI

- transparent role-level/rubric assessment;
- evidence-to-dimension mapping;
- scope/accountability gap analysis;
- role-level consistency checks;
- factual resume proposals from gaps;
- gap-driven interview preparation;
- versioned assessment receipts;
- optional local-first parsing/privacy enhancements;
- provider-neutral explanation layer.

## Keep separate

- MarketTruth branding/trade dress;
- source-for-sale/commercial acquisition mechanics;
- donor-specific frontend/edge/provider stack;
- donor's browser-only application tracker;
- any proprietary point-factor formula;
- any hidden ATS-feed technique;
- unrelated markettruth.ai trading product;
- employment-decision automation for employers.

## Implementation destination

Canonical repo: `rrahul0904/applyai`.

Research branch:

`research/markettruth-hr-rubric-intelligence`

Initial target areas after code audit:

- existing Career Intelligence domain/service;
- existing candidate evidence / FactLock primitives;
- existing job-source snapshot model;
- existing Resume Studio proposal flow;
- existing interview-prep domain;
- reverse-engineering registry/admin projection.

Do not create a new repository. Do not merge this research branch or open production/release actions from this intake alone.

## Implementation status

`SOURCE=done / REDDIT_RESOLVED=done / PUBLIC_EVIDENCE=first-pass-done / LIVE_PRODUCT_URL=unknown / SOURCE_CODE=not-publicly-identified / LICENSE=unknown / INTERNAL_DEDUPE=done / ROUTING=APPLYAI_CAPABILITY_DONOR / CLEAN_ROOM_BOUNDARY=done / PRODUCT_THESIS=done / CONTRACTS=initial / RESEARCH_BRANCH=created / DOSSIER=committed-on-research-branch / FEATURE_IMPLEMENTATION=not-started / TESTS=not-started-for-this-delta / UAT=none / DEPLOYMENT=none / SHIPPED=no`

## Roadmap

### P0 — evidence / routing
- [x] resolve supplied Reddit share;
- [x] capture source claims and limitations;
- [x] disambiguate unrelated MarketTruth trading product;
- [x] inspect ApplyAI product boundary and reverse-engineering taxonomy;
- [x] dedupe against existing ApplyAI resume/interview/career intelligence donor work;
- [x] classify as ApplyAI donor, not standalone;
- [x] create bounded research branch;
- [x] record clean-room specification.

### P1 — current ApplyAI contract audit
- [ ] map candidate evidence/FactLock entities;
- [ ] map target job snapshot/source provenance;
- [ ] map Career Intelligence assessment model;
- [ ] map Resume Studio proposal model;
- [ ] map Interview Prep question/evaluation model;
- [ ] reuse existing contracts wherever semantics already exist;
- [ ] freeze only genuinely missing rubric contracts.

### P2 — deterministic fixture kernel
- [ ] independently authored rubric schema;
- [ ] synthetic candidate/job fixtures;
- [ ] deterministic evidence coverage/gap engine;
- [ ] stale-input detection;
- [ ] canonical digests/receipts;
- [ ] negative/adversarial tests;
- [ ] no live model/provider requirement.

### P3 — bounded model classifier/explainer
- [ ] structured output schema;
- [ ] exact evidence IDs required;
- [ ] post-model deterministic validation;
- [ ] unsupported claims rejected;
- [ ] provider/model drift evaluation;
- [ ] local/BYO/server provider policy compatibility.

### P4 — Resume Studio integration
- [ ] assessment gap → factual rewrite proposal;
- [ ] candidate review/edit/accept;
- [ ] FactLock validation;
- [ ] source revision linkage;
- [ ] no silent mutation.

### P5 — Interview Prep integration
- [ ] assessment gap → evidence-targeted practice question;
- [ ] candidate answer → rubric-specific coaching evidence;
- [ ] no hidden hiring probability claim;
- [ ] readiness is coaching evidence, not employment decision authority.

### P6 — candidate UX
- [ ] transparent dimension cards;
- [ ] evidence/support/unknown states;
- [ ] role-scope comparison;
- [ ] actionable resume/interview next steps;
- [ ] accessibility/mobile acceptance;
- [ ] no manipulative score/gamification.

### P7 — evaluation / UAT
- [ ] labeled fixture benchmark;
- [ ] unsupported-claim rate gate;
- [ ] model/provider comparison;
- [ ] candidate comprehension/usability review;
- [ ] exact-head browser UAT;
- [ ] privacy/tenancy tests;
- [ ] restart/replay/staleness tests.

### P8 — release gate
- [ ] production runtime prerequisites independently healthy;
- [ ] exact implementation SHA + CI;
- [ ] hosted/browser evidence;
- [ ] release/rollback receipts;
- [ ] no `PRODUCTION` or `SHIPPED` state from research/spec evidence alone.

## Smallest next executable action

Audit the current ApplyAI Career Intelligence, FactLock/evidence, job snapshot, Resume Studio, and Interview Prep contracts on this research branch. Then implement only the missing **side-effect-free rubric schema + deterministic synthetic fixture evaluator + negative tests**. Do not add a new numerical ATS score, live provider dependency, or production mutation in the first implementation slice.
