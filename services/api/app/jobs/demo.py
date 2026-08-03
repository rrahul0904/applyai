from __future__ import annotations

import html
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import job_quality_models, job_source_models  # noqa: F401
from app.durability_models import JobIngestionRun
from app.job_quality_models import JobFieldProvenance
from app.job_source_models import JobSourceRegistry
from app.jobs.connectors import ConnectorHealth, JobSourceConnector, NormalizedJob
from app.jobs.contracts import JobSourceType, RawJobPosting
from app.jobs.source_pipeline import RegisteredSourceIngestionPipeline
from app.models import (
    Company,
    CompanySource,
    Job,
    JobCompensation,
    JobLocation,
    JobSource,
    JobSourceLink,
    JobVersion,
    RawJobPosting as RawJobPostingModel,
)

DEMO_COMPANY = "Atlas Demo Labs"
DEMO_SOURCE_IDENTITIES = {
    "GREENHOUSE": "demo-atlas-greenhouse",
    "LEVER": "demo-atlas-lever",
    "ASHBY": "demo-atlas-ashby",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DemoSourceConnector(JobSourceConnector):
    """Deterministic connector that exercises the real registered-source pipeline."""

    def __init__(
        self,
        source_type: JobSourceType,
        source_identity: str,
        records: list[dict[str, Any]],
    ) -> None:
        self.source_type = source_type
        self.source_identity = source_identity
        self.records = [dict(record) for record in records]
        self.key = source_type.value.lower()

    def source_company_identity(self) -> str:
        return self.source_identity

    def fetch(self, checkpoint: dict[str, Any] | None) -> list[dict[str, Any]]:
        del checkpoint
        return [dict(record) for record in self.records]

    def to_raw(self, payload: dict[str, Any]) -> RawJobPosting:
        return RawJobPosting(
            source_type=self.source_type,
            source_name=self.key,
            source_company_identity=self.source_identity,
            source_job_identity=f"{self.source_identity}:{payload['id']}",
            external_job_id=f"{self.source_identity}:{payload['id']}",
            internal_job_id=payload.get("internal_job_id"),
            company_domain="atlas-demo.example",
            company_name=str(payload["company_name"]),
            title=str(payload["title"]),
            description=str(payload["description"]),
            source_url=str(payload["source_url"]),
            apply_url=str(payload["apply_url"]),
            location_text=str(payload.get("location") or "Location not specified"),
            locations=(str(payload.get("location") or "Location not specified"),),
            employment_type=str(payload.get("employment_type") or "FULL_TIME"),
            workplace_type=str(payload.get("work_mode") or "REMOTE"),
            seniority=str(payload.get("seniority") or "MID"),
            salary_min=payload.get("salary_min"),
            salary_max=payload.get("salary_max"),
            salary_currency="USD",
            salary_interval="YEAR",
            salary_provenance=f"{self.source_type.value}_PUBLIC_DEMO_FIXTURE",
            date_posted=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc),
            fetched_at=utcnow(),
            raw_payload=dict(payload),
            source_metadata={
                "provider": self.source_type.value,
                "fixture": True,
                "team": payload.get("team", "Data Platform"),
            },
            skills=tuple(payload.get("skills", [])),
            requirements=tuple(payload.get("requirements", [])),
        )

    def normalize(self, payload: dict[str, Any]) -> NormalizedJob:
        raw = self.to_raw(payload)
        normalized_payload = dict(payload)
        normalized_payload["data_origin"] = f"{self.source_type.value}_DEMO_FIXTURE"
        return NormalizedJob(
            external_job_id=raw.external_job_id,
            company_name=raw.company_name,
            title=raw.title,
            description=raw.description,
            application_url=raw.apply_url,
            locations=list(raw.locations),
            work_mode=raw.workplace_type,
            employment_type=raw.employment_type,
            seniority=raw.seniority,
            salary_min=raw.salary_min,
            salary_max=raw.salary_max,
            salary_provenance=raw.salary_provenance,
            skills=list(raw.skills),
            requirements=list(raw.requirements),
            posted_at=raw.date_posted,
            raw_payload=normalized_payload,
        )

    def checkpoint(self) -> dict[str, Any]:
        return {"count": len(self.records), "fixture": True}

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(True, utcnow(), "Deterministic demo connector ready")


