from __future__ import annotations

import argparse
import json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.jobs.contracts import JobSourceType, SourceTrustLevel
from app.jobs.registry import upsert_source
from app.jobs.source_capabilities import seed_source_capabilities


def main() -> None:
    parser = argparse.ArgumentParser(description="Register official/public job sources")
    parser.add_argument("--usajobs", action="store_true", help="Register the official USAJOBS Search API")
    parser.add_argument("--reliefweb", action="store_true", help="Register the official ReliefWeb jobs API")
    parser.add_argument(
        "--open-jobs",
        action="store_true",
        help="Register the public CC0 Open Jobs discovery corpus",
    )
    parser.add_argument("--all", action="store_true", help="Register every implemented public feed")
    args = parser.parse_args()

    if not (args.usajobs or args.reliefweb or args.open_jobs or args.all):
        parser.error("select --usajobs, --reliefweb, --open-jobs or --all")

    settings = get_settings()
    registered: list[str] = []
    with SessionLocal() as session:
        seed_source_capabilities(session)
        interval = settings.job_source_default_interval_seconds
        if args.usajobs or args.all:
            upsert_source(
                session,
                source_type=JobSourceType.USAJOBS,
                source_name="USAJOBS official Search API",
                source_identity="us-federal-government",
                base_url="https://data.usajobs.gov/api/search",
                configuration={
                    "api_key_env": "USAJOBS_API_KEY",
                    "user_agent_env": "USAJOBS_USER_AGENT",
                    "results_per_page": 500,
                    "max_pages": 20,
                },
                interval_seconds=interval,
                trust_level=SourceTrustLevel.GOVERNMENT_OFFICIAL,
            )
            registered.append("USAJOBS")
        if args.reliefweb or args.all:
            upsert_source(
                session,
                source_type=JobSourceType.RELIEFWEB,
                source_name="ReliefWeb official jobs API",
                source_identity="reliefweb",
                base_url="https://api.reliefweb.int/v2/jobs",
                configuration={
                    "appname_env": "RELIEFWEB_APPNAME",
                    "page_size": 1000,
                    "max_pages": 20,
                },
                interval_seconds=max(interval, 21_600),
                trust_level=SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED,
            )
            registered.append("RELIEFWEB")
        if args.open_jobs or args.all:
            upsert_source(
                session,
                source_type=JobSourceType.AUTHORIZED_AGGREGATOR_FEED,
                source_name="Open Jobs CC0 public corpus",
                source_identity="open-jobs",
                base_url="https://backend.dehnbostele.workers.dev/data",
                configuration={
                    "provider_key": "OPEN_JOBS",
                    "data_base_url": "https://backend.dehnbostele.workers.dev/data",
                    "max_groups_per_run": 25,
                    "max_jobs_per_group": 1000,
                    "timeout_seconds": 30,
                    "authoritative_snapshot": False,
                    "dataset_license": "CC0-1.0",
                    "dataset_role": "DISCOVERY_COVERAGE",
                },
                # A bounded slice is processed on each run. Fifteen-minute cadence lets an
                # initial corpus sweep progress without turning one source task into a multi-GB job.
                interval_seconds=max(900, settings.job_source_min_interval_seconds),
                trust_level=SourceTrustLevel.AUTHORIZED_AGGREGATOR_FEED,
            )
            registered.append("OPEN_JOBS")
        session.commit()

    print(json.dumps({"registered": registered}, sort_keys=True))


if __name__ == "__main__":
    main()
