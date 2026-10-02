from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.durability_models import JobIngestionRun
from app.job_source_models import JobSourceRegistry
from app.jobs.connectors import ConnectorHealth, JobSourceConnector
from app.jobs.source_completeness import CoverageStatus, observed_coverage
from app.jobs.source_pipeline import RegisteredSourceIngestionPipeline
from app.models import Company, Job, JobLocation, JobSource, JobSourceLink


class IncompletePaginationConnector(JobSourceConnector):
    key = "synthetic-ats-incomplete"
    source_completeness = "PAGINATED_FULL_SNAPSHOT"
    pagination_complete = False
    coverage_partitions_expected = 2
    coverage_partitions_observed = 1
    completeness_checks = {"last_page_reached": False}

    def fetch(self, checkpoint):
        del checkpoint
        return []

    def normalize(self, payload):
        raise AssertionError("no payloads expected")

    def checkpoint(self):
        return {}

    def health(self):
        return ConnectorHealth(True, datetime.now(timezone.utc), "synthetic")


class InconclusiveConnector(JobSourceConnector):
    key = "synthetic-ats-inconclusive"

    def fetch(self, checkpoint):
        del checkpoint
        return []

    def normalize(self, payload):
        raise AssertionError("no payloads expected")

    def checkpoint(self):
        return {}

    def health(self):
        return ConnectorHealth(True, datetime.now(timezone.utc), "synthetic")


class FailedConnector(InconclusiveConnector):
    key = "synthetic-ats-failed"

    def fetch(self, checkpoint):
        del checkpoint
        raise RuntimeError("429 rate limited")


def _seed_existing_job(session: Session, *, source_key: str) -> tuple[JobSourceRegistry, JobSource, Job]:
    company = Company(canonical_name="Coverage Co", normalized_name="coverage co")
    session.add(company)
    session.flush()
    job = Job(
        company_id=company.id,
        title="Data Engineer",
        normalized_title="data engineer",
        description="A valid data engineering role with enough description content for testing.",
        search_document="Data Engineer Coverage Co",
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
        source_name="Coverage test",
        source_identity=f"{source_key}.example",
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
        connector_key=source_key,
        external_job_id=f"{source_key}:1",
        source_url=f"https://{source_key}.example/jobs/1",
        checkpoint={"source_registry_id": str(registry.id), "miss_count": 0},
    )
    session.add(posting_source)
    session.flush()
    session.add(JobSourceLink(job_id=job.id, job_source_id=posting_source.id, is_primary=True))
    session.commit()
    return registry, posting_source, job


def test_incomplete_pagination_is_partial_even_when_fetch_returns_normally():
    receipt = observed_coverage(
        IncompletePaginationConnector(),
        {"fetched": 0, "failed": 0},
    )

    assert receipt.status is CoverageStatus.PARTIAL
    assert "PAGINATION_INCOMPLETE" in receipt.reason_codes
    assert "PARTITIONS_MISSING" in receipt.reason_codes


@pytest.mark.parametrize(
    ("connector", "expected"),
    [
        (IncompletePaginationConnector(), CoverageStatus.PARTIAL),
        (InconclusiveConnector(), CoverageStatus.INCONCLUSIVE),
    ],
)
def test_partial_or_inconclusive_fetch_cannot_expire_unseen_jobs(database_url, connector, expected):
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            registry, posting_source, job = _seed_existing_job(
                session,
                source_key=connector.key,
            )
            counts = RegisteredSourceIngestionPipeline(session).run(registry, connector)

            assert counts["closed"] == 0
            assert counts["stale"] == 0
            session.refresh(posting_source)
            session.refresh(job)
            assert posting_source.checkpoint["miss_count"] == 0
            assert job.status == "ACTIVE"

            run = session.scalar(
                select(JobIngestionRun).where(JobIngestionRun.source_id == registry.id)
            )
            assert run is not None
            assert run.coverage_status == expected.value
            assert run.coverage_details["status"] == expected.value
            assert registry.configuration["last_source_coverage"]["status"] == expected.value
    finally:
        engine.dispose()


def test_failed_fetch_records_failed_coverage_and_preserves_open_state(database_url):
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            connector = FailedConnector()
            registry, posting_source, job = _seed_existing_job(
                session,
                source_key=connector.key,
            )
            with pytest.raises(RuntimeError, match="429"):
                RegisteredSourceIngestionPipeline(session).run(registry, connector)

            session.refresh(posting_source)
            session.refresh(job)
            assert posting_source.checkpoint["miss_count"] == 0
            assert job.status == "ACTIVE"
            run = session.scalar(
                select(JobIngestionRun).where(JobIngestionRun.source_id == registry.id)
            )
            assert run is not None
            assert run.coverage_status == CoverageStatus.FAILED.value
            assert run.coverage_details["status"] == CoverageStatus.FAILED.value
            assert registry.configuration["last_source_coverage"]["status"] == (
                CoverageStatus.FAILED.value
            )
    finally:
        engine.dispose()