def _description(role: str) -> str:
    return (
        f"Build and operate {role} capabilities for a production hiring platform. "
        "Partner with data, platform, security, and product teams to deliver reliable "
        "candidate experiences, measurable quality, and explainable operational decisions."
    )


def _posting(
    *,
    posting_id: str,
    title: str,
    provider: str,
    location: str = "Remote - United States",
    internal_job_id: str | None = None,
    salary_min: int = 150_000,
    salary_max: int = 190_000,
    description: str | None = None,
) -> dict[str, Any]:
    provider_slug = provider.lower()
    return {
        "id": posting_id,
        "internal_job_id": internal_job_id,
        "company_name": DEMO_COMPANY,
        "title": title,
        "description": description or _description(title.lower()),
        "location": location,
        "source_url": f"https://jobs.{provider_slug}.example/atlas/{posting_id}",
        "apply_url": f"https://jobs.{provider_slug}.example/atlas/{posting_id}/apply",
        "employment_type": "FULL_TIME",
        "work_mode": "REMOTE" if "Remote" in location else "HYBRID",
        "seniority": "SENIOR" if "Senior" in title else "MID",
        "salary_min": salary_min,
        "salary_max": salary_max,
        "skills": ["Python", "SQL", "Data Platforms"],
        "requirements": ["Production systems experience", "Strong communication"],
        "team": "Data Platform",
    }


def demo_records() -> dict[str, list[dict[str, Any]]]:
    shared_description = _description("shared senior data engineering")
    shared = {
        provider: _posting(
            posting_id=f"shared-{provider.lower()}",
            title="Senior Data Engineer",
            provider=provider,
            internal_job_id="ATLAS-REQ-42",
            description=shared_description,
            salary_min=165_000,
            salary_max=205_000,
        )
        for provider in ("GREENHOUSE", "LEVER", "ASHBY")
    }
    invalid = {
        "id": "invalid-ashby",
        "internal_job_id": None,
        "company_name": DEMO_COMPANY,
        "title": "-",
        "description": "short",
        "location": "Unknown",
        "source_url": "not-a-url",
        "apply_url": "file:///tmp/not-allowed",
        "employment_type": "UNKNOWN",
        "work_mode": "UNKNOWN",
        "seniority": "UNKNOWN",
        "salary_min": None,
        "salary_max": None,
        "skills": [],
        "requirements": [],
    }
    return {
        "GREENHOUSE": [
            shared["GREENHOUSE"],
            _posting(
                posting_id="analytics-engineer-gh",
                title="Analytics Engineer",
                provider="GREENHOUSE",
                location="Boston, MA",
                internal_job_id="ATLAS-REQ-51",
                salary_min=135_000,
                salary_max=170_000,
            ),
        ],
        "LEVER": [
            shared["LEVER"],
            _posting(
                posting_id="data-product-manager-lever",
                title="Data Platform Product Manager",
                provider="LEVER",
                location="New York, NY",
                internal_job_id="ATLAS-REQ-63",
                salary_min=145_000,
                salary_max=180_000,
            ),
        ],
        "ASHBY": [
            shared["ASHBY"],
            _posting(
                posting_id="platform-engineer-ashby",
                title="Platform Engineer",
                provider="ASHBY",
                location="Remote - United States",
                internal_job_id="ATLAS-REQ-77",
                salary_min=155_000,
                salary_max=195_000,
            ),
            invalid,
        ],
    }


def reset_demo_data(session: Session) -> None:
    registries = list(
        session.scalars(
            select(JobSourceRegistry).where(
                JobSourceRegistry.source_identity.in_(DEMO_SOURCE_IDENTITIES.values())
            )
        )
    )
    registry_ids = [str(item.id) for item in registries]
    posting_sources: list[JobSource] = []
    if registry_ids:
        posting_sources = list(
            session.scalars(
                select(JobSource).where(
                    JobSource.checkpoint["source_registry_id"].astext.in_(registry_ids)
                )
            )
        )
    source_ids = [item.id for item in posting_sources]
    job_ids: set[uuid.UUID] = set()
    if source_ids:
        job_ids.update(
            session.scalars(
                select(JobSourceLink.job_id).where(JobSourceLink.job_source_id.in_(source_ids))
            )
        )
    if job_ids:
        session.execute(delete(Job).where(Job.id.in_(job_ids)))
    if source_ids:
        session.execute(delete(JobSource).where(JobSource.id.in_(source_ids)))
    if registries:
        registry_uuid_ids = [item.id for item in registries]
        session.execute(delete(JobIngestionRun).where(JobIngestionRun.source_id.in_(registry_uuid_ids)))
        session.execute(delete(JobSourceRegistry).where(JobSourceRegistry.id.in_(registry_uuid_ids)))
    session.execute(
        delete(CompanySource).where(
            CompanySource.external_company_id.in_(DEMO_SOURCE_IDENTITIES.values())
        )
    )
    session.commit()


