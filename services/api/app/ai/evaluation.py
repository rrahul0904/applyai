from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class RankingCase:
    relevant_ids: frozenset[str]
    ranked_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceCase:
    allowed_refs: frozenset[str]
    emitted_refs: tuple[str, ...]


def precision_at_k(relevant_ids: set[str] | frozenset[str], ranked_ids: Iterable[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be positive")
    ranked = list(ranked_ids)[:k]
    if not ranked:
        return 0.0
    return sum(1 for identifier in ranked if identifier in relevant_ids) / len(ranked)


def reciprocal_rank(relevant_ids: set[str] | frozenset[str], ranked_ids: Iterable[str]) -> float:
    for index, identifier in enumerate(ranked_ids, start=1):
        if identifier in relevant_ids:
            return 1.0 / index
    return 0.0


def evidence_support_rate(allowed_refs: set[str] | frozenset[str], emitted_refs: Iterable[str]) -> float:
    emitted = list(emitted_refs)
    if not emitted:
        return 1.0
    return sum(1 for ref in emitted if ref in allowed_refs) / len(emitted)


def unsupported_reference_count(allowed_refs: set[str] | frozenset[str], emitted_refs: Iterable[str]) -> int:
    return sum(1 for ref in emitted_refs if ref not in allowed_refs)


def evaluate_suite(dataset: dict[str, Any]) -> dict[str, Any]:
    ranking_rows = dataset.get("ranking_cases", [])
    evidence_rows = dataset.get("evidence_cases", [])
    ranking_metrics = []
    for row in ranking_rows:
        relevant = frozenset(str(value) for value in row.get("relevant_ids", []))
        ranked = tuple(str(value) for value in row.get("ranked_ids", []))
        ranking_metrics.append({
            "name": row.get("name", "ranking-case"),
            "precision_at_5": precision_at_k(relevant, ranked, 5),
            "precision_at_10": precision_at_k(relevant, ranked, 10),
            "reciprocal_rank": reciprocal_rank(relevant, ranked),
        })
    evidence_metrics = []
    for row in evidence_rows:
        allowed = frozenset(str(value) for value in row.get("allowed_refs", []))
        emitted = tuple(str(value) for value in row.get("emitted_refs", []))
        evidence_metrics.append({
            "name": row.get("name", "evidence-case"),
            "support_rate": evidence_support_rate(allowed, emitted),
            "unsupported_reference_count": unsupported_reference_count(allowed, emitted),
        })
    return {
        "ranking": ranking_metrics,
        "evidence": evidence_metrics,
        "aggregate": {
            "precision_at_5": mean([row["precision_at_5"] for row in ranking_metrics]) if ranking_metrics else None,
            "precision_at_10": mean([row["precision_at_10"] for row in ranking_metrics]) if ranking_metrics else None,
            "mean_reciprocal_rank": mean([row["reciprocal_rank"] for row in ranking_metrics]) if ranking_metrics else None,
            "evidence_support_rate": mean([row["support_rate"] for row in evidence_metrics]) if evidence_metrics else None,
            "unsupported_reference_count": sum(row["unsupported_reference_count"] for row in evidence_metrics),
        },
    }


def compare_variants(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_result = evaluate_suite(baseline)
    candidate_result = evaluate_suite(candidate)
    metrics = ["precision_at_5", "precision_at_10", "mean_reciprocal_rank", "evidence_support_rate"]
    deltas = {}
    for metric in metrics:
        before = baseline_result["aggregate"].get(metric)
        after = candidate_result["aggregate"].get(metric)
        deltas[metric] = None if before is None or after is None else after - before
    return {"baseline": baseline_result, "candidate": candidate_result, "delta": deltas}
