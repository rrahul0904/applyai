from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.config import get_settings


COMPANY_ID = "00000000-0000-4000-8000-000000000001"
BENCHMARK_ORIGIN = "SYNTHETIC_BENCHMARK"


def uuid_sql(prefix: str, value: str) -> str:
    digest = f"md5('{prefix}' || ({value})::text)"
    return (
        f"(substr({digest},1,8) || '-' || substr({digest},9,4) || '-' || "
        f"substr({digest},13,4) || '-' || substr({digest},17,4) || '-' || "
        f"substr({digest},21,12))::uuid"
    )


def benchmark_job_filter(alias: str = "jobs") -> str:
    return f"{alias}.data_origin = '{BENCHMARK_ORIGIN}'"


def seed_sql(rows: int) -> list[str]:
    job_id = uuid_sql("applyai-benchmark-job-", "i")
    location_id = uuid_sql("applyai-benchmark-location-", "i")
    compensation_id = uuid_sql("applyai-benchmark-comp-", "i")
    benchmark_jobs = f"SELECT id FROM jobs WHERE {benchmark_job_filter()}"
    return [
        f"DELETE FROM job_compensation WHERE job_id IN ({benchmark_jobs})",
        f"DELETE FROM job_locations WHERE job_id IN ({benchmark_jobs})",
        f"DELETE FROM jobs WHERE {benchmark_job_filter()}",
        f"""
        INSERT INTO companies (
            id, canonical_name, normalized_name, website_url, description
        ) VALUES (
            '{COMPANY_ID}'::uuid,
            'ApplyAI Benchmark Company',
            'applyai benchmark company',
            'https://benchmark.example.test',
            'Synthetic non-production benchmark company.'
        ) ON CONFLICT (id) DO UPDATE SET
            canonical_name = EXCLUDED.canonical_name,
            normalized_name = EXCLUDED.normalized_name,
            website_url = EXCLUDED.website_url,
            description = EXCLUDED.description
        """,
        f"""
        INSERT INTO jobs (
            id,
            company_id,
            title,
            normalized_title,
            description,
            search_document,
            search_vector,
            employment_type,
            seniority,
            status,
            posted_at,
            first_seen_at,
            last_seen_at,
            data_origin,
            created_at,
            updated_at
        )
        SELECT
            {job_id},
            '{COMPANY_ID}'::uuid,
            CASE
                WHEN i % 5 = 0 THEN 'Senior Data Engineer'
                WHEN i % 5 = 1 THEN 'Platform Engineer'
                WHEN i % 5 = 2 THEN 'Data Analyst'
                WHEN i % 5 = 3 THEN 'Software Engineer'
                ELSE 'Analytics Engineer'
            END,
            CASE
                WHEN i % 5 = 0 THEN 'senior data engineer'
                WHEN i % 5 = 1 THEN 'platform engineer'
                WHEN i % 5 = 2 THEN 'data analyst'
                WHEN i % 5 = 3 THEN 'software engineer'
                ELSE 'analytics engineer'
            END,
            'Synthetic non-production benchmark posting ' || i ||
            ' for reliable data systems, SQL, Python, cloud platforms, analytics and distributed services.',
            CASE
                WHEN i % 5 = 0 THEN 'Senior Data Engineer synthetic benchmark SQL Python cloud data systems'
                WHEN i % 5 = 1 THEN 'Platform Engineer synthetic benchmark distributed systems cloud'
                WHEN i % 5 = 2 THEN 'Data Analyst synthetic benchmark SQL analytics'
                WHEN i % 5 = 3 THEN 'Software Engineer synthetic benchmark Python services'
                ELSE 'Analytics Engineer synthetic benchmark SQL data models'
            END,
            to_tsvector(
                'english',
                CASE
                    WHEN i % 5 = 0 THEN 'Senior Data Engineer synthetic benchmark SQL Python cloud data systems'
                    WHEN i % 5 = 1 THEN 'Platform Engineer synthetic benchmark distributed systems cloud'
                    WHEN i % 5 = 2 THEN 'Data Analyst synthetic benchmark SQL analytics'
                    WHEN i % 5 = 3 THEN 'Software Engineer synthetic benchmark Python services'
                    ELSE 'Analytics Engineer synthetic benchmark SQL data models'
                END
            ),
            CASE WHEN i % 11 = 0 THEN 'CONTRACT' ELSE 'FULL_TIME' END,
            CASE WHEN i % 7 = 0 THEN 'STAFF' ELSE 'SENIOR' END,
            'ACTIVE',
            now() - ((i % 30) || ' days')::interval,
            now() - ((i % 30) || ' days')::interval,
            now() - ((i % 24) || ' hours')::interval,
            '{BENCHMARK_ORIGIN}',
            now(),
            now()
        FROM generate_series(1, {rows}) AS series(i)
        """,
        f"""
        INSERT INTO job_locations (
            id, job_id, location_text, city, region, country_code, work_mode
        )
        SELECT
            {location_id},
            {job_id},
            CASE
                WHEN i % 3 = 0 THEN 'Boston, MA'
                WHEN i % 3 = 1 THEN 'New York, NY'
                ELSE 'United States'
            END,
            CASE
                WHEN i % 3 = 0 THEN 'Boston'
                WHEN i % 3 = 1 THEN 'New York'
                ELSE NULL
            END,
            CASE
                WHEN i % 3 = 0 THEN 'MA'
                WHEN i % 3 = 1 THEN 'NY'
                ELSE NULL
            END,
            'US',
            CASE WHEN i % 3 = 2 THEN 'REMOTE' ELSE 'HYBRID' END
        FROM generate_series(1, {rows}) AS series(i)
        """,
        f"""
        INSERT INTO job_compensation (
            id, job_id, minimum, maximum, currency, interval, provenance
        )
        SELECT
            {compensation_id},
            {job_id},
            90000 + (i % 20) * 5000,
            130000 + (i % 20) * 5000,
            'USD',
            'YEAR',
            'SOURCE_REPORTED'
        FROM generate_series(1, {rows}) AS series(i)
        """,
        "ANALYZE companies",
        "ANALYZE jobs",
        "ANALYZE job_locations",
        "ANALYZE job_compensation",
    ]


