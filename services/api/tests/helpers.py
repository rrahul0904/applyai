from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import (
    Company,
    Job,
    JobCompensation,
    JobLocation,
    JobRequirement,
    JobSkill,
    JobSource,
    JobSourceLink,
)


def create_job(session: Session) -> Job:
    company = Company(
        canonical_name="Northstar Health",
        normalized_name="northstar health",
        website_url="https://example.test",
    )
    session.add(company)
    session.flush()
    job = Job(
        company_id=company.id,
        title="Product Operations Manager",
        normalized_title="product operations manager",
        description="Lead systems and workflows for a growing care delivery organization.",
        search_document=(
            "Product Operations Manager Northstar Health Operations systems workflows"
        ),
        employment_type="FULL_TIME",
        seniority="MANAGER",
        status="ACTIVE",
        posted_at=datetime.now(timezone.utc),
    )
    session.add(job)
    session.flush()
    source = JobSource(
        connector_key="development-seed",
        external_job_id="northstar-001",
        source_url="https://example.test/jobs/001",
    )
    session.add_all(
        [
            source,
            JobLocation(
                job_id=job.id,
                location_text="Boston, MA",
                city="Boston",
                region="MA",
                country_code="US",
                work_mode="HYBRID",
            ),
            JobCompensation(
                job_id=job.id,
                minimum=130000,
                maximum=160000,
                provenance="EMPLOYER_DISCLOSED",
            ),
            JobRequirement(
                job_id=job.id,
                category="EXPERIENCE",
                text="5+ years in product or operations",
                required=True,
            ),
            JobSkill(
                job_id=job.id,
                name="Operations",
                normalized_name="operations",
                required=True,
            ),
        ]
    )
    session.flush()
    session.add(JobSourceLink(job_id=job.id, job_source_id=source.id, is_primary=True))
    session.execute(
        text(
            "UPDATE jobs SET search_vector = "
            "to_tsvector('english', search_document) WHERE id = :job_id"
        ),
        {"job_id": job.id},
    )
    session.commit()
    session.refresh(job)
    return job
