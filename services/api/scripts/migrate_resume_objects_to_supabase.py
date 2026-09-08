from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy import MetaData, create_engine, select

from scripts.migrate_postgres_to_supabase import normalize_postgres_url, safe_git_sha


def utcnow() -> datetime:
    return datetime.now(UTC)


def project_ref_from_url(url: str) -> str:
    host = url.removeprefix("https://").split("/", 1)[0].strip().lower()
    suffix = ".supabase.co"
    if not host.endswith(suffix):
        raise ValueError("SUPABASE_URL must use the hosted *.supabase.co project URL")
    ref = host[: -len(suffix)]
    if not ref:
        raise ValueError("Unable to derive Supabase project ref")
    return ref


def storage_endpoint(url: str) -> str:
    ref = project_ref_from_url(url)
    return f"https://{ref}.storage.supabase.co/storage/v1/s3"


def build_client(*, url: str, region: str, access_key: str, secret_key: str):
    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=storage_endpoint(url),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def head_or_none(client, *, bucket: str, key: str) -> dict[str, Any] | None:
    try:
        return client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in {"404", "NoSuchKey", "NotFound"} or status == 404:
            return None
        raise


def normalize_content_type(value: str | None) -> str:
    return (value or "application/octet-stream").split(";", 1)[0].strip().lower()


