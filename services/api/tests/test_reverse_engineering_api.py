from app.core.internal_auth import require_internal_api
from app.main import app


def allow_internal() -> None:
    return None


def test_reverse_engineering_registry_auto_classifies_and_persists(client) -> None:
    app.dependency_overrides[require_internal_api] = allow_internal
    response = client.post(
        "/api/v1/internal/reverse-engineering/topics",
        json={
            "title": "Terum-inspired agent evaluation",
            "source_url": "https://example.com/terum-research",
            "summary": (
                "Agent evaluation with A/B evaluation, baseline arm, candidate arm, "
                "regression detection, evaluation receipts, provenance and trigger precision."
            ),
            "qualifying_capabilities": ["release gate", "cost measurement", "latency measurement"],
            "excluded_capabilities": ["generic skill marketplace"],
        },
    )
    assert response.status_code == 201, response.text
    topic = response.json()
    assert topic["applyai_fit"] == "INFRASTRUCTURE"
    assert topic["fit_scope"] == "PARTIAL"
    assert topic["classification_source"] == "AUTO"

    listing = client.get("/api/v1/internal/reverse-engineering/topics")
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [topic["id"]]

    manual = client.patch(
        f"/api/v1/internal/reverse-engineering/topics/{topic['id']}",
        json={"applyai_fit": "INTEGRATION", "rationale": "Operator chose an external execution boundary."},
    )
    assert manual.status_code == 200
    assert manual.json()["classification_source"] == "MANUAL"
    assert manual.json()["destination"] == "external-integration"

    reclassified = client.post(
        f"/api/v1/internal/reverse-engineering/topics/{topic['id']}/reclassify"
    )
    assert reclassified.status_code == 200
    assert reclassified.json()["classification_source"] == "AUTO"
    assert reclassified.json()["applyai_fit"] == "INFRASTRUCTURE"


def test_ai_release_evaluation_persists_immutable_content_bound_receipt(client) -> None:
    app.dependency_overrides[require_internal_api] = allow_internal
    payload = {
        "subject_type": "AGENT",
        "subject_name": "resume-agent",
        "subject_version": "v2",
        "candidate_artifact": {"prompt": "candidate-v2", "max_steps": 6},
        "dataset_version": "resume-golden-v1",
        "baseline_runs": [
            {"case": "a", "passed": False, "cost_usd": 0.01, "duration_ms": 1000, "turns": 2},
            {"case": "b", "passed": False, "cost_usd": 0.01, "duration_ms": 1000, "turns": 2},
            {"case": "c", "passed": True, "cost_usd": 0.01, "duration_ms": 1000, "turns": 2},
        ],
        "candidate_runs": [
            {"case": "a", "passed": True, "cost_usd": 0.02, "duration_ms": 1200, "turns": 3},
            {"case": "b", "passed": True, "cost_usd": 0.02, "duration_ms": 1200, "turns": 3},
            {"case": "c", "passed": True, "cost_usd": 0.02, "duration_ms": 1200, "turns": 3},
        ],
        "triggers": {"tp": 9, "fn": 1, "fp": 1, "tn": 9},
        "provenance": {"model": "deterministic-test", "engine_commit": "abc123"},
        "evaluated_at": "2026-09-17T16:00:00+00:00",
    }
    response = client.post("/api/v1/internal/ai-release-evaluation/evaluate", json=payload)
    assert response.status_code == 201, response.text
    receipt = response.json()
    assert receipt["created"] is True
    assert receipt["verdict"] == "PASS"
    assert receipt["release_gate"] == "PASS"
    assert receipt["content_digest"].startswith("sha256:")
    assert receipt["receipt_digest"].startswith("sha256:")

    duplicate = client.post("/api/v1/internal/ai-release-evaluation/evaluate", json=payload)
    assert duplicate.status_code == 201
    assert duplicate.json()["created"] is False
    assert duplicate.json()["id"] == receipt["id"]

    listing = client.get("/api/v1/internal/ai-release-evaluation/receipts")
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["receipt_digest"] == receipt["receipt_digest"]
