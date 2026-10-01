# ChannelPulse OSS clean-room reverse-engineering plan

**Started:** 2026-09-22  
**Donor:** `willysharp5/ChannelPulse-oss`  
**Target product:** ApplyAI  
**Runtime adjacency:** AgentDock/shared native context-capture boundary  
**Status:** Phase 0 audit and target mapping complete; implementation not yet claimed  
**Donor license:** GNU AGPL-3.0

## Purpose and boundary

ChannelPulse OSS is useful as a behavioral/reference donor for strengthening ApplyAI's interview-preparation and interview-session surfaces. Its desktop capture/runtime ideas may also inform a reusable native capture boundary shared with AgentDock-like runtime work, but the candidate-facing product belongs in ApplyAI rather than becoming another standalone product.

Because the donor is AGPL-3.0, ApplyAI must use a clean-room reimplementation boundary unless the project deliberately elects to accept AGPL obligations. Do not copy donor source, prompt strings, UI assets, database migrations, or other protectable expression into ApplyAI. This document records observable capabilities, interfaces, architectural lessons, and independently specified acceptance criteria only.

## Observed donor capability inventory

### 1. Live interview session UX

- floating desktop overlay;
- speaker-tagged transcript and rolling conversation context;
- AI reply/follow-up assistance;
- microphone and system-audio capture;
- screenshots/screen context;
- keyboard shortcuts and compact desktop controls;
- session history and persistence.

### 2. Native capture and speech runtime

- Tauri/Rust desktop shell with OS-specific audio capture paths;
- separate system-audio and microphone handling;
- local `whisper.cpp` speech-to-text option;
- cloud speech-to-text provider paths;
- recording/turn-management logic;
- window, shortcut, permissions, and screenshot integration.

### 3. Model/provider boundary

- bring-your-own-model configuration;
- local-model support plus hosted provider adapters;
- provider/model selection independent of the main interview workflow;
- live dialogue/triage/turn orchestration;
- interview context assembled from user profile, files, session state, and optional external context.

### 4. Context, files, and memory

- document text extraction;
- embeddings/retrieval-backed file context;
- personas/profile context;
- resume/job/interview context inputs;
- optional web/research ingestion in the broader context pipeline.

### 5. Interview preparation workbenches

- behavioral question practice;
- question bank and practice progress;
- scoring, hints, feedback, and model-answer generation;
- coding workbench with execution/evaluation flow;
- system-design workbench with visual design/evaluation flow;
- assessment/reporting surfaces.

### 6. Privacy/local-first product choices

- local SQLite persistence;
- local speech recognition option;
- local/bring-your-own model paths;
- privacy/settings surface;
- explicit positioning around keeping sensitive interview data under user control.

## ApplyAI mapping

| Donor behavior | ApplyAI destination | Clean-room requirement | Initial state |
|---|---|---|---|
| Interview question bank/practice | Existing `/interview/[jobId]` and company question bank | Reuse ApplyAI's current domain model; independently specify any missing flows | Existing foundation |
| Behavioral coaching and scorecards | Interview practice history/feedback | Define evidence-bound rubrics and explainability independently | Partial foundation |
| Coding workbench | Interview preparation workspace | Use an isolated execution adapter and ApplyAI-owned evaluation contracts | New slice |
| System-design workbench | Interview preparation workspace | ApplyAI-owned canvas/schema/evaluator | New slice |
| Live transcript/session | Interview session domain | New session/transcript/turn contracts with explicit consent | New slice |
| Mic/system-audio/screen capture | Typed native context-capture adapter | Keep OS-specific capture behind a reusable runtime boundary | New slice |
| Local STT | Speech adapter | Independent `whisper.cpp` integration or another reviewed local engine | New slice |
| Cloud STT | Speech adapter | Provider abstraction, secret isolation, redaction policy | New slice |
| BYO/local LLM | Existing AI/provider boundary | Extend existing provider contracts without weakening evidence/provenance | Extension |
| Resume/JD/persona/files context | Existing Career Memory + resume/job evidence | Preserve evidence references and provenance | Existing/extension |
| Local persistence/privacy controls | Candidate privacy + desktop runtime | Define retention/export/delete and secret-storage rules | New slice |

## Target architecture

ApplyAI should not copy the donor's application structure. The intended architecture is:

```text
ApplyAI interview UI
       |
       v
InterviewSession / InterviewTurn domain
       |
       +--> Context assembler
       |      resume + job + Career Memory + approved files
       |
       +--> Speech adapter
       |      local STT | reviewed cloud STT
       |
       +--> Context-capture adapter
       |      mic | system audio | screenshot/screen
       |
       +--> Existing governed AI provider boundary
       |      prompt/schema/version/provenance/cost evidence
       |
       +--> Practice engines
              behavioral | coding sandbox | system design
```

The web product remains canonical. Native desktop capture is an optional client/runtime capability, not a second source of truth for candidate/job/application data.

## Implementation phases

### Phase 0 — donor audit and clean-room map — COMPLETE

- inventory donor product surface;
- identify AGPL boundary;
- map user-facing capabilities into ApplyAI;
- identify native capture as a reusable runtime concern;
- distinguish repository implementation from external/runtime certification.

