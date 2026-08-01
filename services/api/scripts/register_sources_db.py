from __future__ import annotations

import json

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.job_source_models import JobSourceRegistry
from app.jobs.registry import sync_configured_sources


def main() -> None:
    settings = get_settings()
    with SessionLocal() as session:
        sync_configured_sources(session, settings)
        configured = list(
            session.scalars(
                select(JobSourceRegistry)
                .where(
                    JobSourceRegistry.source_type.in_(["GREENHOUSE", "LEVER", "ASHBY"]),
                    JobSourceRegistry.source_identity.in_(
                        [
                            *settings.greenhouse_board_tokens,
                            *settings.lever_site_names,
                            *settings.ashby_board_names,
                        ]
                    ),
                )
                .order_by(
                    JobSourceRegistry.source_type,
                    JobSourceRegistry.source_identity,
                )
            )
        )
    print(
        json.dumps(
            {
                "registered": [
                    {
                        "id": str(source.id),
                        "source_type": source.source_type,
                        "source_identity": source.source_identity,
                        "enabled": source.enabled,
                        "next_run_at": source.next_run_at.isoformat(),
                    }
                    for source in configured
                ]
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
