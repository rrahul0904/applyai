from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.durability_models import JobIngestionRun, TaskOutbox
from app.global_job_supply_models import JobSourceCapability, OrganizationProfile
from app.job_source_models import JobSourceRegistry
from app.jobs.quality import quality_metrics, source_coverage_metrics
from app.jobs.source_capabilities import seed_source_capabilities
from app.models import Job


REPRESENTATIVE_PROVIDER_TYPES = {
    "GREENHOUSE",
    "LEVER",
    "ASHBY",
    "SMARTRECRUITERS",
    "USAJOBS",
    "RELIEFWEB",
    "CAREER_SITE",
}

NON_LIVE_JOB_ORIGINS = {"DEVELOPMENT_SEED", "DEVELOPMENT_DATA"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def evaluate_acceptance(evidence: dict[str, Any], *, app_env: str) -> dict[str, Any]:
    blockers: list[str] = []
    if evidence["organizations_total"] <= 0:
        blockers.append("No non-demo organization universe has been loaded.")
    if evidence["active_real_sources"] <= 0:
        blockers.append("No active non-development job sources are configured.")
    if evidence["successful_real_source_runs"] <= 0:
        blockers.append("No successful real-source ingestion run has been observed.")
    if evidence["real_canonical_jobs"] <= 0:
        blockers.append("No canonical jobs with a non-development data origin are present.")

    representative = set(evidence.get("representative_providers_verified") or [])
    missing_representative = sorted(REPRESENTATIVE_PROVIDER_TYPES - representative)
    staging = app_env.casefold() == "staging"

    if blockers:
        status = "BLOCKED_EXTERNAL_CONFIGURATION"
        claim = "SOURCE_IMPLEMENTED_NOT_LIVE_VERIFIED"
    elif not staging:
        status = "RUNTIME_EVIDENCE_AVAILABLE"
        claim = "LIVE_PUBLIC_SOURCE_EVIDENCE_AVAILABLE_NOT_STAGING_VERIFIED"
    elif missing_representative:
        status = "PARTIAL_STAGING_ACCEPTANCE"
        claim = "LIVE_STAGING_PARTIAL_COVERAGE"
    else:
        status = "PASS"
        claim = "LIVE_STAGING_VERIFIED"

    return {
        "status": status,
        "claim": claim,
        "blocking_dependencies": blockers,
        "missing_representative_providers": missing_representative,
        "is_staging_environment": staging,
    }


def collect_evidence() -> dict[str, Any]:
    settings = get_settings()
    now = utcnow()
    recent = now - timedelta(hours=24)
    with SessionLocal() as session:
        seed_source_capabilities(session)
        session.commit()

        revision = session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
        organizations_total = int(
            session.scalar(select(func.count(OrganizationProfile.id))) or 0
        )
        source_rows = list(
            session.scalars(
                select(JobSourceRegistry).where(
                    JobSourceRegistry.source_type != "DEVELOPMENT_SEED"
                )
            )
        )
        active_real_sources = [
            source
            for source in source_rows
            if source.enabled and source.crawl_allowed
        ]
        completed_runs = list(
            session.scalars(
                select(JobIngestionRun)
                .where(
                    JobIngestionRun.source_id.is_not(None),
                    JobIngestionRun.status == "COMPLETED",
                    JobIngestionRun.source_type != "DEVELOPMENT_SEED",
                )
                .order_by(JobIngestionRun.started_at.desc())
            )
        )
        provider_types_verified = {
            str(run.source_type or "").upper()
            for run in completed_runs
            if run.fetched > 0 and run.valid > 0
        }
        real_canonical_jobs = int(
            session.scalar(
                select(func.count(Job.id)).where(
                    Job.data_origin.notin_(NON_LIVE_JOB_ORIGINS)
                )
            )
            or 0
        )
        recent_real_runs = [run for run in completed_runs if run.started_at >= recent]
        outbox = dict(
            session.execute(
                select(TaskOutbox.status, func.count(TaskOutbox.id)).group_by(TaskOutbox.status)
            ).all()
        )
        capabilities = list(session.scalars(select(JobSourceCapability)))
        external_dependencies = [
            {
                "provider": row.provider_key,
                "implementation_status": row.implementation_status,
                "access_mode": row.access_mode,
                "requires_credentials": bool(
                    (row.metadata_json or {}).get(
                        "requires_credentials", row.authentication_required
                    )
                ),
                "requires_partnership": bool(
                    (row.metadata_json or {}).get("requires_partnership", False)
                ),
            }
            for row in capabilities
            if row.implementation_status
            in {"PARTNERSHIP_REQUIRED", "NOT_YET_SUPPORTED"}
            or row.authentication_required
        ]

        return {
            "generated_at": now.isoformat(),
            "app_env": settings.app_env,
            "git_sha": os.getenv("GITHUB_SHA") or os.getenv("VERCEL_GIT_COMMIT_SHA"),
            "alembic_revision": revision,
            "database_schema_present": bool(revision),
            "provider_capabilities_total": len(capabilities),
            "organizations_total": organizations_total,
            "active_real_sources": len(active_real_sources),
            "successful_real_source_runs": len(completed_runs),
            "successful_real_source_runs_24h": len(recent_real_runs),
            "real_canonical_jobs": real_canonical_jobs,
            "representative_providers_verified": sorted(provider_types_verified),
            "task_outbox_by_status": {key: int(value) for key, value in outbox.items()},
            "quality": quality_metrics(session, window_hours=24),
            "coverage": source_coverage_metrics(session),
            "external_dependencies": external_dependencies,
            "claims": {
                "synthetic_scale_is_live_inventory": False,
                "marketplace_partnerships_assumed": False,
                "production_verified": False,
            },
        }


def build_report() -> dict[str, Any]:
    evidence = collect_evidence()
    evaluation = evaluate_acceptance(evidence, app_env=evidence["app_env"])
    return {**evaluation, "evidence": evidence}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate ApplyAI real job-supply activation using measured runtime evidence."
    )
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Return exit code 0 even when external configuration/live evidence is missing.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the machine-readable JSON report.",
    )
    args = parser.parse_args()

    report = build_report()
    if not args.json_only:
        print("ApplyAI Global Job Supply Acceptance")
        print(f"Status: {report['status']}")
        print(f"Claim boundary: {report['claim']}")
        evidence = report["evidence"]
        print(f"Organizations loaded: {evidence['organizations_total']}")
        print(f"Active real sources: {evidence['active_real_sources']}")
        print(f"Successful real-source runs: {evidence['successful_real_source_runs']}")
        print(f"Real canonical jobs: {evidence['real_canonical_jobs']}")
        if report["blocking_dependencies"]:
            print("Blocking dependencies:")
            for blocker in report["blocking_dependencies"]:
                print(f"- {blocker}")
        if report["missing_representative_providers"]:
            print(
                "Representative provider coverage still missing: "
                + ", ".join(report["missing_representative_providers"])
            )
        print("--- machine-readable evidence ---")
    print(json.dumps(report, indent=2, sort_keys=True, default=str))

    if report["status"] in {"BLOCKED_EXTERNAL_CONFIGURATION", "PARTIAL_STAGING_ACCEPTANCE"}:
        if not args.allow_blocked:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
