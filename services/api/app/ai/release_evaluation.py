from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import comb
import re
from statistics import mean
from typing import Any

RECEIPT_SCHEMA_VERSION = 1
PASS_THRESHOLD = 1 / 3
FAIL_THRESHOLD = -1 / 3
MIN_TRIGGER_PRECISION = 0.80
MIN_TRIGGER_RECALL = 0.80

CREDENTIAL_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}"),
)


def redact_for_receipt(value: Any) -> Any:
    """Redact credential-shaped free text before it crosses into an immutable receipt."""
    if isinstance(value, str):
        redacted = value
        for pattern in CREDENTIAL_PATTERNS:
            redacted = pattern.sub("[redacted]", redacted)
        return redacted
    if isinstance(value, list):
        return [redact_for_receipt(item) for item in value]
    if isinstance(value, tuple):
        return [redact_for_receipt(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): redact_for_receipt(item) for key, item in value.items()}
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def content_digest(value: Any) -> str:
    return f"sha256:{sha256(_canonical_json(value).encode('utf-8')).hexdigest()}"


def _run_key(run: Mapping[str, Any]) -> tuple[str, int]:
    return str(run.get("case") or "case"), int(run.get("rep") or 0)


def _mean_metric(runs: Sequence[Mapping[str, Any]], name: str) -> float | None:
    values = [float(run[name]) for run in runs if run.get(name) is not None]
    return mean(values) if values else None


def _metric_delta(before: float | None, after: float | None) -> float | None:
    return None if before is None or after is None else after - before


