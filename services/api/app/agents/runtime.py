from __future__ import annotations

import hashlib
import json
import socket
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_models import AgentArtifact, AgentCostEvent, AgentEvent, AgentRun, AgentStep
from app.agents.enums import AgentRunStatus, ExecutionClass, ScoutDecision, VerificationDecision
from app.agents.handlers import HANDLERS, HandlerResult
from app.agents.policy import assert_agent_enabled, effective_max_cost
from app.agents.registry import get_agent_definition
from app.agents.state import transition
from app.agents.tools.gateway import ToolGateway, ToolPermissionError
from app.ai.provider import AIProviderError, TransientAIProviderError
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task


ARTIFACT_TYPES = {
    "job_scout": "JOB_SCOUT_DECISION",
    "job_research": "JOB_RESEARCH",
    "resume_tailor": "TAILORED_RESUME",
    "resume_verifier": "RESUME_VERIFICATION",
}

EVENT_TYPES = {
    "job_scout": "JOB_RECOMMENDATION_CREATED",
    "job_research": "JOB_RESEARCH_COMPLETED",
    "resume_tailor": "RESUME_DRAFT_CREATED",
    "resume_verifier": "RESUME_VERIFICATION_COMPLETED",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _input_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(value).encode()).hexdigest()


def _estimated_cost(settings: Settings, input_tokens: int, output_tokens: int) -> Decimal:
    amount = (
        Decimal(str(settings.ai_input_cost_per_million_usd)) * Decimal(input_tokens) / Decimal(1_000_000)
        + Decimal(str(settings.ai_output_cost_per_million_usd)) * Decimal(output_tokens) / Decimal(1_000_000)
    )
    return amount.quantize(Decimal("0.000001"))


def _event(session: Session, *, run: AgentRun, event_type: str, payload: dict[str, Any] | None = None) -> AgentEvent:
    row = AgentEvent(
        run_id=run.id,
        candidate_id=run.candidate_id,
        event_type=event_type,
        payload=payload or {},
    )
    session.add(row)
    return row


def _start_of_day() -> datetime:
    return utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def _daily_candidate_cost(session: Session, candidate_id: uuid.UUID) -> Decimal:
    value = session.scalar(
        select(func.coalesce(func.sum(AgentCostEvent.cost_usd), 0)).where(
            AgentCostEvent.candidate_id == candidate_id,
            AgentCostEvent.created_at >= _start_of_day(),
        )
    )
    return Decimal(str(value or 0))


def _daily_runtime_cost(session: Session) -> Decimal:
    value = session.scalar(
        select(func.coalesce(func.sum(AgentCostEvent.cost_usd), 0)).where(
            AgentCostEvent.created_at >= _start_of_day()
        )
    )
    return Decimal(str(value or 0))


def _daily_candidate_run_count(session: Session, candidate_id: uuid.UUID) -> int:
    value = session.scalar(
        select(func.count()).select_from(AgentRun).where(
            AgentRun.candidate_id == candidate_id,
            AgentRun.created_at >= _start_of_day(),
        )
    )
    return int(value or 0)


def _root_workflow_id(
    *, candidate_id: uuid.UUID, job_id: uuid.UUID | None, agent_name: str, version: str, digest: str
) -> uuid.UUID:
    return uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"applyai-agent:{candidate_id}:{job_id or 'none'}:{agent_name}:{version}:{digest}",
    )


