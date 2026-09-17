from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import CandidateExperience, CandidateProfile, CandidateSkill, JobSkill, User
from tests.helpers import create_job


def _seed_application_kit(database_url: str, client) -> str:
    assert client.get("/api/v1/me").status_code == 200
    engine = create_engine(database_url)
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.email == "a@example.com"))
        assert user is not None
        profile = CandidateProfile(
            user_id=user.id,
            headline="Senior operations leader",
            current_title="Product Operations Manager",
            summary="Led production operations systems and workflow improvements.",
            years_experience=9,
        )
        session.add(profile)
        session.flush()
        session.add_all(
            [
                CandidateSkill(
                    profile_id=profile.id,
                    name="Operations",
                    normalized_name="operations",
                    proficiency="STRONG",
                    provenance="USER_VERIFIED",
                ),
                CandidateExperience(
                    profile_id=profile.id,
                    company_name="Evidence Corp",
                    title="Product Operations Manager",
                    description="Led a verified workflow modernization program for production operations.",
                    provenance="USER_VERIFIED",
                ),
            ]
        )
        job = create_job(session)
        session.add(
            JobSkill(
                job_id=job.id,
                name="Kubernetes",
                normalized_name="kubernetes",
                required=True,
            )
        )
        session.commit()
        job_id = str(job.id)
    engine.dispose()
    return job_id


def test_application_kit_is_evidence_safe_and_exports_real_pdfs(client, database_url):
    job_id = _seed_application_kit(database_url, client)

    generated = client.post(f"/api/v1/career-v2/jobs/{job_id}/application-kit")
    assert generated.status_code == 200, generated.text
    kit = generated.json()
    assert kit["status"] == "REVIEWED"
    assert kit["content"]["kind"] == "JOB_APPLICATION_KIT"
    assert "Operations" in kit["content"]["ats"]["matched_skills"]
    assert "Kubernetes" in kit["content"]["ats"]["missing_required_skills"]
    assert "Evidence Corp" in kit["content"]["cover_letter"]
    assert "missing" not in kit["content"]["resume"]["summary"].lower()
    assert any(item["company"] == "Evidence Corp" for item in kit["content"]["resume"]["experience"])

    fetched = client.get(f"/api/v1/career-v2/jobs/{job_id}/application-kit")
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["id"] == kit["id"]

    resume_pdf = client.get(kit["downloads"]["resume_pdf"])
    assert resume_pdf.status_code == 200, resume_pdf.text
    assert resume_pdf.headers["content-type"].startswith("application/pdf")
    assert resume_pdf.content.startswith(b"%PDF-1.4")
    assert len(resume_pdf.content) > 500

    cover_pdf = client.get(kit["downloads"]["cover_letter_pdf"])
    assert cover_pdf.status_code == 200, cover_pdf.text
    assert cover_pdf.headers["content-type"].startswith("application/pdf")
    assert cover_pdf.content.startswith(b"%PDF-1.4")
    assert len(cover_pdf.content) > 500

    regenerated = client.post(f"/api/v1/career-v2/jobs/{job_id}/application-kit")
    assert regenerated.status_code == 200
    assert regenerated.json()["id"] == kit["id"]
    assert regenerated.json()["version"] == kit["version"] + 1
