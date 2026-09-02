from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import select


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.jobs.dispatcher import dispatch_due_sources, dispatch_due_verifications
from app.jobs.registry import run_due_sources, run_registered_source
from app.job_source_models import JobSourceRegistry
from app.core.database import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch or synchronously run due ApplyAI job sources")
    parser.add_argument(
        "--mode",
        choices=("dispatch", "synchronous"),
        default="dispatch",
        help="dispatch uses the transactional outbox/SQS path; synchronous is for bounded local operations",
    )
    parser.add_argument(
        "--source-identity",
        help="Run one enabled registry source directly by its stable identity",
    )
    args = parser.parse_args()

    if args.source_identity:
        with SessionLocal() as session:
            source_id = session.scalar(
                select(JobSourceRegistry.id).where(
                    JobSourceRegistry.source_identity == args.source_identity,
                    JobSourceRegistry.enabled.is_(True),
                    JobSourceRegistry.crawl_allowed.is_(True),
                )
            )
        if source_id is None:
            parser.error(f"no enabled source found for identity {args.source_identity!r}")
        print(json.dumps({str(source_id): run_registered_source(source_id)}, sort_keys=True))
        return

    if args.mode == "synchronous":
        print(json.dumps(run_due_sources(), sort_keys=True))
        return

    sources = dispatch_due_sources()
    verifications = dispatch_due_verifications()
    print(
        json.dumps(
            {
                "source_ingest_dispatched": [str(value) for value in sources],
                "source_verify_dispatched": [str(value) for value in verifications],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
