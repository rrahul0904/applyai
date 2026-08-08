from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.jobs.organization_universe import import_organizations, load_organization_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Import organizations into the ApplyAI company universe")
    parser.add_argument("--file", required=True, help="CSV, JSON or JSONL organization dataset")
    parser.add_argument("--dataset", help="Dataset/provenance label stored with imported organizations")
    parser.add_argument("--dry-run", action="store_true", help="Validate the input without writing to PostgreSQL")
    args = parser.parse_args()

    records = load_organization_records(args.file, dataset=args.dataset)
    if args.dry_run:
        # Validation occurs during load/upsert; print a deterministic preview without mutating DB.
        print(json.dumps({"records_loaded": len(records), "dry_run": True}, sort_keys=True))
        return

    with SessionLocal() as session:
        counts = import_organizations(session, records)
    print(json.dumps({"records_loaded": len(records), **counts}, sort_keys=True))


if __name__ == "__main__":
    main()
