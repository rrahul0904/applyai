from __future__ import annotations

import argparse
import json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.jobs.contracts import JobSourceType, SourceTrustLevel
from app.jobs.registry import upsert_source
from app.jobs.source_capabilities import seed_source_capabilities


def main() -> None:
    parser = argparse.ArgumentParser(description="Register official public job sources")
    parser.add_argument("--usajobs", action="store_true", help="Register the official USAJOBS Search API")
    parser.add_argument("--reliefweb", action="store_true", help="Register the official ReliefWeb jobs API")
    parser.add_argument("--all", action="store_true", help="Register every implemented public feed")
    args = parser.parse_args()

    if not (args.usajobs or args.reliefweb or args.all):
        parser.error("select --usajobs, --reliefweb or --all")

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
        session.commit()

    print(json.dumps({"registered": registered}, sort_keys=True))


if __name__ == "__main__":
    main()
