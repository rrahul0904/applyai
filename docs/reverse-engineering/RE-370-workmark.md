# RE-370 — Workmark capability-donor research

Research date: 2026-10-01 (America/New_York)

## Source target

- Reddit launch: https://www.reddit.com/r/IMadeThis/comments/1wv75s1/i_made_a_resum%C3%A9_that_finds_work_for_you_for_cs/
- Product: https://www.workmark.org/
- How it works: https://www.workmark.org/how-it-works
- Levels: https://www.workmark.org/levels
- Employer view: https://www.workmark.org/business
- Privacy: https://www.workmark.org/privacy

The Reddit launch described Workmark as a CS student / entry-level product that connects GitHub, infers skills from work already built, gives a roadmap, and matches jobs, internships, hackathons, fellowships, open-source work, events, and perks. At research time the Reddit post had 0 comments, so there was no direct comment feedback to incorporate.

## Publicly observable product behavior

Workmark's first-party pages describe a loop of:

1. user-selected GitHub repositories;
2. a proof-based skills record and evidence-depth levels;
3. target-role skill gaps;
4. guided projects with task/verification workflow;
5. matched opportunities;
6. an opt-in employer-facing view.

Its published methodology says repository selection is user-controlled and that analysis uses repository metadata such as manifests/build files, import relationships, commit dates/authorship and tests. Its public copy says source-code bodies are not stored/read. Its level descriptions distinguish beginner/intermediate/advanced evidence depth and explicitly reserve later confirmation-based levels for future collaborator/dependency evidence.

The privacy page says the service uses GitHub as its outside source after authorization and names service providers including GitHub, Anthropic, Voyage AI, Supabase, Vercel and Resend. Those vendor disclosures are not sufficient evidence of Workmark's private architecture or algorithms.

## What is fact vs inference

### Verified from public product material

- chosen-repository GitHub evidence is central to the candidate record;
- evidence depth/repetition matters more than a raw technology count;
- users can inspect/challenge evidence;
- skill gaps feed guided project recommendations;
- opportunities span more than jobs;
- employer access is intended to be candidate-controlled;
- the product publishes a human-decision boundary for hiring.

### Not verified

- internal scoring weights or model prompts;
- exact repository parser implementation;
- private database schema;
- exact matching/ranking algorithm;
- production scale, accuracy or hiring-outcome performance;
- source code, because no public Workmark repository was identified in this research.

## Comparator scan

Public comparator repositories found during research include:

- SkillSync — CV + GitHub audit, skill-gap analysis, job matching, recruiter/university surfaces: https://github.com/malik-builds/SkillSync
- campus-opportunity-recommender — deterministic opportunity matching and skill-gap feedback: https://github.com/aakashp2008/campus-opportunity-recommender
- KaushalSetu — academia/industry skill mapping, gaps and explainable career matching: https://github.com/codedby-jay/kaushalsetu

These reinforce the broader market pattern, but the Workmark capability donor is specifically the proof-of-work -> evidence depth -> gap -> guided next-build loop.

## ApplyAI integration decision

Do not create a second career platform. ApplyAI already owns the portfolio, Career Intelligence, job matching, opportunity ingestion, employer, privacy/export and candidate-evidence surfaces. RE-370 therefore contributes one bounded vertical slice:

`public GitHub evidence -> deterministic signals -> evidence depth -> transparent role gaps -> next-build recommendation`

Phase A intentionally does not implement private GitHub App access, arbitrary source-code reading, opaque candidate ranking, auto-application behavior, or Workmark parity.

## Prototype acceptance boundary

The prototype must:

- scan at most six recent non-fork, non-archived public repositories owned by the supplied GitHub account;
- use repository metadata and root artifact names only;
- preserve repository-level evidence receipts;
- call recurrence `Observed`, `Repeated`, or `Sustained` without calling it proficiency;
- show transparent target-role requirements and missing evidence;
- generate one bounded project brief with acceptance criteria;
- not write to GitHub;
- fail clearly on invalid usernames, upstream errors and rate limits.
