from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import candidate_context
from app.api.career_product import _match_payload
from app.models import (
    Company,
    Job,
    JobCompensation,
    JobLocation,
    JobRequirement,
    JobSkill,
    JobSource,
    JobSourceLink,
    User,
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def build_career_ai_context(session: Session, user: User, job: Job) -> dict[str, Any]:
    candidate = candidate_context(session, user)
    profile = candidate["profile"]
    preference = candidate["preference"]
    company = session.get(Company, job.company_id)
    locations = list(
        session.scalars(
            select(JobLocation).where(JobLocation.job_id == job.id).order_by(JobLocation.id)
        )
    )
    compensation = session.scalar(
        select(JobCompensation)
        .where(JobCompensation.job_id == job.id)
        .order_by(JobCompensation.id)
        .limit(1)
    )
    skills = list(
        session.scalars(
            select(JobSkill)
            .where(JobSkill.job_id == job.id)
            .order_by(JobSkill.required.desc(), JobSkill.name)
        )
    )
    requirements = list(
        session.scalars(
            select(JobRequirement)
            .where(JobRequirement.job_id == job.id)
            .order_by(JobRequirement.required.desc(), JobRequirement.id)
        )
    )
    source_url = session.scalar(
        select(JobSource.source_url)
        .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
        .where(JobSourceLink.job_id == job.id)
        .order_by(JobSourceLink.is_primary.desc())
        .limit(1)
    )

    evidence: dict[str, str] = {
        "job.title": job.title,
        "job.description": job.description,
    }
    if company:
        evidence["job.company"] = company.canonical_name
    if source_url:
        evidence["job.source_url"] = source_url
    if profile:
        if profile.current_title:
            evidence["candidate.current_title"] = profile.current_title
        if profile.headline:
            evidence["candidate.headline"] = profile.headline
        if profile.summary:
            evidence["candidate.summary"] = profile.summary
        if profile.years_experience is not None:
            evidence["candidate.years_experience"] = str(profile.years_experience)
    for item in candidate["experiences"]:
        evidence[f"candidate.experience.{item.id}"] = " | ".join(
            part
            for part in [item.company_name, item.title, item.description or ""]
            if part
        )
    for item in candidate["skills"]:
        evidence[f"candidate.skill.{item.id}"] = item.name
    for item in candidate["roles"]:
        evidence[f"candidate.target_role.{item.id}"] = item.title
    if preference:
        if preference.location_text:
            evidence["candidate.preference.location"] = preference.location_text
        if preference.work_modes:
            evidence["candidate.preference.work_modes"] = ", ".join(preference.work_modes)
        if preference.minimum_compensation is not None:
            evidence["candidate.preference.minimum_compensation"] = (
                f"{preference.minimum_compensation} {preference.currency}"
            )
    for item in locations:
        evidence[f"job.location.{item.id}"] = f"{item.location_text} | {item.work_mode}"
    for item in skills:
        evidence[f"job.skill.{item.id}"] = (
            f"{item.name} | {'required' if item.required else 'preferred'}"
        )
    for item in requirements:
        evidence[f"job.requirement.{item.id}"] = (
            f"{item.category} | {item.text} | {'required' if item.required else 'preferred'}"
        )
    if compensation:
        evidence[f"job.compensation.{compensation.id}"] = (
            f"{compensation.minimum or ''}-{compensation.maximum or ''} "
            f"{compensation.currency}/{compensation.interval}"
        )

    context = {
        "candidate": {
            "profile_id": str(profile.id) if profile else None,
            "headline": profile.headline if profile else None,
            "current_title": profile.current_title if profile else None,
            "summary": profile.summary if profile else None,
            "years_experience": profile.years_experience if profile else None,
            "target_roles": [
                {"id": str(item.id), "title": item.title, "priority": item.priority}
                for item in candidate["roles"]
            ],
            "skills": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "proficiency": item.proficiency,
                    "provenance": item.provenance,
                }
                for item in candidate["skills"]
            ],
            "experiences": [
                {
                    "id": str(item.id),
                    "company_name": item.company_name,
                    "title": item.title,
                    "start_date": item.start_date.isoformat() if item.start_date else None,
                    "end_date": item.end_date.isoformat() if item.end_date else None,
                    "description": item.description,
                    "provenance": item.provenance,
                }
                for item in candidate["experiences"]
            ],
            "preference": {
                "location_text": preference.location_text,
                "work_modes": preference.work_modes,
                "employment_types": preference.employment_types,
                "minimum_compensation": preference.minimum_compensation,
                "currency": preference.currency,
                "relocation_open": preference.relocation_open,
            }
            if preference
            else None,
        },
        "job": {
            "id": str(job.id),
            "title": job.title,
            "company_name": company.canonical_name if company else "Unknown company",
            "description": job.description,
            "employment_type": job.employment_type,
            "seniority": job.seniority,
            "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            "last_seen_at": job.last_seen_at.isoformat(),
            "source_url": source_url,
            "locations": [
                {
                    "id": str(item.id),
                    "location_text": item.location_text,
                    "city": item.city,
                    "region": item.region,
                    "country_code": item.country_code,
                    "work_mode": item.work_mode,
                }
                for item in locations
            ],
            "skills": [
                {"id": str(item.id), "name": item.name, "required": item.required}
                for item in skills
            ],
            "requirements": [
                {
                    "id": str(item.id),
                    "category": item.category,
                    "text": item.text,
                    "required": item.required,
                }
                for item in requirements
            ],
            "compensation": {
                "minimum": compensation.minimum,
                "maximum": compensation.maximum,
                "currency": compensation.currency,
                "interval": compensation.interval,
            }
            if compensation
            else None,
        },
        "deterministic_match": _match_payload(session, user, job),
        "evidence_catalog": evidence,
    }
    return _json_safe(context)


def get_owned_active_job(session: Session, job_id: uuid.UUID) -> Job | None:
    return session.scalar(select(Job).where(Job.id == job_id, Job.status == "ACTIVE"))
