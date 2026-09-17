import pytest

from app.ai.release_evaluation import content_digest, evaluate_release


def run(case: str, passed: bool | None, *, cost: float = 0.01, duration: int = 1000) -> dict:
    return {
        "case": case,
        "rep": 0,
        "passed": passed,
        "checks": [["deterministic", passed is True]],
        "turns": 2,
        "duration_ms": duration,
        "cost_usd": cost,
    }


def test_candidate_lift_passes_complete_release_gate() -> None:
    receipt = evaluate_release(
        subject_type="AGENT",
        subject_name="resume-agent",
        subject_version="v2",
        candidate_artifact={"prompt": "candidate-v2"},
        dataset_version="resume-golden-v1",
        baseline_runs=[run("a", False), run("b", False), run("c", True)],
        candidate_runs=[run("a", True, cost=0.02), run("b", True, cost=0.02), run("c", True, cost=0.02)],
        trigger_counts={"tp": 9, "fn": 1, "fp": 1, "tn": 9},
        provenance={"model": "deterministic-test"},
        evaluated_at="2026-09-17T16:00:00+00:00",
    )
    assert receipt["verdict"] == "PASS"
    assert receipt["release_gate"] == "PASS"
    assert receipt["execution_status"] == "complete"
    assert receipt["comparison"]["win"] == 2
    assert receipt["comparison"]["loss"] == 0
    assert receipt["comparison"]["net_lift"] == 2 / 3
    assert receipt["triggers"]["precision"] == 0.9
    assert receipt["triggers"]["recall"] == 0.9
    assert receipt["efficiency"]["delta"]["cost_usd"] == 0.01
    assert receipt["subject"]["content_digest"].startswith("sha256:")
    assert receipt["receipt_digest"].startswith("sha256:")


def test_regression_blocks_release() -> None:
    receipt = evaluate_release(
        subject_type="WORKFLOW",
        subject_name="job-ranker",
        subject_version="v3",
        candidate_artifact={"ranker": 3},
        dataset_version="job-ranking-v7",
        baseline_runs=[run("a", True), run("b", True), run("c", True)],
        candidate_runs=[run("a", False), run("b", False), run("c", True)],
        trigger_counts={"tp": 10, "fn": 0, "fp": 0, "tn": 10},
        evaluated_at="2026-09-17T16:00:00+00:00",
    )
    assert receipt["verdict"] == "FAIL"
    assert receipt["release_gate"] == "BLOCK"
    assert receipt["comparison"]["net_lift"] == -2 / 3
    assert any("regression threshold" in reason for reason in receipt["gate_reasons"])


def test_partial_run_blocks_even_when_scored_rows_win() -> None:
    receipt = evaluate_release(
        subject_type="SKILL",
        subject_name="interview-coach",
        subject_version="v1",
        candidate_artifact={"skill": "interview"},
        dataset_version="interview-v1",
        baseline_runs=[run("a", False), run("b", False)],
        candidate_runs=[run("a", True), run("b", None)],
        trigger_counts={"tp": 9, "fn": 1, "fp": 1, "tn": 9},
        evaluated_at="2026-09-17T16:00:00+00:00",
    )
    assert receipt["verdict"] == "PASS"
    assert receipt["execution_status"] == "partial"
    assert receipt["release_gate"] == "BLOCK"
    assert receipt["scored_rows"] == 1
    assert receipt["expected_rows"] == 2


def test_trigger_regression_blocks_release() -> None:
    receipt = evaluate_release(
        subject_type="PROMPT",
        subject_name="company-intelligence-trigger",
        subject_version="v4",
        candidate_artifact={"prompt": "v4"},
        dataset_version="trigger-v2",
        baseline_runs=[run("a", False), run("b", False), run("c", True)],
        candidate_runs=[run("a", True), run("b", True), run("c", True)],
        trigger_counts={"tp": 5, "fn": 5, "fp": 5, "tn": 5},
        evaluated_at="2026-09-17T16:00:00+00:00",
    )
    assert receipt["verdict"] == "PASS"
    assert receipt["release_gate"] == "BLOCK"
    assert any("Trigger precision" in reason for reason in receipt["gate_reasons"])
    assert any("Trigger recall" in reason for reason in receipt["gate_reasons"])


def test_receipt_digest_is_deterministic_for_same_evidence() -> None:
    kwargs = {
        "subject_type": "AGENT",
        "subject_name": "application-agent",
        "subject_version": "v9",
        "candidate_artifact": {"definition": {"max_steps": 8}},
        "dataset_version": "applications-v3",
        "baseline_runs": [run("a", False)],
        "candidate_runs": [run("a", True)],
        "trigger_counts": {"tp": 10, "fn": 0, "fp": 0, "tn": 10},
        "provenance": {"engine_commit": "abc123"},
        "evaluated_at": "2026-09-17T16:00:00+00:00",
    }
    first = evaluate_release(**kwargs)
    second = evaluate_release(**kwargs)
    assert first["receipt_digest"] == second["receipt_digest"]
    assert first["subject"]["content_digest"] == content_digest(kwargs["candidate_artifact"])


def test_receipt_redacts_credential_shaped_provenance_and_check_names() -> None:
    secret = "ghp_abcdefghijklmnopqrstuvwxyz123456"
    receipt = evaluate_release(
        subject_type="AGENT",
        subject_name="safe-receipt",
        subject_version="v1",
        candidate_artifact={"definition": "safe"},
        dataset_version="security-v1",
        baseline_runs=[{"case": "a", "rep": 0, "passed": False, "checks": [[f"token {secret}", False]]}],
        candidate_runs=[{"case": "a", "rep": 0, "passed": True, "checks": [[f"token {secret}", True]]}],
        trigger_counts={"tp": 10, "fn": 0, "fp": 0, "tn": 10},
        provenance={"debug_token": secret},
        evaluated_at="2026-09-17T16:00:00+00:00",
    )
    rendered = str(receipt)
    assert secret not in rendered
    assert "[redacted]" in rendered


def test_duplicate_run_keys_are_rejected_instead_of_overwritten() -> None:
    duplicate_baseline = [run("same", False), run("same", True)]
    with pytest.raises(ValueError, match="Duplicate baseline run key"):
        evaluate_release(
            subject_type="AGENT",
            subject_name="duplicate-key-guard",
            subject_version="v1",
            candidate_artifact={"definition": "candidate"},
            dataset_version="duplicates-v1",
            baseline_runs=duplicate_baseline,
            candidate_runs=[run("same", True)],
            evaluated_at="2026-09-17T16:00:00+00:00",
        )

    duplicate_candidate = [run("same", True), run("same", False)]
    with pytest.raises(ValueError, match="Duplicate candidate run key"):
        evaluate_release(
            subject_type="AGENT",
            subject_name="duplicate-key-guard",
            subject_version="v1",
            candidate_artifact={"definition": "candidate"},
            dataset_version="duplicates-v1",
            baseline_runs=[run("same", False)],
            candidate_runs=duplicate_candidate,
            evaluated_at="2026-09-17T16:00:00+00:00",
        )
