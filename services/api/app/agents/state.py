from __future__ import annotations

from datetime import datetime, timezone

from app.agent_models import AgentRun
from app.agents.enums import AgentRunStatus


VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    AgentRunStatus.QUEUED: frozenset({AgentRunStatus.CLAIMED, AgentRunStatus.CANCELLED, AgentRunStatus.EXPIRED}),
    AgentRunStatus.CLAIMED: frozenset({AgentRunStatus.RUNNING, AgentRunStatus.QUEUED, AgentRunStatus.CANCELLED}),
    AgentRunStatus.RUNNING: frozenset({
        AgentRunStatus.WAITING_FOR_TOOL,
        AgentRunStatus.VALIDATING,
        AgentRunStatus.WAITING_FOR_APPROVAL,
        AgentRunStatus.FAILED_RETRYABLE,
        AgentRunStatus.FAILED_TERMINAL,
        AgentRunStatus.CANCELLED,
    }),
    AgentRunStatus.WAITING_FOR_TOOL: frozenset({AgentRunStatus.RUNNING, AgentRunStatus.FAILED_RETRYABLE, AgentRunStatus.FAILED_TERMINAL}),
    AgentRunStatus.VALIDATING: frozenset({AgentRunStatus.SUCCEEDED, AgentRunStatus.FAILED_RETRYABLE, AgentRunStatus.FAILED_TERMINAL}),
    AgentRunStatus.WAITING_FOR_APPROVAL: frozenset({AgentRunStatus.RUNNING, AgentRunStatus.CANCELLED, AgentRunStatus.EXPIRED}),
    AgentRunStatus.FAILED_RETRYABLE: frozenset({AgentRunStatus.QUEUED, AgentRunStatus.CANCELLED, AgentRunStatus.EXPIRED}),
    AgentRunStatus.FAILED_TERMINAL: frozenset(),
    AgentRunStatus.SUCCEEDED: frozenset(),
    AgentRunStatus.CANCELLED: frozenset(),
    AgentRunStatus.EXPIRED: frozenset(),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def transition(run: AgentRun, target: AgentRunStatus | str) -> None:
    target_value = target.value if isinstance(target, AgentRunStatus) else str(target)
    allowed = VALID_TRANSITIONS.get(run.status, frozenset())
    if target_value not in allowed:
        raise ValueError(f"INVALID_AGENT_STATE_TRANSITION:{run.status}->{target_value}")
    run.status = target_value
    now = utcnow()
    if target_value == AgentRunStatus.RUNNING:
        run.started_at = run.started_at or now
    if target_value == AgentRunStatus.SUCCEEDED:
        run.completed_at = now
    if target_value in {AgentRunStatus.FAILED_RETRYABLE, AgentRunStatus.FAILED_TERMINAL}:
        run.failed_at = now
    if target_value in {AgentRunStatus.SUCCEEDED, AgentRunStatus.FAILED_TERMINAL, AgentRunStatus.CANCELLED, AgentRunStatus.EXPIRED}:
        run.lease_owner = None
        run.lease_acquired_at = None
        run.lease_expires_at = None
        run.heartbeat_at = None
