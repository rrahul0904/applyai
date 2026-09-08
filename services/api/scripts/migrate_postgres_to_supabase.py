from __future__ import annotations

import argparse
import json
import os
import subprocess
import uuid
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, and_, create_engine, func, inspect, select
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.sql.schema import Table

EXCLUDED_TABLES = {
    "alembic_version": "schema_version_managed_by_alembic",
    "roles": "canonical_roles_seeded_by_migration",
}
ACTIVE_WORK_TABLES = {
    "postgres_tasks",
    "task_outbox",
    "job_ingestion_runs",
    "job_source_registry",
}


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_postgres_url(value: str) -> str:
    url = make_url(value)
    if url.drivername == "postgres":
        url = url.set(drivername="postgresql+psycopg")
    elif url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url.render_as_string(hide_password=False)


def safe_git_sha() -> str:
    explicit = os.getenv("GITHUB_SHA") or os.getenv("APPLYAI_RELEASE_SHA")
    if explicit:
        return explicit
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            .strip()
        )
    except Exception:
        return "unknown"


def reflected_public_metadata(engine: Engine) -> MetaData:
    metadata = MetaData()
    metadata.reflect(bind=engine, schema="public")
    return metadata


def table_by_name(metadata: MetaData, name: str) -> Table | None:
    return metadata.tables.get(f"public.{name}") or metadata.tables.get(name)


def public_table_names(metadata: MetaData) -> set[str]:
    return {
        table.name
        for table in metadata.tables.values()
        if table.schema in {None, "public"}
    }


def ordered_migration_tables(source: MetaData, target: MetaData) -> list[str]:
    source_names = public_table_names(source)
    target_names = public_table_names(target)
    shared = source_names & target_names
    ordered = [
        table.name
        for table in target.sorted_tables
        if table.name in shared and table.name not in EXCLUDED_TABLES
    ]
    # SQLAlchemy may omit cyclic tables from deterministic sorting. Append any remaining
    # shared tables so the report exposes them; execution will still fail on an FK violation.
    ordered_set = set(ordered)
    ordered.extend(sorted(shared - ordered_set - set(EXCLUDED_TABLES)))
    return ordered


def row_count(connection: Connection, table: Table) -> int:
    return int(connection.scalar(select(func.count()).select_from(table)) or 0)


def load_identity_map(path: Path | None) -> dict[str, uuid.UUID]:
    if path is None:
        return {}
    raw = json.loads(path.read_text())
    result: dict[str, uuid.UUID] = {}

    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Identity map list entries must be objects")
            email = item.get("email")
            auth_user_id = item.get("supabase_auth_user_id") or item.get("auth_user_id")
            items.append((email, auth_user_id))
    else:
        raise ValueError("Identity map must be a JSON object or array")

    for email, auth_user_id in items:
        normalized_email = str(email or "").strip().lower()
        if "@" not in normalized_email or not auth_user_id:
            raise ValueError("Identity map entries require email and Supabase auth UUID")
        if normalized_email in result:
            raise ValueError(f"Duplicate identity-map email: {normalized_email}")
        result[normalized_email] = uuid.UUID(str(auth_user_id))
    return result


def normalize_migrated_row(
    table_name: str,
    row: Mapping[str, Any],
    *,
    identity_map: Mapping[str, uuid.UUID],
    now: datetime,
) -> tuple[dict[str, Any], list[str]]:
    result = dict(row)
    transformations: list[str] = []

    if table_name == "users":
        email = str(result.get("email") or "").strip().lower()
        mapped = identity_map.get(email)
        if mapped is not None:
            existing = result.get("auth_user_id")
            if existing is not None and uuid.UUID(str(existing)) != mapped:
                raise ValueError(f"Identity map conflicts with existing auth_user_id for {email}")
            result["auth_user_id"] = mapped
            result["auth_provider"] = "supabase"
            transformations.append("linked_supabase_identity")

    if table_name == "postgres_tasks" and result.get("status") == "RUNNING":
        result["status"] = "RETRY_WAIT"
        result["available_at"] = now
        result["lease_owner"] = None
        result["leased_at"] = None
        result["lease_expires_at"] = None
        previous = str(result.get("last_error") or "").strip()
        result["last_error"] = (
            f"{previous};MIGRATION_LEASE_RESET" if previous else "MIGRATION_LEASE_RESET"
        )
        transformations.append("reset_expired_task_lease")

    if table_name == "job_source_registry" and result.get("lease_expires_at") is not None:
        lease_expires_at = result["lease_expires_at"]
        if lease_expires_at <= now:
            result["locked_at"] = None
            result["locked_by"] = None
            result["lease_expires_at"] = None
            transformations.append("clear_expired_source_lease")

    return result, transformations


