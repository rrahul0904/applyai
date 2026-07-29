# AI Architecture

## Status

Advanced AI work is intentionally NOT STARTED during the foundation milestone.

## Governing rules

- Structured product data is the source context.
- Document facts, user-verified facts, and AI inferences remain distinct.
- AI cannot invent employers, dates, education, skills, metrics, duties, or
  achievements.
- Suggestions require user review before profile or application mutation.
- Every task records model, prompt, schema, latency, cost, and outcome.
- Outputs must pass Pydantic/JSON-schema validation.

## Planned task boundary

AI tasks will be asynchronous and idempotent:

- resume structure and suggestion analysis;
- deep job match explanation;
- factual resume rewrite suggestions;
- cover-letter drafts;
- interview preparation;
- career guidance grounded in candidate and job data.

## Safety and cost

Deterministic rules and retrieval run first. Expensive models run only for
high-value tasks. Failures surface as queued, processing, failed, or retryable;
the product never claims completion when no valid result exists.
