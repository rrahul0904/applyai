from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_models import AgentArtifact
from app.career_memory_models import CandidateCareerFact
from app.models import (
    Application,
    CandidateEducation,
    CandidateExperience,
    CandidatePreference,
    CandidateProfile,
    CandidateSkill,
    CandidateTargetRole,
    Company,
    Job,
    JobCompensation,
    JobLocation,
    JobRequirement,
    JobSkill,
    JobSource,
    JobSourceLink,
    Resume,
    ResumeExtraction,
    ResumeVersion,
)


ToolHandler = Callable[[Session, uuid.UUID, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    version: str
    execution_class: str
    handler: ToolHandler
    sensitive: bool = True
    audit_required: bool = True


def _uuid(value: Any, *, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {field}") from exc


def candidate_profile_read(session: Session, candidate_id: uuid.UUID, _args: dict[str, Any]) -> dict[str, Any]:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == candidate_id))
    preference = session.scalar(select(CandidatePreference).where(CandidatePreference.user_id == candidate_id))
    targets = list(session.scalars(select(CandidateTargetRole).where(CandidateTargetRole.user_id == candidate_id)))
    return {
        "profile_id": str(profile.id) if profile else None,
        "headline": profile.headline if profile else None,
        "current_title": profile.current_title if profile else None,
        "summary": profile.summary if profile else None,
        "years_experience": profile.years_experience if profile else None,
        "preferences": {
            "location_text": preference.location_text,
            "work_modes": preference.work_modes,
            "employment_types": preference.employment_types,
            "minimum_compensation": preference.minimum_compensation,
            "currency": preference.currency,
            "relocation_open": preference.relocation_open,
        } if preference else {},
        "target_roles": [
            {"title": row.title, "normalized_title": row.normalized_title, "priority": row.priority}
            for row in targets
        ],
    }


def candidate_evidence_read(session: Session, candidate_id: uuid.UUID, _args: dict[str, Any]) -> dict[str, Any]:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == candidate_id))
    if profile is None:
        return {"experiences": [], "education": [], "skills": [], "evidence_catalog": {}}
    experiences = list(session.scalars(select(CandidateExperience).where(CandidateExperience.profile_id == profile.id)))
    education = list(session.scalars(select(CandidateEducation).where(CandidateEducation.profile_id == profile.id)))
    skills = list(session.scalars(select(CandidateSkill).where(CandidateSkill.profile_id == profile.id)))
    catalog: dict[str, dict[str, Any]] = {}
    exp_payload = []
    for row in experiences:
        ref = f"experience:{row.id}"
        catalog[ref] = {"kind": "experience", "provenance": row.provenance}
        exp_payload.append({
            "id": str(row.id), "company_name": row.company_name, "title": row.title,
            "start_date": str(row.start_date) if row.start_date else None,
            "end_date": str(row.end_date) if row.end_date else None,
            "description": row.description, "provenance": row.provenance, "evidence_ref": ref,
        })
    edu_payload = []
    for row in education:
        ref = f"education:{row.id}"
        catalog[ref] = {"kind": "education", "provenance": row.provenance}
        edu_payload.append({
            "id": str(row.id), "institution": row.institution, "degree": row.degree,
            "field_of_study": row.field_of_study, "provenance": row.provenance, "evidence_ref": ref,
        })
    skill_payload = []
    for row in skills:
        ref = f"skill:{row.id}"
        catalog[ref] = {"kind": "skill", "provenance": row.provenance}
        skill_payload.append({
            "id": str(row.id), "name": row.name, "normalized_name": row.normalized_name,
            "proficiency": row.proficiency, "provenance": row.provenance, "evidence_ref": ref,
        })
    if profile.summary:
        catalog[f"profile:{profile.id}:summary"] = {"kind": "profile_summary", "provenance": "USER_VERIFIED"}
    return {"experiences": exp_payload, "education": edu_payload, "skills": skill_payload, "evidence_catalog": catalog}


def career_memory_read(session: Session, candidate_id: uuid.UUID, _args: dict[str, Any]) -> dict[str, Any]:
    rows = list(session.scalars(
        select(CandidateCareerFact)
        .where(CandidateCareerFact.user_id == candidate_id, CandidateCareerFact.archived_at.is_(None))
        .order_by(CandidateCareerFact.updated_at.desc())
        .limit(100)
    ))
    return {"facts": [
        {"id": str(row.id), "category": row.category, "title": row.title, "fact_text": row.fact_text,
         "source_kind": row.source_kind, "source_ref": row.source_ref, "provenance": row.provenance,
         "user_verified": row.user_verified, "tags": row.tags, "evidence_ref": f"career_memory:{row.id}"}
        for row in rows
    ]}