def duplicate_user_emails(connection: Connection, users: Table | None) -> list[dict[str, Any]]:
    if users is None or "email" not in users.c:
        return []
    rows = connection.execute(
        select(
            func.lower(users.c.email).label("email"),
            func.count().label("count"),
        )
        .group_by(func.lower(users.c.email))
        .having(func.count() > 1)
        .order_by(func.lower(users.c.email))
    )
    return [{"email": row.email, "count": int(row.count)} for row in rows]


def active_work_counts(connection: Connection, metadata: MetaData, *, now: datetime) -> dict[str, int]:
    result: dict[str, int] = {}

    tasks = table_by_name(metadata, "postgres_tasks")
    if tasks is not None:
        result["postgres_tasks_running"] = int(
            connection.scalar(
                select(func.count())
                .select_from(tasks)
                .where(
                    tasks.c.status == "RUNNING",
                    tasks.c.lease_expires_at.is_not(None),
                    tasks.c.lease_expires_at > now,
                )
            )
            or 0
        )

    outbox = table_by_name(metadata, "task_outbox")
    if outbox is not None:
        result["task_outbox_claimed"] = int(
            connection.scalar(
                select(func.count()).select_from(outbox).where(outbox.c.status == "CLAIMED")
            )
            or 0
        )

    ingestion = table_by_name(metadata, "job_ingestion_runs")
    if ingestion is not None:
        result["job_ingestion_runs_running"] = int(
            connection.scalar(
                select(func.count()).select_from(ingestion).where(ingestion.c.status == "RUNNING")
            )
            or 0
        )

    sources = table_by_name(metadata, "job_source_registry")
    if sources is not None:
        result["job_source_registry_live_leases"] = int(
            connection.scalar(
                select(func.count())
                .select_from(sources)
                .where(
                    sources.c.locked_by.is_not(None),
                    sources.c.lease_expires_at.is_not(None),
                    sources.c.lease_expires_at > now,
                )
            )
            or 0
        )

    return result


def target_nonempty_tables(
    connection: Connection,
    metadata: MetaData,
    table_names: Iterable[str],
) -> dict[str, int]:
    result: dict[str, int] = {}
    for name in table_names:
        table = table_by_name(metadata, name)
        if table is None:
            continue
        count = row_count(connection, table)
        if count:
            result[name] = count
    return result


def orphan_counts(connection: Connection, metadata: MetaData, table_names: Iterable[str]) -> dict[str, int]:
    inspector = inspect(connection)
    available = set(table_names)
    result: dict[str, int] = {}

    for child_name in sorted(available):
        child = table_by_name(metadata, child_name)
        if child is None:
            continue
        for fk in inspector.get_foreign_keys(child_name, schema="public"):
            parent_name = fk.get("referred_table")
            constrained = fk.get("constrained_columns") or []
            referred = fk.get("referred_columns") or []
            if not parent_name or parent_name not in available:
                continue
            if len(constrained) != 1 or len(referred) != 1:
                # Composite FK coverage can be added if ApplyAI introduces one; report rather
                # than silently claim verification.
                result[f"{child_name}:{fk.get('name') or 'composite'}"] = -1
                continue
            parent = table_by_name(metadata, parent_name)
            if parent is None:
                continue
            child_col = child.c[constrained[0]]
            parent_col = parent.c[referred[0]]
            count = int(
                connection.scalar(
                    select(func.count())
                    .select_from(child.outerjoin(parent, child_col == parent_col))
                    .where(child_col.is_not(None), parent_col.is_(None))
                )
                or 0
            )
            result[f"{child_name}.{constrained[0]}->{parent_name}.{referred[0]}"] = count
    return result


