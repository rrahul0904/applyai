from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.jobs.dispatcher import dispatch_due_sources, dispatch_due_verifications
from app.jobs.registry import run_due_sources


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch or synchronously run due ApplyAI job sources")
    parser.add_argument(
        "--mode",
        choices=("dispatch", "synchronous"),
        default="dispatch",
        help="dispatch uses the transactional outbox/SQS path; synchronous is for bounded local operations",
    )
    args = parser.parse_args()

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
