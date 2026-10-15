from dataclasses import replace
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.queue import Task, supports_task_type
from app.durability_models import TaskOutbox
from app.job_radar_models import JobScan, JobScanMatch, JobSearchProfile
from app.job_radar_service import (
    NormalizedJobCandidate,
    ScoringProfileSnapshot,
    deduplicate_candidates,
    deterministic_score,
    parse_salary_text,
    run_job_scan,
    snapshot_scoring_profile,
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
    single = parse_salary_text("$135k/year")
    assert single is not None
    assert (single.minimum, single.maximum) == (135_000, 135_000)

    floor = parse_salary_text("from $125k/year")
    assert floor is not None
    assert (floor.minimum, floor.maximum) == (125_000, None)

    ceiling = parse_salary_text("up to EUR 10k/month")
    assert ceiling is not None
    assert (ceiling.minimum, ceiling.maximum, ceiling.currency, ceiling.interval) == (
        None,
        10_000,
        "EUR",
        "MONTH",
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


def test_deterministic_score_discloses_missing_signals_without_imputation():
    profile = JobSearchProfile(
        target_titles=["Data Engineer"],
        skills=[],
        years_experience=None,
        seniority_preferences=[],
        preferred_locations=[],
        remote_policy="ANY",
        salary_min=None,
        salary_currency="USD",
        query_hints={},
    )
    job = NormalizedJobCandidate(
        provider="canonical-store-v1",
        provider_job_id="job-missing-signals",
        application_url="https://jobs.example.com/roles/missing-signals",
        title="Data Engineer",
        company="Example",
        description="",
        canonical_job_id=None,
        location=None,
        work_mode=None,
        employment_type=None,
        seniority=None,
        skills=(),
        salary=None,
        posted_at=None,
    )

    score, breakdown = deterministic_score(profile, job)

    assert score == 40
    assert breakdown["version"] == "job-radar-deterministic-v1"
    assert breakdown["signals"]["title"] == 100
    assert breakdown["missing_signals"] == ["skills", "experience", "location", "salary"]
    assert breakdown["contributions"]["skills"] == 0
    assert breakdown["contributions"]["salary"] == 0


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
    assert payload["external_job_providers"] == "NOT_IMPLEMENTED"
    assert payload["realtime_streaming"] == "NOT_IMPLEMENTED"
    assert payload["autonomous_applications"] == "NOT_IMPLEMENTED"
    assert payload["jobs_seen"] == 1
    assert payload["jobs_ranked"] == 1
    assert len(payload["matches"]) == 1
    assert payload["matches"][0]["application_url"] == "https://jobs.example.com/radar-1"
    assert payload["matches"][0]["deterministic_score"] >= 80
    assert payload["matches"][0]["score_breakdown"]["version"] == "job-radar-deterministic-v1"
    evidence = payload["matches"][0]["source_evidence"]
    assert evidence["remote_eligibility"]["decision"] == "INELIGIBLE"
    assert evidence["remote_eligibility"]["remote_scope"] == "NOT_REMOTE"
    assert evidence["opportunity"]["state"] == "OPEN"
    assert evidence["opportunity"]["first_seen"]
    assert evidence["opportunity"]["last_seen"]
    assert evidence["provenance"]["canonical_sources"]
    assert evidence["provenance"]["aggregator_sources"] == []
    assert payload["matches"][0]["score_breakdown"]["missing_signals"] == []
    assert payload["matches"][0]["source_evidence"]["provider_job_id"] == "radar-1"
    assert payload["matches"][0]["source_evidence"]["salary"] == {
        "minimum": 150000,
        "maximum": 180000,
        "currency": "USD",
        "interval": "YEAR",
        "raw": "provider-structured",
        "provenance": "TEST",
    }

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


def _queued_scan(client, monkeypatch, *, key="snapshot-scan"):
    from app.api import job_radar

    _seed_job()
    original = {
        "target_titles": ["Data Engineer"],
        "skills": ["Python", "SQL", "AWS"],
        "years_experience": 8,
        "seniority_preferences": ["SENIOR"],
        "preferred_locations": ["Boston"],
        "remote_policy": "HYBRID",
        "salary_min": 140000,
        "salary_currency": "USD",
    }
    assert client.put("/api/v1/job-radar/profile", json=original).status_code == 200
    # Suppress memory-mode inline execution to reproduce durable queue delay.
    # The real worker service is invoked below, in a separate database session.
    monkeypatch.setattr(job_radar, "run_job_scan", lambda *args, **kwargs: True)
    response = client.post("/api/v1/job-radar/scans", headers={"Idempotency-Key": key}, json={"top_k": 5})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "QUEUED"
    import uuid
    return uuid.UUID(response.json()["id"]), original


def test_queued_scan_and_retry_use_enqueue_time_profile(client, monkeypatch):
    scan_id, original = _queued_scan(client, monkeypatch)
    changed = {
        **original,
        "target_titles": ["Product Manager"],
        "skills": ["Kubernetes"],
        "years_experience": 0,
        "seniority_preferences": ["ENTRY"],
        "preferred_locations": ["Berlin"],
        "remote_policy": "REMOTE",
        "salary_min": 999999,
        "salary_currency": "EUR",
    }
    assert client.put("/api/v1/job-radar/profile", json=changed).status_code == 200
    requests = []
    with SessionLocal() as session:
        scan = session.get(JobScan, scan_id)
        frozen_inputs = dict(scan.scoring_profile_snapshot)
        assert frozen_inputs["target_titles"] == original["target_titles"]
        assert frozen_inputs["skills"] == original["skills"]
        assert frozen_inputs["salary_min"] == original["salary_min"]
        assert frozen_inputs["snapshot_version"] == 1

        class FailingProvider:
            name = "canonical-store-v1"

            def search(self, request):
                requests.append(request)
                raise RuntimeError("temporary provider failure")

        assert not run_job_scan(session, scan_id=scan_id, provider=FailingProvider())
        assert session.get(JobScan, scan_id).status == "FAILED"
        assert session.get(JobScan, scan_id).scoring_profile_snapshot == frozen_inputs

    # Another edit before the task retry must not change the original score.
    assert client.put("/api/v1/job-radar/profile", json={**changed, "salary_min": 2000000, "years_experience": 1}).status_code == 200
    assert dispatch_task(
        Task(task_type="JOB_RADAR_SCAN", payload={"scan_id": str(scan_id)}, idempotency_key=f"snapshot-retry:{scan_id}"),
        Settings(task_queue_provider="postgres"),
    )
    with SessionLocal() as session:
        scan = session.get(JobScan, scan_id)
        match = session.scalar(select(JobScanMatch).where(JobScanMatch.scan_id == scan_id))
        assert scan.status == "COMPLETED"
        assert scan.scoring_profile_snapshot == frozen_inputs
        assert match is not None
        assert match.deterministic_score == 100
        assert match.score_breakdown["signals"] == {"title": 100, "skills": 100, "experience": 100, "location": 100, "salary": 100}
        assert scan.query_plan_json[0]["query"] == "Data Engineer"
        assert scan.query_plan_json[0]["location"] == "Boston"
    assert requests[0].query == "Data Engineer"
    assert requests[0].location == "Boston"
    duplicate = client.post("/api/v1/job-radar/scans", headers={"Idempotency-Key": "snapshot-scan"}, json={"top_k": 5})
    assert duplicate.json()["id"] == str(scan_id)
    assert duplicate.json()["matches"][0]["deterministic_score"] == 100


def test_snapshot_detaches_mutable_profile_collections(client, monkeypatch):
    scan_id, _ = _queued_scan(client, monkeypatch)
    with SessionLocal() as session:
        scan = session.get(JobScan, scan_id)
        profile = session.get(JobSearchProfile, scan.profile_id)
        snapshot = snapshot_scoring_profile(profile)
        frozen = ScoringProfileSnapshot.model_validate(snapshot)
        profile.skills.append("unrelated skill")
        profile.preferred_locations.append("Berlin")
        assert frozen.skills == ("Python", "SQL", "AWS")
        assert snapshot["skills"] == ["Python", "SQL", "AWS"]
        assert frozen.preferred_locations == ("Boston",)
        with pytest.raises(ValidationError, match="frozen"):
            frozen.salary_min = 1


@pytest.mark.parametrize("corruption,error", [
    (None, "SCORING_PROFILE_SNAPSHOT_MISSING"),
    ({}, "SCORING_PROFILE_SNAPSHOT_INVALID"),
    ({"snapshot_version": 999}, "SCORING_PROFILE_SNAPSHOT_INVALID"),
])
def test_legacy_or_invalid_snapshot_never_uses_current_profile(client, monkeypatch, corruption, error):
    scan_id, _ = _queued_scan(client, monkeypatch)
    with SessionLocal() as session:
        scan = session.get(JobScan, scan_id)
        scan.scoring_profile_snapshot = corruption
        session.commit()
        assert run_job_scan(session, scan_id=scan_id)
        assert scan.status == "FAILED"
        assert scan.error_code == error
        assert session.scalar(select(JobScanMatch).where(JobScanMatch.scan_id == scan_id)) is None


def test_snapshot_owner_must_match_scan(client, monkeypatch):
    import uuid
    scan_id, _ = _queued_scan(client, monkeypatch)
    with SessionLocal() as session:
        scan = session.get(JobScan, scan_id)
        scan.scoring_profile_snapshot = {**scan.scoring_profile_snapshot, "user_id": str(uuid.uuid4())}
        session.commit()
        assert run_job_scan(session, scan_id=scan_id)
        assert scan.error_code == "SCORING_PROFILE_SNAPSHOT_INVALID"
        assert session.scalar(select(JobScanMatch).where(JobScanMatch.scan_id == scan_id)) is None


def test_completed_legacy_scan_keeps_results_without_snapshot(client, monkeypatch):
    scan_id, _ = _queued_scan(client, monkeypatch)
    with SessionLocal() as session:
        assert run_job_scan(session, scan_id=scan_id)
        scan = session.get(JobScan, scan_id)
        assert scan.status == "COMPLETED"
        match = session.scalar(select(JobScanMatch).where(JobScanMatch.scan_id == scan_id))
        match_id = match.id
        scan.scoring_profile_snapshot = None
        session.commit()
        assert run_job_scan(session, scan_id=scan_id)
        assert scan.status == "COMPLETED"
        assert session.scalar(select(JobScanMatch).where(JobScanMatch.scan_id == scan_id)).id == match_id