def queue_agent_run(
    session: Session,
    *,
    candidate_id: uuid.UUID,
    agent_name: str,
    job_id: uuid.UUID | None = None,
    version: str | None = None,
    trigger_type: str = "USER_REQUEST",
    trigger_id: str | None = None,
    workflow_type: str = "OPPORTUNITY_PREPARATION",
    workflow_id: uuid.UUID | None = None,
    input_json: dict[str, Any] | None = None,
    priority: int | None = None,
    settings: Settings | None = None,
) -> AgentRun:
    settings = settings or get_settings()
    definition = get_agent_definition(agent_name, version)
    assert_agent_enabled(session, definition)
    payload = input_json or {}
    digest = _input_hash(payload)
    workflow_id = workflow_id or _root_workflow_id(
        candidate_id=candidate_id,
        job_id=job_id,
        agent_name=definition.name,
        version=definition.version,
        digest=digest,
    )
    idempotency_key = ":".join(
        [
            "agent",
            str(candidate_id),
            str(job_id or "none"),
            definition.name,
            definition.version,
            str(workflow_id),
            digest,
        ]
    )
    existing = session.scalar(select(AgentRun).where(AgentRun.idempotency_key == idempotency_key))
    if existing is not None:
        return existing

    if _daily_candidate_run_count(session, candidate_id) >= settings.agent_candidate_daily_run_limit:
        raise RuntimeError("CANDIDATE_DAILY_RUN_LIMIT_EXCEEDED")
    runtime_limit = Decimal(str(settings.agent_runtime_daily_cost_limit_usd))
    if runtime_limit > 0 and _daily_runtime_cost(session) >= runtime_limit:
        raise RuntimeError("RUNTIME_DAILY_BUDGET_EXCEEDED")
    candidate_limit = Decimal(str(settings.agent_candidate_daily_cost_limit_usd))
    if candidate_limit > 0 and _daily_candidate_cost(session, candidate_id) >= candidate_limit:
        raise RuntimeError("CANDIDATE_DAILY_BUDGET_EXCEEDED")

    max_cost = effective_max_cost(session, definition)
    run = AgentRun(
        candidate_id=candidate_id,
        job_id=job_id,
        agent_name=definition.name,
        agent_version=definition.version,
        trigger_type=trigger_type,
        trigger_id=trigger_id,
        workflow_type=workflow_type,
        workflow_id=workflow_id,
        status=AgentRunStatus.QUEUED,
        execution_class=definition.execution_class.value,
        queue_class=definition.queue_class,
        priority=priority if priority is not None else definition.priority,
        idempotency_key=idempotency_key,
        input_json=payload,
        max_steps=definition.max_steps,
        timeout_seconds=definition.timeout_seconds,
        max_cost_usd=max_cost,
        prompt_version=definition.prompt_version,
        schema_version=definition.schema_version,
    )
    session.add(run)
    session.flush()
    _event(
        session,
        run=run,
        event_type="AGENT_RUN_REQUESTED",
        payload={"agent": run.agent_name, "version": run.agent_version},
    )
    add_task_outbox_event(
        session,
        task=Task(
            task_type="AGENT_RUN",
            payload={"run_id": str(run.id), "queue_class": run.queue_class},
            idempotency_key=f"agent-run:{run.id}:attempt:1",
        ),
        aggregate_type="AgentRun",
        aggregate_id=run.id,
    )
    return run


def claim_agent_run(
    session: Session,
    run_id: uuid.UUID,
    *,
    worker_id: str,
    settings: Settings,
) -> AgentRun | None:
    run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
    if run is None:
        return None
    now = utcnow()
    terminal = {
        AgentRunStatus.SUCCEEDED,
        AgentRunStatus.FAILED_TERMINAL,
        AgentRunStatus.CANCELLED,
        AgentRunStatus.EXPIRED,
    }
    if run.status in terminal:
        return None
    if run.status in {AgentRunStatus.CLAIMED, AgentRunStatus.RUNNING}:
        if run.lease_expires_at and run.lease_expires_at > now and run.lease_owner != worker_id:
            return None
        run.status = AgentRunStatus.CLAIMED
    elif run.status == AgentRunStatus.FAILED_RETRYABLE:
        transition(run, AgentRunStatus.QUEUED)
        transition(run, AgentRunStatus.CLAIMED)
    elif run.status == AgentRunStatus.QUEUED:
        transition(run, AgentRunStatus.CLAIMED)
    else:
        return None

    run.lease_owner = worker_id
    run.lease_acquired_at = now
    run.heartbeat_at = now
    run.lease_expires_at = now + timedelta(seconds=settings.agent_lease_seconds)
    run.attempt_count += 1
    session.commit()
    return run


def heartbeat_agent_run(run_id: uuid.UUID, *, worker_id: str, settings: Settings) -> bool:
    with SessionLocal() as session:
        run = session.scalar(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.lease_owner == worker_id).with_for_update()
        )
        if run is None or run.status not in {
            AgentRunStatus.CLAIMED,
            AgentRunStatus.RUNNING,
            AgentRunStatus.WAITING_FOR_TOOL,
            AgentRunStatus.VALIDATING,
        }:
            return False
        now = utcnow()
        run.heartbeat_at = now
        run.lease_expires_at = now + timedelta(seconds=settings.agent_lease_seconds)
        session.commit()
        return True


def _create_step(session: Session, run: AgentRun, *, name: str, position: int) -> AgentStep:
    step = AgentStep(
        run_id=run.id,
        position=position,
        step_name=name,
        step_version="v1",
        status="RUNNING",
        attempt=run.attempt_count,
        input_ref={"run_id": str(run.id)},
    )
    session.add(step)
    run.current_step = name
    session.flush()
    return step