### Phase 1 — governed interview-session foundation

Implement the smallest durable model before native capture:

- `InterviewSession`, `InterviewTurn`, and transcript-segment persistence;
- explicit source labels (`candidate_mic`, `remote_audio`, `manual_note`, `screen_context`);
- consent/state transitions for capture;
- retention and deletion controls;
- provider-run provenance using existing ApplyAI AI-run/artifact contracts;
- latency and error telemetry that contains no raw transcript by default.

**Exit:** deterministic API/tests can create, append to, end, reload, export, and delete a session without a desktop client.

### Phase 2 — speech and live-turn pipeline

- typed speech adapter;
- local STT implementation first where feasible;
- reviewed cloud STT adapters behind environment configuration;
- incremental transcript updates;
- turn segmentation and interruption-safe state handling;
- retry/backpressure and session recovery;
- measured end-to-end latency budget.

**Exit:** recorded fixtures and a manual local session pass through speech -> transcript -> governed AI suggestion without unsupported evidence claims.

### Phase 3 — optional native context capture

- desktop/native client boundary;
- macOS/Windows/Linux capability matrix;
- microphone capture;
- system-audio capture where supported;
- user-initiated screenshot/screen context;
- visible capture state and stop control;
- OS permission denial/revocation behavior;
- secure secret storage and crash recovery.

**Exit:** supported OS paths are browser/manual-UAT certified; unsupported paths fail closed rather than silently degrading privacy controls.

### Phase 4 — context intelligence

- resume/job/Career Memory context assembler;
- approved file retrieval with evidence references;
- persona/profile preferences as candidate-owned context;
- screenshot/vision context behind explicit user action;
- source provenance on generated coaching output;
- context-size budgeting and redaction.

**Exit:** every material claim sourced from candidate/job/file evidence is traceable to an approved source; unsupported evidence references fail closed.

### Phase 5 — preparation workbenches

- behavioral practice workspace and scorecard;
- clean-room model-answer/hint flow;
- isolated coding runner with language/time/resource limits;
- code evaluation separated from model commentary;
- system-design canvas/schema plus evidence-backed review rubric;
- practice history, progress, and comparison reporting.

**Exit:** each workbench has unit/integration coverage, abuse/resource limits, and user-visible explanation of automated scoring limitations.

### Phase 6 — hardening and certification

- accessibility and keyboard-only flows;
- signed desktop builds and update strategy if desktop is shipped;
- permission/security threat model;
- secret storage review;
- coding-sandbox isolation review;
- cross-platform capture matrix;
- privacy/retention verification;
- recovery/resume tests;
- hosted provider acceptance and cost/latency measurement;
- release evidence pinned to exact commit/head.

## Product and safety constraints

- ApplyAI should frame live assistance as user-controlled interview preparation/coaching and must not market stealth, concealment, evasion, or bypassing interviewer/employer controls.
- Capture must be obvious to the user, independently stoppable, and permission-aware.
- Do not infer or fabricate claims about the candidate; preserve ApplyAI's evidence-boundary semantics.
- Do not send raw transcripts/screens to a cloud provider unless the user has enabled the relevant provider/capture path and the product can explain that data flow.
- No telemetry should silently collect raw interview audio/transcripts/screens.

## Key engineering risks

1. **AGPL contamination:** keep implementation independent and review provenance of any ported behavior.
2. **OS audio complexity:** system-audio APIs and permissions differ substantially across macOS, Windows, and Linux.
3. **Speech latency/quality:** local STT performance varies by hardware/model; cloud STT adds network, cost, and privacy boundaries.
4. **Secret handling:** provider keys and desktop tokens need OS-grade or equivalent reviewed storage rather than convenient plaintext persistence.
5. **Coding sandbox:** arbitrary code execution requires isolation, quotas, timeouts, and restricted network/filesystem access.
6. **Overclaiming scoring quality:** practice scores must be presented as coaching signals, not predictions of employer decisions.
7. **External certification:** repository tests cannot prove real OS permissions, signed builds, provider acceptance, or production latency.

## Definition of end-to-end parity for ApplyAI

Do not call this donor fully reverse-engineered/implemented until ApplyAI can demonstrate, with exact-head evidence:

- durable interview session/transcript lifecycle;
- user-controlled microphone/system-audio capture on each claimed OS;
- at least one reviewed local STT path and any claimed cloud STT paths;
- governed suggestion generation with provider/schema/provenance records;
- resume/job/file context with evidence references;
- behavioral practice and scorecard;
- coding practice in a bounded sandbox;
- system-design practice/evaluation;
- history/export/delete/privacy workflows;
- recovery after interruption;
- accessibility and browser/native UAT;
- release/security/privacy certification for every environment claimed as production-ready.

## Smallest next repository slice

Implement **Phase 1 only**: the governed `InterviewSession`/`InterviewTurn`/transcript contract in the existing FastAPI + PostgreSQL modular monolith, with API/service tests and candidate-ownership/retention rules. Do not begin by cloning the desktop overlay. This gives ApplyAI a canonical, testable domain boundary that later speech, native capture, and all three practice workbenches can depend on without creating a second system of record.
