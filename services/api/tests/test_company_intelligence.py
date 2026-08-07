from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Company, Job, JobLocation, JobRequirement, JobSkill


def test_company_intelligence_is_evidence_backed(client, database_url):
    engine = create_engine(database_url)
    with Session(engine) as session:
        company = Company(canonical_name="Evidence Corp", normalized_name="evidence corp")
        session.add(company)
        session.flush()
        job = Job(
            company_id=company.id,
            title="AI Platform Director",
            normalized_title="ai platform director",
            description="Lead our generative AI platform and distributed team.",
            search_document="ai platform director",
            status="ACTIVE",
            data_origin="DEVELOPMENT_SEED",
        )
        session.add(job)
        session.flush()
        session.add(JobLocation(job_id=job.id, location_text="Boston, MA", work_mode="HYBRID"))
        session.add(JobSkill(job_id=job.id, name="Python", normalized_name="python", required=True))
        session.add(
            JobRequirement(
                job_id=job.id,
                category="OTHER",
                text="Visa sponsorship available for qualified candidates",
                required=False,
            )
        )
        session.commit()
        job_id = str(job.id)
    engine.dispose()

    response = client.get(f"/api/v1/company-intelligence/jobs/{job_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["company_name"] == "Evidence Corp"
    assert body["active_job_count"] == 1
    assert body["top_skills"][0]["name"] == "Python"
    assert body["signals"]["visa_sponsorship"] == "MENTIONED_AVAILABLE"
    assert body["signals"]["ai_language_present"] is True
