from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.database import SessionLocal
from app.jobs.demo import write_demo_artifact


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
