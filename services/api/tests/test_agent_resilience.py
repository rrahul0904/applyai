from __future__ import annotations

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.agent_models import AgentArtifact, AgentRun
from app.agents.handlers import HANDLERS
from app.agents.runtime import execute_agent_run, queue_agent_run
from app.ai.provider import TransientAIProviderError
from app.core.config import Settings
from app.durability_models import TaskOutbox
from app.models import CandidateProfile, CandidateTargetRole, User
from tests.helpers import create_job


def _seed(session: Session, clerk_id: str) -> User:
    user = User(clerk_user_id=clerk_id, email=f"{clerk_id}@example.com", onboarding_completed=True)
    session.add(user)
    session.flush()
    profile = CandidateProfile(
        user_id=user.id,
        current_title="Product Operations Manager",
        summary="Verified profile",
        years_experience=6,
    )
    session.add(profile)
    session.flush()
    session.add(
        CandidateTargetRole(
            user_id=user.id,
            title="Product Operations Manager",
            normalized_title="product operations manager",
            priority=1,
        )
    )
    session.commit()
    return user


def test_transient_provider_failure_requeues_through_outbox_then_completes(database_url: str, monkeypatch) -> None:
    engine = create_engine(database_url)
    settings = Settings(database_url=database_url, ai_provider="deterministic", task_queue_provider="memory")
    original = HANDLERS["job_scout"]
    calls = {"count": 0}

    def flaky(session, run, gateway, definition, runtime_settings):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TransientAIProviderError("temporary provider outage")
        return original(session, run, gateway, definition, runtime_settings)

    monkeypatch.setitem(HANDLERS, "job_scout", flaky)
    try:
        with Session(engine) as session:
            user = _seed(session, "retry-agent")
            job = create_job(session)
            run = queue_agent_run(
                session,
                candidate_id=user.id,
                job_id=job.id,
                agent_name="job_scout",
                input_json={"retry": True},
                settings=settings,
            )
            run_id = run.id
            session.commit()

        assert execute_agent_run(run_id, settings, worker_id="retry-worker-1") is False
        with Session(engine) as session:
            row = session.get(AgentRun, run_id)
            assert row is not None
            assert row.status == "QUEUED"
            assert row.error_code == "AI_PROVIDER_TRANSIENT"
            outbox_count = session.scalar(
                select(func.count()).select_from(TaskOutbox).where(TaskOutbox.aggregate_id == run_id)
            )
            assert int(outbox_count or 0) == 2

        assert execute_agent_run(run_id, settings, worker_id="retry-worker-2") is True
        with Session(engine) as session:
            row = session.get(AgentRun, run_id)
            assert row is not None and row.status == "SUCCEEDED"
            artifacts = list(session.scalars(select(AgentArtifact).where(AgentArtifact.run_id == run_id)))
            assert len(artifacts) == 1
            assert row.attempt_count == 2
    finally:
        engine.dispose()


def test_candidate_daily_run_limit_fails_closed(database_url: str) -> None:
    engine = create_engine(database_url)
    settings = Settings(
        database_url=database_url,
        ai_provider="deterministic",
        task_queue_provider="memory",
        agent_candidate_daily_run_limit=1,
    )
    try:
        with Session(engine) as session:
            user = _seed(session, "budget-agent")
            job = create_job(session)
            queue_agent_run(
                session,
                candidate_id=user.id,
                job_id=job.id,
                agent_name="job_scout",
                input_json={"budget": 1},
                settings=settings,
            )
            session.commit()
            try:
                queue_agent_run(
                    session,
                    candidate_id=user.id,
                    job_id=job.id,
                    agent_name="job_research",
                    input_json={"budget": 2},
                    settings=settings,
                )
            except RuntimeError as exc:
                assert str(exc) == "CANDIDATE_DAILY_RUN_LIMIT_EXCEEDED"
            else:
                raise AssertionError("Expected candidate run budget to fail closed")
    finally:
        engine.dispose()