def _registry(provider: str) -> JobSourceRegistry:
    trust = {
        "GREENHOUSE": "EMPLOYER_DIRECT",
        "LEVER": "OFFICIAL_ATS",
        "ASHBY": "THIRD_PARTY_SOURCE",
    }[provider]
    priority = {"GREENHOUSE": 100, "LEVER": 80, "ASHBY": 40}[provider]
    identity = DEMO_SOURCE_IDENTITIES[provider]
    return JobSourceRegistry(
        source_type=provider,
        source_name=f"{DEMO_COMPANY} — {provider.title()}",
        source_identity=identity,
        base_url=f"https://jobs.{provider.lower()}.example/atlas",
        careers_url="https://atlas-demo.example/careers",
        configuration={"fixture": True, "provider": provider},
        trust_level=trust,
        priority=priority,
        enabled=True,
        crawl_allowed=True,
        health_status="HEALTHY",
        crawl_interval_seconds=3600,
        min_interval_seconds=900,
        max_interval_seconds=86_400,
        next_run_at=utcnow(),
    )


def build_demo(session: Session) -> dict[str, Any]:
    reset_demo_data(session)
    records = demo_records()
    registries = {provider: _registry(provider) for provider in records}
    session.add_all(registries.values())
    session.commit()

    pipeline = RegisteredSourceIngestionPipeline(session)
    initial_runs: list[dict[str, Any]] = []
    for provider in ("GREENHOUSE", "LEVER", "ASHBY"):
        source_type = JobSourceType(provider)
        counts = pipeline.run(
            registries[provider],
            DemoSourceConnector(source_type, DEMO_SOURCE_IDENTITIES[provider], records[provider]),
        )
        initial_runs.append({"provider": provider, "counts": counts})

    # Prove that one source disappearing does not retire a multi-source canonical job.
    lever_unique_only = [records["LEVER"][1]]
    lifecycle_counts = pipeline.run(
        registries["LEVER"],
        DemoSourceConnector(
            JobSourceType.LEVER,
            DEMO_SOURCE_IDENTITIES["LEVER"],
            lever_unique_only,
        ),
    )

    jobs = list(
        session.execute(
            select(Job, Company)
            .join(Company, Company.id == Job.company_id)
            .where(Company.normalized_name == DEMO_COMPANY.lower())
            .order_by(Job.title)
        )
    )
    canonical_jobs: list[dict[str, Any]] = []
    for job, company in jobs:
        location = session.scalar(
            select(JobLocation).where(JobLocation.job_id == job.id).order_by(JobLocation.id).limit(1)
        )
        compensation = session.scalar(
            select(JobCompensation)
            .where(JobCompensation.job_id == job.id)
            .order_by(JobCompensation.id)
            .limit(1)
        )
        links = list(
            session.execute(
                select(JobSourceLink, JobSource)
                .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
                .where(JobSourceLink.job_id == job.id)
                .order_by(JobSource.connector_key)
            )
        )
        source_rows: list[dict[str, Any]] = []
        for link, source in links:
            checkpoint = dict(source.checkpoint or {})
            registry = session.get(JobSourceRegistry, checkpoint.get("source_registry_id"))
            source_rows.append(
                {
                    "provider": checkpoint.get("source_type") or source.connector_key.upper(),
                    "trust_level": registry.trust_level if registry else "UNVERIFIED",
                    "is_primary": link.is_primary,
                    "dedup_reason": checkpoint.get("dedup_reason") or "SOURCE_IDENTITY",
                    "validation_status": checkpoint.get("validation_status") or "UNKNOWN",
                    "miss_count": int(checkpoint.get("miss_count") or 0),
                    "source_url": checkpoint.get("source_url") or source.source_url,
                    "apply_url": source.source_url,
                }
            )
        provenance = [
            {
                "field": item.field_name,
                "selection_reason": item.selection_reason,
            }
            for item in session.scalars(
                select(JobFieldProvenance)
                .where(JobFieldProvenance.job_id == job.id)
                .order_by(JobFieldProvenance.field_name)
            )
        ]
        version_count = len(
            list(session.scalars(select(JobVersion.id).where(JobVersion.job_id == job.id)))
        )
        canonical_jobs.append(
            {
                "id": str(job.id),
                "company": company.canonical_name,
                "title": job.title,
                "status": job.status,
                "location": location.location_text if location else "Unknown",
                "work_mode": location.work_mode if location else "UNKNOWN",
                "salary": {
                    "minimum": compensation.minimum if compensation else None,
                    "maximum": compensation.maximum if compensation else None,
                    "currency": compensation.currency if compensation else None,
                },
                "source_count": len(source_rows),
                "version_count": version_count,
                "sources": source_rows,
                "provenance": provenance,
            }
        )

    source_cards = []
    for provider in ("GREENHOUSE", "LEVER", "ASHBY"):
        registry = registries[provider]
        session.refresh(registry)
        latest_run = session.scalar(
            select(JobIngestionRun)
            .where(JobIngestionRun.source_id == registry.id)
            .order_by(JobIngestionRun.started_at.desc())
            .limit(1)
        )
        source_cards.append(
            {
                "provider": provider,
                "source_name": registry.source_name,
                "trust_level": registry.trust_level,
                "health_status": registry.health_status,
                "priority": registry.priority,
                "last_job_count": registry.last_job_count,
                "latest_run": {
                    "status": latest_run.status if latest_run else "UNKNOWN",
                    "fetched": latest_run.fetched if latest_run else 0,
                    "valid": latest_run.valid if latest_run else 0,
                    "invalid": latest_run.invalid if latest_run else 0,
                    "deduplicated": latest_run.deduplicated if latest_run else 0,
                    "duration_ms": latest_run.duration_ms if latest_run else None,
                },
            }
        )

    invalid_count = len(
        list(
            session.scalars(
                select(RawJobPostingModel.id).where(
                    RawJobPostingModel.normalization_status == "INVALID"
                )
            )
        )
    )
    shared_job = next(job for job in canonical_jobs if job["title"] == "Senior Data Engineer")
    totals = {
        "provider_sources": len(source_cards),
        "source_postings": sum(item["counts"]["valid"] for item in initial_runs),
        "canonical_jobs": len(canonical_jobs),
        "deduplicated_postings": sum(
            item["counts"]["deduplicated"] for item in initial_runs
        ),
        "invalid_quarantined": invalid_count,
        "shared_job_sources": shared_job["source_count"],
    }
    assertions = {
        "three_providers_registered": totals["provider_sources"] == 3,
        "six_valid_source_postings": totals["source_postings"] == 6,
        "four_canonical_jobs": totals["canonical_jobs"] == 4,
        "shared_job_deduplicated": shared_job["source_count"] == 3,
        "primary_source_is_greenhouse": any(
            source["provider"] == "GREENHOUSE" and source["is_primary"]
            for source in shared_job["sources"]
        ),
        "missing_lever_copy_did_not_retire_job": shared_job["status"] == "ACTIVE",
        "invalid_record_retained": invalid_count >= 1,
        "field_provenance_recorded": len(shared_job["provenance"]) >= 7,
    }
    if not all(assertions.values()):
        failures = [name for name, passed in assertions.items() if not passed]
        raise RuntimeError(f"Job-source demo assertions failed: {', '.join(failures)}")

    return {
        "title": "ApplyAI Multi-Source Job Platform Demo",
        "generated_at": utcnow().isoformat(),
        "company": DEMO_COMPANY,
        "totals": totals,
        "assertions": assertions,
        "source_cards": source_cards,
        "initial_runs": initial_runs,
        "lifecycle_run": {
            "provider": "LEVER",
            "scenario": "Shared posting absent while Greenhouse and Ashby remain fresh",
            "counts": lifecycle_counts,
            "canonical_job_status": shared_job["status"],
        },
        "canonical_jobs": canonical_jobs,
        "shared_job": shared_job,
        "architecture": [
            "Provider fixtures",
            "Registered source validation",
            "Canonical ingestion",
            "Deduplication",
            "Authority selection",
            "Field provenance",
            "Candidate-visible jobs",
        ],
        "scope": {
            "real_pipeline": True,
            "real_postgresql": True,
            "live_provider_calls": False,
            "aws_required": False,
            "external_accounts_required": False,
        },
    }


