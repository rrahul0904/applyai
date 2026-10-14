from types import SimpleNamespace

from scripts.job_supply_initial_acceptance import (
    completed_open_jobs_cycle,
    evaluate_initial_acceptance,
)


def _run(**overrides):
    values = {
        "status": "PARTIAL",
        "coverage_status": "PARTIAL",
        "coverage_details": {
            "status": "PARTIAL",
            "completeness_checks": {
                "cycle_complete": True,
                "cycle_restarted_for_manifest_change": False,
            },
        },
        "failed": 0,
        "fetched": 12,
        "valid": 12,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_accepts_completed_discovery_cycle_without_marking_batch_complete():
    run = _run()

    assert completed_open_jobs_cycle(run) is True
    assert run.status == "PARTIAL"
    assert run.coverage_status == "PARTIAL"


def test_rejects_incomplete_or_failed_discovery_cycle():
    assert completed_open_jobs_cycle(None) is False
    incomplete = _run(coverage_details={"completeness_checks": {"cycle_complete": False}})
    assert completed_open_jobs_cycle(incomplete) is False
    assert completed_open_jobs_cycle(_run(failed=1)) is False
    assert completed_open_jobs_cycle(_run(status="COMPLETED")) is False


def test_initial_supply_acceptance_uses_cycle_receipt_for_bounded_source():
    evidence = {
        "database_schema_present": True,
        "open_jobs_source_active": True,
        "successful_open_jobs_run": False,
        "completed_open_jobs_cycle": True,
        "real_canonical_jobs": 12,
        "latest_open_jobs_failed": 0,
        "open_jobs_source_postings": 12,
        "company_identity_preserved": True,
    }

    report = evaluate_initial_acceptance(evidence, min_jobs=1)

    assert report["status"] == "PASS"
    assert report["claim"] == "INITIAL_PRODUCTION_JOB_SUPPLY_VERIFIED"
