# ApplyAI Interview Intelligence

This module is a clean-room implementation of interview-intelligence product mechanics. It does **not** copy a competitor's proprietary question bank, tutorials, solutions, private forum content, or paywalled material.

## Product surface

| Capability | ApplyAI implementation | Status |
|---|---|---|
| Multi-track question bank | Coding, SQL, System Design, ML System Design, OOD, Behavioral | Implemented |
| Company question collections | Company radar + company-linked canonical questions | Implemented |
| Search/filter/sort | company, track, difficulty, confidence, frequency | Implemented |
| Recency/confidence | persisted report count, last reported, evidence confidence, frequency | Implemented |
| Practice workspace | reasoning/answer editor, code text editor, staged hints, solution framework, follow-ups | Implemented |
| Saved attempts/progress | durable attempts + per-track progress/score aggregation | Implemented |
| AI-style coaching | evidence-safe staged coaching contract; deterministic fallback | Implemented |
| Job-specific personalization | ApplyAI job requirements + verified candidate skills -> readiness/gaps/actions | Implemented |
| Mock interview | existing ApplyAI interview engine integrated with job-specific plan | Implemented |
| Candidate reports | user submission + de-dup fingerprint + moderation queue | Implemented |
| Provenance/moderation | source/license/status fields, operator review, explicit evidence linking | Implemented |
| Canonicalization boundary | approved report -> explicit canonical question evidence link | Implemented |
| Community/forum | categories, feed, post, reply API, reactions/views | Implemented |
| Admin/operator controls | metrics, moderation queue, canonical catalog, evidence linking | Implemented |
| Subscription entitlements | existing ApplyAI FREE/PRO/TEAM interview-practice entitlements | Existing platform capability |
| Referral growth loop | referral codes/events + auditable credit ledger + candidate workspace | Implemented |
| Coding execution | remote isolated sandbox provider boundary | Implemented, requires sandbox deployment/config |
| SQL execution | intentionally not executed in-process | Pending isolated SQL sandbox provider |

## Architecture

```text
Candidate UI
  ├─ Question intelligence / company radar
  ├─ Practice / progress
  ├─ Job-specific preparation plans
  ├─ Mock interviews
  ├─ Community
  └─ Referral workspace
          |
          v
FastAPI
  ├─ interview_intelligence
  ├─ interview_execution
  ├─ referrals
  └─ internal moderation/evidence APIs
          |
          v
PostgreSQL / Supabase
  ├─ canonical questions
  ├─ source reports + evidence graph
  ├─ attempts + preparation plans
  ├─ community
  └─ referral ledger

Untrusted candidate code
  -> never runs in FastAPI/Next.js
  -> interview_execution provider adapter
  -> remote isolated sandbox only
```

## Evidence lifecycle

```text
USER_SUBMISSION / APPROVED SOURCE
        -> fingerprint + provenance
        -> REVIEW_REQUIRED
        -> APPROVED or REJECTED
        -> explicit canonical-question link
        -> recompute report count / recency / confidence / frequency
        -> candidate-facing intelligence
```

A community post is not automatically evidence. A user-submitted report is not automatically a canonical question. Only approved reports explicitly linked by an operator affect question confidence/recency.

## Execution security

The API never uses `eval`, a shell, local Python execution, Docker-in-Docker, or database execution for candidate code. `POST /api/v1/interview-intelligence/execution/run` requires a configured remote sandbox provider. Current adapter configuration:

- `INTERVIEW_EXECUTION_PROVIDER=piston`
- `INTERVIEW_PISTON_URL=https://<sandbox-host>`
- `INTERVIEW_PISTON_TOKEN=<optional-private-token>`

When not configured, execution returns 503 and the rest of interview prep remains functional. SQL execution remains disabled until a dedicated isolated SQL runtime is connected.

## Clean-room seed

The migration seeds six original questions only to make the post-migration product usable without scraping external content. Their company labels are product demo metadata, not claims that a company has asked those exact questions.

## Remaining external configuration

The application implementation has no dependency on a proprietary interview-prep provider. The only infrastructure capability that cannot safely be emulated in the application process is arbitrary code/SQL execution. Production must provision an isolated execution service before enabling the Run Code UI.