def _money(value: int | None) -> str:
    return "—" if value is None else f"${value:,.0f}"


def render_demo_html(report: dict[str, Any]) -> str:
    totals = report["totals"]
    source_cards = "".join(
        f"""
        <article class="source-card">
          <div class="source-head"><span class="provider provider-{item['provider'].lower()}">{item['provider']}</span><span class="health">{item['health_status']}</span></div>
          <h3>{html.escape(item['source_name'])}</h3>
          <p>{item['trust_level'].replace('_', ' ').title()} · priority {item['priority']}</p>
          <div class="mini-grid"><span>Fetched <strong>{item['latest_run']['fetched']}</strong></span><span>Valid <strong>{item['latest_run']['valid']}</strong></span><span>Invalid <strong>{item['latest_run']['invalid']}</strong></span><span>Deduped <strong>{item['latest_run']['deduplicated']}</strong></span></div>
        </article>
        """
        for item in report["source_cards"]
    )
    job_rows = "".join(
        f"""
        <tr>
          <td><strong>{html.escape(job['title'])}</strong><small>{html.escape(job['company'])}</small></td>
          <td><span class="status status-{job['status'].lower()}">{job['status']}</span></td>
          <td>{html.escape(job['location'])}<small>{job['work_mode']}</small></td>
          <td>{_money(job['salary']['minimum'])}–{_money(job['salary']['maximum'])}</td>
          <td>{job['source_count']}</td>
          <td>{job['version_count']}</td>
        </tr>
        """
        for job in report["canonical_jobs"]
    )
    shared = report["shared_job"]
    source_rows = "".join(
        f"""
        <tr>
          <td><span class="provider provider-{source['provider'].lower()}">{source['provider']}</span></td>
          <td>{source['trust_level'].replace('_', ' ').title()}</td>
          <td>{'Primary' if source['is_primary'] else 'Linked'}</td>
          <td>{source['dedup_reason'].replace('_', ' ').title()}</td>
          <td>{source['miss_count']}</td>
        </tr>
        """
        for source in shared["sources"]
    )
    provenance_rows = "".join(
        f"<tr><td>{item['field'].replace('_', ' ').title()}</td><td>{item['selection_reason'].replace('_', ' ')}</td></tr>"
        for item in shared["provenance"]
    )
    checks = "".join(
        f"<li><span>✓</span>{name.replace('_', ' ').title()}</li>"
        for name, passed in report["assertions"].items()
        if passed
    )
    flow = "".join(
        f"<div class="flow-step"><span>{index}</span><strong>{html.escape(label)}</strong></div>"
        for index, label in enumerate(report["architecture"], start=1)
    )
    payload = json.dumps(report, sort_keys=True).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{html.escape(report['title'])}</title>
