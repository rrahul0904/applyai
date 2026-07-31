from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.job_source_models import JobSourceRegistry
from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob
from app.jobs.contracts import JobSourceType, RawJobPosting
from app.jobs.source_pipeline import RegisteredSourceIngestionPipeline
from app.models import Job, JobSource, JobSourceLink


class RegistryFixtureConnector(JobSourceConnector):
    def __init__(self, key: str, source_identity: str, records: list[dict]) -> None:
        self.key = key
        self.source_identity = source_identity
        self.records = records

    def source_company_identity(self) -> str:
        return self.source_identity

    def fetch(self, checkpoint):
        del checkpoint
        return [dict(record) for record in self.records]

    def to_raw(self, payload: dict) -> RawJobPosting:
        source_type = JobSourceType(self.key.upper())
        return RawJobPosting(
            source_type=source_type,
            source_name=self.key,
            source_company_identity=self.source_identity,
            source_job_identity=f"{self.source_identity}:{payload['id']}",
            external_job_id=f"{self.source_identity}:{payload['id']}",
            internal_job_id=payload.get("internal_job_id"),
            source_url=payload["source_url"],
            apply_url=payload["apply_url"],
            company_name=payload["company_name"],
            title=payload["title"],
            description=payload["description"],
            location_text=payload["location"],
            locations=(payload["location"],),
            employment_type="FULL_TIME",
            workplace_type="REMOTE",
            raw_payload=payload,
        )

    def normalize(self, payload: dict) -> NormalizedJob:
        raw = self.to_raw(payload)
        return NormalizedJob(
            external_job_id=raw.external_job_id,
            company_name=raw.company_name,
            title=raw.title,
            description=raw.description,
            application_url=raw.apply_url,
            locations=list(raw.locations),
            work_mode=raw.workplace_type,
            employment_type=raw.employment_type,
            seniority="UNKNOWN",
            salary_min=None,
            salary_max=None,
            salary_provenance=None,
            skills=[],
            requirements=[],
            posted_at=None,
            raw_payload=payload,
        )

    def checkpoint(self):
        return {"count": len(self.records)}

    def health(self):
        return ConnectorHealth(True, datetime.now(timezone.utc), "fixture")


def source(source_type: str, identity: str) -> JobSourceRegistry:
    return JobSourceRegistry(
        source_type=source_type,
        source_name=f"{source_type}: {identity}",
        source_identity=identity,
        configuration={},
        trust_level="OFFICIAL_ATS",
        enabled=True,
        crawl_allowed=True,
        health_status="HEALTHY",
        crawl_interval_seconds=3600,
        next_run_at=datetime.now(timezone.utc),
    )


def posting(source_identity: str, posting_id: str, source_url: str) -> dict:
    return {
        "id": posting_id,
        "internal_job_id": "req-42",
        "company_name": "Example Labs",
        "title": "Senior Data Engineer",
        "description": (
            "Build reliable production data platforms, streaming systems, and "
            "analytics services used by customer-facing applications."
        ),
        "location": "Remote - United States",
        "source_url": source_url,
        "apply_url": f"{source_url}/apply",
        "data_origin": f"{source_identity.upper()}_PUBLIC_API",
    }


def test_one_missing_source_does_not_retire_job_while_other_source_is_fresh(database_url):
    engine = create_engine(database_url)
    with Session(engine, expire_on_commit=False) as session:
        lever_source = source("LEVER", "lever-example")
        ashby_source = source("ASHBY", "ashby-example")
        session.add_all([lever_source, ashby_source])
        session.commit()

        lever_post = posting(
            "lever",
            "lever-job-1",
            "https://jobs.lever.co/example/lever-job-1",
        )
        ashby_post = posting(
            "ashby",
            "ashby-job-1",
            "https://jobs.ashbyhq.com/example/ashby-job-1",
        )
        pipeline = RegisteredSourceIngestionPipeline(session)
        pipeline.run(
            lever_source,
            RegistryFixtureConnector("lever", "lever-example", [lever_post]),
        )
        pipeline.run(
            ashby_source,
            RegistryFixtureConnector("ashby", "ashby-example", [ashby_post]),
        )

        assert session.scalar(select(func.count(Job.id))) == 1
        assert session.scalar(select(func.count(JobSource.id))) == 2
        assert session.scalar(select(func.count(JobSourceLink.id))) == 2

        pipeline.run(
            lever_source,
            RegistryFixtureConnector("lever", "lever-example", []),
        )
        pipeline.run(
            ashby_source,
            RegistryFixtureConnector("ashby", "ashby-example", [ashby_post]),
        )
        job = session.scalar(select(Job))
        assert job is not None and job.status == "ACTIVE"


def test_registry_source_moves_unknown_stale_and_reactivates(database_url):
    engine = create_engine(database_url)
    settings = Settings(job_unknown_after_misses=1, job_stale_after_misses=2)
    with Session(engine, expire_on_commit=False) as session:
        registry = source("LEVER", "example")
        session.add(registry)
        session.commit()
        record = posting(
            "lever",
            "job-1",
            "https://jobs.lever.co/example/job-1",
        )
        pipeline = RegisteredSourceIngestionPipeline(session)
        pipeline.canonical.settings = settings

        pipeline.run(registry, RegistryFixtureConnector("lever", "example", [record]))
        pipeline.run(registry, RegistryFixtureConnector("lever", "example", []))
        job = session.scalar(select(Job))
        assert job is not None and job.status == "UNKNOWN"

        pipeline.run(registry, RegistryFixtureConnector("lever", "example", []))
        session.refresh(job)
        assert job.status == "STALE"

        pipeline.run(registry, RegistryFixtureConnector("lever", "example", [record]))
        session.refresh(job)
        assert job.status == "ACTIVE"
