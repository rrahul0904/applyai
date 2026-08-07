from app.ai.evaluation import compare_variants, evaluate_suite, precision_at_k


def test_ai_evaluation_tracks_ranking_and_evidence_safety():
    dataset = {
        "ranking_cases": [{"name": "ranking", "relevant_ids": ["a", "b"], "ranked_ids": ["a", "x", "b"]}],
        "evidence_cases": [{"name": "evidence", "allowed_refs": ["fact:a", "fact:b"], "emitted_refs": ["fact:a", "fact:b"]}],
    }
    result = evaluate_suite(dataset)
    assert result["aggregate"]["precision_at_5"] == 2 / 3
    assert result["aggregate"]["mean_reciprocal_rank"] == 1.0
    assert result["aggregate"]["evidence_support_rate"] == 1.0
    assert result["aggregate"]["unsupported_reference_count"] == 0


def test_variant_comparison_exposes_quality_regression():
    baseline = {
        "ranking_cases": [{"relevant_ids": ["a"], "ranked_ids": ["a", "x"]}],
        "evidence_cases": [{"allowed_refs": ["fact:a"], "emitted_refs": ["fact:a"]}],
    }
    candidate = {
        "ranking_cases": [{"relevant_ids": ["a"], "ranked_ids": ["x", "a"]}],
        "evidence_cases": [{"allowed_refs": ["fact:a"], "emitted_refs": ["fact:invented"]}],
    }
    result = compare_variants(baseline, candidate)
    assert result["delta"]["mean_reciprocal_rank"] < 0
    assert result["delta"]["evidence_support_rate"] < 0


def test_precision_at_k_requires_positive_k():
    try:
        precision_at_k({"a"}, ["a"], 0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("Expected positive-k validation")
