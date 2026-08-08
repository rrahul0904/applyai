from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.global_job_supply_models import JobDedupCandidate
from app.jobs.dedup_review import build_dedup_candidates
from app.models import Company, Job, JobLocation


def test_borderline_cross_source_jobs_are_queued_for_review(database_url):
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            company = Company(canonical_name="Dedup Example", normalized_name="dedup example")
            session.add(company)
            session.flush()
            jobs = []
            descriptions = [
                "Build reliable Python and SQL data platforms for analytics teams, improve pipelines, and operate cloud infrastructure with strong engineering practices.",
                "Build reliable Python and SQL data platforms for analytics teams, improve pipelines, and operate cloud infrastructure using strong production engineering practices.",
            ]
            for index, description in enumerate(descriptions):
                job = Job(
                    company_id=company.id,
                    title="Senior Data Engineer",
                    normalized_title="senior data engineer",
                    description=description,
                    search_document=description,
                    employment_type="FULL_TIME",
                    seniority="SENIOR",
                    status="ACTIVE",
                    data_origin=f"TEST_{index}",
                )
                session.add(job)
                session.flush()
                session.add(JobLocation(job_id=job.id, location_text="Boston, MA", work_mode="HYBRID"))
                jobs.append(job)
            session.commit()

            counts = build_dedup_candidates(
                session,
                minimum_similarity=0.80,
                automatic_merge_threshold=0.999,
            )
            assert counts["created"] == 1
            candidate = session.scalar(select(JobDedupCandidate))
            assert candidate is not None
            assert candidate.status == "PENDING"
            assert candidate.confidence_bps >= 8000
            assert candidate.evidence["description_similarity"] >= 0.80
    finally:
        engine.dispose()
