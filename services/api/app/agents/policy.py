from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_models import AgentApproval, AgentRun
from app.agent_policy_models import AgentRuntimePolicy
from app.agents.contracts import AgentDefinition
from app.agents.enums import ApprovalStatus, ExecutionClass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_runtime_policy(session: Session, *, agent_name: str, agent_version: str) -> AgentRuntimePolicy | None:
    return session.scalar(
        select(AgentRuntimePolicy).where(
            AgentRuntimePolicy.agent_name == agent_name,
            AgentRuntimePolicy.agent_version == agent_version,
        )
    )


def assert_agent_enabled(session: Session, definition: AgentDefinition) -> None:
    if not definition.enabled:
        raise PermissionError("AGENT_DISABLED_BY_DEFINITION")
    policy = get_runtime_policy(session, agent_name=definition.name, agent_version=definition.version)
    if policy is not None and policy.enabled_override is False:
        raise PermissionError("AGENT_DISABLED_BY_OPERATOR")
    if policy is not None and policy.paused_at is not None:
        raise PermissionError("AGENT_PAUSED_BY_OPERATOR")


def effective_max_cost(session: Session, definition: AgentDefinition) -> Decimal:
    policy = get_runtime_policy(session, agent_name=definition.name, agent_version=definition.version)
    if policy is not None and policy.max_cost_usd_override is not None:
        return min(Decimal(str(definition.max_cost_usd)), Decimal(str(policy.max_cost_usd_override)))
    return Decimal(str(definition.max_cost_usd))


def set_agent_enabled(
    session: Session,
    *,
    agent_name: str,
    agent_version: str,
    enabled: bool,
    reason: str | None,
    updated_by: str,
) -> AgentRuntimePolicy:
    policy = get_runtime_policy(session, agent_name=agent_name, agent_version=agent_version)
    if policy is None:
        policy = AgentRuntimePolicy(agent_name=agent_name, agent_version=agent_version)
        session.add(policy)
    policy.enabled_override = enabled
    policy.paused_at = None if enabled else utcnow()
    policy.reason = reason
    policy.updated_by = updated_by
    session.flush()
    return policy


def request_approval(
    session: Session,
    *,
    run: AgentRun,
    action_type: str,
    artifact_id: uuid.UUID | None = None,
    expires_at: datetime | None = None,
    policy_version: str = "v1",
) -> AgentApproval:
    if run.execution_class != ExecutionClass.EXECUTE:
        raise ValueError("APPROVAL_ONLY_REQUIRED_FOR_EXECUTE_ACTIONS")
    existing = session.scalar(
        select(AgentApproval).where(
            AgentApproval.run_id == run.id,
            AgentApproval.action_type == action_type,
            AgentApproval.status == ApprovalStatus.PENDING,
        )
    )
    if existing is not None:
        return existing
    approval = AgentApproval(
        run_id=run.id,
        candidate_id=run.candidate_id,
        action_type=action_type,
        artifact_id=artifact_id,
        status=ApprovalStatus.PENDING,
        policy_version=policy_version,
        expires_at=expires_at,
    )
    session.add(approval)
    session.flush()
    return approval


def approve(session: Session, *, approval: AgentApproval, candidate_id: uuid.UUID) -> AgentApproval:
    if approval.candidate_id != candidate_id:
        raise PermissionError("CROSS_CANDIDATE_APPROVAL_DENIED")
    if approval.status != ApprovalStatus.PENDING:
        raise ValueError("APPROVAL_NOT_PENDING")
    if approval.expires_at is not None and approval.expires_at <= utcnow():
        approval.status = ApprovalStatus.EXPIRED
        raise ValueError("APPROVAL_EXPIRED")
    approval.status = ApprovalStatus.APPROVED
    approval.approved_at = utcnow()
    approval.approved_by = candidate_id
    return approval


def reject(session: Session, *, approval: AgentApproval, candidate_id: uuid.UUID) -> AgentApproval:
    if approval.candidate_id != candidate_id:
        raise PermissionError("CROSS_CANDIDATE_APPROVAL_DENIED")
    if approval.status != ApprovalStatus.PENDING:
        raise ValueError("APPROVAL_NOT_PENDING")
    approval.status = ApprovalStatus.REJECTED
    approval.rejected_at = utcnow()
    return approval


def assert_execute_approved(
    session: Session,
    *,
    run: AgentRun,
    action_type: str,
    artifact_id: uuid.UUID | None = None,
) -> AgentApproval:
    approval = session.scalar(
        select(AgentApproval).where(
            AgentApproval.run_id == run.id,
            AgentApproval.candidate_id == run.candidate_id,
            AgentApproval.action_type == action_type,
            AgentApproval.status == ApprovalStatus.APPROVED,
        )
    )
    if approval is None:
        raise PermissionError("EXECUTE_APPROVAL_REQUIRED")
    if approval.expires_at is not None and approval.expires_at <= utcnow():
        approval.status = ApprovalStatus.EXPIRED
        raise PermissionError("EXECUTE_APPROVAL_EXPIRED")
    if artifact_id is not None and approval.artifact_id != artifact_id:
        raise PermissionError("EXECUTE_APPROVAL_ARTIFACT_MISMATCH")
    return approval
