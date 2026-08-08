from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.jobs.adaptive_schedule import recommended_interval_seconds, source_shard
from app.jobs.organization_universe import OrganizationRecord, validate_record


def benchmark(*, organizations: int, shards: int, output: Path) -> dict:
    organizations = max(1, int(organizations))
    shards = max(1, int(shards))

    started = time.perf_counter()
    validated = 0
    for index in range(organizations):
        record = OrganizationRecord(
            canonical_name=f"Synthetic Organization {index}",
            domain=f"org-{index}.example.test",
            organization_type=(
                "UNIVERSITY" if index % 11 == 0 else "NONPROFIT" if index % 7 == 0 else "COMPANY"
            ),
            country_code="US",
            state_region="MA" if index % 2 == 0 else "NY",
            priority=index % 101,
            dataset="SYNTHETIC_SCALE_BENCHMARK",
        )
        validate_record(record)
        validated += 1
    validation_seconds = time.perf_counter() - started

    started = time.perf_counter()
    distribution: Counter[int] = Counter()
    schedules: Counter[str] = Counter()
    for index in range(organizations):
        source_id = uuid.uuid5(uuid.NAMESPACE_URL, f"applyai-source-{index}")
        distribution[source_shard(source_id, shards)] += 1
        interval = recommended_interval_seconds(
            base_seconds=21_600,
            minimum_seconds=900,
            maximum_seconds=604_800,
            priority=index % 101,
            job_count=(index * 17) % 1500,
            change_count=(index * 13) % 80,
            consecutive_failures=1 if index % 113 == 0 else 0,
        )
        if interval <= 10_800:
            schedules["fast_1_to_3h"] += 1
        elif interval <= 43_200:
            schedules["normal_up_to_12h"] += 1
        elif interval <= 86_400:
            schedules["daily"] += 1
        else:
            schedules["backoff"] += 1
    scheduling_seconds = time.perf_counter() - started

    shard_values = list(distribution.values())
    report = {
        "evidence_class": "SYNTHETIC_SCALE_EVIDENCE",
        "organizations": organizations,
        "shards": shards,
        "validated": validated,
        "validation_seconds": round(validation_seconds, 6),
        "validation_records_per_second": round(validated / max(validation_seconds, 1e-9), 2),
        "scheduling_seconds": round(scheduling_seconds, 6),
        "sources_scheduled_per_second": round(organizations / max(scheduling_seconds, 1e-9), 2),
        "shard_distribution": {str(key): value for key, value in sorted(distribution.items())},
        "shard_min": min(shard_values) if shard_values else 0,
        "shard_max": max(shard_values) if shard_values else 0,
        "schedule_buckets": dict(schedules),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": os.getenv("GITHUB_SHA"),
        "source_ref": os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF"),
        "environment": "synthetic_cpu_only",
        "claims": {
            "database_ingestion": False,
            "external_provider": False,
            "production": False,
            "production_inventory": False,
            "live_source_coverage": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--organizations", type=int, default=50_000)
    parser.add_argument("--shards", type=int, default=32)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(benchmark(organizations=args.organizations, shards=args.shards, output=args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
