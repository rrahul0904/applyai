from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agent_models import AgentArtifact, AgentCostEvent, AgentEvent, AgentRun, AgentToolCall
from app.agents.runtime import claim_agent_run, execute_agent_run, queue_agent_run
from app.core.config import Settings
from app.models import (
    CandidateExperience,
    CandidatePreference,
    CandidateProfile,
    CandidateSkill,
    CandidateTargetRole,
    User,
)
from tests.helpers import create_job


def _seed_candidate(session: Session, *, clerk_id: str = "agent_candidate") -> User:
    user = User(clerk_user_id=clerk_id, email=f"{clerk_id}@example.com", onboarding_completed=True)
    session.add(user)
    session.flush()
    profile = CandidateProfile(
        user_id=user.id,
        headline="Product operations leader",
        current_title="Product Operations Manager",
        summary="Operations leader focused on systems and workflows.",
        years_experience=8,
    )
    session.add(profile)
    session.flush()
    session.add_all(
        [
            CandidateExperience(
                profile_id=profile.id,
                company_name="Verified Health",
                title="Product Operations Manager",
                description="Improved operations workflows and cross-functional delivery.",
                provenance="USER_VERIFIED",
            ),
            CandidateSkill(
                profile_id=profile.id,
                name="Operations",
                normalized_name="operations",
                proficiency="ADVANCED",
                provenance="USER_VERIFIED",
            ),
            CandidatePreference(
                user_id=user.id,
                location_text="Boston, MA",
                work_modes=["HYBRID", "REMOTE"],
                employment_types=["FULL_TIME"],
                minimum_compensation=120000,
                currency="USD",
                relocation_open=False,
            ),
            CandidateTargetRole(
                user_id=user.id,
                title="Product Operations Manager",
                normalized_title="product operations manager",
                priority=1,
            ),
        ]
    )
    session.commit()
    session.refresh(user)
    return user


def _settings(database_url: str) -> Settings:
    return Settings(
        database_url=database_url,
        ai_provider="deterministic",
        task_queue_provider="memory",
        agent_candidate_daily_run_limit=200,
        agent_candidate_daily_cost_limit_usd=5,
        agent_runtime_daily_cost_limit_usd=500,
    )


def test_full_agent_workflow_is_durable_and_idempotent(database_url: str) -> None:
    engine = create_engine(database_url)
    settings = _settings(database_url)
    try:
        with Session(engine) as session:
            user = _seed_candidate(session)
            job = create_job(session)
            user_id = user.id
            job_id = job.id
            run = queue_agent_run(
                session,
                candidate_id=user_id,
                job_id=job_id,
                agent_name="job_scout",
                input_json={"source": "test"},
                settings=settings,
            )
            duplicate = queue_agent_run(
                session,
                candidate_id=user_id,
                job_id=job_id,
                agent_name="job_scout",
                input_json={"source": "test"},
                settings=settings,
            )
            assert duplicate.id == run.id
            workflow_id = run.workflow_id
            run_id = run.id
            session.commit()

        assert execute_agent_run(run_id, settings, worker_id="worker-a") is True
        assert execute_agent_run(run_id, settings, worker_id="worker-duplicate") is True

        with Session(engine) as session:
            runs = list(
                session.scalars(
                    select(AgentRun)
                    .where(AgentRun.workflow_id == workflow_id)
                    .order_by(AgentRun.created_at)
                )
            )
            assert [row.agent_name for row in runs] == [
                "job_scout",
                "job_research",
                "resume_tailor",
                "resume_verifier",
            ]
            assert all(row.status == "SUCCEEDED" for row in runs)

            artifacts = list(
                session.scalars(
                    select(AgentArtifact)
                    .where(AgentArtifact.candidate_id == user_id, AgentArtifact.job_id == job_id)
                    .order_by(AgentArtifact.created_at)
                )
            )
            assert [row.artifact_type for row in artifacts] == [
                "JOB_SCOUT_DECISION",
                "JOB_RESEARCH",
                "TAILORED_RESUME",
                "RESUME_VERIFICATION",
            ]
            assert len({row.id for row in artifacts}) == 4
            assert artifacts[-1].parent_artifact_id == artifacts[-2].id
            assert artifacts[-1].content_json["decision"] == "PASS"

            ready = session.scalar(
                select(AgentEvent).where(
                    AgentEvent.candidate_id == user_id,
                    AgentEvent.event_type == "READY_FOR_CANDIDATE",
                )
            )
            assert ready is not None
            assert len(list(session.scalars(select(AgentCostEvent).where(AgentCostEvent.candidate_id == user_id)))) == 4
            assert len(list(session.scalars(select(AgentToolCall).where(AgentToolCall.candidate_id == user_id)))) >= 8
    finally:
        engine.dispose()