def job_read(session: Session, _candidate_id: uuid.UUID, args: dict[str, Any]) -> dict[str, Any]:
    job_id = _uuid(args.get("job_id"), field="job_id")
    job = session.get(Job, job_id)
    if job is None:
        raise LookupError("Job not found")
    company = session.get(Company, job.company_id)
    locations = list(session.scalars(select(JobLocation).where(JobLocation.job_id == job.id)))
    skills = list(session.scalars(select(JobSkill).where(JobSkill.job_id == job.id)))
    requirements = list(session.scalars(select(JobRequirement).where(JobRequirement.job_id == job.id)))
    compensation = list(session.scalars(select(JobCompensation).where(JobCompensation.job_id == job.id)))
    links = list(session.scalars(select(JobSourceLink).where(JobSourceLink.job_id == job.id)))
    source_ids = [row.job_source_id for row in links]
    sources = list(session.scalars(select(JobSource).where(JobSource.id.in_(source_ids)))) if source_ids else []
    return {
        "id": str(job.id), "status": job.status, "title": job.title, "normalized_title": job.normalized_title,
        "description": job.description, "employment_type": job.employment_type, "seniority": job.seniority,
        "posted_at": job.posted_at.isoformat() if job.posted_at else None,
        "first_seen_at": job.first_seen_at.isoformat() if job.first_seen_at else None,
        "last_seen_at": job.last_seen_at.isoformat() if job.last_seen_at else None,
        "company": {"id": str(company.id), "name": company.canonical_name, "website_url": company.website_url,
                    "description": company.description} if company else {},
        "locations": [{"text": row.location_text, "city": row.city, "region": row.region,
                       "country_code": row.country_code, "work_mode": row.work_mode} for row in locations],
        "skills": [{"name": row.name, "normalized_name": row.normalized_name, "required": row.required} for row in skills],
        "requirements": [{"category": row.category, "text": row.text, "required": row.required} for row in requirements],
        "compensation": [{"minimum": row.minimum, "maximum": row.maximum, "currency": row.currency,
                          "interval": row.interval, "provenance": row.provenance} for row in compensation],
        "sources": [{"id": str(row.id), "connector_key": row.connector_key, "source_url": row.source_url,
                     "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None} for row in sources],
        "evidence_ref": f"job:{job.id}",
    }


def company_read(session: Session, _candidate_id: uuid.UUID, args: dict[str, Any]) -> dict[str, Any]:
    if args.get("company_id"):
        company = session.get(Company, _uuid(args.get("company_id"), field="company_id"))
    else:
        job = session.get(Job, _uuid(args.get("job_id"), field="job_id"))
        company = session.get(Company, job.company_id) if job else None
    if company is None:
        raise LookupError("Company not found")
    return {"id": str(company.id), "canonical_name": company.canonical_name,
            "website_url": company.website_url, "description": company.description,
            "evidence_ref": f"company:{company.id}"}


def resume_master_read(session: Session, candidate_id: uuid.UUID, _args: dict[str, Any]) -> dict[str, Any]:
    resume = session.scalar(select(Resume).where(Resume.user_id == candidate_id, Resume.is_master.is_(True)))
    if resume is None:
        return {"resume_id": None, "version_id": None, "extracted_text": None, "structured_data": None}
    version = session.scalar(
        select(ResumeVersion)
        .where(ResumeVersion.resume_id == resume.id, ResumeVersion.user_id == candidate_id)
        .order_by(ResumeVersion.version_number.desc())
        .limit(1)
    )
    extraction = session.scalar(
        select(ResumeExtraction)
        .where(ResumeExtraction.resume_version_id == version.id, ResumeExtraction.status == "COMPLETED")
        .order_by(ResumeExtraction.created_at.desc())
        .limit(1)
    ) if version else None
    return {
        "resume_id": str(resume.id), "version_id": str(version.id) if version else None,
        "version_number": version.version_number if version else None,
        "extracted_text": extraction.extracted_text if extraction else None,
        "structured_data": extraction.structured_data if extraction else None,
        "evidence_ref": f"resume:{version.id}" if version else f"resume:{resume.id}",
    }


def application_read(session: Session, candidate_id: uuid.UUID, args: dict[str, Any]) -> dict[str, Any]:
    query = select(Application).where(Application.user_id == candidate_id)
    if args.get("job_id"):
        query = query.where(Application.job_id == _uuid(args.get("job_id"), field="job_id"))
    rows = list(session.scalars(query.order_by(Application.updated_at.desc()).limit(100)))
    return {"applications": [
        {"id": str(row.id), "job_id": str(row.job_id), "current_status": row.current_status,
         "updated_at": row.updated_at.isoformat() if row.updated_at else None}
        for row in rows
    ]}


def artifact_read(session: Session, candidate_id: uuid.UUID, args: dict[str, Any]) -> dict[str, Any]:
    query = select(AgentArtifact).where(AgentArtifact.candidate_id == candidate_id)
    if args.get("artifact_id"):
        query = query.where(AgentArtifact.id == _uuid(args.get("artifact_id"), field="artifact_id"))
    if args.get("job_id"):
        query = query.where(AgentArtifact.job_id == _uuid(args.get("job_id"), field="job_id"))
    if args.get("artifact_type"):
        query = query.where(AgentArtifact.artifact_type == str(args["artifact_type"]))
    rows = list(session.scalars(query.order_by(AgentArtifact.created_at.desc()).limit(20)))
    return {"artifacts": [
        {"id": str(row.id), "run_id": str(row.run_id), "job_id": str(row.job_id) if row.job_id else None,
         "artifact_type": row.artifact_type, "status": row.status, "version": row.version,
         "content": row.content_json, "evidence": row.evidence_json,
         "prompt_version": row.prompt_version, "schema_version": row.schema_version}
        for row in rows
    ]}


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "candidate.profile.read": ToolDefinition("candidate.profile.read", "v1", "READ", candidate_profile_read),
    "candidate.evidence.read": ToolDefinition("candidate.evidence.read", "v1", "READ", candidate_evidence_read),
    "career_memory.read": ToolDefinition("career_memory.read", "v1", "READ", career_memory_read),
    "job.read": ToolDefinition("job.read", "v1", "READ", job_read),
    "company.read": ToolDefinition("company.read", "v1", "READ", company_read),
    "resume.master.read": ToolDefinition("resume.master.read", "v1", "READ", resume_master_read),
    "application.read": ToolDefinition("application.read", "v1", "READ", application_read),
    "artifact.read": ToolDefinition("artifact.read", "v1", "READ", artifact_read),
}
