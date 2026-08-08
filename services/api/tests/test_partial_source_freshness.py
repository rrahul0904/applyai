from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.job_source_models import JobSourceRegistry
from app.jobs.connectors import ConnectorHealth, JobSourceConnector
from app.jobs.source_pipeline import RegisteredSourceIngestionPipeline
from app.models import Company, Job, JobLocation, JobSource, JobSourceLink


class EmptyPartialConnector(JobSourceConnector):
    key = "partial-test"
    authoritative_snapshot = False

    def fetch(self, checkpoint):
        del checkpoint
        return []

    def normalize(self, payload):
        raise AssertionError("no payloads expected")

    def checkpoint(self):
        return {}

    def health(self):
        return ConnectorHealth(True, datetime.now(timezone.utc), "test")


def test_partial_snapshot_does_not_increment_miss_count_or_close_job(database_url):
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            company = Company(canonical_name="Partial Source Co", normalized_name="partial source co")
            session.add(company)
            session.flush()
            job = Job(
                company_id=company.id,
                title="Data Engineer",
                normalized_title="data engineer",
                description="A valid data engineering role with enough description content for testing.",
                search_document="Data Engineer Partial Source Co",
                employment_type="FULL_TIME",
                seniority="MID",
                status="ACTIVE",
                data_origin="TEST",
            )
            session.add(job)
            session.flush()
            session.add(JobLocation(job_id=job.id, location_text="Boston, MA", work_mode="HYBRID"))
            registry = JobSourceRegistry(
                source_type="CAREER_SITE",
                source_name="Partial test",
                source_identity="partial.example",
                configuration={},
                trust_level="EMPLOYER_CAREER_SITE",
                priority=85,
                enabled=True,
                crawl_allowed=True,
                health_status="HEALTHY",
                crawl_interval_seconds=21_600,
                min_interval_seconds=900,
                max_interval_seconds=604_800,
            )
            session.add(registry)
            session.flush()
            posting_source = JobSource(
                connector_key="partial-test",
                external_job_id="partial:1",
                source_url="https://partial.example/jobs/1",
                checkpoint={"source_registry_id": str(registry.id), "miss_count": 0},
            )
            session.add(posting_source)
            session.flush()
            session.add(JobSourceLink(job_id=job.id, job_source_id=posting_source.id, is_primary=True))
            session.commit()

            counts = RegisteredSourceIngestionPipeline(session).run(
                registry,
                EmptyPartialConnector(),
            )
            assert counts["closed"] == 0
            assert counts["stale"] == 0
            session.refresh(posting_source)
            session.refresh(job)
            assert posting_source.checkpoint["miss_count"] == 0
            assert job.status == "ACTIVE"
    finally:
        engine.dispose()
