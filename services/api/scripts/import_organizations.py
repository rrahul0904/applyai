from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.jobs.organization_datasets import DATASETS, load_dataset_records
from app.jobs.organization_universe import (
    import_organizations,
    load_organization_records,
    validate_record,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import organizations into the ApplyAI company universe"
    )
    parser.add_argument(
        "--file",
        required=True,
        help="CSV, JSON or JSONL organization dataset",
    )
    parser.add_argument(
        "--dataset",
        help="Dataset/provenance label stored with generic organization imports",
    )
    parser.add_argument(
        "--dataset-type",
        choices=["generic", *sorted(DATASETS)],
        default="generic",
        help=(
            "Use an authoritative dataset parser for SEC, IPEDS, CMS, IRS or government inputs; "
            "generic preserves the existing normalized importer."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the input without writing to PostgreSQL",
    )
    args = parser.parse_args()

    if args.dataset_type == "generic":
        records = load_organization_records(args.file, dataset=args.dataset)
    else:
        records = load_dataset_records(args.file, dataset_type=args.dataset_type)

    valid = 0
    failed = 0
    for record in records:
        try:
            validate_record(record)
            valid += 1
        except ValueError:
            failed += 1

    if args.dry_run:
        print(
            json.dumps(
                {
                    "records_loaded": len(records),
                    "valid": valid,
                    "failed": failed,
                    "dataset_type": args.dataset_type,
                    "dry_run": True,
                },
                sort_keys=True,
            )
        )
        if failed:
            raise SystemExit(2)
        return

    with SessionLocal() as session:
        counts = import_organizations(session, records)
    print(
        json.dumps(
            {
                "records_loaded": len(records),
                "dataset_type": args.dataset_type,
                **counts,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
