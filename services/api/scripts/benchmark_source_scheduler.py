from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, func, insert, select

from app.core.config import Settings
from app.core.database import SessionLocal
from app.job_source_models import JobSourceRegistry
from app.jobs.registry import claim_due_source_ids


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _insert_sources(count: int) -> float:
    started = time.perf_counter()
    now = utcnow() - timedelta(minutes=5)
    chunk_size = 5_000
    with SessionLocal() as session:
        session.execute(delete(JobSourceRegistry))
        session.commit()
        for start in range(0, count, chunk_size):
            values = []
            for index in range(start, min(start + chunk_size, count)):
                values.append(
                    {
                        "id": uuid.uuid5(uuid.NAMESPACE_URL, f"applyai-scheduler-source-{index}"),
                        "source_type": "GREENHOUSE",
                        "source_name": f"Synthetic scheduler source {index}",
                        "source_identity": f"synthetic-scheduler-{index}",
                        "base_url": f"https://example.test/boards/{index}",
                        "configuration": {"synthetic_scale_evidence": True},
                        "trust_level": "OFFICIAL_ATS",
                        "priority": index % 101,
                        "enabled": True,
                        "crawl_allowed": True,
                        "last_job_count": index % 500,
                        "last_change_count": index % 20,
                        "health_status": "HEALTHY",
                        "consecutive_failures": 0,
                        "crawl_interval_seconds": 21_600,
                        "min_interval_seconds": 900,
                        "max_interval_seconds": 604_800,
                        "next_run_at": now,
                    }
                )
            session.execute(insert(JobSourceRegistry), values)
            session.commit()
    return time.perf_counter() - started


def _claim_all(count: int) -> dict:
    settings = Settings(
        job_source_claim_batch_size=100,
        job_source_lease_seconds=900,
    )
    claimed: list[uuid.UUID] = []
    batch_latencies: list[float] = []
    started = time.perf_counter()
    worker_index = 0
    with SessionLocal() as session:
        while len(claimed) < count:
            batch_started = time.perf_counter()
            batch = claim_due_source_ids(
                session,
                settings=settings,
                worker_id=f"benchmark-worker-{worker_index}",
            )
            batch_latencies.append(time.perf_counter() - batch_started)
            if not batch:
                break
            claimed.extend(batch)
            worker_index += 1

        duplicate_claims = len(claimed) - len(set(claimed))
        locked_count = int(
            session.scalar(
                select(func.count(JobSourceRegistry.id)).where(
                    JobSourceRegistry.locked_by.is_not(None),
                    JobSourceRegistry.lease_expires_at.is_not(None),
                )
            )
            or 0
        )
        # A second worker must not be able to reclaim an already leased row.
        conflict_probe = claim_due_source_ids(
            session,
            settings=settings,
            worker_id="benchmark-conflict-probe",
        )
    elapsed = time.perf_counter() - started
    sorted_latency = sorted(batch_latencies)
    p95_index = max(0, min(len(sorted_latency) - 1, int(len(sorted_latency) * 0.95))) if sorted_latency else 0
    return {
        "claim_seconds": round(elapsed, 6),
        "claimed": len(claimed),
        "unique_claimed": len(set(claimed)),
        "duplicate_claims": duplicate_claims,
        "locked_count": locked_count,
        "unexpected_second_worker_claims": len(conflict_probe),
        "claim_batches": len(batch_latencies),
        "first_batch_ms": round(batch_latencies[0] * 1000, 3) if batch_latencies else None,
        "batch_p95_ms": round(sorted_latency[p95_index] * 1000, 3) if sorted_latency else None,
        "claims_per_second": round(len(claimed) / max(elapsed, 1e-9), 2),
    }


def benchmark(*, sources: int, output: Path, cleanup: bool) -> dict:
    sources = max(1, int(sources))
    insert_seconds = _insert_sources(sources)
    claim = _claim_all(sources)
    report = {
        "evidence_class": "SYNTHETIC_SCALE_EVIDENCE",
        "sources": sources,
        "insert_seconds": round(insert_seconds, 6),
        "insert_sources_per_second": round(sources / max(insert_seconds, 1e-9), 2),
        **claim,
        "generated_at": utcnow().isoformat(),
        "source_commit": os.getenv("GITHUB_SHA"),
        "source_ref": os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF"),
        "claims": {
            "external_provider_requests": False,
            "production_inventory": False,
            "live_source_coverage": False,
            "postgresql_scheduler_execution": True,
        },
    }
    if claim["claimed"] != sources:
        raise RuntimeError(f"Scheduler claimed {claim['claimed']} of {sources} due sources")
    if claim["duplicate_claims"] != 0:
        raise RuntimeError("Scheduler produced duplicate source leases")
    if claim["unexpected_second_worker_claims"] != 0:
        raise RuntimeError("Second worker claimed rows after all due sources were leased")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if cleanup:
        with SessionLocal() as session:
            session.execute(delete(JobSourceRegistry))
            session.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            benchmark(sources=args.sources, output=args.output, cleanup=args.cleanup),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
