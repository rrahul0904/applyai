from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.durability_models import JobIngestionRun
from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob
from app.jobs.pipeline import JobIngestionPipeline
from app.models import (
    CompanySource,
    Job,
    JobSource,
    JobSourceLink,
    JobVersion,
    RawJobPosting,
)


class MutableGreenhouseConnector(JobSourceConnector):
    key = "greenhouse"

    def __init__(self, board_token: str, records: list[dict]) -> None:
        self.board_token = board_token
        self.records = records
        self.fail_fetch = False
        self.fetch_number = 0

    def source_company_identity(self) -> str:
        return self.board_token

    def fetch(self, checkpoint):
        del checkpoint
        if self.fail_fetch:
            raise RuntimeError("board unavailable")
        self.fetch_number += 1
        fetched_at = datetime.now(timezone.utc).isoformat()
        return [
            {**deepcopy(record), "_applyai_fetched_at": fetched_at}
            for record in self.records
        ]

    def normalize(self, payload: dict) -> NormalizedJob:
        post_id = str(payload["id"])
        return NormalizedJob(
            external_job_id=f"{self.board_token}:{post_id}",
            company_name=payload["_applyai_company_name"],
            title=payload["title"],
            description=payload["description"],
            application_url=payload["absolute_url"],
            locations=[payload["location"]],
            work_mode=payload.get("work_mode", "REMOTE"),
            employment_type=payload.get("employment_type", "UNKNOWN"),
            seniority=payload.get("seniority", "UNKNOWN"),
            salary_min=payload.get("salary_min"),
            salary_max=payload.get("salary_max"),
            salary_provenance=payload.get("salary_provenance"),
            skills=payload.get("skills", []),
            requirements=payload.get("requirements", []),
            posted_at=None,
            raw_payload=payload,
        )

    def checkpoint(self):
        return {"board_token": self.board_token, "count": len(self.records)}

    def health(self):
        return ConnectorHealth(True, datetime.now(timezone.utc), "test connector")


def posting(
    *,
    board: str = "example",
    post_id: int = 127817,
    internal_job_id: int = 4815,
    company: str = "Example Labs",
    title: str = "Senior Data Engineer",
    description: str = "Build reliable data platforms for production analytics.",
    location: str = "Remote - United States",
    url: str | None = None,
    source_updated_at: str = "2026-07-25T10:55:28-05:00",
) -> dict:
    return {
        "id": post_id,
        "title": title,
        "description": description,
        "location": location,
        "absolute_url": url or f"https://boards.greenhouse.io/{board}/jobs/{post_id}",
        "work_mode": "REMOTE",
        "skills": ["Python", "SQL"],
        "requirements": ["Build production data platforms"],
        "_applyai_company_name": company,
        "_applyai_board_token": board,
        "_applyai_greenhouse_post_id": str(post_id),
        "_applyai_internal_job_id": str(internal_job_id),
        "_applyai_source_updated_at": source_updated_at,
        "_applyai_company_source_url": f"https://boards-api.greenhouse.io/v1/boards/{board}",
        "data_origin": "GREENHOUSE_PUBLIC_API",
    }


def test_same_posting_refreshes_last_seen_without_duplicate_version(database_url):
    engine = create_engine(database_url)
    connector = MutableGreenhouseConnector("example", [posting()])
    with Session(engine, expire_on_commit=False) as session:
        first = JobIngestionPipeline(session).run(connector)
        assert first["created"] == 1
        source = session.scalar(select(JobSource))
        job = session.scalar(select(Job))
        assert source is not None and job is not None
        source_first_seen = source.first_seen_at
        job_first_seen = job.first_seen_at

        old_seen = datetime.now(timezone.utc) - timedelta(days=2)
        source.last_seen_at = old_seen
        job.last_seen_at = old_seen
        session.commit()

        second = JobIngestionPipeline(session).run(connector)
        session.expire_all()
        source = session.scalar(select(JobSource))
        job = session.scalar(select(Job))
        assert second["unchanged"] == 1
        assert source is not None and job is not None
        assert source.first_seen_at == source_first_seen
        assert job.first_seen_at == job_first_seen
        assert source.last_seen_at > old_seen
        assert job.last_seen_at > old_seen
        assert session.scalar(select(func.count(JobSource.id))) == 1
        assert session.scalar(select(func.count(Job.id))) == 1
        assert session.scalar(select(func.count(JobVersion.id))) == 1
        assert session.scalar(select(func.count(RawJobPosting.id))) == 1
    engine.dispose()