<style>
:root{{--bg:#07111f;--panel:#0d1c2e;--panel2:#12253b;--text:#eef6ff;--muted:#9eb2c8;--line:#263b51;--accent:#78e6c4;--blue:#77bdfb;--amber:#ffc86b;--red:#ff8d8d}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at top right,#153458 0,#07111f 42%);color:var(--text);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}}
button{{font:inherit}}.shell{{max-width:1420px;margin:0 auto;padding:32px}}.eyebrow{{color:var(--accent);text-transform:uppercase;letter-spacing:.16em;font-weight:800;font-size:12px}}h1{{font-size:48px;line-height:1.05;margin:8px 0 14px;max-width:900px}}.lede{{color:var(--muted);font-size:18px;max-width:900px}}.tabs{{display:flex;gap:10px;margin:28px 0 22px;position:sticky;top:0;padding:12px 0;background:rgba(7,17,31,.9);backdrop-filter:blur(14px);z-index:3}}.tab{{border:1px solid var(--line);background:var(--panel);color:var(--muted);padding:10px 16px;border-radius:999px;cursor:pointer}}.tab.active{{background:var(--accent);color:#052019;border-color:var(--accent);font-weight:800}}.view{{display:none}}.view.active{{display:block}}.metric-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:14px;margin:24px 0}}.metric,.source-card,.panel{{background:linear-gradient(145deg,rgba(18,37,59,.95),rgba(10,25,42,.95));border:1px solid var(--line);border-radius:18px;box-shadow:0 16px 50px rgba(0,0,0,.18)}}.metric{{padding:18px}}.metric span{{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.08em}}.metric strong{{display:block;font-size:30px;margin-top:6px}}.source-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}}.source-card{{padding:20px}}.source-head{{display:flex;align-items:center;justify-content:space-between}}.source-card h3{{font-size:19px;margin:16px 0 3px}}.source-card p{{color:var(--muted);margin:0 0 16px}}.provider,.health,.status{{display:inline-flex;border-radius:999px;padding:5px 10px;font-size:11px;font-weight:900;letter-spacing:.06em}}.provider-greenhouse{{background:#dbffe9;color:#0d6a37}}.provider-lever{{background:#e4e8ff;color:#4f4db1}}.provider-ashby{{background:#fff0d5;color:#925b00}}.health{{background:rgba(120,230,196,.14);color:var(--accent)}}.status-active{{background:rgba(120,230,196,.15);color:var(--accent)}}.mini-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;color:var(--muted)}}.mini-grid span{{background:rgba(255,255,255,.035);padding:8px;border-radius:10px}}.mini-grid strong{{color:var(--text);float:right}}.panel{{padding:24px;margin-top:20px}}.panel h2{{font-size:24px;margin:0 0 4px}}.panel-sub{{color:var(--muted);margin:0 0 18px}}table{{width:100%;border-collapse:collapse}}th{{text-align:left;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em;padding:12px;border-bottom:1px solid var(--line)}}td{{padding:15px 12px;border-bottom:1px solid rgba(38,59,81,.7);vertical-align:top}}td small{{display:block;color:var(--muted);margin-top:2px}}.flow{{display:grid;grid-template-columns:repeat(7,1fr);gap:10px;margin:20px 0}}.flow-step{{position:relative;background:var(--panel);border:1px solid var(--line);padding:16px;border-radius:14px;min-height:92px}}.flow-step span{{display:block;color:var(--accent);font-weight:900;margin-bottom:8px}}.flow-step:not(:last-child):after{{content:"→";position:absolute;right:-10px;top:35px;color:var(--blue);z-index:2}}.split{{display:grid;grid-template-columns:1.35fr .65fr;gap:20px}}.checks{{list-style:none;padding:0;margin:0;display:grid;gap:8px}}.checks li{{background:rgba(255,255,255,.035);padding:11px 13px;border-radius:10px}}.checks span{{color:var(--accent);font-weight:900;margin-right:9px}}.callout{{border-left:4px solid var(--amber);padding:16px 18px;background:rgba(255,200,107,.08);border-radius:0 14px 14px 0;color:#ffe1a6}}.scope{{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}}.scope span{{border:1px solid var(--line);padding:7px 10px;border-radius:999px;color:var(--muted)}}.footer{{color:var(--muted);margin:28px 0 8px;font-size:13px}}@media(max-width:1000px){{.metric-grid{{grid-template-columns:repeat(3,1fr)}}.source-grid,.split{{grid-template-columns:1fr}}.flow{{grid-template-columns:1fr 1fr}}h1{{font-size:38px}}}}@media(max-width:600px){{.shell{{padding:20px}}.metric-grid{{grid-template-columns:1fr 1fr}}.flow{{grid-template-columns:1fr}}.tabs{{overflow:auto}}}}
</style>
</head>
<body>
<main class="shell">
  <div class="eyebrow">Deterministic PostgreSQL-backed demonstration</div>
  <h1>One trusted job catalog from three provider sources.</h1>
  <p class="lede">This artifact is generated by the real ApplyAI registered-source pipeline. It validates records, persists raw payloads, creates canonical jobs, links duplicates, selects a primary source, records field provenance, and evaluates multi-source freshness.</p>
  <nav class="tabs" aria-label="Demo views">
    <button class="tab active" data-tab="overview">Platform overview</button>
    <button class="tab" data-tab="provenance">Dedup & provenance</button>
    <button class="tab" data-tab="evidence">Execution evidence</button>
  </nav>

  <section id="overview" class="view active">
    <div class="metric-grid">
      <div class="metric"><span>Providers</span><strong>{totals['provider_sources']}</strong></div>
      <div class="metric"><span>Valid postings</span><strong>{totals['source_postings']}</strong></div>
      <div class="metric"><span>Canonical jobs</span><strong>{totals['canonical_jobs']}</strong></div>
      <div class="metric"><span>Deduplicated</span><strong>{totals['deduplicated_postings']}</strong></div>
      <div class="metric"><span>Invalid retained</span><strong>{totals['invalid_quarantined']}</strong></div>
      <div class="metric"><span>Sources on shared job</span><strong>{totals['shared_job_sources']}</strong></div>
    </div>
    <div class="source-grid">{source_cards}</div>
    <div class="panel">
      <h2>Canonical candidate catalog</h2><p class="panel-sub">Six valid provider postings become four candidate-visible jobs.</p>
      <table><thead><tr><th>Job</th><th>Status</th><th>Location</th><th>Compensation</th><th>Sources</th><th>Versions</th></tr></thead><tbody>{job_rows}</tbody></table>
    </div>
    <div class="panel"><h2>Data flow</h2><p class="panel-sub">Every step below executes during artifact generation.</p><div class="flow">{flow}</div></div>
  </section>

  <section id="provenance" class="view">
    <div class="panel">
      <h2>Shared canonical job: {html.escape(shared['title'])}</h2>
      <p class="panel-sub">Three provider records converge on one active job. The highest-authority source owns candidate-facing fields.</p>
      <table><thead><tr><th>Provider</th><th>Trust</th><th>Role</th><th>Dedup reason</th><th>Miss count</th></tr></thead><tbody>{source_rows}</tbody></table>
    </div>
    <div class="split">
      <div class="panel"><h2>Field-level provenance</h2><p class="panel-sub">The selected source is recorded for each canonical field.</p><table><thead><tr><th>Field</th><th>Selection reason</th></tr></thead><tbody>{provenance_rows}</tbody></table></div>
      <div class="panel"><h2>Freshness result</h2><p class="panel-sub">Lever omitted the shared posting on a later run.</p><div class="callout"><strong>Canonical status: {report['lifecycle_run']['canonical_job_status']}</strong><br/>The job stays active because Greenhouse and Ashby remain fresh. One missing source cannot retire a multi-source job.</div><div class="scope"><span>Lever miss count: 1</span><span>Greenhouse: primary</span><span>Ashby: linked</span></div></div>
    </div>
  </section>

  <section id="evidence" class="view">
    <div class="split">
      <div class="panel"><h2>Acceptance checks</h2><p class="panel-sub">Artifact generation fails when any check below is false.</p><ul class="checks">{checks}</ul></div>
      <div class="panel"><h2>Demo boundaries</h2><p class="panel-sub">Clear separation between executed behavior and intentionally excluded external services.</p><ul class="checks"><li><span>✓</span>Real SQLAlchemy models and PostgreSQL</li><li><span>✓</span>Real registered-source ingestion pipeline</li><li><span>✓</span>Real validation, dedup, authority, freshness and provenance</li><li><span>✓</span>No AWS account required</li><li><span>✓</span>No live provider or anti-bot interaction</li></ul></div>
    </div>
    <div class="panel"><h2>Machine-readable report</h2><p class="panel-sub">The workflow publishes this page, screenshots, and <code>report.json</code> as one artifact.</p><pre style="white-space:pre-wrap;color:#b9d2eb;background:#07111f;padding:18px;border-radius:12px;max-height:360px;overflow:auto">{html.escape(json.dumps(report['totals'], indent=2))}</pre></div>
  </section>
  <p class="footer">Generated {html.escape(report['generated_at'])} · deterministic provider fixtures · no external accounts or network calls</p>
</main>
<script id="demo-report" type="application/json">{payload}</script>
<script>
for (const button of document.querySelectorAll('.tab')) {{
  button.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach((item) => item.classList.remove('active'));
    document.querySelectorAll('.view').forEach((item) => item.classList.remove('active'));
    button.classList.add('active');
    document.getElementById(button.dataset.tab).classList.add('active');
  }});
}}
</script>
</body>
</html>"""


def write_demo_artifact(session: Session, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_demo(session)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    (output_dir / "index.html").write_text(render_demo_html(report), encoding="utf-8")
    return report
