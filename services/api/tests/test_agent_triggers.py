from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agent_models import AgentRun
from app.agents.triggers import queue_scouts_for_job, source_agent_trigger_config
from app.core.config import Settings
from app.models import CandidateTargetRole, User
from tests.helpers import create_job


def _settings(database_url: str) -> Settings:
    return Settings(database_url=database_url, ai_provider="deterministic", task_queue_provider="memory")


def test_source_agent_trigger_is_opt_in_and_bounded() -> None:
    assert source_agent_trigger_config({}) == (False, 25)
    assert source_agent_trigger_config({"agent_scout_on_new_jobs": True, "agent_scout_candidate_limit": 999}) == (True, 250)
    assert source_agent_trigger_config({"agent_scout_on_new_jobs": True, "agent_scout_candidate_limit": "bad"}) == (True, 25)


def test_job_created_targeting_uses_exact_target_role_and_limit(database_url: str) -> None:
    engine = create_engine(database_url)
    settings = _settings(database_url)
    try:
        with Session(engine) as session:
            job = create_job(session)
            exact_ids = []
            for index in range(4):
                user = User(
                    clerk_user_id=f"agent-target-exact-{index}",
                    email=f"agent-target-exact-{index}@example.com",
                    onboarding_completed=True,
                )
                session.add(user)
                session.flush()
                exact_ids.append(user.id)
                session.add(
                    CandidateTargetRole(
                        user_id=user.id,
                        title=job.title,
                        normalized_title=job.normalized_title,
                        priority=index + 1,
                    )
                )
            mismatch = User(
                clerk_user_id="agent-target-mismatch",
                email="agent-target-mismatch@example.com",
                onboarding_completed=True,
            )
            session.add(mismatch)
            session.flush()
            session.add(
                CandidateTargetRole(
                    user_id=mismatch.id,
                    title="Unrelated Role",
                    normalized_title="unrelated role",
                    priority=1,
                )
            )
            inactive = User(
                clerk_user_id="agent-target-inactive",
                email="agent-target-inactive@example.com",
                onboarding_completed=True,
                account_status="SUSPENDED",
            )
            session.add(inactive)
            session.flush()
            session.add(
                CandidateTargetRole(
                    user_id=inactive.id,
                    title=job.title,
                    normalized_title=job.normalized_title,
                    priority=1,
                )
            )
            session.commit()

            queued = queue_scouts_for_job(
                session,
                job_id=job.id,
                trigger_type="JOB_CREATED",
                settings=settings,
                max_candidates=2,
            )
            session.commit()

            assert len(queued) == 2
            runs = list(session.scalars(select(AgentRun).where(AgentRun.id.in_(queued)).order_by(AgentRun.created_at)))
            assert {row.candidate_id for row in runs}.issubset(set(exact_ids))
            assert mismatch.id not in {row.candidate_id for row in runs}
            assert inactive.id not in {row.candidate_id for row in runs}
            assert all(row.trigger_type == "JOB_CREATED" for row in runs)
            assert all(row.input_json["targeting"] == "EXACT_NORMALIZED_TARGET_ROLE" for row in runs)
    finally:
        engine.dispose()