def _sign_test_p(wins: int, losses: int) -> float:
    """Exact two-sided sign-test p-value, ignoring ties."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = min(wins, losses)
    one_sided = sum(comb(n, k) for k in range(tail + 1)) / (2 ** n)
    return min(1.0, 2 * one_sided)


def trigger_metrics(counts: Mapping[str, int] | None) -> dict[str, float | int | None] | None:
    if counts is None:
        return None
    tp = int(counts.get("tp", 0))
    fn = int(counts.get("fn", 0))
    fp = int(counts.get("fp", 0))
    tn = int(counts.get("tn", 0))
    precision_denominator = tp + fp
    recall_denominator = tp + fn
    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "precision": tp / precision_denominator if precision_denominator else None,
        "recall": tp / recall_denominator if recall_denominator else None,
    }


def evaluate_release(
    *,
    subject_type: str,
    subject_name: str,
    subject_version: str,
    candidate_artifact: Any,
    dataset_version: str,
    baseline_runs: Sequence[Mapping[str, Any]],
    candidate_runs: Sequence[Mapping[str, Any]],
    trigger_counts: Mapping[str, int] | None = None,
    provenance: Mapping[str, Any] | None = None,
    pass_threshold: float = PASS_THRESHOLD,
    fail_threshold: float = FAIL_THRESHOLD,
    minimum_trigger_precision: float = MIN_TRIGGER_PRECISION,
    minimum_trigger_recall: float = MIN_TRIGGER_RECALL,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    if fail_threshold >= pass_threshold:
        raise ValueError("fail_threshold must be lower than pass_threshold")

    baseline_by_key = {_run_key(run): run for run in baseline_runs}
    candidate_by_key = {_run_key(run): run for run in candidate_runs}
    keys = sorted(set(baseline_by_key) | set(candidate_by_key))

    per_case: list[dict[str, Any]] = []
    wins = losses = ties = scored = 0
    for case, rep in keys:
        baseline = baseline_by_key.get((case, rep))
        candidate = candidate_by_key.get((case, rep))
        baseline_passed = baseline.get("passed") if baseline is not None else None
        candidate_passed = candidate.get("passed") if candidate is not None else None
        outcome: str | None = None
        if isinstance(baseline_passed, bool) and isinstance(candidate_passed, bool):
            scored += 1
            if candidate_passed and not baseline_passed:
                wins += 1
                outcome = "win"
            elif baseline_passed and not candidate_passed:
                losses += 1
                outcome = "loss"
            else:
                ties += 1
                outcome = "tie"
        per_case.append(
            {
                "case": case,
                "rep": rep,
                "baseline_passed": baseline_passed if isinstance(baseline_passed, bool) else None,
                "candidate_passed": candidate_passed if isinstance(candidate_passed, bool) else None,
                "outcome": outcome,
                "baseline_checks": redact_for_receipt(list((baseline or {}).get("checks") or [])),
                "candidate_checks": redact_for_receipt(list((candidate or {}).get("checks") or [])),
            }
        )

    expected = len(keys)
    net_lift = (wins - losses) / scored if scored else 0.0
    if net_lift >= pass_threshold:
        verdict = "PASS"
    elif net_lift <= fail_threshold:
        verdict = "FAIL"
    else:
        verdict = "NEUTRAL"

    triggers = trigger_metrics(trigger_counts)
    gate_reasons: list[str] = []
    if expected == 0:
        gate_reasons.append("No comparable evaluation rows were supplied.")
    if scored < expected:
        gate_reasons.append(f"Only {scored} of {expected} evaluation rows were scored.")
    if verdict == "FAIL":
        gate_reasons.append(f"Net lift {net_lift:.3f} crossed the regression threshold {fail_threshold:.3f}.")
    if triggers is not None:
        precision = triggers["precision"]
        recall = triggers["recall"]
        if precision is not None and precision < minimum_trigger_precision:
            gate_reasons.append(
                f"Trigger precision {precision:.3f} is below {minimum_trigger_precision:.3f}."
            )
        if recall is not None and recall < minimum_trigger_recall:
            gate_reasons.append(
                f"Trigger recall {recall:.3f} is below {minimum_trigger_recall:.3f}."
            )

    execution_status = "complete" if expected > 0 and scored == expected else "partial"
    release_gate = "PASS" if not gate_reasons else "BLOCK"

    baseline_efficiency = {
        "turns": _mean_metric(baseline_runs, "turns"),
        "duration_ms": _mean_metric(baseline_runs, "duration_ms"),
        "cost_usd": _mean_metric(baseline_runs, "cost_usd"),
    }
    candidate_efficiency = {
        "turns": _mean_metric(candidate_runs, "turns"),
        "duration_ms": _mean_metric(candidate_runs, "duration_ms"),
        "cost_usd": _mean_metric(candidate_runs, "cost_usd"),
    }
    efficiency_delta = {
        key: _metric_delta(baseline_efficiency[key], candidate_efficiency[key])
        for key in baseline_efficiency
    }

    timestamp = evaluated_at or datetime.now(timezone.utc).isoformat()
    normalized_provenance = {
        "engine": "applyai-release-evaluation",
        "engine_schema_version": RECEIPT_SCHEMA_VERSION,
        "dataset_version": dataset_version,
        **redact_for_receipt(dict(provenance or {})),
        "evaluated_at": timestamp,
    }
    receipt = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "subject": {
            "type": subject_type.upper(),
            "name": subject_name,
            "version": subject_version,
            "content_digest": content_digest(candidate_artifact),
        },
        "dataset_version": dataset_version,
        "verdict": verdict,
        "release_gate": release_gate,
        "gate_reasons": gate_reasons,
        "execution_status": execution_status,
        "expected_rows": expected,
        "scored_rows": scored,
        "comparison": {
            "win": wins,
            "loss": losses,
            "tie": ties,
            "net_lift": net_lift,
            "sign_p": _sign_test_p(wins, losses),
            "pass_threshold": pass_threshold,
            "fail_threshold": fail_threshold,
        },
        "triggers": triggers,
        "trigger_thresholds": {
            "minimum_precision": minimum_trigger_precision,
            "minimum_recall": minimum_trigger_recall,
        },
        "efficiency": {
            "baseline": baseline_efficiency,
            "candidate": candidate_efficiency,
            "delta": efficiency_delta,
        },
        "per_case": per_case,
        "provenance": normalized_provenance,
    }
    receipt["receipt_digest"] = content_digest(receipt)
    return receipt