def test_agent_lease_blocks_second_worker_and_recovers_after_expiry(database_url: str) -> None:
    engine = create_engine(database_url)
    settings = _settings(database_url)
    try:
        with Session(engine) as session:
            user = _seed_candidate(session, clerk_id="lease_candidate")
            job = create_job(session)
            run = queue_agent_run(
                session,
                candidate_id=user.id,
                job_id=job.id,
                agent_name="job_scout",
                input_json={"lease": True},
                settings=settings,
            )
            run_id = run.id
            session.commit()

        with Session(engine) as session:
            claimed = claim_agent_run(session, run_id, worker_id="worker-a", settings=settings)
            assert claimed is not None
            assert claimed.lease_owner == "worker-a"
        with Session(engine) as session:
            assert claim_agent_run(session, run_id, worker_id="worker-b", settings=settings) is None
            row = session.get(AgentRun, run_id)
            assert row is not None
            row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            session.commit()
        with Session(engine) as session:
            recovered = claim_agent_run(session, run_id, worker_id="worker-b", settings=settings)
            assert recovered is not None
            assert recovered.lease_owner == "worker-b"
            assert recovered.attempt_count == 2
    finally:
        engine.dispose()


def test_resume_verifier_rejects_invented_metric_skill_and_credential(database_url: str) -> None:
    engine = create_engine(database_url)
    settings = _settings(database_url)
    try:
        with Session(engine) as session:
            user = _seed_candidate(session, clerk_id="verifier_candidate")
            job = create_job(session)
            user_id = user.id
            job_id = job.id
            scout = queue_agent_run(
                session,
                candidate_id=user_id,
                job_id=job_id,
                agent_name="job_scout",
                input_json={"initial": True},
                settings=settings,
            )
            scout_id = scout.id
            session.commit()
        assert execute_agent_run(scout_id, settings)

        with Session(engine) as session:
            tailor = session.scalar(
                select(AgentRun).where(
                    AgentRun.candidate_id == user_id,
                    AgentRun.job_id == job_id,
                    AgentRun.agent_name == "resume_tailor",
                )
            )
            assert tailor is not None
            experience = session.scalar(
                select(CandidateExperience).join(CandidateProfile).where(CandidateProfile.user_id == user_id)
            )
            assert experience is not None
            session.add(
                AgentArtifact(
                    run_id=tailor.id,
                    candidate_id=user_id,
                    job_id=job_id,
                    artifact_type="TAILORED_RESUME",
                    status="NEEDS_VERIFICATION",
                    version=2,
                    content_json={
                        "strategy_summary": "malicious fixture",
                        "edits": [
                            {
                                "source_text": experience.description,
                                "suggested_text": "Delivered $10M impact, Kubernetes modernization, and AWS certification.",
                                "reason": "fixture",
                                "evidence_refs": [f"experience:{experience.id}"],
                                "risk_flags": [],
                                "confidence": 1.0,
                            }
                        ],
                        "evidence_refs": [f"experience:{experience.id}"],
                    },
                    evidence_json={"refs": [f"experience:{experience.id}"]},
                    prompt_version="fixture",
                    schema_version="fixture",
                )
            )
            verifier = queue_agent_run(
                session,
                candidate_id=user_id,
                job_id=job_id,
                agent_name="resume_verifier",
                input_json={"adversarial": True},
                settings=settings,
            )
            verifier_id = verifier.id
            session.commit()
        assert execute_agent_run(verifier_id, settings)

        with Session(engine) as session:
            artifact = session.scalar(
                select(AgentArtifact).where(
                    AgentArtifact.run_id == verifier_id,
                    AgentArtifact.artifact_type == "RESUME_VERIFICATION",
                )
            )
            assert artifact is not None
            assert artifact.content_json["decision"] == "REJECT"
            issue_types = {item["issue_type"] for item in artifact.content_json["issues"]}
            assert "UNSUPPORTED_METRIC_OR_NUMBER" in issue_types
            assert "UNSUPPORTED_SCOPE_OR_CREDENTIAL" in issue_types
    finally:
        engine.dispose()