def copy_table(
    source_connection: Connection,
    target_connection: Connection,
    source_table: Table,
    target_table: Table,
    *,
    identity_map: Mapping[str, uuid.UUID],
    batch_size: int,
    now: datetime,
) -> tuple[int, dict[str, int]]:
    source_columns = {column.name for column in source_table.columns}
    target_columns = {column.name for column in target_table.columns}
    missing_target_columns = sorted(source_columns - target_columns)
    if missing_target_columns:
        raise RuntimeError(
            f"Target table {target_table.name} is missing source columns: "
            + ", ".join(missing_target_columns)
        )

    transferable_columns = [column.name for column in source_table.columns if column.name in target_columns]
    order_columns = list(source_table.primary_key.columns)
    statement = select(source_table)
    if order_columns:
        statement = statement.order_by(*order_columns)

    copied = 0
    transformations: dict[str, int] = {}
    result = source_connection.execution_options(stream_results=True).execute(statement)
    while True:
        rows = result.mappings().fetchmany(batch_size)
        if not rows:
            break
        payload: list[dict[str, Any]] = []
        for row in rows:
            normalized, applied = normalize_migrated_row(
                source_table.name,
                row,
                identity_map=identity_map,
                now=now,
            )
            payload.append({name: normalized.get(name) for name in transferable_columns})
            for transformation in applied:
                transformations[transformation] = transformations.get(transformation, 0) + 1
        target_connection.execute(target_table.insert(), payload)
        copied += len(payload)
    return copied, transformations


def query_alembic_heads(connection: Connection, metadata: MetaData) -> list[str]:
    table = table_by_name(metadata, "alembic_version")
    if table is None:
        # Alembic tables do not always reflect with the public schema prefix.
        rows = connection.exec_driver_sql(
            "select version_num from public.alembic_version order by version_num"
        )
        return [str(row[0]) for row in rows]
    return [str(row[0]) for row in connection.execute(select(table.c.version_num))]


def build_report_base(
    *,
    source_url: str,
    target_url: str,
    execute: bool,
    identity_map_path: Path | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "created_at": utcnow().isoformat(),
        "git_sha": safe_git_sha(),
        "mode": "execute" if execute else "dry-run",
        "source": {
            "driver": make_url(normalize_postgres_url(source_url)).drivername,
            "host": make_url(normalize_postgres_url(source_url)).host,
        },
        "target": {
            "driver": make_url(normalize_postgres_url(target_url)).drivername,
            "host": make_url(normalize_postgres_url(target_url)).host,
        },
        "identity_map_provided": identity_map_path is not None,
        "excluded_tables": EXCLUDED_TABLES,
        "tables": {},
        "active_work": {},
        "duplicate_identity_emails": [],
        "unmapped_identities": 0,
        "orphan_counts": {},
        "status": "PENDING",
        "failures": [],
    }


