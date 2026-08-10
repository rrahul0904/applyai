from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.agent_models import AgentApproval, AgentArtifact, AgentEvent, AgentRun
from app.agents.registry import AGENT_REGISTRY
from app.agents.tools.registry import TOOL_REGISTRY
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.queue import resolve_agent_queue_url
from app.models import JobSource, JobSourceLink


CORE_AGENTS = {"job_scout", "job_research", "resume_tailor", "resume_verifier"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _workflow_evidence(session, *, require_openai: bool) -> dict | None:
    workflows = session.execute(
        select(AgentRun.workflow_id)
        .where(AgentRun.workflow_id.is_not(None), AgentRun.created_at >= utcnow() - timedelta(days=7))
        .group_by(AgentRun.workflow_id)
        .having(func.count(func.distinct(AgentRun.agent_name)) >= 4)
        .order_by(func.max(AgentRun.created_at).desc())
        .limit(50)
    ).scalars()
    for workflow_id in workflows:
        rows = list(session.scalars(select(AgentRun).where(AgentRun.workflow_id == workflow_id)))
        by_agent = {row.agent_name: row for row in rows if row.agent_name in CORE_AGENTS}
        if set(by_agent) != CORE_AGENTS:
            continue
        if not all(row.status == "SUCCEEDED" for row in by_agent.values()):
            continue
        if require_openai and not all(row.provider == "openai" for row in by_agent.values()):
            continue
        candidate_id = next(iter(by_agent.values())).candidate_id
        job_id = next(iter(by_agent.values())).job_id
        ready = session.scalar(
            select(AgentEvent).where(
                AgentEvent.candidate_id == candidate_id,
                AgentEvent.event_type == "READY_FOR_CANDIDATE",
                AgentEvent.payload["workflow_id"].astext == str(workflow_id),
            )
        )
        if ready is None:
            continue
        source_keys: list[str] = []
        if job_id is not None:
            source_keys = list(
                session.scalars(
                    select(JobSource.connector_key)
                    .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
                    .where(JobSourceLink.job_id == job_id)
                )
            )
        return {
            "workflow_id": str(workflow_id),
            "candidate_id": str(candidate_id),
            "job_id": str(job_id) if job_id else None,
            "agents": {
                name: {
                    "run_id": str(row.id),
                    "provider": row.provider,
                    "model": row.model,
                    "input_tokens": row.input_tokens,
                    "output_tokens": row.output_tokens,
                    "cost_usd": float(row.cost_usd or 0),
                }
                for name, row in by_agent.items()
            },
            "source_keys": source_keys,
            "ready_for_candidate": True,
        }
    return None


def build_report() -> dict:
    settings = get_settings()
    with SessionLocal() as session:
        status_rows = session.execute(select(AgentRun.status, func.count()).group_by(AgentRun.status)).all()
        recent_failures = int(
            session.scalar(
                select(func.count()).select_from(AgentRun).where(
                    AgentRun.status.in_(["FAILED_RETRYABLE", "FAILED_TERMINAL"]),
                    AgentRun.created_at >= utcnow() - timedelta(hours=24),
                )
            )
            or 0
        )
        pending_approvals = int(
            session.scalar(select(func.count()).select_from(AgentApproval).where(AgentApproval.status == "PENDING")) or 0
        )
        artifact_count = int(session.scalar(select(func.count()).select_from(AgentArtifact)) or 0)
        local_workflow = _workflow_evidence(session, require_openai=False)
        live_workflow = _workflow_evidence(session, require_openai=True)

    definitions = sorted({name for name, _version in AGENT_REGISTRY})
    resolved_agent_queue = resolve_agent_queue_url(settings)
    queue_configured = bool(resolved_agent_queue)
    dedicated_agent_queue = bool(
        settings.agent_sqs_queue_url
        or (resolved_agent_queue and settings.app_env.lower() in {"staging", "production"})
    )
    environment = settings.app_env.lower()
    external_blockers: list[str] = []

    if environment in {"staging", "production"}:
        if settings.task_queue_provider != "sqs":
            external_blockers.append("TASK_QUEUE_PROVIDER_NOT_SQS")
        if not dedicated_agent_queue:
            external_blockers.append("DEDICATED_AGENT_SQS_QUEUE_NOT_CONFIGURED")
        if settings.ai_provider != "openai":
            external_blockers.append("LIVE_AI_PROVIDER_NOT_CONFIGURED")
        if live_workflow is None:
            external_blockers.append("NO_COMPLETE_LIVE_PROVIDER_WORKFLOW_EVIDENCE")

    local_verified = (
        settings.ai_provider == "deterministic"
        and settings.task_queue_provider == "memory"
        and local_workflow is not None
        and CORE_AGENTS.issubset(set(definitions))
    )

    status = "BLOCKED_EXTERNAL_CONFIGURATION"
    if environment not in {"staging", "production"} and local_verified:
        status = "LOCAL_RUNTIME_VERIFIED"
    elif environment in {"staging", "production"} and queue_configured and not external_blockers:
        source_keys = set((live_workflow or {}).get("source_keys") or [])
        real_source = any(key not in {"development-seed", "agent-demo"} for key in source_keys)
        status = "PASS" if live_workflow is not None and real_source else "STAGING_RUNTIME_AVAILABLE"
        if status != "PASS" and not real_source:
            external_blockers.append("NO_REAL_CANONICAL_JOB_SOURCE_EVIDENCE")

    return {
        "status": status,
        "environment": settings.app_env,
        "provider": settings.ai_provider,
        "queue_provider": settings.task_queue_provider,
        "dedicated_agent_queue_configured": dedicated_agent_queue,
        "registered_agents": definitions,
        "registered_tools": sorted(TOOL_REGISTRY),
        "runs_by_status": {str(key): int(value) for key, value in status_rows},
        "recent_failures_24h": recent_failures,
        "pending_approvals": pending_approvals,
        "artifacts": artifact_count,
        "local_workflow_evidence": local_workflow,
        "live_workflow_evidence": live_workflow,
        "external_blockers": external_blockers,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-blocked", action="store_true")
    args = parser.parse_args()
    report = build_report()
    print(json.dumps(report, indent=2, default=str))
    if report["status"] in {"LOCAL_RUNTIME_VERIFIED", "PASS"}:
        return
    if args.allow_blocked:
        return
    raise SystemExit(2)


if __name__ == "__main__":
    main()
