from __future__ import annotations

import json

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.jobs.registry import bootstrap_open_jobs_source
from app.jobs.source_capabilities import seed_source_capabilities


def main() -> None:
    settings = get_settings()
    with SessionLocal() as session:
        seed_source_capabilities(session)
        source = bootstrap_open_jobs_source(session, settings)
        session.commit()
        print(
            json.dumps(
                {
                    "source_id": str(source.id),
                    "source_identity": source.source_identity,
                    "source_type": source.source_type,
                    "enabled": source.enabled,
                    "crawl_allowed": source.crawl_allowed,
                    "next_run_at": source.next_run_at.isoformat() if source.next_run_at else None,
                    "interval_seconds": source.crawl_interval_seconds,
                    "authoritative_snapshot": (source.configuration or {}).get(
                        "authoritative_snapshot"
                    ),
                    "dataset_license": (source.configuration or {}).get("dataset_license"),
                    "dataset_role": (source.configuration or {}).get("dataset_role"),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