def migrate(args: argparse.Namespace) -> dict[str, Any]:
    source_url = args.source_url or os.getenv("APPLYAI_MIGRATION_SOURCE_DATABASE_URL")
    target_url = args.target_url or os.getenv("APPLYAI_MIGRATION_TARGET_DATABASE_URL")
    if not source_url or not target_url:
        raise SystemExit(
            "Set APPLYAI_MIGRATION_SOURCE_DATABASE_URL and "
            "APPLYAI_MIGRATION_TARGET_DATABASE_URL or pass --source-url/--target-url"
        )
    if normalize_postgres_url(source_url) == normalize_postgres_url(target_url):
        raise SystemExit("Source and target databases must be different")

    identity_map_path = Path(args.identity_map) if args.identity_map else None
    identity_map = load_identity_map(identity_map_path)
    report = build_report_base(
        source_url=source_url,
        target_url=target_url,
        execute=args.execute,
        identity_map_path=identity_map_path,
    )
    now = utcnow()

    source_engine = create_engine(normalize_postgres_url(source_url), pool_pre_ping=True)
    target_engine = create_engine(normalize_postgres_url(target_url), pool_pre_ping=True)
    source_metadata = reflected_public_metadata(source_engine)
    target_metadata = reflected_public_metadata(target_engine)

    source_names = public_table_names(source_metadata)
    target_names = public_table_names(target_metadata)
    missing_target_tables = sorted(
        source_names - target_names - set(EXCLUDED_TABLES)
    )
    if missing_target_tables:
        report["failures"].append(
            {"code": "TARGET_SCHEMA_MISSING_TABLES", "tables": missing_target_tables}
        )

    table_names = ordered_migration_tables(source_metadata, target_metadata)
    with source_engine.connect() as source_connection, target_engine.connect() as target_connection:
        report["source_alembic_heads"] = query_alembic_heads(
            source_connection, source_metadata
        )
        report["target_alembic_heads"] = query_alembic_heads(
            target_connection, target_metadata
        )
        if len(report["target_alembic_heads"]) != 1:
            report["failures"].append(
                {
                    "code": "TARGET_ALEMBIC_HEAD_COUNT",
                    "heads": report["target_alembic_heads"],
                }
            )

        report["active_work"] = active_work_counts(
            source_connection, source_metadata, now=now
        )
        active_total = sum(report["active_work"].values())
        if active_total:
            report["failures"].append(
                {
                    "code": "SOURCE_NOT_QUIESCED",
                    "active_work": report["active_work"],
                }
            )

        users = table_by_name(source_metadata, "users")
        report["duplicate_identity_emails"] = duplicate_user_emails(
            source_connection, users
        )
        duplicate_emails = {
            item["email"] for item in report["duplicate_identity_emails"]
        }
        conflicting_identity_map = sorted(duplicate_emails & set(identity_map))
        if conflicting_identity_map:
            report["failures"].append(
                {
                    "code": "AMBIGUOUS_IDENTITY_MAP",
                    "emails": conflicting_identity_map,
                }
            )
        if users is not None and "auth_user_id" in users.c:
            report["unmapped_identities"] = int(
                source_connection.scalar(
                    select(func.count())
                    .select_from(users)
                    .where(users.c.auth_user_id.is_(None))
                )
                or 0
            )

        nonempty_target = target_nonempty_tables(
            target_connection, target_metadata, table_names
        )
        report["preexisting_target_rows"] = nonempty_target
        if args.execute and nonempty_target:
            report["failures"].append(
                {
                    "code": "TARGET_NOT_EMPTY",
                    "tables": nonempty_target,
                    "message": "Use a fresh migrated Supabase schema; this tool will not overwrite existing application rows.",
                }
            )

        for name in table_names:
            source_table = table_by_name(source_metadata, name)
            target_table = table_by_name(target_metadata, name)
            if source_table is None or target_table is None:
                continue
            report["tables"][name] = {
                "source_rows": row_count(source_connection, source_table),
                "target_rows_before": row_count(target_connection, target_table),
                "copied_rows": 0,
                "target_rows_after": row_count(target_connection, target_table),
                "transformations": {},
            }

    if args.execute and report["failures"]:
        report["status"] = "BLOCKED"
        return report

    if args.execute:
        with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
            for name in table_names:
                source_table = table_by_name(source_metadata, name)
                target_table = table_by_name(target_metadata, name)
                if source_table is None or target_table is None:
                    continue
                copied, transformations = copy_table(
                    source_connection,
                    target_connection,
                    source_table,
                    target_table,
                    identity_map=identity_map,
                    batch_size=args.batch_size,
                    now=now,
                )
                report["tables"][name]["copied_rows"] = copied
                report["tables"][name]["transformations"] = transformations

        with target_engine.connect() as target_connection:
            for name in table_names:
                target_table = table_by_name(target_metadata, name)
                if target_table is None:
                    continue
                report["tables"][name]["target_rows_after"] = row_count(
                    target_connection, target_table
                )
            report["orphan_counts"] = orphan_counts(
                target_connection, target_metadata, table_names
            )
    else:
        # Dry-run still gives a useful target integrity baseline.
        with target_engine.connect() as target_connection:
            report["orphan_counts"] = orphan_counts(
                target_connection, target_metadata, table_names
            )

    for name, evidence in report["tables"].items():
        expected = evidence["source_rows"] if args.execute else evidence["target_rows_before"]
        actual = evidence["target_rows_after"]
        if args.execute and actual != expected:
            report["failures"].append(
                {
                    "code": "ROW_COUNT_MISMATCH",
                    "table": name,
                    "source_rows": evidence["source_rows"],
                    "target_rows": actual,
                }
            )

    material_orphans = {
        key: count
        for key, count in report["orphan_counts"].items()
        if count not in {0}
    }
    if material_orphans:
        report["failures"].append(
            {"code": "FOREIGN_KEY_ORPHANS", "relationships": material_orphans}
        )

    report["status"] = "PASS" if not report["failures"] else "BLOCKED"
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit/copy ApplyAI public PostgreSQL data into a fresh Supabase Postgres schema."
    )
    parser.add_argument("--source-url")
    parser.add_argument("--target-url")
    parser.add_argument("--identity-map")
    parser.add_argument("--report", default="artifacts/supabase-data-migration-report.json")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually insert rows. Without this flag the command is audit-only.",
    )
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 5000:
        parser.error("--batch-size must be between 1 and 5000")
    return args


def main() -> int:
    args = parse_args()
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        report = migrate(args)
    except Exception as exc:
        report = {
            "schema_version": 1,
            "created_at": utcnow().isoformat(),
            "git_sha": safe_git_sha(),
            "mode": "execute" if args.execute else "dry-run",
            "status": "ERROR",
            "failures": [
                {
                    "code": type(exc).__name__,
                    "message": str(exc),
                }
            ],
        }
        report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
        raise
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
