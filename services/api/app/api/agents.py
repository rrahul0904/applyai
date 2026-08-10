from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_models import AgentApproval, AgentArtifact, AgentRun
from app.agents.enums import AgentRunStatus
from app.agents.policy import approve, reject
from app.agents.runtime import execute_agent_run, queue_agent_run
from app.agents.state import transition
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.models import Job, User


router = APIRouter(prefix="/agents", tags=["agents"])

PUBLIC_AGENTS = {"job_scout", "job_research", "resume_tailor", "resume_verifier"}


class AgentRunCreate(BaseModel):
    agent_name: Literal["job_scout", "job_research", "resume_tailor", "resume_verifier"]
    job_id: uuid.UUID
    workflow_id: uuid.UUID | None = None
    context: dict = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: uuid.UUID | None
    agent_name: str
    agent_version: str
    workflow_id: uuid.UUID | None
    status: str
    execution_class: str
    queue_class: str
    attempt_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    provider: str | None
    model: str | None
    error_code: str | None


class AgentArtifactResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    job_id: uuid.UUID | None
    artifact_type: str
    status: str
    version: int
    content: dict
    evidence: dict


def _run_payload(run: AgentRun) -> dict:
    return {
        "id": run.id,
        "candidate_id": run.candidate_id,
        "job_id": run.job_id,
        "agent_name": run.agent_name,
        "agent_version": run.agent_version,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "execution_class": run.execution_class,
        "queue_class": run.queue_class,
        "attempt_count": run.attempt_count,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "cost_usd": float(run.cost_usd or 0),
        "provider": run.provider,
        "model": run.model,
        "error_code": run.error_code,
    }


def _artifact_payload(row: AgentArtifact) -> dict:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "job_id": row.job_id,
        "artifact_type": row.artifact_type,
        "status": row.status,
        "version": row.version,
        "content": row.content_json,
        "evidence": row.evidence_json,
    }


@router.post("/runs", response_model=AgentRunResponse)
def create_run(
    body: AgentRunCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    job = session.get(Job, body.job_id)
    if job is None or job.status != "ACTIVE":
        raise HTTPException(status_code=404, detail="Active job not found")
    if body.agent_name not in PUBLIC_AGENTS:
        raise HTTPException(status_code=422, detail="Unsupported agent")
    run = queue_agent_run(
        session,
        candidate_id=user.id,
        job_id=job.id,
        agent_name=body.agent_name,
        workflow_id=body.workflow_id,
        input_json=body.context,
        trigger_type="USER_REQUEST",
    )
    session.commit()
    if settings.task_queue_provider == "memory":
        execute_agent_run(run.id, settings)
        session.expire_all()
        run = session.get(AgentRun, run.id) or run
    return _run_payload(run)


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
def get_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    run = session.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.candidate_id == user.id))
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return _run_payload(run)


@router.post("/runs/{run_id}/cancel", response_model=AgentRunResponse)
def cancel_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    run = session.scalar(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.candidate_id == user.id).with_for_update()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    try:
        transition(run, AgentRunStatus.CANCELLED)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Agent run cannot be cancelled in its current state") from exc
    session.commit()
    return _run_payload(run)


@router.get("/runs/{run_id}/artifacts", response_model=list[AgentArtifactResponse])
def list_run_artifacts(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    run = session.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.candidate_id == user.id))
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    rows = list(
        session.scalars(
            select(AgentArtifact)
            .where(AgentArtifact.run_id == run.id, AgentArtifact.candidate_id == user.id)
            .order_by(AgentArtifact.version, AgentArtifact.created_at)
        )
    )
    return [_artifact_payload(row) for row in rows]


@router.post("/approvals/{approval_id}/approve")
def approve_action(
    approval_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.scalar(
        select(AgentApproval).where(AgentApproval.id == approval_id, AgentApproval.candidate_id == user.id).with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    try:
        approve(session, approval=row, candidate_id=user.id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return {"id": row.id, "status": row.status, "action_type": row.action_type}


@router.post("/approvals/{approval_id}/reject")
def reject_action(
    approval_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    row = session.scalar(
        select(AgentApproval).where(AgentApproval.id == approval_id, AgentApproval.candidate_id == user.id).with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    try:
        reject(session, approval=row, candidate_id=user.id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.commit()
    return {"id": row.id, "status": row.status, "action_type": row.action_type}
