# Applied donor reverse-engineering intake

Status: SPECIFIED / consolidation donor

Reviewed: 2026-10-11

## Source evidence

- User-supplied Reddit launch: https://www.reddit.com/r/SideProject/comments/1x3lbri/built_a_job_tracker_that_pulls_linkedin_jobs/
- Public source repository: https://github.com/tonghohin/applied
- Source head reviewed: `054f081ac6f742dac85d848ca39dc80eaf1b01e1`
- Source license: MIT
- ApplyAI baseline head for this intake: `9798aa613c45cdf9d54f3e2c6c47481ca31d1852`
- Canonical ApplyAI workstreams: GitHub issues #75 and #84

The Reddit launch was new at the time of review and exposed no substantive commenter feedback in the visible thread. Community requirements must not be invented from an empty comment set.

## Product reconstruction

Applied is a self-hosted job-search and application workflow with the following observable loop:

1. Capture profile, resume, target title, skills, location/workplace preferences and exclusions.
2. Run a LinkedIn-oriented job search, including scheduled searches.
3. Filter excluded titles/companies and deduplicate previously seen jobs.
4. Fetch surviving job details.
5. Score each job against the candidate resume with an LLM and persist score/reasoning.
6. Review candidates in a dashboard with status, workplace, company-history, search and score filters.
7. Generate a tailored resume and cover letter for a selected job.
8. Optionally run browser automation to fill and submit selected applications.
9. Persist application/run state and expose failures for manual recovery.

The upstream architecture is a TypeScript/Turborepo monorepo with Next.js, tRPC, PostgreSQL/Drizzle, Redis/BullMQ workers, Playwright automation, LLM scoring/application generation and observability. It is useful as a behavioral benchmark, not as ApplyAI's target architecture.

## Important upstream limitations

The upstream README explicitly warns that its LinkedIn automation may violate LinkedIn's User Agreement and can result in account suspension. The repository also documents bot-detection failures, account-creation-required application flows and unsupported/custom forms.

ApplyAI must not adopt stealth/anti-bot circumvention, credential capture, CAPTCHA solving, proxy rotation or private endpoint use as product requirements.

## Consolidation decision

Do **not** create a standalone clone or second job-search product.

Applied maps into existing ApplyAI capability families:

- Job Radar / Career Intelligence: issue #75
- Resume Studio / evidence-locked tailoring: existing ApplyAI product + issue #84
- Governed browser execution: issue #84
- Application command center: existing ApplyAI product
- Durable task/runtime observability: existing ApplyAI architecture

Donor classification: **benchmark + targeted capability donor**.

## MATCH / IMPROVE / NEW / OMIT

### MATCH

Already present or already canonical in ApplyAI:

- candidate profile and resume
- job search / matching surfaces
- canonical job and application records
- saved searches / alert direction
- deterministic evidence-aware Career Intelligence
- durable AI tasks
- tailored resume/application artifacts
- candidate-owned application state
- candidate-approved third-party action boundary
- worker/task observability and production verification gates

### IMPROVE

Useful donor ideas to strengthen existing ApplyAI contracts:

1. **Candidate-owned company history context**
   - prior application count
   - prior rejection count
   - prior interview count
   - most recent application date
   - same-company cooldown/duplicate warning
   - never convert this into an unsupported employer quality score

2. **Job Radar run receipts**
   - search-profile version
   - provider/source set
   - started/completed timestamps
   - discovered / normalized / deduped / filtered / scored / delivered counts
   - partial/inconclusive/failure counts
   - retry and worker-attempt metadata
   - exact ranking/rule/model versions

3. **Inspectable dedupe reasons**
   - provider ID
   - canonical URL
   - guarded company + title + location fallback
   - duplicate reason and provenance retained for audit

4. **Score evidence parity**
   - persist reasoning/version beside score
   - deterministic evidence remains distinct from model-generated explanation
   - the explanation must point to the evidence used by the scored artifact

5. **Fast triage UX**
   - split-view/table review patterns
   - filters for status, workplace mode, search text, score and candidate-owned company history
   - independently authored ApplyAI UI rather than copying donor screens

6. **Scheduled scan ergonomics**
   - timezone-aware cadence
   - idempotent execution
   - pause/resume
   - already-delivered suppression
   - configurable active hours and caps
   - no copied default cadence as a product constant

7. **Application execution receipts**
   - immutable approved artifact/version IDs
   - gate receipt ID
   - candidate approval event
   - adapter/version
   - timestamps
   - terminal outcome and failure taxonomy
   - exact submitted artifact hashes

### NEW

The donor does not justify a new standalone ApplyAI capability family. New code should be limited to the missing deltas above inside existing Job Radar and governed-application contracts.

### OMIT

Explicitly reject:

- LinkedIn credentials/session as a required source dependency
- stealth browser behavior / anti-bot evasion
- CAPTCHA bypass
- private provider endpoints
- interpreting source disappearance as proof a job is closed
- unverified `applied` success state
- opaque 0-100 scoring without evidence/versioning
- automatic submission immediately after search without a persisted authorization policy

## Behavioral contracts

### Job discovery and deduplication

- Provider/source identity is retained on every discovered job.
- Repeated discovery of the same provider ID or canonical URL is idempotent.
- Guarded fallback dedupe may use normalized company + title + location only when stronger IDs are unavailable.
- Every suppression produces an inspectable reason code.
- Materially different roles must not be merged because titles look similar.
- Partial/inconclusive provider runs cannot expire previously known jobs.

### Ranking

- Deterministic score/evidence is the auditable baseline.
- Optional model reranking/explanation is versioned and separately persisted.
- Candidate-facing reasoning cannot cite evidence absent from the underlying scored artifact.
- Unknown/insufficient evidence remains a valid state.

