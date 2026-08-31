# ApplyAI Recruiter Lens — Wave 1

## Mission

Add a candidate-side **Recruiter Lens** to ApplyAI using only publicly observable product behavior from JAN Screening as inspiration. This is a clean-room implementation with original architecture, UX, copy, scoring logic, and code.

The goal is not to turn ApplyAI into an ATS or employer screening platform. The goal is to answer a candidate question ApplyAI is uniquely positioned to answer:

> If a strong recruiter screened my verified evidence against this exact role, what would they see, what would concern them, and what would they ask me next?

## Publicly observed inspiration

JAN publicly presents a workflow built around:

- uploading resumes;
- defining job-specific screening criteria;
- evidence-backed scoring and A/B/C/D tiering;
- explicit concerns and rationale;
- interview questions derived from unanswered resume gaps;
- blind/compliance-aware screening;
- reusable criteria;
- shareable reports;
- high-volume batch screening, ATS integration, and candidate-pool analytics for enterprise users.

ApplyAI Wave 1 intentionally implements only the candidate-relevant subset.

## Product decision

### Build now: Recruiter Lens

Recruiter Lens is a self-assessment simulation embedded in the existing job-specific Career System.

It must:

1. derive job-relevant criteria from ApplyAI's structured job skills and requirements;
2. evaluate only saved candidate evidence relevant to work history and skills;
3. classify each criterion as `SUPPORTED`, `PARTIAL`, or `NOT_EVIDENCED`;
4. show the evidence snippet behind each supported/partial criterion;
5. produce a 0-100 **screening readiness score** and A-D readiness tier;
6. surface the most important concerns without inventing deficiencies;
7. generate gap-driven interview questions;
8. clearly state that the result is a candidate-side simulation, not an employer score, hiring probability, or automated employment decision;
9. reuse the existing Career System payload and UI rather than create a parallel product.

### Defer

Do not add in Wave 1:

- employer accounts;
- bulk candidate upload;
- candidate ranking against other people;
- ATS integrations;
- automated rejection or advancement;
- applicant-pool analytics;
- public share links;
- custom employer screening criteria persistence;
- any workflow that would make ApplyAI an Automated Employment Decision Tool.

Those capabilities belong in a future employer product only if ApplyAI deliberately enters that market and implements the required legal/compliance controls.

## Clean-room constraints

- Do not copy JAN source code, prompts, scoring weights, visual assets, copy, private APIs, or implementation details.
- Do not attempt to infer or reproduce patent-pending internals.
- Use only public product behavior as problem-space inspiration.
- Use original names, labels, data structures, deterministic scoring logic, UX, and tests.

## Existing ApplyAI systems to reuse

- `candidate_context(...)` for verified profile, experience, roles, and skills;
- structured `JobSkill` and `JobRequirement` records;
- existing `career-v1` explainable fit engine;
- existing Career System endpoint and job detail UI;
- existing interview-prep artifact pipeline;
- existing candidate review/evidence safety model.

No database migration is required for Wave 1.

## Backend design

Create `services/api/app/recruiter_lens.py` with a deterministic builder:

`build_recruiter_lens(session, user, job) -> dict`

### Criteria

Build criteria from:

- required job skills first;
- preferred job skills second;
- required job requirements next;
- optional requirements only when needed to reach useful coverage.

Keep the response bounded to a maximum of 12 criteria.

### Evidence matching

For every criterion:

- use exact normalized skill matching when available;
- otherwise use meaningful token overlap against verified profile summary, current title, target roles, experience titles/descriptions, and skills;
- ignore generic stop words;
- never infer employers, credentials, metrics, years, or responsibilities that do not exist in saved evidence.

### Criterion status

- `SUPPORTED`: direct or strong verified evidence;
- `PARTIAL`: adjacent evidence exists but the requirement is not explicit enough;
- `NOT_EVIDENCED`: ApplyAI cannot find verified evidence supporting the criterion.

### Scoring

Compute a weighted 0-100 readiness score from criterion statuses.

Required criteria carry more weight than preferred criteria.

Suggested deterministic value map:

- `SUPPORTED` = 1.0
- `PARTIAL` = 0.55
- `NOT_EVIDENCED` = 0.0

Tier mapping:

- A: 85-100
- B: 70-84
- C: 55-69
- D: below 55

This is an ApplyAI readiness tier only.

### Concerns

Return up to five evidence-bound concerns, prioritizing:

1. required `NOT_EVIDENCED` criteria;
2. required `PARTIAL` criteria;
3. preferred `NOT_EVIDENCED` criteria.

### Interview questions

Return up to six questions targeted at gaps. Questions should ask the candidate to clarify or supply a truthful example; they must never suggest fabricating missing experience.

## Career System integration

Extend `services/api/app/api/career_system.py` to include:

```json
"recruiter_lens": {
  "score": 0,
  "tier": "A|B|C|D",
  "confidence": "HIGH|MEDIUM|LOW",
  "criteria_source": "STRUCTURED_JOB_POSTING",
  "criteria": [],
  "concerns": [],
  "interview_questions": [],
  "disclaimer": "...",
  "policy": {
    "candidate_self_assessment": true,
    "employer_prediction": false,
    "identity_fields_used": false
  }
}
```

## Web UX

Add a **Recruiter Lens** section inside the current Career System panel.

Show:

- A-D tier prominently;
- screening readiness score;
- supported / partial / not-evidenced counts;
- top criteria with evidence status;
- top concerns;
- 3-4 gap-driven interview questions;
- an explicit disclaimer that this is not an employer decision or hiring probability.

Use existing ApplyAI UI components and visual language. Do not imitate JAN screenshots.

## Test requirements

Backend tests must verify:

- deterministic score and tier;
- supported skills are backed by candidate evidence;
- unsupported required criteria become concerns;
- interview questions are generated from gaps;
- no identity fields are used;
- endpoint continues to return existing Career System fields.

Web tests must verify:

- Recruiter Lens renders from the Career System response;
- tier and readiness score are visible;
- gap criteria and interview questions render;
- disclaimer is visible;
- existing Career System actions remain functional.

## Definition of done

Wave 1 is complete when:

- Recruiter Lens is visible on the job detail Career System;
- scoring is deterministic and evidence-bound;
- no migration or new external AI dependency is required;
- backend and web tests pass;
- lint/typecheck/build pass;
- no production deployment or merge is performed automatically.
