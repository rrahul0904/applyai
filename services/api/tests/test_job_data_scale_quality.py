from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.durability_models import TaskOutbox
from app.job_quality_models import JobApplyUrlCheck, JobClosureEvidence, JobFieldProvenance
from app.job_source_models import JobSourceRegistry
from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob
from app.jobs.contracts import JobSourceType, RawJobPosting
from app.jobs.dispatcher import dispatch_due_sources
from app.jobs.quality import quality_metrics, source_coverage_metrics
from app.jobs.registry import adaptive_interval_seconds
from app.jobs.source_authority import choose_primary_source_link, record_field_provenance
from app.jobs.source_pipeline import RegisteredSourceIngestionPipeline
from app.jobs.verifier import verify_job_source_url
from app.jobs.web_security import CrawlBudget, SafeHttpFetcher
from app.models import Job, JobSource, JobSourceLink, RawJobPosting as RawJobPostingModel


class FixtureConnector(JobSourceConnector):
    def __init__(self, key: str, identity: str, records: list[dict]) -> None:
        self.key = key
        self.identity = identity
        self.records = records

    def source_company_identity(self) -> str:
        return self.identity

    def fetch(self, checkpoint):
        del checkpoint
        return [dict(value) for value in self.records]

    def to_raw(self, payload: dict) -> RawJobPosting:
        return RawJobPosting(
            source_type=JobSourceType(self.key.upper()),
            source_name=self.key,
            source_company_identity=self.identity,
            source_job_identity=f"{self.identity}:{payload['id']}",
            external_job_id=f"{self.identity}:{payload['id']}",
            internal_job_id="REQ-42",
            source_url=payload["url"],
            apply_url=payload["url"],
            company_name="Example Labs",
            title="Senior Data Engineer",
            description=payload["description"],
            location_text="Remote - United States",
            locations=("Remote - United States",),
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
            seniority="SENIOR",
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


def registry(source_type: str, identity: str, trust: str, priority: int) -> JobSourceRegistry:
    return JobSourceRegistry(
        source_type=source_type,
        source_name=f"{source_type}: {identity}",
        source_identity=identity,
        configuration={},
        trust_level=trust,
        priority=priority,
        enabled=True,
        crawl_allowed=True,
        health_status="HEALTHY",
        crawl_interval_seconds=21_600,
        min_interval_seconds=900,
        max_interval_seconds=604_800,
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )


def posting(posting_id: str, url: str, description: str) -> dict:
    return {
        "id": posting_id,
        "url": url,
        "description": description,
        "data_origin": "PUBLIC_API",
    }


def public_resolver(host: str, port: int):
    del host, port
    return [(2, 1, 6, "", ("93.184.216.34", 443))]


def test_dispatcher_atomically_leases_and_creates_outbox(database_url, monkeypatch):
    engine = create_engine(database_url)
    source = registry("LEVER", "example", "OFFICIAL_ATS", 90)
    with Session(engine, expire_on_commit=False) as session:
        session.add(source)
        session.commit()

    monkeypatch.setattr("app.jobs.dispatcher.SessionLocal", lambda: Session(engine))
    monkeypatch.setattr("app.jobs.dispatcher.sync_configured_sources", lambda session, settings: [])
    dispatched = dispatch_due_sources(
        Settings(job_source_dispatch_batch_size=5, job_source_max_inflight=5),
        dispatcher_id="test-dispatcher",
    )
    assert dispatched == [source.id]

    with Session(engine) as session:
        persisted = session.get(JobSourceRegistry, source.id)
        event = session.scalar(
            select(TaskOutbox).where(TaskOutbox.aggregate_id == source.id)
        )
        assert persisted is not None and persisted.locked_by
        assert persisted.lease_expires_at is not None
        assert event is not None and event.event_type == "SOURCE_INGEST"
        assert event.payload["lease_token"] == persisted.locked_by
    engine.dispose()


def test_adaptive_interval_is_bounded_by_change_volume_and_failures():
    settings = Settings(
        job_source_min_interval_seconds=900,
        job_source_default_interval_seconds=21_600,
        job_source_max_interval_seconds=604_800,
    )
    source = registry("LEVER", "example", "OFFICIAL_ATS", 90)
    source.last_job_count = 1_000
    source.last_change_count = 200
    assert adaptive_interval_seconds(source, settings) == 10_800

    source.last_change_count = 0
    source.last_job_count = 10
    assert adaptive_interval_seconds(source, settings) == 27_000

    source.consecutive_failures = 3
    assert adaptive_interval_seconds(source, settings) == 172_800


def test_official_ats_remains_primary_over_lower_authority_copy(database_url):
    engine = create_engine(database_url)
    official_description = (
        "Official employer description for building reliable production data platforms "
        "and customer-facing analytics services."
    )
    copy_description = (
        "Lower authority feed description that must remain provenance without replacing "
        "the official employer content."
    )
    with Session(engine, expire_on_commit=False) as session:
        official = registry("LEVER", "official", "OFFICIAL_ATS", 90)
        copy = registry("ASHBY", "copy", "THIRD_PARTY_SOURCE", 40)
        session.add_all([official, copy])
        session.commit()
        pipeline = RegisteredSourceIngestionPipeline(session)
        pipeline.run(
            official,
            FixtureConnector(
                "lever",
                "official",
                [posting("official-1", "https://8.8.8.8/jobs/req-42", official_description)],
            ),
        )
        pipeline.run(
            copy,
            FixtureConnector(
                "ashby",
                "copy",
                [posting("copy-1", "https://8.8.8.8/jobs/req-42", copy_description)],
            ),
        )
        job = session.scalar(select(Job))
        assert job is not None
        assert job.description == official_description
        assert session.scalar(select(func.count(JobSourceLink.id))) == 2
        selected = choose_primary_source_link(session, job.id)
        assert selected is not None
        selected_source = session.get(JobSource, selected.job_source_id)
        assert selected_source is not None and selected_source.connector_key == "lever"
        record_field_provenance(session, job.id)
        session.commit()
        assert session.scalar(select(func.count(JobFieldProvenance.id))) == 7
    engine.dispose()


def test_repeated_not_found_evidence_closes_only_after_confirmation(database_url, monkeypatch):
    engine = create_engine(database_url)
    description = (
        "Build reliable production data platforms and analytics services used by "
        "customer-facing applications."
    )
    with Session(engine, expire_on_commit=False) as session:
        source_registry = registry("LEVER", "example", "OFFICIAL_ATS", 90)
        session.add(source_registry)
        session.commit()
        RegisteredSourceIngestionPipeline(session).run(
            source_registry,
            FixtureConnector(
                "lever",
                "example",
                [posting("job-1", "https://8.8.8.8/jobs/job-1", description)],
            ),
        )
        source = session.scalar(select(JobSource))
        job = session.scalar(select(Job))
        assert source is not None and job is not None
        source_id = source.id
        job_id = job.id

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(404, text="Not found")

    fetcher = SafeHttpFetcher(
        budget=CrawlBudget(max_pages=5),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        resolver=public_resolver,
    )
    monkeypatch.setattr("app.jobs.verifier.SessionLocal", lambda: Session(engine))
    settings = Settings(apply_url_not_found_confirmations=2)
    first = verify_job_source_url(source_id, settings=settings, fetcher=fetcher)
    assert first.status == "NOT_FOUND"
    with Session(engine) as session:
        assert session.get(Job, job_id).status == "ACTIVE"

    second = verify_job_source_url(source_id, settings=settings, fetcher=fetcher)
    assert second.status == "NOT_FOUND"
    with Session(engine) as session:
        assert session.get(Job, job_id).status == "CLOSED"
        evidence = session.scalar(select(JobClosureEvidence))
        assert evidence is not None and evidence.applied is True
        assert session.scalar(select(func.count(JobApplyUrlCheck.id))) == 2
    engine.dispose()


def test_quality_metrics_are_measured_not_invented(database_url):
    engine = create_engine(database_url)
    with Session(engine) as session:
        metrics = quality_metrics(session, window_hours=24)
        coverage = source_coverage_metrics(session)
        assert metrics["canonical_active_jobs"] == 0
        assert metrics["source_postings"] == 0
        assert metrics["canonical_source_ratio"] is None
        assert metrics["apply_url_validity_percentage"] is None
        assert metrics["measured_estimated_cost_usd"] is None
        assert coverage["sources_by_type"] == {}
    engine.dispose()


def test_raw_payload_retention_keeps_latest_per_source(database_url, monkeypatch):
    from app.jobs.retention import purge_expired_raw_payloads

    engine = create_engine(database_url)
    with Session(engine, expire_on_commit=False) as session:
        source = JobSource(
            connector_key="lever",
            external_job_id="example:1",
            source_url="https://8.8.8.8/jobs/1",
            checkpoint={},
        )
        session.add(source)
        session.flush()
        old = RawJobPostingModel(
            job_source_id=source.id,
            payload={"version": 1},
            content_hash="a" * 64,
            normalization_status="NORMALIZED",
            fetched_at=datetime.now(timezone.utc) - timedelta(days=200),
        )
        latest = RawJobPostingModel(
            job_source_id=source.id,
            payload={"version": 2},
            content_hash="b" * 64,
            normalization_status="NORMALIZED",
            fetched_at=datetime.now(timezone.utc) - timedelta(days=150),
        )
        session.add_all([old, latest])
        session.commit()

    monkeypatch.setattr("app.jobs.retention.SessionLocal", lambda: Session(engine))
    assert purge_expired_raw_payloads(Settings(raw_job_payload_retention_days=90)) == 1
    with Session(engine) as session:
        rows = list(session.scalars(select(RawJobPostingModel)))
        assert len(rows) == 1 and rows[0].payload["version"] == 2
    engine.dispose()
