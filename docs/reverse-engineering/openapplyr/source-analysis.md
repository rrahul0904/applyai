# OpenApplyr source analysis

Status: reverse-engineering intake
Source repository: https://github.com/shivashis-adhikari/openapplyr
Source head reviewed: `f184360f03dd6cb2cbfb45b6801493ec35832781`
Reddit source: https://www.reddit.com/r/SaaS/s/FPfFN0nQX3
License observed: AGPL-3.0
ApplyAI tracking issue: #84

## Product thesis

OpenApplyr is a local-first job-search and application assistant. The product loop is broader than an auto-fill utility:

1. discover and normalize public jobs;
2. score fit and surface warning signals;
3. prepare a tailored resume, cover letter and form answers;
4. validate the package against candidate facts and policy gates;
5. wait for candidate approval unless bounded autopilot is explicitly enabled;
6. execute supported application forms in a candidate-owned browser;
7. pace submissions and avoid duplicate/company-overuse patterns;
8. track replies and application-stage changes;
9. draft follow-up outreach;
10. prepare the candidate for interviews and offers.

## Source-observed architecture

The source tree separates major concerns rather than implementing one monolithic agent.

- `src/engine/sources/*`: public job-source discovery, ATS/aggregator adapters, source detection, registry and polling.
- `src/engine/apply/*`: browser lifecycle, form inspection, adapter behavior, run/runner orchestration, pacing and tests.
- `src/engine/docs/*`: resume/letter generation and deterministic factuality controls.
- `src/engine/packages/*`: prepared application package and pre-send gates.
- `src/engine/ai/*`: provider catalog, provider abstraction, prompt/service boundaries, prices and cost ledger.
- scheduler/queue/worker modules: durable local task claiming and execution.
- mail/outreach modules: reply tracking and candidate-approved communication.
- renderer/main/preload layers: Electron desktop boundary and local UI.

The repository uses Electron + React/TypeScript, Playwright, Vitest, local browser control, document parsing/generation and multiple model providers including local-model support.

## Most important behavioral contract: factuality before submission

OpenApplyr's strongest donor idea is not the UI. It is the deterministic factuality layer surrounding generated resumes.

Observed FactLock behavior includes:

- generated work/project lines carry source fact IDs;
- numbers/metrics are normalized and checked against cited source facts;
- named technologies/entities are checked against cited facts or verified skills;
- employer/title/date structures are required to match the candidate profile;
- unsupported generated lines can be flagged/reverted;
- package gates block autopilot when factuality fails;
- an optional second reviewer can detect unsupported claims.

This is materially compatible with ApplyAI's existing evidence-bound artifact model and should be reimplemented natively rather than copied.

## Pre-send gate model

Observed gate categories include:

- posting remains open;
- match score clears configured threshold;
- posting/risk signals do not block automation;
- every required form question has an answer;
- generated open-text answers comply with the hunt's automation policy;
- resume factuality passes;
- optional second read finds no unsupported claims;
- cover-letter/style checks pass.

Pacing is intentionally treated separately from package correctness: an approved package may wait until a valid execution slot.

## Job source coverage

The project documents/supports company-career flows including Greenhouse, Lever, Ashby, Workday, SmartRecruiters, Workable and Recruitee, with additional generic-form handling. LinkedIn and Indeed direct automated applying are explicitly not claimed.

For ApplyAI this creates a concrete adapter gap analysis rather than a reason to replace the current ingestion system.

## Browser/application execution

The observed application layer is built around a normal candidate browser session and explicit form handling. Product documentation states that CAPTCHA is not solved or bypassed and that site terms still apply.

The useful donor contract for ApplyAI is therefore:

`inspect -> prepare -> preview -> approve -> execute -> observe confirmation -> receipt`

Unknown questions, authentication boundaries, CAPTCHA/consent and unsupported forms should pause rather than guess.

## Privacy and model policy

OpenApplyr is local-first and stores candidate data locally. It supports multiple cloud AI providers and local models, and maintains task cost accounting/budget concepts.

ApplyAI is cloud-first, so the deployment topology should not be copied. The reusable ideas are provider abstraction, minimum-context disclosure, model/task receipts, cost/budget controls, and an optional constrained local execution companion where browser ownership matters.

## What should not be cloned

- Electron as a second canonical product shell.
- A second candidate/profile/application database.
- AGPL implementation code.
- Any claim of LinkedIn/Indeed automated application support.
- CAPTCHA bypass, anti-bot evasion or private ATS endpoint use.
- Autonomous send behavior without explicit user policy and persisted gates.

## ApplyAI implication

OpenApplyr should be treated as a donor to the canonical `rrahul0904/applyai` platform. The first safe/high-value implementation is deterministic resume FactLock plus unified application-package gates. Browser execution, mailbox integration and added ATS adapters come only after those correctness primitives are proven.