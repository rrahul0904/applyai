"""Prove that unrelated global jobs cannot certify an unrefreshed source."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from scripts.verify_job_supply import verified_source_run


NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)


def fixtures():
    source_id = uuid4()
    source = SimpleNamespace(
        id=source_id,
        enabled=True,
        crawl_allowed=True,
        health_status="HEALTHY",
        source_type="GREENHOUSE",
        last_job_count=20,
        last_success_at=NOW - timedelta(hours=1),
    )
    run = SimpleNamespace(
        id=uuid4(),
        source_id=source_id,
        status="COMPLETED",
        started_at=NOW - timedelta(hours=1, minutes=1),
        completed_at=NOW - timedelta(hours=1),
        fetched=20,
        valid=20,
        failed=0,
    )
    return source, run


def check(source, run, total=500):
    return verified_source_run(
        source, run,
        external_active_jobs=total,
        now=NOW,
        minimum_jobs=1,
        maximum_source_age_hours=30,
    )


def test_one_fresh_source_run_with_persisted_external_jobs_passes():
    source, run = fixtures()
    assert check(source, run) is True


def test_no_run_never_passes_even_when_global_job_inventory_is_large():
    source, run = fixtures()
    assert check(source, None, total=2_000_000) is False


def test_different_source_run_cannot_certify_selected_source():
    source, run = fixtures()
    run.source_id = uuid4()
    assert check(source, run) is False


def test_failed_or_empty_run_cannot_pass():
    source, run = fixtures()
    run.status = "FAILED"
    assert check(source, run) is False
    run.status = "COMPLETED"
    run.valid = 0
    assert check(source, run) is False
    run.valid = 20
    run.failed = 1
    assert check(source, run) is False


def test_stale_runs_or_failing_source_cannot_pass():
    source, run = fixtures()
    run.completed_at = NOW - timedelta(hours=48)
    assert check(source, run) is False
    run.completed_at = NOW
    source.health_status = "FAILED"
    assert check(source, run) is False


def test_no_external_active_jobs_cannot_pass():
    source, run = fixtures()
    assert check(source, run, total=0) is False


def test_development_source_never_passes():
    source, run = fixtures()
    source.source_type = "DEVELOPMENT_SEED"
    assert check(source, run) is False
