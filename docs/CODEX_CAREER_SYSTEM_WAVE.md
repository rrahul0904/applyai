# ApplyAI Career System — Codex Implementation Wave

## Mission

Turn ApplyAI's existing resume, job intelligence, application, browser-agent, career-memory, and interview capabilities into one cohesive candidate workflow inspired by the public value proposition of modern AI career platforms, while keeping ApplyAI's original architecture, UX, copy, safety model, and implementation.

This is **not** a Websumes clone and does not replace ApplyAI's existing domains. It composes them.

## Product outcome

For any target job, a candidate should be able to open one **Career System** and understand:

1. Is my verified profile/resume ready?
2. How strong is the role fit, and why?
3. Is a tailored resume ready?
4. Is the cover letter/application package ready?
5. What recruiter outreach should I send?
6. What follow-up should I send after applying?
7. What would my public portfolio/profile say using only verified evidence?
8. Is job-specific interview preparation ready?
9. What is the next best action?

## Existing ApplyAI primitives to reuse

- `Resume`, `ResumeVersion`, `ResumeExtraction`, durable upload intents and S3 processing
- candidate profile + career-memory evidence
- explainable Career V1 match engine
- Career V2 evidence-bound AI artifacts
- evidence-locked resume tailoring
- application assistant + `ApplicationAnswer`
- application lifecycle/history
- governed application/browser agent
- `INTERVIEW_PREP` AI artifacts

Do not create parallel resume, job, application, or interview tables.

## Wave scope

### Backend

Add authenticated `/api/v1/career-system/jobs/{job_id}` composition APIs that:

- return one normalized job-specific system snapshot;
- expose latest resume processing state;
- reuse explainable match output;
- reuse application-assistant readiness and finalized resume state;
- produce deterministic recruiter outreach and post-application follow-up drafts from verified evidence;
- persist candidate-reviewed outreach/follow-up in existing application-owned answer storage;
- produce a portfolio/profile preview using only verified candidate evidence;
- expose the latest `INTERVIEW_PREP` artifact if present and safe deterministic prompts otherwise;
- return an explicit progress score and next action that measures workflow completion, **not hiring probability**.

### Web

Add a `CareerSystemPanel` to the job-detail experience with:

- progress and next action;
- resume + fit summary;
- application package state;
- outreach/follow-up drafts;
- portfolio preview;
- interview-prep action/status;
- links into existing ApplyAI resume, application, and career workflows.

### Safety

- No invented work history, skills, metrics, credentials, or outcomes.
- Generated copy must be derived from verified candidate/profile evidence and job metadata.
- Candidate review remains required before outreach or external application execution.
- Career-system progress must never be described as a hiring probability.
- Do not bypass the existing browser-agent review/approval states.

### Data model

No migration in this wave. Persist communication assets through the existing candidate-owned `ApplicationAnswer` model. Existing resume, AI artifact, application, and career-memory records remain canonical.

## Verification

- Backend tests for system snapshot, candidate isolation, asset persistence, portfolio evidence boundaries, and interview-artifact state.
- Web lint/typecheck/tests/build.
- Existing API tests must remain green.
- No production deployment or merge as part of this implementation wave.
