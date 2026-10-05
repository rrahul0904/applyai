# OpenApplyr clean-room boundary

Tracking issue: #84
Source repository: https://github.com/shivashis-adhikari/openapplyr
Observed source license: AGPL-3.0

## Purpose

OpenApplyr is used as a behavioral and architectural reference. ApplyAI must not copy source code, source comments, prompts, test fixtures or distinctive implementation text from the AGPL repository into the ApplyAI codebase.

## Allowed inputs

The ApplyAI implementation team may use:

- publicly observable product behavior;
- public README/product documentation;
- high-level architecture and component boundaries;
- generic ideas such as provenance validation, pre-send gates, pacing and candidate approval;
- independently written acceptance criteria derived from behavior;
- public ATS documentation and independently researched provider contracts.

## Prohibited reuse

Do not paste or mechanically translate:

- implementation functions/classes;
- regular expressions or algorithms copied verbatim from source;
- prompts/system messages;
- tests or fixtures;
- UI copy beyond generic product terminology;
- schemas/types whose structure is only known from the source implementation;
- source comments or documentation passages.

## Independent implementation procedure

For each donor capability:

1. write a behavioral contract in ApplyAI terms;
2. map it to existing ApplyAI domain entities and architecture;
3. define positive and negative acceptance cases without consulting source code while implementing;
4. implement in ApplyAI-native Python/TypeScript conventions;
5. run repository tests and record exact-head evidence;
6. compare only externally observable behavior and the previously written contract;
7. document intentional differences.

## Architectural boundary

ApplyAI remains the canonical system of record:

- PostgreSQL owns candidate, job, application and evidence state;
- R2/private storage owns candidate documents;
- FastAPI owns domain/API behavior;
- the durable task/outbox system owns background execution;
- Next.js/mobile/extension remain the canonical user surfaces.

A future local browser executor, if built, is a constrained execution client. It may not become a second candidate database, second job database or second policy engine.

## Browser automation safety boundary

A clean-room runner must:

- use a candidate-authorized browser/session;
- interact only with public/user-visible application flows;
- never solve/bypass CAPTCHA;
- never bypass authentication or anti-bot controls;
- never invoke undocumented private employer endpoints to evade normal form behavior;
- pause on unknown questions or consent boundaries;
- require persisted eligibility/approval policy before submission;
- emit a receipt based on observed outcome;
- never mark success merely because a click was attempted.

## Data/privacy boundary

For any local companion or mailbox integration:

- minimize transferred candidate data;
- never store raw credentials in application records;
- use platform/system secret storage where appropriate;
- scope mailbox access to explicit opt-in and job-related processing;
- preserve candidate-visible evidence for automated stage changes;
- make disconnect/delete behavior explicit.

## Licensing checkpoint

If a future implementation intentionally imports or adapts AGPL code, stop the clean-room work and perform an explicit licensing/product decision first. Do not silently mix that code into ApplyAI.