### Scheduled scans

- Candidate timezone and cadence are persisted.
- Each scheduled run has an idempotency key.
- Worker retries cannot produce duplicate deliveries.
- A job is not redelivered unless a configured material lifecycle change makes it eligible again.
- Run receipts survive worker restart/crash recovery.

### Candidate-owned company history

- Aggregation is scoped to the authenticated candidate.
- Cross-tenant/cross-user history must never leak.
- History is derived from canonical applications, not scraped reputation data.
- A history warning may influence candidate triage but must not silently alter canonical job facts.

### Governed application execution

State model should distinguish at least:

- `prepared`
- `approved`
- `running`
- `needs_login`
- `needs_account_creation`
- `needs_user_answer`
- `blocked_by_captcha_or_antibot`
- `unsupported_form`
- `submission_unconfirmed`
- `submitted_confirmed`
- `failed`

Rules:

- candidate-owned/authorized browser context only
- no CAPTCHA solving, stealth/anti-bot bypass or private endpoint use
- pause on login, account creation, consent or unknown required questions
- no success state without observed submission confirmation
- ambiguous final state must require candidate review
- retry after crash must not double-submit
- browser traces/receipts must redact credentials and session secrets
- store the exact resume, cover letter and answer revisions that were approved/sent

## Architecture mapping

Preserve ApplyAI's canonical architecture:

```text
Next.js / mobile / extension
          |
          v
       FastAPI
          |
          v
PostgreSQL + R2
          |
transactional outbox
          |
          v
   durable worker
```

Do not replace this with the donor's Next.js/tRPC/Redis/BullMQ topology merely for parity.

Potential implementation mapping:

- Job Radar run receipts -> existing job-scan / task-run persistence
- company history -> derived query/read model from canonical applications
- dedupe reason -> source normalization/lifecycle domain
- score reasoning/version -> Career Intelligence artifacts
- execution receipt -> governed application command/run domain
- browser runtime -> optional constrained runner/adapter with signed candidate-authorized tasks

## Implementation slices

### Slice A — Job Radar observability + history

1. Add/confirm run-receipt fields for discovery/dedupe/filter/score/delivery counts and version metadata.
2. Add dedupe reason/provenance to suppression receipts.
3. Add candidate-scoped company-history aggregation service/read model.
4. Surface company history + dedupe/match evidence in the canonical jobs/matches UI.
5. Add tests for tenant isolation, idempotency, fallback-dedupe collision avoidance and run-retry durability.

### Slice B — scheduling hardening

1. Persist timezone/cadence/active-window/caps.
2. Add idempotent scheduler dispatch.
3. Add already-delivered suppression and material-change re-eligibility.
4. Add restart/retry/failure-injection tests.

### Slice C — governed execution receipt hardening

1. Add explicit execution terminal states.
2. Bind each run to candidate-approved artifact revisions and gate receipt.
3. Persist non-secret run receipts and exact artifact hashes.
4. Fail closed on login/account/CAPTCHA/unknown-question/unsupported-form boundaries.
5. Add crash-retry no-double-submit tests.

### Slice D — reviewed browser adapter

1. Choose one public ATS flow already approved for this project.
2. Implement inspect -> prepare -> preview -> approve -> execute -> verify.
3. Keep external handoff as the default for every unsupported provider.
4. Run hosted/browser certification before changing any production claim.

## Acceptance tests

### Job Radar

- rerunning identical scan is idempotent
- duplicate provider ID is suppressed with exact reason
- duplicate canonical URL is suppressed with exact reason
- guarded fallback does not collapse different role/location combinations
- provider 429/5xx/parser failure yields partial/inconclusive, never false closure
- company-history query cannot read another candidate's applications
- score explanation version and evidence IDs are persisted
- worker crash/retry preserves a single logical run receipt

### Scheduling

- timezone boundary behavior
- repeated scheduler tick produces one logical run
- delivered job is not resent
- materially changed/reopened job can become eligible according to explicit policy
- pause/resume persists across process restart

### Application execution

- approved package + reviewed adapter + observed confirmation -> `submitted_confirmed`
- CAPTCHA -> `blocked_by_captcha_or_antibot`
- login -> `needs_login`
- account creation -> `needs_account_creation`
- unknown required question -> `needs_user_answer`
- unsupported form -> `unsupported_form`
- ambiguous final page -> `submission_unconfirmed`
- crash retry cannot double-submit
- exact sent artifact hashes match approved revisions
- secrets are absent from logs/traces/receipts

## Verification ladder

Do not call this donor integrated or complete until each implemented slice passes the applicable gates:

1. code review
2. unit tests
3. integration tests
4. API/contract tests
5. durable-runtime/restart tests
6. browser/UI tests
7. persistence/failure-injection tests
8. candidate UAT
9. preview/hosted verification
10. production deployment evidence
11. exact-SHA receipt recorded in tracker

Repository tests alone do not prove LinkedIn/ATS/provider acceptance or production deployment.

## Tracker truth

- Source: complete for reviewed snapshot
- Understanding: complete for reviewed snapshot
- Evidence: complete for public Reddit/GitHub snapshot; no substantive Reddit comment feedback observed
- Reconstruction model: complete
- Consolidation: complete -> #75 + #84; no new standalone product
- Specification: complete in this document
- Implementation: not yet claimed by this intake
- Runtime verification: not yet claimed by this intake
- Product UAT: not yet claimed by this intake
- Deployment/promotion: not yet claimed by this intake

Next eligible engineering work is Slice A inside the canonical ApplyAI workstreams, without weakening the existing provider/safety boundaries.