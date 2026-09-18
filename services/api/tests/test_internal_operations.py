from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.operator_auth import require_operator_or_internal
from app.durability_models import TaskOutbox
from app.job_source_models import JobSourceRegistry
from app.main import app
from app.operations_models import OperationsCertification, ServiceCostEntry


def _seed_source(database_url: str) -> str:
    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            source = JobSourceRegistry(
                source_type="GREENHOUSE",
                source_name="Operations test source",
                source_identity="operations-test",
                trust_level="OFFICIAL_ATS",
                enabled=True,
                crawl_allowed=True,
                health_status="HEALTHY",
                priority=90,
                next_run_at=datetime.now(timezone.utc),
            )
            session.add(source)
            session.commit()
            session.refresh(source)
            return str(source.id)
    finally:
        engine.dispose()


def test_internal_operations_refresh_queues_source_ingest_and_reports_summary(
    client, database_url: str
) -> None:
    app.dependency_overrides[require_operator_or_internal] = lambda: None
    source_id = _seed_source(database_url)

    response = client.post(f"/api/v1/internal/operations/sources/{source_id}/refresh")
    assert response.status_code == 202
    payload = response.json()
    assert payload["scheduled"] is True
    assert payload["source_id"] == source_id

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            event = session.scalar(
                select(TaskOutbox).where(TaskOutbox.event_type == "SOURCE_INGEST")
            )
            assert event is not None
            assert event.payload["source_id"] == source_id
            assert event.aggregate_type == "job_source_registry"
    finally:
        engine.dispose()

    summary = client.get("/api/v1/internal/operations/summary")
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["sources"]["total"] == 1
    assert summary_payload["sources"]["live_leases"] == 0
    assert summary_payload["ingestion"]["pending_source_tasks"] == 1
    assert summary_payload["runtime"]["database_reachable"] is True
    assert summary_payload["runtime"]["task_queue_provider"] == "memory"
    assert summary_payload["runtime"]["storage_configured"] is True
    assert summary_payload["queue"]["pending"] == 0


def test_internal_operations_certification_is_persisted_and_cursor_paginated(
    client, database_url: str
) -> None:
    app.dependency_overrides[require_operator_or_internal] = lambda: None

    for status in ("BLOCKED", "PASS"):
        response = client.post(
            "/api/v1/internal/operations/certifications",
            json={
                "certification_type": "FULL_FUNCTIONAL",
                "status": status,
                "environment": "cleanroom",
                "git_sha": "abc123",
                "evidence": {"SOURCE_INGEST": True, "internal_operations": True},
                "notes": f"certification {status}",
                "created_by": "e2e.candidate@example.test",
            },
        )
        assert response.status_code == 201

    first = client.get("/api/v1/internal/operations/certifications?limit=1")
    assert first.status_code == 200
    first_payload = first.json()
    assert len(first_payload["items"]) == 1
    assert first_payload["next_cursor"]

    second = client.get(
        "/api/v1/internal/operations/certifications",
        params={"limit": 1, "cursor": first_payload["next_cursor"]},
    )
    assert second.status_code == 200
    assert len(second.json()["items"]) == 1
    assert second.json()["items"][0]["id"] != first_payload["items"][0]["id"]

    invalid = client.get(
        "/api/v1/internal/operations/certifications",
        params={"cursor": "not-a-valid-cursor"},
    )
    assert invalid.status_code == 400

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            records = list(session.scalars(select(OperationsCertification)))
            assert {row.status for row in records} == {"PASS", "BLOCKED"}
    finally:
        engine.dispose()



def test_internal_operations_cost_ledger_is_auditable_and_separates_runtime_estimates(
    client, database_url: str
) -> None:
    app.dependency_overrides[require_operator_or_internal] = lambda: None

    response = client.post(
        "/api/v1/internal/operations/costs",
        json={
            "provider": "Vercel",
            "service": "Web and API hosting",
            "category": "HOSTING",
            "cost_type": "INVOICE",
            "amount_usd": "42.125000",
            "period_start": "2026-09-01T00:00:00Z",
            "period_end": "2026-09-30T23:59:59Z",
            "source_ref": "invoice:vercel:2026-09",
            "notes": "September provider invoice",
            "created_by": "operator@example.test",
        },
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["provider"] == "Vercel"
    assert created["amount_usd"] == 42.125

    costs = client.get("/api/v1/internal/operations/costs?days=30")
    assert costs.status_code == 200, costs.text
    payload = costs.json()
    assert payload["recorded_service_total_usd"] == 42.125
    assert payload["career_ai_estimated_usd"] >= 0
    assert payload["agent_runtime_measured_usd"] >= 0
    assert payload["by_provider"] == [{"provider": "Vercel", "amount_usd": 42.125}]
    assert payload["entries"][0]["source_ref"] == "invoice:vercel:2026-09"
    assert "not added" in payload["accounting_note"]

    invalid = client.post(
        "/api/v1/internal/operations/costs",
        json={
            "provider": "Supabase",
            "service": "Database",
            "category": "DATABASE",
            "cost_type": "INVOICE",
            "amount_usd": "10.00",
            "period_start": "2026-09-30T00:00:00Z",
            "period_end": "2026-09-01T00:00:00Z",
        },
    )
    assert invalid.status_code == 422

    engine = create_engine(database_url)
    try:
        with Session(engine) as session:
            records = list(session.scalars(select(ServiceCostEntry)))
            assert len(records) == 1
            assert records[0].service == "Web and API hosting"
    finally:
        engine.dispose()
