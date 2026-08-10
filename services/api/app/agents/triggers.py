from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.runtime import queue_agent_run
from app.core.config import Settings
from app.models import CandidateTargetRole, Job, User


def queue_scouts_for_job(
    session: Session,
    *,
    job_id: uuid.UUID,
    trigger_type: str,
    settings: Settings,
    max_candidates: int = 25,
) -> list[uuid.UUID]:
    """Bounded deterministic candidate targeting for a canonical job event.

    Release 1 intentionally uses exact normalized target-role matching. It does not
    call an LLM to decide which candidates should receive LLM work, and it never
    scans the full candidate x job matrix.
    """
    max_candidates = max(1, min(int(max_candidates), 250))
    job = session.get(Job, job_id)
    if job is None or job.status != "ACTIVE" or not job.normalized_title:
        return []

    candidate_ids = list(
        session.scalars(
            select(User.id)
            .join(CandidateTargetRole, CandidateTargetRole.user_id == User.id)
            .where(
                User.account_status == "ACTIVE",
                User.onboarding_completed.is_(True),
                CandidateTargetRole.normalized_title == job.normalized_title,
            )
            .order_by(CandidateTargetRole.priority.asc(), User.created_at.asc())
            .limit(max_candidates)
        )
    )
    revision = job.updated_at.isoformat() if job.updated_at else str(job.id)
    queued: list[uuid.UUID] = []
    for candidate_id in candidate_ids:
        run = queue_agent_run(
            session,
            candidate_id=candidate_id,
            job_id=job.id,
            agent_name="job_scout",
            trigger_type=trigger_type,
            trigger_id=f"job:{job.id}:{revision}",
            workflow_type="OPPORTUNITY_PREPARATION",
            input_json={
                "job_revision": revision,
                "targeting": "EXACT_NORMALIZED_TARGET_ROLE",
                "trigger_type": trigger_type,
            },
            settings=settings,
        )
        queued.append(run.id)
    return queued


def source_agent_trigger_config(configuration: dict[str, Any] | None) -> tuple[bool, int]:
    values = configuration or {}
    enabled = bool(values.get("agent_scout_on_new_jobs", False))
    try:
        limit = int(values.get("agent_scout_candidate_limit", 25))
    except (TypeError, ValueError):
        limit = 25
    return enabled, max(1, min(limit, 250))