def _latest_artifact(
    session: Session,
    *,
    candidate_id: uuid.UUID,
    job_id: uuid.UUID | None,
    artifact_type: str,
) -> AgentArtifact | None:
    return session.scalar(
        select(AgentArtifact)
        .where(
            AgentArtifact.candidate_id == candidate_id,
            AgentArtifact.job_id == job_id,
            AgentArtifact.artifact_type == artifact_type,
        )
        .order_by(AgentArtifact.version.desc(), AgentArtifact.created_at.desc())
        .limit(1)
    )


def _write_artifact(session: Session, run: AgentRun, result: HandlerResult) -> AgentArtifact:
    artifact_type = ARTIFACT_TYPES[run.agent_name]
    previous_same = _latest_artifact(
        session,
        candidate_id=run.candidate_id,
        job_id=run.job_id,
        artifact_type=artifact_type,
    )
    parent: AgentArtifact | None = None
    if run.agent_name == "resume_verifier":
        parent = _latest_artifact(
            session,
            candidate_id=run.candidate_id,
            job_id=run.job_id,
            artifact_type="TAILORED_RESUME",
        )
    version = (previous_same.version + 1) if previous_same else 1
    payload = result.output.model_dump(mode="json")
    evidence_refs = payload.get("evidence_refs") or payload.get("source_refs") or []
    status = "READY"
    if run.agent_name == "resume_tailor":
        status = "NEEDS_VERIFICATION"
    elif run.agent_name == "resume_verifier":
        status = str(payload.get("decision") or "UNKNOWN")
    artifact = AgentArtifact(
        run_id=run.id,
        candidate_id=run.candidate_id,
        job_id=run.job_id,
        artifact_type=artifact_type,
        status=status,
        version=version,
        content_json=payload,
        evidence_json={"refs": list(evidence_refs)},
        parent_artifact_id=parent.id if parent else None,
        supersedes_artifact_id=previous_same.id if previous_same else None,
        prompt_version=run.prompt_version,
        schema_version=run.schema_version,
    )
    session.add(artifact)
    session.flush()
    return artifact


def _queue_child(
    session: Session,
    *,
    parent: AgentRun,
    agent_name: str,
    trigger_type: str,
    settings: Settings,
) -> AgentRun:
    return queue_agent_run(
        session,
        candidate_id=parent.candidate_id,
        job_id=parent.job_id,
        agent_name=agent_name,
        trigger_type=trigger_type,
        trigger_id=str(parent.id),
        workflow_type=parent.workflow_type or "OPPORTUNITY_PREPARATION",
        workflow_id=parent.workflow_id,
        input_json={"parent_run_id": str(parent.id)},
        settings=settings,
    )


def _orchestrate(
    session: Session,
    run: AgentRun,
    artifact: AgentArtifact,
    *,
    settings: Settings,
) -> list[uuid.UUID]:
    payload = artifact.content_json
    queued: list[uuid.UUID] = []
    if run.agent_name == "job_scout":
        decision = str(payload.get("decision"))
        if decision in {ScoutDecision.APPLY_NOW.value, ScoutDecision.STRONG.value}:
            queued.append(
                _queue_child(
                    session,
                    parent=run,
                    agent_name="job_research",
                    trigger_type="JOB_RECOMMENDATION_CREATED",
                    settings=settings,
                ).id
            )
    elif run.agent_name == "job_research":
        if str(payload.get("status")) == "VERIFIED":
            queued.append(
                _queue_child(
                    session,
                    parent=run,
                    agent_name="resume_tailor",
                    trigger_type="JOB_RESEARCH_COMPLETED",
                    settings=settings,
                ).id
            )
    elif run.agent_name == "resume_tailor":
        queued.append(
            _queue_child(
                session,
                parent=run,
                agent_name="resume_verifier",
                trigger_type="RESUME_DRAFT_CREATED",
                settings=settings,
            ).id
        )
    elif run.agent_name == "resume_verifier":
        if str(payload.get("decision")) in {
            VerificationDecision.PASS.value,
            VerificationDecision.PASS_WITH_WARNINGS.value,
        }:
            _event(
                session,
                run=run,
                event_type="READY_FOR_CANDIDATE",
                payload={
                    "job_id": str(run.job_id),
                    "artifact_id": str(artifact.id),
                    "workflow_id": str(run.workflow_id),
                },
            )
    return queued


