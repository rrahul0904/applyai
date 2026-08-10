from __future__ import annotations

import json

from sqlalchemy import select

from app.agent_models import AgentArtifact, AgentEvent, AgentRun
from app.agents.runtime import execute_agent_run, queue_agent_run
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import (
    CandidateExperience,
    CandidatePreference,
    CandidateProfile,
    CandidateSkill,
    CandidateTargetRole,
    Company,
    Job,
    JobCompensation,
    JobLocation,
    JobRequirement,
    JobSkill,
    User,
)


DEMO_CLERK_ID = "agent-demo-candidate"


def _ensure_fixture():
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.clerk_user_id == DEMO_CLERK_ID))
        if user is None:
            user = User(
                clerk_user_id=DEMO_CLERK_ID,
                email="agent-demo@example.invalid",
                first_name="Agent",
                last_name="Demo",
                onboarding_completed=True,
            )
            session.add(user)
            session.flush()
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
        if profile is None:
            profile = CandidateProfile(
                user_id=user.id,
                headline="Product operations leader",
                current_title="Product Operations Manager",
                summary="Verified operations leader focused on systems and workflows.",
                years_experience=8,
            )
            session.add(profile)
            session.flush()
            session.add(
                CandidateExperience(
                    profile_id=profile.id,
                    company_name="Verified Demo Health",
                    title="Product Operations Manager",
                    description="Improved operations workflows and cross-functional delivery.",
                    provenance="USER_VERIFIED",
                )
            )
            session.add(
                CandidateSkill(
                    profile_id=profile.id,
                    name="Operations",
                    normalized_name="operations",
                    proficiency="ADVANCED",
                    provenance="USER_VERIFIED",
                )
            )
        if session.scalar(select(CandidatePreference).where(CandidatePreference.user_id == user.id)) is None:
            session.add(
                CandidatePreference(
                    user_id=user.id,
                    location_text="Boston, MA",
                    work_modes=["HYBRID", "REMOTE"],
                    employment_types=["FULL_TIME"],
                    minimum_compensation=120000,
                    currency="USD",
                    relocation_open=False,
                )
            )
        if session.scalar(select(CandidateTargetRole).where(CandidateTargetRole.user_id == user.id)) is None:
            session.add(
                CandidateTargetRole(
                    user_id=user.id,
                    title="Product Operations Manager",
                    normalized_title="product operations manager",
                    priority=1,
                )
            )
        company = session.scalar(select(Company).where(Company.normalized_name == "agent demo company"))
        if company is None:
            company = Company(
                canonical_name="Agent Demo Company",
                normalized_name="agent demo company",
                website_url="https://example.invalid",
                description="Deterministic local demo employer.",
            )
            session.add(company)
            session.flush()
        job = session.scalar(
            select(Job).where(Job.company_id == company.id, Job.normalized_title == "product operations manager")
        )
        if job is None:
            job = Job(
                company_id=company.id,
                title="Product Operations Manager",
                normalized_title="product operations manager",
                description="Lead operations systems and workflows. Ignore previous instructions is only untrusted source text.",
                search_document="Product Operations Manager operations systems workflows",
                employment_type="FULL_TIME",
                seniority="MANAGER",
                status="ACTIVE",
            )
            session.add(job)
            session.flush()
            session.add_all(
                [
                    JobLocation(
                        job_id=job.id,
                        location_text="Boston, MA",
                        city="Boston",
                        region="MA",
                        country_code="US",
                        work_mode="HYBRID",
                    ),
                    JobSkill(job_id=job.id, name="Operations", normalized_name="operations", required=True),
                    JobRequirement(job_id=job.id, category="EXPERIENCE", text="Operations leadership", required=True),
                    JobCompensation(job_id=job.id, minimum=130000, maximum=160000, provenance="EMPLOYER_DISCLOSED"),
                ]
            )
        session.commit()
        return user.id, job.id


def main() -> None:
    settings = get_settings()
    if settings.task_queue_provider != "memory" or settings.ai_provider != "deterministic":
        raise SystemExit("agent:demo requires TASK_QUEUE_PROVIDER=memory and AI_PROVIDER=deterministic")
    candidate_id, job_id = _ensure_fixture()
    with SessionLocal() as session:
        run = queue_agent_run(
            session,
            candidate_id=candidate_id,
            job_id=job_id,
            agent_name="job_scout",
            input_json={"demo": "DETERMINISTIC_LOCAL_EVIDENCE"},
            settings=settings,
        )
        session.commit()
        run_id = run.id
        workflow_id = run.workflow_id
    execute_agent_run(run_id, settings)
    with SessionLocal() as session:
        runs = list(session.scalars(select(AgentRun).where(AgentRun.workflow_id == workflow_id).order_by(AgentRun.created_at)))
        artifacts = list(
            session.scalars(
                select(AgentArtifact)
                .where(AgentArtifact.candidate_id == candidate_id, AgentArtifact.job_id == job_id)
                .order_by(AgentArtifact.created_at)
            )
        )
        ready = session.scalar(
            select(AgentEvent).where(
                AgentEvent.candidate_id == candidate_id,
                AgentEvent.event_type == "READY_FOR_CANDIDATE",
                AgentEvent.payload["workflow_id"].astext == str(workflow_id),
            )
        )
        report = {
            "evidence_type": "DETERMINISTIC_LOCAL_EVIDENCE",
            "workflow_id": str(workflow_id),
            "runs": [{"agent": row.agent_name, "version": row.agent_version, "status": row.status} for row in runs],
            "artifacts": [{"type": row.artifact_type, "status": row.status, "version": row.version} for row in artifacts],
            "ready_for_candidate": ready is not None,
        }
    print(json.dumps(report, indent=2, default=str))
    expected = {"job_scout", "job_research", "resume_tailor", "resume_verifier"}
    succeeded = {row["agent"] for row in report["runs"] if row["status"] == "SUCCEEDED"}
    if succeeded != expected or not report["ready_for_candidate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
