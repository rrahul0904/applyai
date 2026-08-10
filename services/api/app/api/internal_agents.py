from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_models import AgentApproval, AgentArtifact, AgentCostEvent, AgentRun, AgentStep, AgentToolCall
from app.agent_policy_models import AgentRuntimePolicy
from app.agents.enums import AgentRunStatus
from app.agents.policy import get_runtime_policy, set_agent_enabled
from app.agents.registry import AGENT_REGISTRY, get_agent_definition
from app.agents.runtime import retry_agent_run
from app.agents.state import transition
from app.agents.tools.registry import TOOL_REGISTRY
from app.core.database import get_session
from app.core.internal_auth import require_internal_api


router = APIRouter(
    prefix="/internal/agents",
    tags=["internal-agents"],
    dependencies=[Depends(require_internal_api)],
)


class PolicyWrite(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=255)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _run(row: AgentRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "candidate_id": row.candidate_id,
        "job_id": row.job_id,
        "agent_name": row.agent_name,
        "agent_version": row.agent_version,
        "workflow_id": row.workflow_id,
        "status": row.status,
        "execution_class": row.execution_class,
        "queue_class": row.queue_class,
        "priority": row.priority,
        "attempt_count": row.attempt_count,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "cost_usd": float(row.cost_usd or 0),
        "provider": row.provider,
        "model": row.model,
        "current_step": row.current_step,
        "lease_owner": row.lease_owner,
        "lease_expires_at": row.lease_expires_at,
        "error_code": row.error_code,
        "created_at": row.created_at,
        "completed_at": row.completed_at,
    }


@router.get("/overview")
def overview(session: Session = Depends(get_session)) -> dict[str, Any]:
    since = utcnow() - timedelta(hours=24)
    status_rows = session.execute(
        select(AgentRun.status, func.count()).group_by(AgentRun.status)
    ).all()
    cost_24h = session.scalar(
        select(func.coalesce(func.sum(AgentCostEvent.cost_usd), 0)).where(AgentCostEvent.created_at >= since)
    )
    approvals = session.scalar(
        select(func.count()).select_from(AgentApproval).where(AgentApproval.status == "PENDING")
    )
    failures_24h = session.scalar(
        select(func.count()).select_from(AgentRun).where(
            AgentRun.created_at >= since,
            AgentRun.status.in_(["FAILED_RETRYABLE", "FAILED_TERMINAL"]),
        )
    )
    return {
        "definitions": len(AGENT_REGISTRY),
        "tools": len(TOOL_REGISTRY),
        "runs_by_status": {str(status): int(count) for status, count in status_rows},
        "failures_24h": int(failures_24h or 0),
        "pending_approvals": int(approvals or 0),
        "cost_usd_24h": float(cost_24h or 0),
    }


