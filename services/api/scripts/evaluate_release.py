from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.ai.release_evaluation import evaluate_release


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate baseline/candidate evidence and fail closed when the ApplyAI release gate blocks."
    )
    parser.add_argument("spec", type=Path, help="JSON evaluation specification")
    parser.add_argument("--receipt-out", type=Path, help="Optional path for the immutable JSON receipt")
    args = parser.parse_args()

    payload = json.loads(args.spec.read_text(encoding="utf-8"))
    receipt = evaluate_release(
        subject_type=payload["subject_type"],
        subject_name=payload["subject_name"],
        subject_version=payload["subject_version"],
        candidate_artifact=payload["candidate_artifact"],
        dataset_version=payload["dataset_version"],
        baseline_runs=payload["baseline_runs"],
        candidate_runs=payload["candidate_runs"],
        trigger_counts=payload.get("triggers"),
        provenance=payload.get("provenance"),
        pass_threshold=float(payload.get("pass_threshold", 1 / 3)),
        fail_threshold=float(payload.get("fail_threshold", -1 / 3)),
        minimum_trigger_precision=float(payload.get("minimum_trigger_precision", 0.80)),
        minimum_trigger_recall=float(payload.get("minimum_trigger_recall", 0.80)),
        evaluated_at=payload.get("evaluated_at"),
    )

    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    print(rendered)
    if args.receipt_out:
        args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_out.write_text(rendered + "\n", encoding="utf-8")
    return 0 if receipt["release_gate"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
