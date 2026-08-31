from __future__ import annotations

import argparse
import json
import os
from typing import Any

from sqlalchemy import distinct, func, select, text

from app.core.database import SessionLocal
from app.durability_models import JobIngestionRun
from app.job_source_models import JobSourceRegistry
from app.models import Job, JobSource, JobSourceLink


NON_LIVE_JOB_ORIGINS = {"DEVELOPMENT_SEED", "DEVELOPMENT_DATA"}


def evaluate_initial_acceptance(evidence: dict[str, Any], *, min_jobs: int) -> dict[str, Any]:
    blockers: list[str] = []
    if not evidence["database_schema_present"]:
        blockers.append("Alembic migration state is not present in the production database.")
    if not evidence["open_jobs_source_active"]:
        blockers.append("The Open Jobs real source is not active.")
    if not evidence["successful_open_jobs_run"]:
        blockers.append("No successful Open Jobs ingestion run has completed.")
    if evidence["real_canonical_jobs"] < min_jobs:
        blockers.append(
            f"Real canonical job count {evidence['real_canonical_jobs']} is below required minimum {min_jobs}."
        )
    if evidence["latest_open_jobs_failed"] > 0:
        blockers.append("The latest Open Jobs run contains failed postings.")
    if evidence["open_jobs_source_postings"] <= 0:
        blockers.append("No Open Jobs posting provenance was persisted.")
    if not evidence["company_identity_preserved"]:
        blockers.append("Open Jobs employer identities appear collapsed during canonicalization.")

    return {
        "status": "PASS" if not blockers else "BLOCKED_EXTERNAL_CONFIGURATION",
        "claim": (
            "INITIAL_PRODUCTION_JOB_SUPPLY_VERIFIED"
            if not blockers
            else "INITIAL_PRODUCTION_JOB_SUPPLY_NOT_VERIFIED"
        ),
        "blocking_dependencies": blockers,
        "minimum_real_jobs": min_jobs,
    }


def collect_evidence() -> dict[str, Any]:
    with SessionLocal() as session:
        revision = session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        source = session.scalar(
            select(JobSourceRegistry).where(JobSourceRegistry.source_identity == "open-jobs").limit(1)
        )
        source_active = bool(source and source.enabled and source.crawl_allowed)
        latest_run = None
        if source is not None:
            latest_run = session.scalar(
                select(JobIngestionRun)
                .where(JobIngestionRun.source_id == source.id)
                .order_by(JobIngestionRun.started_at.desc(), JobIngestionRun.id.desc())
                .limit(1)
            )

        real_canonical_jobs = int(
            session.scalar(
                select(func.count(Job.id)).where(Job.data_origin.notin_(NON_LIVE_JOB_ORIGINS))
            )
            or 0
        )

        source_postings = 0
        distinct_source_companies = 0
        distinct_canonical_companies = 0
        if source is not None:
            registry_id = str(source.id)
            source_filter = JobSource.checkpoint["source_registry_id"].astext == registry_id
            source_postings = int(
                session.scalar(select(func.count(JobSource.id)).where(source_filter)) or 0
            )
            distinct_source_companies = int(
                session.scalar(
                    select(
                        func.count(
                            distinct(JobSource.checkpoint["source_company_identity"].astext)
                        )
                    ).where(source_filter)
                )
                or 0
            )
            distinct_canonical_companies = int(
                session.scalar(
                    select(func.count(distinct(Job.company_id)))
                    .select_from(JobSource)
                    .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
                    .join(Job, Job.id == JobSourceLink.job_id)
                    .where(source_filter)
                )
                or 0
            )

        identity_preserved = (
            source_postings > 0
            and (
                distinct_source_companies <= 1
                or distinct_canonical_companies > 1
            )
        )
        return {
            "git_sha": os.getenv("GITHUB_SHA") or os.getenv("RAILWAY_GIT_COMMIT_SHA"),
            "alembic_revision": revision,
            "database_schema_present": bool(revision),
            "open_jobs_source_active": source_active,
            "successful_open_jobs_run": bool(
                latest_run
                and latest_run.status == "COMPLETED"
                and latest_run.fetched > 0
                and latest_run.valid > 0
                and latest_run.failed == 0
            ),
            "latest_open_jobs_status": latest_run.status if latest_run else None,
            "latest_open_jobs_fetched": int(latest_run.fetched) if latest_run else 0,
            "latest_open_jobs_valid": int(latest_run.valid) if latest_run else 0,
            "latest_open_jobs_failed": int(latest_run.failed) if latest_run else 0,
            "real_canonical_jobs": real_canonical_jobs,
            "open_jobs_source_postings": source_postings,
            "open_jobs_source_company_identities": distinct_source_companies,
            "open_jobs_canonical_companies": distinct_canonical_companies,
            "company_identity_preserved": identity_preserved,
            "development_seed_jobs_counted_as_real": False,
        }


def build_report(*, min_jobs: int) -> dict[str, Any]:
    evidence = collect_evidence()
    return {**evaluate_initial_acceptance(evidence, min_jobs=min_jobs), "evidence": evidence}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify ApplyAI's initial real production job inventory without weakening mature source coverage acceptance."
    )
    parser.add_argument("--min-jobs", type=int, default=1)
    parser.add_argument("--allow-blocked", action="store_true")
    args = parser.parse_args()
    if args.min_jobs < 1:
        parser.error("--min-jobs must be at least 1")

    report = build_report(min_jobs=args.min_jobs)
    print(json.dumps(report, indent=2, sort_keys=True, default=str))
    if report["status"] != "PASS" and not args.allow_blocked:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
