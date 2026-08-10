# ApplyAI Agent Runtime Operations

Updated: 2026-08-10

## Operator surfaces

The existing `/admin` application now includes Governed Agent Runtime status and controls backed by `/api/v1/internal/agents/*`.

Available operator views/actions:

- runtime overview and run status counts;
- definitions and allow-listed tools;
- recent runs/failures;
- measured token/cost groups;
- pending approvals;
- pause/enable an agent version;
- cancel a non-terminal run;
- retry a failed run;
- reject an artifact.

## Inspect a run

Use `GET /api/v1/internal/agents/runs/{run_id}` with the internal operator token. The response includes run metadata, steps, tool-call audit metadata and artifact lineage without copying full sensitive tool payloads into the operator log model.

## Retry

Retry is explicit. Failed runs are reset to `QUEUED` and a new `AGENT_RUN` task is written through the transactional outbox. Completed runs are not silently replayed.

## Cancel

Cancellation passes through the state machine. A terminal successful/failed run cannot be rewritten to cancelled.

## Lease recovery

Workers claim with a PostgreSQL row lock and lease. A live lease blocks another worker. If a worker dies and the lease expires, a new worker may recover the same logical run. Idempotency prevents a second logical artifact from being created after a completed run.

## SQS duplicate delivery

The worker treats the queue as at-least-once. Completed/terminal runs are acknowledged without replay. A transient execution failure creates a durable retry outbox event before the original delivery is acknowledged.

## DLQ

The staging and clean-room infrastructure includes a dedicated agent DLQ. A visible DLQ message raises CloudWatch/local diagnostic evidence. Operators must inspect the corresponding `AgentRun` and `error_code` before redriving.

## Cost controls

Controls exist at:

- agent-definition max cost;
- persistent operator max-cost override (lower-only relative to the source definition);
- candidate daily run limit;
- candidate daily cost limit;
- runtime daily cost limit.

A budget violation is terminal for that run and does not silently switch providers/models.

## Disable an agent

Pause/disable through the internal API or `/admin`. Runtime checks the persisted policy immediately before execution, so already-queued work cannot bypass an operator pause simply because it was enqueued earlier.

## Local evidence

```bash
pnpm agent:demo
pnpm agent:acceptance
```

`agent:demo` requires deterministic provider + in-memory task mode and prints `DETERMINISTIC_LOCAL_EVIDENCE`.

## Synthetic scale evidence

```bash
pnpm agent:scale
```

The benchmark inserts/leases 1K, 10K and 50K synthetic AgentRun records in PostgreSQL and reports claim throughput/duplicate leases. It is explicitly `SYNTHETIC_SCALE_EVIDENCE`, not proof of live candidate traffic or provider throughput.

## Trace an opportunity workflow

Filter AgentRun by `workflow_id`. Expected release-1 sequence:

`job_scout -> job_research -> resume_tailor -> resume_verifier`.

A successful verifier emits `READY_FOR_CANDIDATE`.

## Incident rules

- Provider 429/5xx/timeout: bounded retry; do not rewrite a failed output as success.
- Permission denial: terminal security failure; inspect definition/tool policy.
- Evidence verifier rejection: keep the rejected artifact; do not delete audit history.
- Queue depth growth: prioritize user-triggered/high-value work and reduce background fan-out before increasing model spend.
- DLQ visible: treat as an operational incident, not a signal to bulk redrive blindly.
