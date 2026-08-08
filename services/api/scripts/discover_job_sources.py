from __future__ import annotations

import argparse
import json
from urllib.parse import urlsplit

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.outbox import add_task_outbox_event
from app.core.queue import Task
from app.global_job_supply_models import OrganizationProfile
from app.job_source_models import JobSourceDiscovery
from app.jobs.discovery import request_key_for
from app.jobs.contracts import canonicalize_public_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue bounded ATS/career discovery for organization universe")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--min-priority", type=int, default=0)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()

    statuses = ["NEW", "DISCOVERED"]
    if args.retry_failed:
        statuses.append("FAILED")

    queued = 0
    reused = 0
    with SessionLocal() as session:
        profiles = list(
            session.scalars(
                select(OrganizationProfile)
                .where(
                    OrganizationProfile.source_status.in_(statuses),
                    OrganizationProfile.priority >= max(0, min(args.min_priority, 100)),
                )
                .order_by(OrganizationProfile.priority.desc(), OrganizationProfile.id)
                .limit(max(1, min(args.limit, 5000)))
            )
        )
        for profile in profiles:
            candidate = profile.careers_url or (
                f"https://{profile.canonical_domain}" if profile.canonical_domain else None
            )
            canonical = canonicalize_public_url(candidate)
            if not canonical:
                profile.source_status = "REQUIRES_REVIEW"
                continue
            request_key = request_key_for(None, canonical)
            discovery = session.scalar(
                select(JobSourceDiscovery).where(JobSourceDiscovery.request_key == request_key)
            )
            if discovery is None:
                discovery = JobSourceDiscovery(
                    company_id=profile.company_id,
                    request_key=request_key,
                    input_url=canonical,
                    input_domain=(urlsplit(canonical).hostname or "").casefold(),
                    status="QUEUED",
                    evidence=["organization-universe-discovery"],
                )
                session.add(discovery)
                session.flush()
            else:
                reused += 1
                if discovery.status in {"VERIFIED", "BLOCKED", "REJECTED"}:
                    profile.source_status = (
                        "VERIFIED" if discovery.status == "VERIFIED" else discovery.status
                    )
                    continue
                discovery.status = "QUEUED"

            add_task_outbox_event(
                session,
                task=Task(
                    task_type="SOURCE_DISCOVERY",
                    payload={"discovery_id": str(discovery.id)},
                    idempotency_key=f"organization-source-discovery:{discovery.id}:{discovery.attempt_count}",
                ),
                aggregate_type="JOB_SOURCE_DISCOVERY",
                aggregate_id=discovery.id,
            )
            profile.source_status = "DISCOVERING"
            queued += 1
        session.commit()

    print(json.dumps({"queued": queued, "reused": reused}, sort_keys=True))


if __name__ == "__main__":
    main()
