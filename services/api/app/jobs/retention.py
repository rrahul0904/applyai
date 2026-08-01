from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.models import RawJobPosting


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def purge_expired_raw_payloads(settings: Settings | None = None) -> int:
    """Delete old duplicate raw payloads while retaining the newest row per source.

    S3 archival is intentionally deferred until measured PostgreSQL growth justifies it.
    """
    settings = settings or get_settings()
    cutoff = utcnow() - timedelta(days=settings.raw_job_payload_retention_days)
    newest = (
        select(
            RawJobPosting.job_source_id,
            func.max(RawJobPosting.fetched_at).label("latest_fetched_at"),
        )
        .group_by(RawJobPosting.job_source_id)
        .subquery()
    )
    with SessionLocal() as session:
        expired_ids = list(
            session.scalars(
                select(RawJobPosting.id)
                .join(
                    newest,
                    newest.c.job_source_id == RawJobPosting.job_source_id,
                )
                .where(
                    RawJobPosting.fetched_at < cutoff,
                    RawJobPosting.fetched_at < newest.c.latest_fetched_at,
                )
                .limit(10_000)
            )
        )
        if expired_ids:
            session.execute(delete(RawJobPosting).where(RawJobPosting.id.in_(expired_ids)))
            session.commit()
        return len(expired_ids)


def main() -> None:
    print(json.dumps({"deleted": purge_expired_raw_payloads()}))


if __name__ == "__main__":
    main()
