from __future__ import annotations

import argparse
import json
import os
from typing import Any

from sqlalchemy import distinct, func, select, text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.durability_models import JobIngestionRun
from app.job_source_models import JobSourceRegistry
from app.models import Job, JobSource, JobSourceLink


NON_LIVE_JOB_ORIGINS = {"DEVELOPMENT_SEED", "DEVELOPMENT_DATA"}
EMPLOYER_ATS_SOURCE_TYPES = {"GREENHOUSE", "LEVER", "ASHBY", "SMARTRECRUITERS"}


def completed_open_jobs_cycle(run: JobIngestionRun | None) -> bool:
    """Accept a completed multi-run CC0 discovery sweep without claiming a snapshot.

    Open Jobs is deliberately non-authoritative: each bounded ingestion run stays
    PARTIAL, and its jobs cannot be closed based on absence from that slice. The
    connector's durable cursor only advances across failure-free runs, so a final
    cycle receipt proves traversal while preserving those closure semantics.
    """
    if run is None or run.status != "PARTIAL" or run.coverage_status != "PARTIAL":
        return False
    if int(run.failed or 0) > 0 or int(run.fetched or 0) <= 0 or int(run.valid or 0) <= 0:
        return False
    details = run.coverage_details if isinstance(run.coverage_details, dict) else {}
    checks = details.get("completeness_checks")
    return isinstance(checks, dict) and checks.get("cycle_complete") is True