def migrate(args: argparse.Namespace) -> dict[str, Any]:
    database_url = args.source_url or os.getenv("APPLYAI_MIGRATION_SOURCE_DATABASE_URL")
    supabase_url = args.supabase_url or os.getenv("APPLYAI_SUPABASE_URL")
    access_key = args.access_key or os.getenv("APPLYAI_SUPABASE_S3_ACCESS_KEY_ID")
    secret_key = args.secret_key or os.getenv("APPLYAI_SUPABASE_S3_SECRET_ACCESS_KEY")
    bucket = args.bucket or os.getenv("APPLYAI_SUPABASE_STORAGE_BUCKET", "resumes")
    region = args.region or os.getenv("APPLYAI_SUPABASE_STORAGE_REGION", "us-east-2")

    missing = [
        name
        for name, value in {
            "source database URL": database_url,
            "Supabase URL": supabase_url,
            "Supabase S3 access key": access_key,
            "Supabase S3 secret key": secret_key,
            "bucket": bucket,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit("Missing required migration configuration: " + ", ".join(missing))

    report: dict[str, Any] = {
        "schema_version": 1,
        "created_at": utcnow().isoformat(),
        "git_sha": safe_git_sha(),
        "mode": "execute" if args.execute else "dry-run",
        "source_provider": "postgres_database_objects",
        "target_provider": "supabase_storage_s3",
        "bucket": bucket,
        "source_objects": 0,
        "target_objects_verified": 0,
        "uploaded_objects": 0,
        "already_matching": 0,
        "missing_objects": [],
        "size_mismatches": [],
        "content_type_mismatches": [],
        "failures": [],
        "source_deleted": False,
        "status": "PENDING",
    }

    engine = create_engine(normalize_postgres_url(database_url), pool_pre_ping=True)
    metadata = MetaData()
    metadata.reflect(bind=engine, schema="public", only=["database_objects"])
    objects = metadata.tables.get("public.database_objects")
    if objects is None:
        report["status"] = "PASS"
        report["note"] = "Source database has no database_objects table"
        return report

    client = build_client(
        url=supabase_url,
        region=region,
        access_key=access_key,
        secret_key=secret_key,
    )

    with engine.connect() as connection:
        rows = connection.execution_options(stream_results=True).execute(
            select(
                objects.c.key,
                objects.c.content_type,
                objects.c.size,
                objects.c.content,
            ).order_by(objects.c.key)
        )
        for row in rows.mappings():
            report["source_objects"] += 1
            key = str(row["key"])
            expected_size = int(row["size"])
            expected_type = normalize_content_type(row["content_type"])

            try:
                existing = head_or_none(client, bucket=bucket, key=key)
                if existing is not None:
                    actual_size = int(existing.get("ContentLength", -1))
                    actual_type = normalize_content_type(existing.get("ContentType"))
                    if actual_size == expected_size and actual_type == expected_type:
                        report["already_matching"] += 1
                        report["target_objects_verified"] += 1
                        continue
                    if actual_size != expected_size:
                        report["size_mismatches"].append(
                            {
                                "key": key,
                                "source_size": expected_size,
                                "target_size": actual_size,
                            }
                        )
                    if actual_type != expected_type:
                        report["content_type_mismatches"].append(
                            {
                                "key": key,
                                "source_content_type": expected_type,
                                "target_content_type": actual_type,
                            }
                        )
                    if not args.execute:
                        continue

                if not args.execute:
                    report["missing_objects"].append(key)
                    continue

                client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=bytes(row["content"]),
                    ContentType=expected_type,
                )
                report["uploaded_objects"] += 1
                verified = head_or_none(client, bucket=bucket, key=key)
                if verified is None:
                    report["failures"].append(
                        {"key": key, "code": "OBJECT_NOT_FOUND_AFTER_UPLOAD"}
                    )
                    continue
                actual_size = int(verified.get("ContentLength", -1))
                actual_type = normalize_content_type(verified.get("ContentType"))
                if actual_size != expected_size:
                    report["size_mismatches"].append(
                        {
                            "key": key,
                            "source_size": expected_size,
                            "target_size": actual_size,
                        }
                    )
                elif actual_type != expected_type:
                    report["content_type_mismatches"].append(
                        {
                            "key": key,
                            "source_content_type": expected_type,
                            "target_content_type": actual_type,
                        }
                    )
                else:
                    report["target_objects_verified"] += 1
            except Exception as exc:
                report["failures"].append(
                    {
                        "key": key,
                        "code": type(exc).__name__,
                        "message": str(exc),
                    }
                )

    if args.execute:
        # Reconcile missing/mismatch arrays against the final target state. Source deletion is
        # deliberately not implemented in this command; cutover must retain rollback data.
        report["missing_objects"] = []
        report["size_mismatches"] = []
        report["content_type_mismatches"] = []
        with engine.connect() as connection:
            rows = connection.execute(
                select(
                    objects.c.key,
                    objects.c.content_type,
                    objects.c.size,
                ).order_by(objects.c.key)
            )
            verified_count = 0
            for row in rows.mappings():
                key = str(row["key"])
                existing = head_or_none(client, bucket=bucket, key=key)
                if existing is None:
                    report["missing_objects"].append(key)
                    continue
                expected_size = int(row["size"])
                actual_size = int(existing.get("ContentLength", -1))
                expected_type = normalize_content_type(row["content_type"])
                actual_type = normalize_content_type(existing.get("ContentType"))
                if actual_size != expected_size:
                    report["size_mismatches"].append(
                        {
                            "key": key,
                            "source_size": expected_size,
                            "target_size": actual_size,
                        }
                    )
                if actual_type != expected_type:
                    report["content_type_mismatches"].append(
                        {
                            "key": key,
                            "source_content_type": expected_type,
                            "target_content_type": actual_type,
                        }
                    )
                if actual_size == expected_size and actual_type == expected_type:
                    verified_count += 1
            report["target_objects_verified"] = verified_count

    blocking = (
        report["failures"]
        or report["missing_objects"]
        or report["size_mismatches"]
        or report["content_type_mismatches"]
    )
    report["status"] = "PASS" if not blocking else "BLOCKED"
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit/copy ApplyAI database-backed resume objects into Supabase Storage."
    )
    parser.add_argument("--source-url")
    parser.add_argument("--supabase-url")
    parser.add_argument("--access-key")
    parser.add_argument("--secret-key")
    parser.add_argument("--bucket", default="resumes")
    parser.add_argument("--region", default="us-east-2")
    parser.add_argument(
        "--report",
        default="artifacts/supabase-resume-object-migration-report.json",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Upload missing/mismatched objects. Dry-run is the default.",
    )
    return parser.parse_args()


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
                {"code": type(exc).__name__, "message": str(exc)}
            ],
            "source_deleted": False,
        }
        report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
        raise
    report_path.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