@router.get("/definitions")
def definitions(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    items = []
    for key in sorted(AGENT_REGISTRY):
        definition = AGENT_REGISTRY[key]
        policy = get_runtime_policy(session, agent_name=definition.name, agent_version=definition.version)
        items.append({
            "name": definition.name,
            "version": definition.version,
            "description": definition.description,
            "execution_class": definition.execution_class,
            "allowed_tools": sorted(definition.allowed_tools),
            "denied_tools": sorted(definition.denied_tools),
            "queue_class": definition.queue_class,
            "max_steps": definition.max_steps,
            "timeout_seconds": definition.timeout_seconds,
            "max_cost_usd": float(definition.max_cost_usd),
            "definition_enabled": definition.enabled,
            "enabled_override": policy.enabled_override if policy else None,
            "paused_at": policy.paused_at if policy else None,
            "policy_reason": policy.reason if policy else None,
        })
    return items


@router.get("/tools")
def tools() -> list[dict[str, Any]]:
    return [
        {
            "name": row.name,
            "version": row.version,
            "execution_class": row.execution_class,
            "sensitive": row.sensitive,
            "audit_required": row.audit_required,
        }
        for row in sorted(TOOL_REGISTRY.values(), key=lambda item: item.name)
    ]


@router.get("/runs")
def runs(
    status: str | None = None,
    agent_name: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(AgentRun)
    if status:
        query = query.where(AgentRun.status == status)
    if agent_name:
        query = query.where(AgentRun.agent_name == agent_name)
    rows = list(session.scalars(query.order_by(AgentRun.created_at.desc()).limit(limit)))
    return [_run(row) for row in rows]


@router.get("/runs/{run_id}")
def run_detail(run_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(AgentRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    steps = list(session.scalars(select(AgentStep).where(AgentStep.run_id == row.id).order_by(AgentStep.position)))
    tools = list(session.scalars(select(AgentToolCall).where(AgentToolCall.run_id == row.id).order_by(AgentToolCall.created_at)))
    artifacts = list(session.scalars(select(AgentArtifact).where(AgentArtifact.run_id == row.id).order_by(AgentArtifact.version)))
    return {
        **_run(row),
        "steps": [
            {"id": item.id, "name": item.step_name, "status": item.status, "attempt": item.attempt,
             "provider": item.provider, "model": item.model, "cost_usd": float(item.cost_usd or 0),
             "error_code": item.error_code, "output_ref": item.output_ref}
            for item in steps
        ],
        "tool_calls": [
            {"id": item.id, "tool": item.tool_name, "status": item.status, "execution_class": item.execution_class,
             "latency_ms": item.latency_ms, "error_code": item.error_code}
            for item in tools
        ],
        "artifacts": [
            {"id": item.id, "type": item.artifact_type, "status": item.status, "version": item.version,
             "evidence": item.evidence_json}
            for item in artifacts
        ],
    }


@router.get("/failures")
def failures(limit: int = Query(default=100, ge=1, le=500), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    rows = list(session.scalars(
        select(AgentRun)
        .where(AgentRun.status.in_(["FAILED_RETRYABLE", "FAILED_TERMINAL"]))
        .order_by(AgentRun.failed_at.desc().nullslast(), AgentRun.created_at.desc())
        .limit(limit)
    ))
    return [_run(row) for row in rows]


@router.get("/cost")
def cost(days: int = Query(default=7, ge=1, le=90), session: Session = Depends(get_session)) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    rows = session.execute(
        select(
            AgentCostEvent.agent_name,
            AgentCostEvent.provider,
            AgentCostEvent.model,
            func.count(),
            func.coalesce(func.sum(AgentCostEvent.cost_usd), 0),
            func.coalesce(func.sum(AgentCostEvent.input_tokens), 0),
            func.coalesce(func.sum(AgentCostEvent.output_tokens), 0),
        )
        .where(AgentCostEvent.created_at >= since)
        .group_by(AgentCostEvent.agent_name, AgentCostEvent.provider, AgentCostEvent.model)
    ).all()
    return {
        "days": days,
        "groups": [
            {
                "agent_name": agent,
                "provider": provider,
                "model": model,
                "runs": int(count),
                "cost_usd": float(total or 0),
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
            }
            for agent, provider, model, count, total, input_tokens, output_tokens in rows
        ],
    }


@router.get("/approvals")
def approvals(status: str | None = None, session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    query = select(AgentApproval)
    if status:
        query = query.where(AgentApproval.status == status)
    rows = list(session.scalars(query.order_by(AgentApproval.requested_at.desc()).limit(500)))
    return [
        {"id": row.id, "run_id": row.run_id, "candidate_id": row.candidate_id, "action_type": row.action_type,
         "artifact_id": row.artifact_id, "status": row.status, "requested_at": row.requested_at,
         "expires_at": row.expires_at}
        for row in rows
    ]


@router.post("/runs/{run_id}/retry")
def retry(run_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    try:
        retry_agent_run(session, row)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return _run(row)


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
    if row is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    try:
        transition(row, AgentRunStatus.CANCELLED)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Agent run cannot be cancelled") from exc
    session.commit()
    return _run(row)


@router.post("/definitions/{agent_name}/{agent_version}/enabled")
def change_enabled(
    agent_name: str,
    agent_version: str,
    body: PolicyWrite,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        get_agent_definition(agent_name, agent_version)
    except (KeyError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail="Agent definition not found") from exc
    policy = set_agent_enabled(
        session,
        agent_name=agent_name,
        agent_version=agent_version,
        enabled=body.enabled,
        reason=body.reason,
        updated_by="internal-operator",
    )
    session.commit()
    return {
        "agent_name": policy.agent_name,
        "agent_version": policy.agent_version,
        "enabled_override": policy.enabled_override,
        "paused_at": policy.paused_at,
        "reason": policy.reason,
    }


@router.post("/artifacts/{artifact_id}/reject")
def reject_artifact(artifact_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(AgentArtifact, artifact_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent artifact not found")
    row.status = "REJECTED_BY_OPERATOR"
    session.commit()
    return {"id": row.id, "status": row.status}