def test_changed_posting_updates_canonical_job_and_creates_one_version(database_url):
    engine = create_engine(database_url)
    record = posting()
    connector = MutableGreenhouseConnector("example", [record])
    with Session(engine, expire_on_commit=False) as session:
        JobIngestionPipeline(session).run(connector)
        record["title"] = "Principal Data Engineer"
        record["description"] = "Lead reliable lakehouse and streaming platform architecture."
        record["skills"] = ["Python", "SQL", "Kafka"]
        record["_applyai_source_updated_at"] = "2026-07-29T10:00:00-05:00"

        result = JobIngestionPipeline(session).run(connector)
        job = session.scalar(select(Job))
        assert result["updated"] == 1
        assert job is not None
        assert job.title == "Principal Data Engineer"
        assert "lakehouse" in job.description
        assert "Kafka" in job.search_document
        assert session.scalar(select(func.count(JobVersion.id))) == 2
        assert session.scalar(select(func.count(RawJobPosting.id))) == 2

        matching = session.scalar(
            select(Job.id).where(
                Job.search_vector.op("@@")(
                    func.websearch_to_tsquery("english", "lakehouse")
                )
            )
        )
        assert matching == job.id
    engine.dispose()


def test_greenhouse_company_source_and_board_scoped_source_identity(database_url):
    engine = create_engine(database_url)
    connector = MutableGreenhouseConnector("example", [posting()])
    with Session(engine) as session:
        JobIngestionPipeline(session).run(connector)
        company_source = session.scalar(select(CompanySource))
        source = session.scalar(select(JobSource))
        assert company_source is not None
        assert company_source.source_name == "GREENHOUSE"
        assert company_source.external_company_id == "example"
        assert source is not None
        assert source.external_job_id == "example:127817"
        assert source.checkpoint["board_token"] == "example"
        assert source.checkpoint["greenhouse_post_id"] == "127817"
        assert source.checkpoint["internal_job_id"] == "4815"
        assert source.checkpoint["source_updated_at"]
    engine.dispose()


def test_strict_cross_source_dedup_records_reason_without_perfect_confidence(database_url):
    engine = create_engine(database_url)
    first = MutableGreenhouseConnector("board-a", [
        posting(board="board-a", post_id=1, internal_job_id=101, url="https://jobs.example.test/a")
    ])
    second = MutableGreenhouseConnector("board-b", [
        posting(board="board-b", post_id=2, internal_job_id=202, url="https://jobs.example.test/b")
    ])
    with Session(engine) as session:
        JobIngestionPipeline(session).run(first)
        JobIngestionPipeline(session).run(second)
        assert session.scalar(select(func.count(Job.id))) == 1
        assert session.scalar(select(func.count(JobSource.id))) == 2
        assert session.scalar(select(func.count(JobSourceLink.id))) == 2
        assert session.scalar(select(func.count(CompanySource.id))) == 2
        job = session.scalar(select(Job))
        assert job is not None
        assert str(job.dedup_confidence) == "0.8500"
        reasons = {
            source.checkpoint.get("dedup_reason")
            for source in session.scalars(select(JobSource))
        }
        assert "COMPANY_TITLE_LOCATION_DESCRIPTION" in reasons
    engine.dispose()


def test_failed_board_run_never_marks_existing_job_missing(database_url):
    engine = create_engine(database_url)
    connector = MutableGreenhouseConnector("example", [posting()])
    with Session(engine) as session:
        JobIngestionPipeline(session).run(connector)
        connector.fail_fetch = True
        with pytest.raises(RuntimeError, match="board unavailable"):
            JobIngestionPipeline(session).run(connector)

        job = session.scalar(select(Job))
        source = session.scalar(select(JobSource))
        failed_run = session.scalar(
            select(JobIngestionRun)
            .where(JobIngestionRun.status == "FAILED")
            .order_by(JobIngestionRun.started_at.desc())
        )
        assert job is not None and job.status == "ACTIVE"
        assert source is not None and int(source.checkpoint.get("miss_count") or 0) == 0
        assert failed_run is not None and failed_run.failed == 1
    engine.dispose()


def test_complete_board_misses_transition_unknown_then_stale_and_seen_reactivates(database_url):
    engine = create_engine(database_url)
    settings = Settings(job_unknown_after_misses=1, job_stale_after_misses=2)
    connector = MutableGreenhouseConnector("example", [posting()])
    with Session(engine) as session:
        JobIngestionPipeline(session, settings).run(connector)
        connector.records = []
        JobIngestionPipeline(session, settings).run(connector)
        job = session.scalar(select(Job))
        assert job is not None and job.status == "UNKNOWN"

        JobIngestionPipeline(session, settings).run(connector)
        session.refresh(job)
        assert job.status == "STALE"

        connector.records = [posting()]
        JobIngestionPipeline(session, settings).run(connector)
        session.refresh(job)
        source = session.scalar(select(JobSource))
        assert job.status == "ACTIVE"
        assert source is not None and source.checkpoint["miss_count"] == 0
    engine.dispose()