def _mark_current_step_failed(session: Session, run: AgentRun, *, code: str, detail: str) -> None:
    step = session.scalar(
        select(AgentStep)
        .where(
            AgentStep.run_id == run.id,
            AgentStep.attempt == run.attempt_count,
            AgentStep.status == "RUNNING",
        )
        .order_by(AgentStep.position.desc())
        .limit(1)
    )
    if step is not None:
        step.status = "FAILED"
        step.error_code = code[:80]
        step.error_detail = detail[:1000]
        step.completed_at = utcnow()


def _fail_run(run_id: uuid.UUID, *, retryable: bool, code: str, detail: str) -> bool:
    with SessionLocal() as session:
        run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None:
            return True
        definition = get_agent_definition(run.agent_name, run.agent_version)
        should_retry = retryable and run.attempt_count < definition.retry_policy.max_attempts
        target = AgentRunStatus.FAILED_RETRYABLE if should_retry else AgentRunStatus.FAILED_TERMINAL
        _mark_current_step_failed(session, run, code=code, detail=detail)
        if run.status == AgentRunStatus.CLAIMED:
            transition(run, AgentRunStatus.RUNNING)
        if run.status in {
            AgentRunStatus.RUNNING,
            AgentRunStatus.WAITING_FOR_TOOL,
            AgentRunStatus.VALIDATING,
        }:
            transition(run, target)
        else:
            run.status = target
        run.error_code = code[:80]
        run.error_detail = detail[:1000]
        _event(
            session,
            run=run,
            event_type="AGENT_RUN_FAILED",
            payload={"retryable": should_retry, "error_code": run.error_code},
        )
        if should_retry:
            run.lease_owner = None
            run.lease_acquired_at = None
            run.lease_expires_at = None
            run.heartbeat_at = None
            transition(run, AgentRunStatus.QUEUED)
            add_task_outbox_event(
                session,
                task=Task(
                    task_type="AGENT_RUN",
                    payload={"run_id": str(run.id), "queue_class": run.queue_class},
                    idempotency_key=f"agent-run:{run.id}:attempt:{run.attempt_count + 1}",
                ),
                aggregate_type="AgentRun",
                aggregate_id=run.id,
            )
        session.commit()
        return not should_retry


