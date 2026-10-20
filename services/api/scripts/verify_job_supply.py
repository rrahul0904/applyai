"""Fail a scheduled release check when its verified external job supply is stale.

This is intentionally small and read-only so it can run from GitHub Actions against
the production database after a bounded source refresh.  It reports counts and
timestamps only; it never prints credentials or candidate data.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.database import SessionLocal
from app.job_source_models import JobSourceRegistry
from app.durability_models import JobIngestionRun
from app.models import Job


def verified_source_run(source, run, *, external_active_jobs: int, now: datetime,
                        minimum_jobs: int, maximum_source_age_hours: int) -> bool:
    """Fail closed unless *this* source has a recent completed run with usable records.

    Aggregate job counts alone must never certify an unrelated registered source.
    """
    if source is None or run is None:
        return False
    cutoff = now - timedelta(hours=maximum_source_age_hours)
    last_success_at = source.last_success_at
    completed_at = run.completed_at
    if (
        last_success_at is None
        or completed_at is None
        or last_success_at.tzinfo is None
        or completed_at.tzinfo is None
    ):
        return False
    return bool(
        source.enabled
        and source.crawl_allowed
        and source.health_status == "HEALTHY"
        and source.source_type != "DEVELOPMENT_SEED"
        and run.source_id == source.id
        and run.status == "COMPLETED"
        and run.failed == 0
        and run.fetched >= minimum_jobs
        and run.valid >= minimum_jobs
        and source.last_job_count >= minimum_jobs
        and int(external_active_jobs) >= minimum_jobs
        and last_success_at >= cutoff
        and completed_at >= cutoff
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify fresh externally sourced ApplyAI jobs")
    parser.add_argument("--source-identity", required=True)
    parser.add_argument("--minimum-active-jobs", type=int, default=1)
    parser.add_argument("--maximum-source-age-hours", type=int, default=30)
    args = parser.parse_args()

    if args.minimum_active_jobs < 1 or args.maximum_source_age_hours < 1:
        parser.error("minimum jobs and maximum source age must both be positive")

    with SessionLocal() as session:
        source = session.scalar(
            select(JobSourceRegistry).where(
                JobSourceRegistry.source_identity == args.source_identity
            )
        )
        latest_run = (
            session.scalar(
                select(JobIngestionRun)
                .where(JobIngestionRun.source_id == source.id)
                .order_by(JobIngestionRun.started_at.desc())
                .limit(1)
            )
            if source is not None
            else None
        )
        external_active_jobs = session.scalar(
            select(func.count(Job.id)).where(
                Job.status == "ACTIVE",
                Job.data_origin.notin_(("DEVELOPMENT_SEED", "DEVELOPMENT_DATA")),
            )
        )

    if source is None:
        raise SystemExit(f"No registry source exists for {args.source_identity!r}")

    now = datetime.now(UTC)
    last_success_at = source.last_success_at
    healthy = verified_source_run(
        source,
        latest_run,
        external_active_jobs=int(external_active_jobs or 0),
        now=now,
        minimum_jobs=args.minimum_active_jobs,
        maximum_source_age_hours=args.maximum_source_age_hours,
    )
    summary = {
        "source_identity": source.source_identity,
        "source_enabled": source.enabled,
        "source_health_status": source.health_status,
        "source_last_success_at": last_success_at.isoformat() if last_success_at else None,
        "source_last_job_count": source.last_job_count,
        "last_run_id": str(latest_run.id) if latest_run is not None else None,
        "last_run_status": latest_run.status if latest_run is not None else None,
        "last_run_completed_at": (
            latest_run.completed_at.isoformat()
            if latest_run is not None and latest_run.completed_at is not None
            else None
        ),
        "last_run_valid": latest_run.valid if latest_run is not None else 0,
        "last_run_failed": latest_run.failed if latest_run is not None else 0,
        "external_active_jobs": int(external_active_jobs or 0),
        "maximum_source_age_hours": args.maximum_source_age_hours,
    }
    print(json.dumps(summary, sort_keys=True))
    if not healthy:
        raise SystemExit("Verified external job supply is unavailable, unhealthy, or stale")


if __name__ == "__main__":
    main()
