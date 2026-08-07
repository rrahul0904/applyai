# AI Architecture

Updated: 2026-08-06

## Status

Career Intelligence is implemented in two layers:

- **V1 deterministic intelligence** — merged on `main`: explainable job prioritization,
  evidence-locked resume wording and reviewed application-material preparation.
- **V2 durable AI architecture** — implemented on PR #12: first-class AI runs/artifacts,
  verified Career Memory, hybrid matching, asynchronous model work, strict evidence validation,
  candidate review, quality telemetry and staging AI worker infrastructure.

The repository can validate V2 with a deterministic evidence-safe provider. A real external model
invocation remains a separate staging acceptance gate and must not be inferred from source CI.

See [`CAREER_INTELLIGENCE_V2.md`](CAREER_INTELLIGENCE_V2.md) for the complete runtime and
acceptance contract.

## Governing rules

- Structured product data is the source context.
- Document facts, user-verified facts and model inferences remain distinct.
- Verified Career Memory is candidate-owned and cannot be silently populated by a model.
- AI cannot invent employers, dates, education, skills, metrics, duties, achievements or outcomes.
- Every factual candidate claim must point to an exact server-generated evidence reference.
- Suggestions require candidate review before they become verified application material.
- Prepared content never implies that an external application, email or message was submitted.
- Every durable model task records provider, model, prompt/schema version, latency, token usage,
  configured cost estimate and outcome when those values are available.
- Outputs must pass strict Pydantic/JSON-schema validation and evidence validation before an
  artifact is materialized.

## Runtime boundary

The current task types are:

```text
AI_DEEP_MATCH
AI_RESUME_TAILOR
AI_APPLICATION_COPILOT
AI_INTERVIEW_PREP
```

They use the same durable pattern:

```text
FastAPI
  -> PostgreSQL transaction: AIJobRun + task_outbox
  -> queue-aware outbox publisher
  -> dedicated AI SQS/DLQ
  -> AI worker
  -> provider abstraction
  -> strict structured output
  -> evidence validation
  -> first-class AIArtifact/domain rows
  -> candidate review
```

Local development and CI may execute the same task contract inline with the deterministic provider;
staging/production are expected to use the durable SQS path.

## Matching architecture

The V1 explainable score remains an auditable baseline. V2 persists a hybrid match whose current
combination is:

```text
65% deterministic baseline + 35% model score
```

The model may improve prioritization/explanation, but it cannot erase the deterministic factors or
turn a fit score into a hiring-probability claim.

## Evidence architecture

Server-side context includes:

- candidate profile, verified experience, skills, target roles and preferences;
- verified, non-archived Career Memory facts;
- canonical job description, company, source, requirements, skills, location and compensation;
- deterministic V1 factor breakdown;
- a generated evidence catalog.

The runtime rejects missing or unknown evidence references. This is the core factuality boundary for
resume, application and interview generation.

## Provider architecture

`BaseAIProvider` isolates model transport from product rules.

- `DeterministicAIProvider`: stable development/CI baseline, explicitly not an LLM.
- `OpenAIResponsesProvider`: server-side Responses API client using strict JSON-schema output,
  configured reasoning level, `store=false` and a pseudonymous safety identifier.

Provider choice, model identifier and cost coefficients are deployment configuration. The model API
key must be injected from secret storage and is never part of the browser bundle or AI task payload.

429/5xx/transport failures remain retryable. Non-retryable provider failures, schema failures and
evidence violations fail closed.

## Persistence architecture

V2 introduces first-class tables:

```text
AIJobRun
AIArtifact
CareerMatch
ResumeTailoring
ResumeTailoringRevision
CoverLetter
ApplicationQuestionDraft
CandidateAIArtifactFeedback
CandidateCareerFact
```

This removes the V1 magic-string `ApplicationAnswer` storage pattern from the V2 architecture while
leaving V1 compatibility routes in place for regression stability.

## Quality and cost

The protected AI quality service reports measured run, latency, usage, configured-cost, candidate
verification and feedback metrics. Missing provider usage is represented as missing/zero evidence,
not estimated token counts.

Deterministic rules and retrieval still run before high-value model work. Model invocation is used
only where it adds candidate value; failures surface as queued, processing, failed or retryable, and
the product never claims completion without a validated persisted result.

## Deployment boundary

Terraform now contains a dedicated AI queue/DLQ, worker, universal queue-aware outbox, conditional
Secrets Manager access, log groups and alarms. V2 release/verification workflows activate and inspect
that runtime.

Real AWS/Vercel/Clerk/model acceptance is still external evidence. No source document or CI result
should claim those resources exist until the staging workflows have actually been run successfully.
