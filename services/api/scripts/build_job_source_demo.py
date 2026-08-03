from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.jobs.demo import write_demo_artifact  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the deterministic ApplyAI multi-source job-platform demo."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../../artifacts/job-source-platform-demo"),
        help="Directory for index.html and report.json.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output.resolve()
    with SessionLocal() as session:
        report = write_demo_artifact(session, output_dir)
    print(
        json.dumps(
            {
                "output": str(output_dir),
                "totals": report["totals"],
                "assertions": report["assertions"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
