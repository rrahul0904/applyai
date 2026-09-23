from dataclasses import replace
from datetime import datetime, timezone

from sqlalchemy import delete, select

from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.queue import Task, supports_task_type
from app.durability_models import TaskOutbox
from app.job_radar_models import JobScan, JobScanMatch
from app.job_radar_service import (
    NormalizedJobCandidate,
    deduplicate_candidates,
    parse_salary_text,
)
from app.models import (
    Company,
    Job,
    JobCompensation,
    JobLocation,
    JobSkill,
    JobSource,
    JobSourceLink,
)
from app.workers.postgres import dispatch_task


def test_salary_parser_preserves_evidenced_period_currency_and_unknowns():
    annual = parse_salary_text("$120k-$150k/year")
    assert annual is not None
    assert (annual.minimum, annual.maximum, annual.currency, annual.interval) == (
        120_000,
        150_000,
        "USD",
        "YEAR",
    )

    hourly = parse_salary_text("$70-$90/hour")
    assert hourly is not None
    assert (hourly.minimum, hourly.maximum, hourly.interval) == (70, 90, "HOUR")

    monthly = parse_salary_text("EUR 8k-10k/month")
    assert monthly is not None
    assert (monthly.minimum, monthly.maximum, monthly.currency, monthly.interval) == (
        8_000,
        10_000,
        "EUR",
        "MONTH",
    )

    lpa = parse_salary_text("20 LPA - 30 LPA CTC")
    assert lpa is not None
    assert (lpa.minimum, lpa.maximum, lpa.currency, lpa.interval) == (
        2_000_000,
        3_000_000,
        "INR",
        "YEAR",
    )
    assert parse_salary_text("competitive") is None
    assert parse_salary_text("$150k-$120k/year") is None


def test_dedupe_prefers_provider_id_then_canonical_url():
    base = NormalizedJobCandidate(
        provider="provider-a",
        provider_job_id="job-1",
        application_url="https://jobs.example.com/roles/1",
        title="Data Engineer",
        company="Example",
        description="Python and SQL",
        canonical_job_id=None,
        location="Boston, MA",
        work_mode="HYBRID",
        employment_type="FULL_TIME",
        seniority="SENIOR",
        skills=("python", "sql"),
        salary=None,
        posted_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
    )
    duplicate_id = replace(base, application_url="https://jobs.example.com/roles/1-alt")
    duplicate_url = replace(base, provider_job_id="job-2")
    unique = replace(
        base,
        provider_job_id="job-3",
        application_url="https://jobs.example.com/roles/3",
    )
    assert deduplicate_candidates([base, duplicate_id, duplicate_url, unique]) == [base, unique]


def _seed_job() -> None:
    with SessionLocal() as session:
        company = Company(canonical_name="Radar Labs", normalized_name="radar labs")
        session.add(company)
        session.flush()
        job = Job(
            company_id=company.id,
            title="Senior Data Engineer",
            normalized_title="senior data engineer",
            description="Python SQL AWS data platform engineering",
            search_document="Senior Data Engineer Python SQL AWS data platform engineering",
            employment_type="FULL_TIME",
            seniority="SENIOR",
            status="ACTIVE",
            posted_at=datetime.now(timezone.utc),
            data_origin="TEST",
        )
        session.add(job)
        session.flush()
        source = JobSource(
            connector_key="test-radar",
            external_job_id="radar-1",
            source_url="https://jobs.example.com/radar-1?utm_source=test",
        )
        session.add(source)
        session.flush()
        session.add(JobSourceLink(job_id=job.id, job_source_id=source.id, is_primary=True))
        session.add(
            JobLocation(
                job_id=job.id,
                location_text="Boston, MA",
                city="Boston",
                region="MA",
                country_code="US",
                work_mode="HYBRID",
            )
        )
        session.add(JobSkill(job_id=job.id, name="Python", normalized_name="python", required=True))
        session.add(JobSkill(job_id=job.id, name="SQL", normalized_name="sql", required=True))
        session.add(
            JobCompensation(
                job_id=job.id,
                minimum=150_000,
                maximum=180_000,
                currency="USD",
                interval="YEAR",
                provenance="TEST",
            )
        )
        session.commit()


def test_on_demand_scan_is_persisted_idempotent_and_worker_routable(client, switch_user):
    _seed_job()
    profile = client.put(
        "/api/v1/job-radar/profile",
        json={
            "target_titles": ["Data Engineer"],
            "skills": ["Python", "SQL", "AWS"],
            "years_experience": 8,
            "preferred_locations": ["Boston"],
            "remote_policy": "HYBRID",
            "salary_min": 140000,
            "salary_currency": "USD",
        },
    )
    assert profile.status_code == 200

    headers = {"Idempotency-Key": "jobprime-phase-a-test"}
    first = client.post(
        "/api/v1/job-radar/scans",
        headers=headers,
        json={"max_queries": 3, "per_query_limit": 10, "top_k": 5},
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload["status"] == "COMPLETED"
    assert payload["providers"] == ["canonical-store-v1"]
    assert payload["scoring_version"] == "job-radar-deterministic-v1"
    assert payload["top_k"] == 5
    assert payload["ai_reranking"] == "NOT_IMPLEMENTED"
    assert payload["scheduled_delivery"] == "NOT_IMPLEMENTED"
    assert payload["jobs_seen"] == 1
    assert payload["jobs_ranked"] == 1
    assert len(payload["matches"]) == 1
    assert payload["matches"][0]["application_url"] == "https://jobs.example.com/radar-1"
    assert payload["matches"][0]["deterministic_score"] >= 80
    assert payload["matches"][0]["score_breakdown"]["version"] == "job-radar-deterministic-v1"
    assert payload["matches"][0]["source_evidence"]["provider_job_id"] == "radar-1"

    second = client.post(
        "/api/v1/job-radar/scans",
        headers=headers,
        json={"max_queries": 3, "per_query_limit": 10, "top_k": 5},
    )
    assert second.status_code == 200
    assert second.json()["id"] == payload["id"]

    assert supports_task_type(Settings(task_queue_provider="postgres"), "JOB_RADAR_SCAN")
    with SessionLocal() as session:
        scans = list(session.scalars(select(JobScan)))
        matches = list(session.scalars(select(JobScanMatch)))
        outbox = list(
            session.scalars(select(TaskOutbox).where(TaskOutbox.event_type == "JOB_RADAR_SCAN"))
        )
        assert len(scans) == 1
        assert len(matches) == 1
        assert len(outbox) == 1
        scan_id = scans[0].id
        scans[0].status = "QUEUED"
        scans[0].completed_at = None
        session.execute(delete(JobScanMatch).where(JobScanMatch.scan_id == scan_id))
        session.commit()

    assert dispatch_task(
        Task(
            task_type="JOB_RADAR_SCAN",
            payload={"scan_id": str(scan_id)},
            idempotency_key=f"job-radar-scan:{scan_id}:worker-test",
        ),
        Settings(task_queue_provider="postgres"),
    )
    with SessionLocal() as session:
        refreshed = session.get(JobScan, scan_id)
        assert refreshed is not None
        assert refreshed.status == "COMPLETED"
        assert session.scalar(select(JobScanMatch).where(JobScanMatch.scan_id == scan_id)) is not None

    switch_user("clerk_user_b", "b@example.com")
    forbidden = client.get(f"/api/v1/job-radar/scans/{scan_id}")
    assert forbidden.status_code == 404
