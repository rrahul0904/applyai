from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.durability_models import JobIngestionRun
from app.job_source_models import JobSourceRegistry
from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob
from app.jobs.contracts import JobSourceType, RawJobPosting
from app.jobs.registry import claim_due_source_ids, sync_configured_sources
from app.jobs.source_pipeline import RegisteredSourceIngestionPipeline
from app.models import Job, JobSource, JobVersion, RawJobPosting as RawJobPostingModel


class MutableRegistryConnector(JobSourceConnector):
    key = "lever"

    def __init__(self, records: list[dict]) -> None:
        self.records = records

    def source_company_identity(self) -> str:
        return "example"

    def fetch(self, checkpoint):
        del checkpoint
        return [dict(record) for record in self.records]

    def to_raw(self, payload: dict) -> RawJobPosting:
        return RawJobPosting(
            source_type=JobSourceType.LEVER,
            source_name="lever",
            source_company_identity="example",
            source_job_identity=f"example:{payload['id']}",
            external_job_id=f"example:{payload['id']}",
            internal_job_id=str(payload.get("internal_job_id") or payload["id"]),
            source_url=payload["source_url"],
            apply_url=payload["apply_url"],
            company_name=payload["company_name"],
            title=payload["title"],
            description=payload["description"],
            location_text=payload.get("location"),
            locations=(payload["location"],) if payload.get("location") else (),
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
        return ConnectorHealth(True, datetime.now(timezone.utc), "test source")


def valid_posting(posting_id: str = "job-1") -> dict:
    return {
        "id": posting_id,
        "internal_job_id": f"req-{posting_id}",
        "company_name": "Example Labs",
        "title": "Senior Data Engineer",
        "description": (
            "Build reliable production data platforms, streaming services, and "
            "analytics foundations for customer-facing products."
        ),
        "location": "Remote - United States",
        "source_url": f"https://jobs.example.test/{posting_id}",
        "apply_url": f"https://jobs.example.test/{posting_id}/apply",
        "data_origin": "LEVER_PUBLIC_POSTINGS_API",
    }


def registry_source() -> JobSourceRegistry:
    return JobSourceRegistry(
        source_type="LEVER",
        source_name="Example Lever",
        source_identity="example",
        base_url="https://jobs.lever.co/example",
        configuration={"site": "example", "company_name": "Example Labs"},
        trust_level="OFFICIAL_ATS",
        enabled=True,
        crawl_allowed=True,
        health_status="HEALTHY",
        crawl_interval_seconds=3600,
        next_run_at=datetime.now(timezone.utc),
    )


def test_registered_source_pipeline_is_idempotent_and_records_metrics(database_url):
    engine = create_engine(database_url)
    with Session(engine, expire_on_commit=False) as session:
        source = registry_source()
        session.add(source)
        session.commit()

        connector = MutableRegistryConnector([valid_posting()])
        first = RegisteredSourceIngestionPipeline(session).run(source, connector)
        second = RegisteredSourceIngestionPipeline(session).run(source, connector)

        assert first["created"] == 1
        assert first["valid"] == 1
        assert second["unchanged"] == 1
        assert session.scalar(select(func.count(Job.id))) == 1
        assert session.scalar(select(func.count(JobSource.id))) == 1
        assert session.scalar(select(func.count(JobVersion.id))) == 1
        assert session.scalar(select(func.count(RawJobPostingModel.id))) == 1

        runs = list(
            session.scalars(
                select(JobIngestionRun).order_by(JobIngestionRun.started_at)
            )
        )
        assert len(runs) == 2
        assert all(run.source_id == source.id for run in runs)
        assert all(run.source_type == "LEVER" for run in runs)
        assert runs[0].valid == 1
        assert runs[0].duration_ms is not None
        posting_source = session.scalar(select(JobSource))
        assert posting_source is not None
        assert posting_source.checkpoint["source_registry_id"] == str(source.id)
        assert posting_source.checkpoint["validation_status"] == "VALID"
    engine.dispose()


def test_invalid_source_record_is_retained_without_becoming_searchable(database_url):
    engine = create_engine(database_url)
    invalid = valid_posting("bad-1")
    invalid["title"] = "-"
    invalid["description"] = "short"
    invalid["apply_url"] = "file:///private/apply"
    with Session(engine) as session:
        source = registry_source()
        session.add(source)
        session.commit()

        counts = RegisteredSourceIngestionPipeline(session).run(
            source,
            MutableRegistryConnector([invalid]),
        )

        assert counts["invalid"] == 1
        assert counts["created"] == 0
        assert session.scalar(select(func.count(Job.id))) == 0
        posting_source = session.scalar(select(JobSource))
        raw = session.scalar(select(RawJobPostingModel))
        assert posting_source is not None
        assert raw is not None and raw.normalization_status == "INVALID"
        assert "TITLE_MISSING_OR_PLACEHOLDER" in posting_source.checkpoint["validation_errors"]
    engine.dispose()


def test_due_source_claim_uses_durable_exclusive_lease(database_url):
    engine = create_engine(database_url)
    settings = Settings(job_source_claim_batch_size=10, job_source_lease_seconds=300)
    with Session(engine, expire_on_commit=False) as first_session:
        first = registry_source()
        second = registry_source()
        second.source_identity = "other"
        second.source_name = "Other Lever"
        first_session.add_all([first, second])
        first_session.commit()

        first_claim = claim_due_source_ids(
            first_session,
            settings=settings,
            worker_id="worker-a",
        )
        assert set(first_claim) == {first.id, second.id}

    with Session(engine) as second_session:
        second_claim = claim_due_source_ids(
            second_session,
            settings=settings,
            worker_id="worker-b",
        )
        assert second_claim == []
        leased = list(second_session.scalars(select(JobSourceRegistry)))
        assert all(source.locked_by == "worker-a" for source in leased)
        assert all(source.lease_expires_at is not None for source in leased)
    engine.dispose()


def test_configured_source_sync_is_idempotent(database_url):
    engine = create_engine(database_url)
    settings = Settings(
        greenhouse_board_tokens=["greenhouse-example"],
        lever_site_names=["lever-example"],
        ashby_board_names=["ashby-example"],
    )
    with Session(engine) as session:
        first = sync_configured_sources(session, settings)
        second = sync_configured_sources(session, settings)
        assert len(first) == 3
        assert len(second) == 3
        assert session.scalar(select(func.count(JobSourceRegistry.id))) == 3
        assert {
            source.source_type for source in session.scalars(select(JobSourceRegistry))
        } == {"GREENHOUSE", "LEVER", "ASHBY"}
    engine.dispose()


def test_internal_source_api_requires_separate_operator_token(client: TestClient):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        internal_api_token="operator-token-at-least-24-characters"
    )

    denied = client.get("/api/v1/internal/job-sources")
    assert denied.status_code == 403

    headers = {"X-ApplyAI-Internal-Token": "operator-token-at-least-24-characters"}
    created = client.post(
        "/api/v1/internal/job-sources",
        headers=headers,
        json={
            "source_type": "LEVER",
            "source_name": "Example Lever",
            "source_identity": "example",
            "base_url": "https://jobs.lever.co/example",
            "configuration": {"site": "example"},
            "crawl_interval_seconds": 3600,
        },
    )
    assert created.status_code == 201
    source_id = created.json()["id"]

    listed = client.get("/api/v1/internal/job-sources", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    disabled = client.post(
        f"/api/v1/internal/job-sources/{source_id}/disable",
        headers=headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["health_status"] == "DISABLED"
