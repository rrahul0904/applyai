# OpenApplyr donor implementation plan

Tracking issue: #84
Branch: `re/openapplyr-intake-84`

## Goal

Adopt the strongest OpenApplyr behavioral ideas inside ApplyAI without creating a parallel product or weakening ApplyAI's existing safety and verification boundaries.

## Phase 0 — Intake and clean-room specification

Deliverables:

- source analysis;
- feature parity matrix;
- clean-room boundary;
- implementation plan;
- exact source head and license recorded;
- explicit rejected behaviors.

Exit criteria: another engineer can implement the first slice using only these ApplyAI-authored contracts.

## Phase 1 — Deterministic resume factuality

Build an ApplyAI-native factuality validator around existing candidate evidence and resume-tailoring artifacts.

Required behavior:

- every generated work/project bullet carries one or more evidence references;
- numeric claims must be supported by referenced candidate evidence;
- named technologies/entities must be supported by referenced evidence or verified skills;
- employer/title/start/end metadata cannot drift from the verified profile;
- unsupported generated content fails validation;
- the API returns structured issue records;
- a safe fallback may restore supported/source wording rather than inventing replacements.

Required negative tests:

- invented percentage;
- invented dollar/revenue metric;
- invented technology;
- technology borrowed from a different role without evidence;
- changed employer;
- changed title;
- changed dates;
- missing evidence ID;
- unknown evidence ID.

## Phase 2 — Unified package eligibility gates

Create one canonical persisted gate evaluation for a candidate application package.

Initial gates:

- job open/current enough to apply;
- match threshold satisfied when configured;
- no blocking source/risk signal;
- all required answers available;
- generated open-text answer policy satisfied;
- resume factuality clean;
- optional reviewer clean;
- candidate approval state valid.

The gate result must include version, input references, per-gate outcome and timestamp. Re-evaluate when material inputs change.

Exit criteria: no future browser executor can obtain an eligible task when a required gate fails.

## Phase 3 — Application pacing and duplicate policy

Add explicit execution-policy primitives:

- per-search daily cap;
- candidate-wide daily cap;
- same-company cooldown;
- active-hours window;
- scheduling jitter;
- duplicate canonical-job/application protection;
- idempotency key for execution attempts.

These policies delay or refuse execution but do not mutate package correctness gates.

## Phase 4 — ATS coverage expansion

Evaluate independent public integrations for:

- Workday;
- Workable;
- Recruitee.

For each source first implement discovery/normalization and closure/apply-URL evidence. Do not couple ingestion success to browser submission support.

Exit criteria per adapter: fixtures + contract tests + real public endpoint/page acceptance where allowed.

## Phase 5 — Constrained browser execution proof

Start with exactly one reviewed ATS/application shape.

Execution state machine:

`requested -> inspected -> prepared -> awaiting_approval -> eligible -> executing -> submitted|paused|failed|unknown`

Rules:

- no CAPTCHA bypass;
- no credential harvesting;
- no private endpoint circumvention;
- pause on login/consent/unknown required fields;
- require gate receipt + approval/policy receipt;
- record field actions without secrets;
- require observable submission confirmation for `submitted`;
- retries must be idempotent or explicitly manual-review-only.

Do not expose a production auto-apply claim until a real candidate-controlled browser run is verified end to end.

## Phase 6 — Reply tracking and outreach

Add an opt-in mailbox boundary only after application identity/correlation is reliable.

Capabilities:

- associate job-related messages with canonical applications;
- propose stage transitions with evidence;
- candidate confirms ambiguous changes;
- draft recruiter/hiring-manager follow-up;
- send only with explicit approval unless the user has separately configured a bounded communication policy;
- keep full mailbox access outside normal product data surfaces.

## Phase 7 — Provider/budget enhancements

Extend current AI runtime metadata into candidate-visible controls where useful:

- per-task provider/model disclosure;
- estimated cost ledger;
- daily/monthly AI-spend ceiling;
- optional BYO/local execution policy;
- fail closed when output/evidence schemas do not validate.

A local model is an optional provider path, not a reason to move the canonical ApplyAI database to the desktop.

## Phase 8 — UX integration

Surface the new contracts in existing canonical pages rather than new duplicate dashboards:

- Resume Studio: evidence/factuality status and issue repair;
- Application detail: package gates and approval state;
- Settings: pacing/autopilot/budget policy;
- Operations/Admin: gate failure distributions, executor failures and adapter quality;
- Notifications: paused application requiring candidate input.

## Verification ladder

For every phase:

1. focused unit tests;
2. domain/API integration tests;
3. persistence/migration tests when schema changes;
4. web contract/type tests for surfaced UX;
5. exact-head CI;
6. real-environment evidence for external providers/browser/mail;
7. explicit residual-gap note.

Repository-green is not equivalent to hosted/browser/provider verified.

## Smallest next code change

Implement Phase 1 only: deterministic resume factuality plus structured issues, integrated into the existing resume-tailoring artifact path. Do not add browser auto-submit in the same PR.

A follow-up PR can then make package eligibility consume that validator as a required gate.