def evaluate_initial_acceptance(
    evidence: dict[str, Any],
    *,
    min_jobs: int,
    app_env: str = "production",
) -> dict[str, Any]:
    blockers: list[str] = []
    if not evidence["database_schema_present"]:
        blockers.append("Alembic migration state is not present in the production database.")
    open_jobs_verified = bool(
        evidence["open_jobs_source_active"]
        and (
            evidence["successful_open_jobs_run"]
            or evidence["completed_open_jobs_cycle"]
        )
        and evidence.get("open_jobs_canonical_jobs", 0) >= min_jobs
        and evidence["open_jobs_source_postings"] > 0
        and evidence["company_identity_preserved"]
    )
    employer_ats_verified = bool(
        evidence.get("employer_source_verified")
        and str(evidence.get("employer_source_type") or "").upper()
        in EMPLOYER_ATS_SOURCE_TYPES
        and evidence.get("employer_source_fetched", 0) > 0
        and evidence.get("employer_source_valid", 0) > 0
        and evidence.get("employer_source_canonical_jobs", 0) >= min_jobs
        and evidence.get("employer_source_postings", 0) > 0
        and evidence.get("employer_source_failed", 0) == 0
        and evidence.get("employer_company_identity_preserved")
    )
    if not (open_jobs_verified or employer_ats_verified):
        blockers.append(
            "No successful Open Jobs discovery cycle or complete employer ATS ingestion with real provenance has completed."
        )
    if evidence["real_canonical_jobs"] < min_jobs:
        blockers.append(
            f"Real canonical job count {evidence['real_canonical_jobs']} is below required minimum {min_jobs}."
        )
    if not employer_ats_verified and evidence["latest_open_jobs_failed"] > 0:
        blockers.append("The latest Open Jobs run contains failed postings.")
    if not (open_jobs_verified or employer_ats_verified) and evidence["open_jobs_source_postings"] <= 0:
        blockers.append("No Open Jobs posting provenance was persisted.")
    if (
        open_jobs_verified
        and evidence["open_jobs_source_postings"] > 0
        and not evidence["company_identity_preserved"]
    ):
        blockers.append("Open Jobs employer identities appear collapsed during canonicalization.")

    durable_environment = app_env.casefold() in {"staging", "production"}
    source_path = "OPEN_JOBS" if open_jobs_verified else "EMPLOYER_ATS" if employer_ats_verified else None
    if source_path == "OPEN_JOBS":
        source_postings = evidence["open_jobs_source_postings"]
        source_jobs = evidence["open_jobs_canonical_jobs"]
        company_identity_preserved = evidence["company_identity_preserved"]
    elif source_path == "EMPLOYER_ATS":
        source_postings = evidence["employer_source_postings"]
        source_jobs = evidence["employer_source_canonical_jobs"]
        company_identity_preserved = evidence["employer_company_identity_preserved"]
    else:
        source_postings = 0
        source_jobs = 0
        company_identity_preserved = False
    if blockers:
        status = "BLOCKED_EXTERNAL_CONFIGURATION"
        claim = "INITIAL_PRODUCTION_JOB_SUPPLY_NOT_VERIFIED"
    elif durable_environment:
        status = "PASS"
        claim = "INITIAL_PRODUCTION_JOB_SUPPLY_VERIFIED"
    else:
        status = "RUNTIME_EVIDENCE_AVAILABLE"
        claim = "REAL_JOB_SUPPLY_VERIFIED_NOT_STAGING"

    return {
        "status": status,
        "claim": claim,
        "source_path": source_path,
        "source_postings": source_postings,
        "source_canonical_jobs": source_jobs,
        "company_identity_preserved": company_identity_preserved,
        "open_jobs_provider_warning": evidence.get("open_jobs_provider_warning"),
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

        employer_evidence: dict[str, Any] = {
            "employer_source_verified": False,
            "employer_source_identity": None,
            "employer_source_type": None,
            "employer_source_run_id": None,
            "employer_source_fetched": 0,
            "employer_source_valid": 0,
            "employer_source_failed": 0,
            "employer_source_postings": 0,
            "employer_source_canonical_jobs": 0,
            "employer_source_company_identities": 0,
            "employer_source_canonical_companies": 0,
            "employer_company_identity_preserved": False,
        }
        candidates = list(
            session.scalars(
                select(JobSourceRegistry)
                .where(
                    JobSourceRegistry.source_type.in_(EMPLOYER_ATS_SOURCE_TYPES),
                    JobSourceRegistry.enabled.is_(True),
                    JobSourceRegistry.crawl_allowed.is_(True),
                )
                .order_by(JobSourceRegistry.source_identity)
            )
        )
        for candidate in candidates:
            candidate_run = session.scalar(
                select(JobIngestionRun)
                .where(JobIngestionRun.source_id == candidate.id)
                .order_by(JobIngestionRun.started_at.desc(), JobIngestionRun.id.desc())
                .limit(1)
            )
            if (
                candidate_run is None
                or candidate_run.status != "COMPLETED"
                or candidate_run.coverage_status != "COMPLETE"
                or int(candidate_run.fetched or 0) <= 0
                or int(candidate_run.valid or 0) <= 0
                or int(candidate_run.failed or 0) > 0
            ):
                continue
            candidate_filter = (
                JobSource.checkpoint["source_registry_id"].astext == str(candidate.id)
            )
            postings = int(
                session.scalar(select(func.count(JobSource.id)).where(candidate_filter)) or 0
            )
            canonical_jobs = int(
                session.scalar(
                    select(func.count(distinct(Job.id)))
                    .select_from(JobSource)
                    .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
                    .join(Job, Job.id == JobSourceLink.job_id)
                    .where(candidate_filter, Job.data_origin.notin_(NON_LIVE_JOB_ORIGINS))
                )
                or 0
            )
            source_companies = int(
                session.scalar(
                    select(
                        func.count(distinct(JobSource.checkpoint["source_company_identity"].astext))
                    ).where(candidate_filter)
                )
                or 0
            )
            canonical_companies = int(
                session.scalar(
                    select(func.count(distinct(Job.company_id)))
                    .select_from(JobSource)
                    .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
                    .join(Job, Job.id == JobSourceLink.job_id)
                    .where(candidate_filter)
                )
                or 0
            )
            identity_preserved = postings > 0 and (
                source_companies <= 1 or canonical_companies > 1
            )
            if not identity_preserved:
                continue
            candidate_evidence = {
                "employer_source_verified": canonical_jobs > 0,
                "employer_source_identity": candidate.source_identity,
                "employer_source_type": candidate.source_type,
                "employer_source_run_id": str(candidate_run.id),
                "employer_source_fetched": int(candidate_run.fetched),
                "employer_source_valid": int(candidate_run.valid),
                "employer_source_failed": int(candidate_run.failed),
                "employer_source_postings": postings,
                "employer_source_canonical_jobs": canonical_jobs,
                "employer_source_company_identities": source_companies,
                "employer_source_canonical_companies": canonical_companies,
                "employer_company_identity_preserved": identity_preserved,
            }
            if candidate_evidence["employer_source_canonical_jobs"] > employer_evidence[
                "employer_source_canonical_jobs"
            ]:
                employer_evidence = candidate_evidence

        source_postings = 0
        canonical_open_jobs = 0
        distinct_source_companies = 0
        distinct_canonical_companies = 0
        if source is not None:
            registry_id = str(source.id)
            source_filter = JobSource.checkpoint["source_registry_id"].astext == registry_id
            source_postings = int(
                session.scalar(select(func.count(JobSource.id)).where(source_filter)) or 0
            )
            canonical_open_jobs = int(
                session.scalar(
                    select(func.count(distinct(Job.id)))
                    .select_from(JobSource)
                    .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
                    .join(Job, Job.id == JobSourceLink.job_id)
                    .where(source_filter, Job.data_origin.notin_(NON_LIVE_JOB_ORIGINS))
                )
                or 0
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
            "open_jobs_provider_warning": (
                {
                    "health_status": source.health_status,
                    "error_category": source.last_error_category,
                    "error_summary": source.last_error_summary,
                }
                if source and source.health_status in {"DEGRADED", "FAILING"}
                else latest_run.coverage_details.get("reason_codes")
                if latest_run and isinstance(latest_run.coverage_details, dict)
                else None
            ),
            "successful_open_jobs_run": bool(
                latest_run
                and latest_run.status == "COMPLETED"
                and latest_run.coverage_status == "COMPLETE"
                and latest_run.fetched > 0
                and latest_run.valid > 0
                and latest_run.failed == 0
            ),
            "completed_open_jobs_cycle": completed_open_jobs_cycle(latest_run),
            "latest_open_jobs_status": latest_run.status if latest_run else None,
            "latest_open_jobs_fetched": int(latest_run.fetched) if latest_run else 0,
            "latest_open_jobs_valid": int(latest_run.valid) if latest_run else 0,
            "latest_open_jobs_failed": int(latest_run.failed) if latest_run else 0,
            "real_canonical_jobs": real_canonical_jobs,
            "open_jobs_source_postings": source_postings,
            "open_jobs_canonical_jobs": canonical_open_jobs,
            "open_jobs_source_company_identities": distinct_source_companies,
            "open_jobs_canonical_companies": distinct_canonical_companies,
            "company_identity_preserved": identity_preserved,
            "development_seed_jobs_counted_as_real": False,
            **employer_evidence,
            "app_env": get_settings().app_env,
        }


def build_report(*, min_jobs: int) -> dict[str, Any]:
    evidence = collect_evidence()
    return {
        **evaluate_initial_acceptance(
            evidence,
            min_jobs=min_jobs,
            app_env=str(evidence["app_env"]),
        ),
        "evidence": evidence,
    }


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
