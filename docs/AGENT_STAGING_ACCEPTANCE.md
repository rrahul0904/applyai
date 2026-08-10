# ApplyAI Governed Agent Staging Acceptance

Updated: 2026-08-10

Repository implementation and deterministic clean-room evidence are not live-provider evidence. This runbook is the gate for `LIVE_STAGING_VERIFIED`.

## Preconditions

Staging must have:

- real PostgreSQL/Aurora;
- transactional outbox publisher;
- dedicated `applyai-staging-agent-tasks` SQS queue and DLQ;
- ECS Agent Worker enabled intentionally (`agent_worker_desired_count > 0`);
- real provider secret available only to authorized AI/agent workers;
- configured real canonical job source;
- candidate fixture/profile whose evidence may be used for acceptance;
- internal operator token available through the approved secret path.

## Required workflow

Use a **real canonical job** that arrived through an approved live job source. Do not manually fabricate the job only to make acceptance pass.

Execute:

```text
Job Scout
 -> STRONG/APPLY_NOW
 -> Job Research
 -> Resume Tailor
 -> Resume Verifier
 -> READY_FOR_CANDIDATE
```

Capture for each run:

- run ID and workflow ID;
- agent/version;
- provider/model;
- prompt/schema version;
- input/output tokens;
- measured cost;
- latency/step evidence;
- audited tool names;
- artifact ID/version/evidence refs;
- verification result.

## Acceptance command

```bash
pnpm agent:acceptance
```

The command is fail closed.

Possible states:

- `LOCAL_RUNTIME_VERIFIED`
- `BLOCKED_EXTERNAL_CONFIGURATION`
- `STAGING_RUNTIME_AVAILABLE`
- `PASS`

`PASS` requires a complete live-provider four-agent workflow plus a real non-demo canonical job source. Deterministic/synthetic evidence cannot produce staging PASS.

## Worker-death drill

1. start a run;
2. terminate the Agent Worker while it owns a lease;
3. wait for lease/visibility recovery;
4. start/recover worker capacity;
5. prove the same logical run completes;
6. prove no duplicate canonical artifact was created.

## Duplicate-delivery drill

Deliver the same `AGENT_RUN` work twice. The completed logical run/artifact count must remain one.

## Provider-failure drill

Exercise timeout/429/5xx behavior in a controlled staging test. Prove:

- bounded retry;
- original SQS delivery does not race the explicit retry;
- no invalid artifact is marked ready;
- terminal/DLQ state is observable if retries exhaust.

## Isolation drill

Create candidate A and B. Prove B cannot read A's:

- agent run;
- artifacts;
- approvals;
- underlying candidate evidence.

## Prompt-injection drill

Use a legitimate test job whose description contains instructions requesting secret disclosure or an external action. Prove the runtime treats the text as data and executes only tools allowed by the registered agent definition.

## Approval drill

Release 1 has no external EXECUTE agent, but the approval primitive must be tested before any EXECUTE tool is enabled:

- no execution without approval;
- candidate B cannot approve candidate A;
- expired approval fails;
- approval is action/artifact specific;
- duplicate delivery does not execute twice.

## Logging review

Review API/outbox/worker logs. Confirm no:

- provider secret;
- raw resume body in operational audit telemetry;
- sensitive prompt payload unnecessarily emitted;
- cross-candidate data.

## Evidence status

Only after this runbook and `pnpm agent:acceptance = PASS` should the four release-1 agents be labeled `LIVE_STAGING_VERIFIED`. Production verification remains a separate promotion/recovery gate.