QUERIES = {
    "keyword": """
        SELECT id FROM jobs
        WHERE status = 'ACTIVE'
          AND search_vector @@ websearch_to_tsquery('english', 'data engineer')
        ORDER BY ts_rank_cd(search_vector, websearch_to_tsquery('english', 'data engineer')) DESC,
                 last_seen_at DESC, id DESC
        LIMIT 20
    """,
    "location": """
        SELECT j.id FROM jobs j
        WHERE j.status = 'ACTIVE'
          AND EXISTS (
            SELECT 1 FROM job_locations l
            WHERE l.job_id = j.id AND l.location_text ILIKE '%Boston%'
          )
        ORDER BY j.last_seen_at DESC, j.id DESC
        LIMIT 20
    """,
    "remote": """
        SELECT j.id FROM jobs j
        WHERE j.status = 'ACTIVE'
          AND EXISTS (
            SELECT 1 FROM job_locations l
            WHERE l.job_id = j.id AND l.work_mode = 'REMOTE'
          )
        ORDER BY j.last_seen_at DESC, j.id DESC
        LIMIT 20
    """,
    "salary": """
        SELECT j.id FROM jobs j
        WHERE j.status = 'ACTIVE'
          AND EXISTS (
            SELECT 1 FROM job_compensation c
            WHERE c.job_id = j.id AND c.maximum >= 180000
          )
        ORDER BY j.last_seen_at DESC, j.id DESC
        LIMIT 20
    """,
    "keyset_pagination": """
        SELECT id FROM jobs
        WHERE status = 'ACTIVE'
          AND (last_seen_at, id) < (now(), 'ffffffff-ffff-ffff-ffff-ffffffffffff'::uuid)
        ORDER BY last_seen_at DESC, id DESC
        LIMIT 50
    """,
    "saved_jobs_shape": """
        SELECT j.id, j.title, j.last_seen_at
        FROM jobs j
        WHERE j.status = 'ACTIVE'
        ORDER BY j.last_seen_at DESC, j.id DESC
        LIMIT 50
    """,
    "job_detail": f"""
        SELECT j.*, c.canonical_name
        FROM jobs j
        JOIN companies c ON c.id = j.company_id
        WHERE {benchmark_job_filter('j')}
        ORDER BY j.id
        LIMIT 1
    """,
}


def cleanup_sql() -> list[str]:
    benchmark_jobs = f"SELECT id FROM jobs WHERE {benchmark_job_filter()}"
    return [
        f"DELETE FROM job_compensation WHERE job_id IN ({benchmark_jobs})",
        f"DELETE FROM job_locations WHERE job_id IN ({benchmark_jobs})",
        f"DELETE FROM jobs WHERE {benchmark_job_filter()}",
    ]


def benchmark(rows: int, output: Path, cleanup: bool) -> dict:
    engine = create_engine(get_settings().database_url)
    started = time.monotonic()
    with engine.begin() as connection:
        for statement in seed_sql(rows):
            connection.execute(text(statement))
    seed_seconds = time.monotonic() - started

    results: dict[str, dict] = {}
    with engine.connect() as connection:
        actual_rows = connection.scalar(
            text(f"SELECT count(*) FROM jobs WHERE {benchmark_job_filter()}")
        )
        database_bytes = connection.scalar(text("SELECT pg_database_size(current_database())"))
        postgres_version = connection.scalar(text("SHOW server_version"))
        for name, query in QUERIES.items():
            plan = connection.execute(
                text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}")
            ).scalar_one()[0]
            results[name] = {
                "planning_time_ms": plan.get("Planning Time"),
                "execution_time_ms": plan.get("Execution Time"),
                "plan_rows": plan["Plan"].get("Plan Rows"),
                "actual_rows": plan["Plan"].get("Actual Rows"),
                "shared_hit_blocks": plan["Plan"].get("Shared Hit Blocks"),
                "shared_read_blocks": plan["Plan"].get("Shared Read Blocks"),
                "node_type": plan["Plan"].get("Node Type"),
                "plan": plan["Plan"],
            }

    report = {
        "requested_rows": rows,
        "inserted_rows": int(actual_rows or 0),
        "seed_seconds": round(seed_seconds, 4),
        "database_bytes_after_seed": int(database_bytes or 0),
        "postgresql_version": str(postgres_version),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": os.getenv("GITHUB_SHA"),
        "source_ref": os.getenv("GITHUB_HEAD_REF") or os.getenv("GITHUB_REF"),
        "queries": results,
        "environment": "synthetic_github_hosted_postgresql",
        "claims": {
            "aurora": False,
            "production": False,
            "live_provider": False,
            "aws_cost": False,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if cleanup:
        with engine.begin() as connection:
            for statement in cleanup_sql():
                connection.execute(text(statement))
    engine.dispose()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, choices=(10_000, 50_000, 250_000), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    print(json.dumps(benchmark(args.rows, args.output, args.cleanup), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