def execute_agent_run(
    run_id: uuid.UUID,
    settings: Settings | None = None,
    *,
    worker_id: str | None = None,
) -> bool:
    settings = settings or get_settings()
    worker_id = worker_id or f"{socket.gethostname()}:{uuid.uuid4()}"

    with SessionLocal() as session:
        claimed = claim_agent_run(session, run_id, worker_id=worker_id, settings=settings)
        if claimed is None:
            existing = session.get(AgentRun, run_id)
            return existing is None or existing.status in {
                AgentRunStatus.SUCCEEDED,
                AgentRunStatus.FAILED_TERMINAL,
                AgentRunStatus.CANCELLED,
                AgentRunStatus.EXPIRED,
            }

    try:
        with SessionLocal() as session:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run is None:
                return True
            definition = get_agent_definition(run.agent_name, run.agent_version)
            assert_agent_enabled(session, definition)
            candidate_limit = Decimal(str(settings.agent_candidate_daily_cost_limit_usd))
            runtime_limit = Decimal(str(settings.agent_runtime_daily_cost_limit_usd))
            if candidate_limit > 0 and _daily_candidate_cost(session, run.candidate_id) >= candidate_limit:
                raise RuntimeError("CANDIDATE_DAILY_BUDGET_EXCEEDED")
            if runtime_limit > 0 and _daily_runtime_cost(session) >= runtime_limit:
                raise RuntimeError("RUNTIME_DAILY_BUDGET_EXCEEDED")
            transition(run, AgentRunStatus.RUNNING)
            _create_step(session, run, name="execute_agent", position=1)
            session.commit()

        with SessionLocal() as session:
            run = session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
            if run is None:
                return True
            definition = get_agent_definition(run.agent_name, run.agent_version)
            assert_agent_enabled(session, definition)
            if definition.execution_class == ExecutionClass.EXECUTE and definition.requires_human_approval:
                raise PermissionError("EXECUTE_AGENT_REQUIRES_APPROVAL_GATE")
            gateway = ToolGateway(session, run=run, definition=definition)
            handler = HANDLERS[run.agent_name]
            result = handler(session, run, gateway, definition, settings)
            if result.input_tokens > definition.max_input_tokens or result.output_tokens > definition.max_output_tokens:
                raise RuntimeError("TOKEN_BUDGET_EXCEEDED")
            cost = _estimated_cost(settings, result.input_tokens, result.output_tokens)
            max_cost = effective_max_cost(session, definition)
            if cost > max_cost:
                raise RuntimeError("RUN_COST_BUDGET_EXCEEDED")
            transition(run, AgentRunStatus.VALIDATING)
            run.provider = result.provider
            run.model = result.model
            run.input_tokens += result.input_tokens
            run.output_tokens += result.output_tokens
            run.cost_usd += cost
            artifact = _write_artifact(session, run, result)
            step = session.scalar(
                select(AgentStep)
                .where(
                    AgentStep.run_id == run.id,
                    AgentStep.step_name == "execute_agent",
                    AgentStep.attempt == run.attempt_count,
                )
                .order_by(AgentStep.started_at.desc())
                .limit(1)
            )
            if step:
                step.status = "SUCCEEDED"
                step.output_ref = {
                    "artifact_id": str(artifact.id),
                    "artifact_type": artifact.artifact_type,
                }
                step.provider = result.provider
                step.model = result.model
                step.input_tokens = result.input_tokens
                step.output_tokens = result.output_tokens
                step.cost_usd = cost
                step.completed_at = utcnow()
            session.add(
                AgentCostEvent(
                    run_id=run.id,
                    candidate_id=run.candidate_id,
                    agent_name=run.agent_name,
                    agent_version=run.agent_version,
                    provider=result.provider,
                    model=result.model,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cost_usd=cost,
                )
            )
            _event(
                session,
                run=run,
                event_type=EVENT_TYPES[run.agent_name],
                payload={
                    "artifact_id": str(artifact.id),
                    "job_id": str(run.job_id) if run.job_id else None,
                },
            )
            child_ids = _orchestrate(session, run, artifact, settings=settings)
            transition(run, AgentRunStatus.SUCCEEDED)
            _event(
                session,
                run=run,
                event_type="AGENT_RUN_COMPLETED",
                payload={"artifact_id": str(artifact.id)},
            )
            session.commit()

        if settings.task_queue_provider == "memory":
            for child_id in child_ids:
                execute_agent_run(child_id, settings)
        return True
    except TransientAIProviderError as exc:
        return _fail_run(
            run_id,
            retryable=True,
            code="AI_PROVIDER_TRANSIENT",
            detail=str(exc),
        )
    except (AIProviderError, ToolPermissionError, PermissionError, ValueError) as exc:
        return _fail_run(
            run_id,
            retryable=False,
            code=type(exc).__name__,
            detail=str(exc),
        )
    except RuntimeError as exc:
        code = str(exc).split(":", 1)[0] or type(exc).__name__
        retryable = code not in {
            "CANDIDATE_DAILY_RUN_LIMIT_EXCEEDED",
            "CANDIDATE_DAILY_BUDGET_EXCEEDED",
            "RUNTIME_DAILY_BUDGET_EXCEEDED",
            "TOKEN_BUDGET_EXCEEDED",
            "RUN_COST_BUDGET_EXCEEDED",
        }
        return _fail_run(run_id, retryable=retryable, code=code, detail=str(exc))
    except Exception as exc:
        return _fail_run(
            run_id,
            retryable=True,
            code=type(exc).__name__,
            detail="Unexpected governed agent failure",
        )


def retry_agent_run(session: Session, run: AgentRun) -> AgentRun:
    if run.status not in {AgentRunStatus.FAILED_RETRYABLE, AgentRunStatus.FAILED_TERMINAL}:
        raise ValueError("Only failed agent runs can be retried")
    if run.status == AgentRunStatus.FAILED_TERMINAL:
        run.status = AgentRunStatus.FAILED_RETRYABLE
    transition(run, AgentRunStatus.QUEUED)
    run.error_code = None
    run.error_detail = None
    run.lease_owner = None
    run.lease_acquired_at = None
    run.lease_expires_at = None
    run.heartbeat_at = None
    add_task_outbox_event(
        session,
        task=Task(
            task_type="AGENT_RUN",
            payload={"run_id": str(run.id), "queue_class": run.queue_class},
            idempotency_key=f"agent-run:{run.id}:manual:{run.attempt_count + 1}",
        ),
        aggregate_type="AgentRun",
        aggregate_id=run.id,
    )
    _event(session, run=run, event_type="AGENT_RUN_RETRY_REQUESTED")
    return run
