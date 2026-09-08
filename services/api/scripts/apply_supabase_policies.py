from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

from scripts.migrate_postgres_to_supabase import safe_git_sha
from scripts.validate_supabase_policies import repository_root, validate_policy_sql


def psycopg_dsn(value: str) -> str:
    url = make_url(value)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("Supabase policy target must be PostgreSQL")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate and transactionally apply ApplyAI Supabase RLS/Storage policies."
    )
    parser.add_argument("--database-url")
    parser.add_argument(
        "--policies",
        default=str(repository_root() / "supabase" / "policies.sql"),
    )
    parser.add_argument(
        "--report",
        default="artifacts/supabase-policy-application.json",
    )
    args = parser.parse_args()

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL or --database-url is required")

    policy_path = Path(args.policies)
    sql = policy_path.read_text()
    validation = validate_policy_sql(sql)
    report = {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "git_sha": safe_git_sha(),
        "policy_file": str(policy_path.name),
        "validation_status": validation["status"],
        "applied": False,
        "status": "BLOCKED",
        "failures": list(validation["failures"]),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if validation["status"] != "PASS":
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 2

    try:
        with psycopg.connect(psycopg_dsn(database_url)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            connection.commit()
        report["applied"] = True
        report["status"] = "PASS"
    except Exception as exc:
        report["failures"].append(
            {"code": type(exc).__name__, "message": str(exc)}
        )
        report["status"] = "ERROR"

    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
