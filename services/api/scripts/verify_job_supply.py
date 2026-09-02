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
from app.models import Job


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
        external_active_jobs = session.scalar(
            select(func.count(Job.id)).where(
                Job.status == "ACTIVE",
                Job.data_origin != "DEVELOPMENT_SEED",
            )
        )

    if source is None:
        raise SystemExit(f"No registry source exists for {args.source_identity!r}")

    now = datetime.now(UTC)
    last_success_at = source.last_success_at
    age_is_acceptable = (
        last_success_at is not None
        and last_success_at >= now - timedelta(hours=args.maximum_source_age_hours)
    )
    healthy = (
        source.enabled
        and source.crawl_allowed
        and source.health_status == "HEALTHY"
        and age_is_acceptable
        and int(source.last_job_count) >= args.minimum_active_jobs
        and int(external_active_jobs or 0) >= args.minimum_active_jobs
    )
    summary = {
        "source_identity": source.source_identity,
        "source_enabled": source.enabled,
        "source_health_status": source.health_status,
        "source_last_success_at": last_success_at.isoformat() if last_success_at else None,
        "source_last_job_count": source.last_job_count,
        "external_active_jobs": int(external_active_jobs or 0),
        "maximum_source_age_hours": args.maximum_source_age_hours,
    }
    print(json.dumps(summary, sort_keys=True))
    if not healthy:
        raise SystemExit("Verified external job supply is unavailable, unhealthy, or stale")


if __name__ == "__main__":
    main()
