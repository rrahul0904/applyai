from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.jobs.dedup_review import build_dedup_candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="Build borderline cross-source job dedup candidates")
    parser.add_argument("--limit-jobs", type=int, default=5000)
    parser.add_argument("--minimum-similarity", type=float, default=0.85)
    parser.add_argument("--automatic-merge-threshold", type=float, default=0.94)
    args = parser.parse_args()
    if not (0 < args.minimum_similarity < args.automatic_merge_threshold <= 1):
        parser.error("similarity thresholds must satisfy 0 < minimum < automatic <= 1")
    with SessionLocal() as session:
        counts = build_dedup_candidates(
            session,
            limit_jobs=args.limit_jobs,
            minimum_similarity=args.minimum_similarity,
            automatic_merge_threshold=args.automatic_merge_threshold,
        )
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
