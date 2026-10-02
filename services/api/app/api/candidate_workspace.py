import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from itertools import islice
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.career_models import CareerMatch
from app.models import (
    Application,
    ApplicationAnswer,
    ApplicationEvent,
    CandidateExperience,
    CandidatePreference,
    CandidateProfile,
    CandidateSkill,
    CandidateTargetRole,
    Company,
    Job,
    JobCompensation,
    JobLocation,
    JobSkill,
    JobSource,
    JobSourceLink,
    SavedJob,
    User,
)
from app.platform_models import CandidateAnalyticsEvent
from app.jobs.remote_eligibility import (
    RemoteSourceEvidence,
    assess_remote_eligibility,
    assess_remote_sources,
)

router = APIRouter(prefix="/workspace", tags=["candidate workspace"])
TAILORING_PREFIX = "APPLYAI_RESUME_EDIT"


class TailoringEditWrite(BaseModel):
    index: int = Field(ge=0, le=20)
    text: str = Field(min_length=1, max_length=4000)
    decision: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"


class TailoringWrite(BaseModel):
    edits: list[TailoringEditWrite] = Field(min_length=1, max_length=20)


def tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", value.lower())
        if len(token) > 2
    }


def _candidate_geography(location: str | None) -> tuple[str | None, tuple[str, ...]]:
    if not location:
        return None, ()
    value = location.strip().upper()
    tokens_in_location = re.findall(r"[A-Z]{2,}", value)
    country_aliases = {
        "US": "US", "USA": "US", "UNITED STATES": "US", "CANADA": "CA",
        "UK": "GB", "UNITED KINGDOM": "GB", "IRELAND": "IE", "GERMANY": "DE",
        "FRANCE": "FR", "SPAIN": "ES", "ITALY": "IT", "AUSTRALIA": "AU",
        "INDIA": "IN", "SINGAPORE": "SG", "NETHERLANDS": "NL",
    }
    normalized = " ".join(value.split())
    for label, code in country_aliases.items():
        if normalized == label or normalized.endswith(f", {label}") or normalized.endswith(f" {label}"):
            region_tokens = tuple(token for token in tokens_in_location if token != label)
            return code, region_tokens
    us_states = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
        "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
        "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
        "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
        "WI", "WY", "DC",
    }
    state = next((token for token in reversed(tokens_in_location) if token in us_states), None)
    if state:
        return "US", (state,)
    return None, ()


def _remote_sources_for_jobs(
    session: Session,
    jobs: list[Job],
) -> dict[uuid.UUID, tuple[RemoteSourceEvidence, ...]]:
    if not jobs:
        return {}
    job_ids = [job.id for job in jobs]
    locations: dict[uuid.UUID, JobLocation] = {}
    for location in session.scalars(
        select(JobLocation).where(JobLocation.job_id.in_(job_ids)).order_by(JobLocation.id)
    ):
        locations.setdefault(location.job_id, location)
    evidence: dict[uuid.UUID, list[RemoteSourceEvidence]] = defaultdict(list)
    rows = session.execute(
        select(JobSource, JobSourceLink)
        .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
        .where(JobSourceLink.job_id.in_(job_ids))
        .order_by(JobSourceLink.is_primary.desc(), JobSource.connector_key, JobSource.source_url)
    )
    ats_types = {"GREENHOUSE", "LEVER", "ASHBY", "SMARTRECRUITERS", "WORKDAY", "WORKABLE", "ICIMS", "ORACLE", "SUCCESSFACTORS"}
    employer_types = {"EMPLOYER_DIRECT", "CAREER_SITE", "JSON_LD", "EMPLOYER_JSONLD", "EMPLOYER_CAREER_SITE", "EMPLOYER_OFFICIAL_API"}
    aggregator_types = {"OPEN_JOBS", "AUTHORIZED_AGGREGATOR_FEED", "LICENSED_FEED", "RELIEFWEB", "GOVERNMENT_FEED"}
    for source, link in rows:
        checkpoint = source.checkpoint if isinstance(source.checkpoint, dict) else {}
        metadata = checkpoint.get("source_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        source_type = str(checkpoint.get("source_type") or "").strip().upper()
        connector_key = source.connector_key.strip().upper().replace("-", "_")
        authority = (
            "ATS" if source_type in ats_types or connector_key in ats_types else
            "EMPLOYER" if source_type in employer_types or connector_key in employer_types else
            "AGGREGATOR" if source_type in aggregator_types or connector_key in aggregator_types else
            "UNKNOWN"
        )
        location = locations.get(link.job_id)

        def strings(key: str) -> tuple[str, ...]:
            value = metadata.get(key)
            if not isinstance(value, (tuple, list)):
                return ()
            return tuple(item[:120] for item in value if isinstance(item, str) and item.strip())[:40]

        evidence[link.job_id].append(RemoteSourceEvidence(
            canonical_job_id=str(link.job_id),
            source_url=source.source_url,
            authority=authority,
            work_mode=(metadata.get("work_mode") if isinstance(metadata.get("work_mode"), str) else location.work_mode if link.is_primary and location else None),
            location=(metadata.get("location") if isinstance(metadata.get("location"), str) else location.location_text if link.is_primary and location else None),
            scope=(metadata.get("remote_scope") if isinstance(metadata.get("remote_scope"), str) else None),
            countries=strings("eligible_countries"),
            regions=strings("eligible_regions"),
        ))
    return {job_id: tuple(items) for job_id, items in evidence.items()}


def candidate_context(session: Session, user: User) -> dict:
    profile = session.scalar(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    preference = session.scalar(
        select(CandidatePreference).where(CandidatePreference.user_id == user.id)
    )
    roles = list(
        session.scalars(
            select(CandidateTargetRole)
            .where(CandidateTargetRole.user_id == user.id)
            .order_by(CandidateTargetRole.priority)
        )
    )
    skills: list[CandidateSkill] = []
    experiences: list[CandidateExperience] = []
    if profile is not None:
        skills = list(
            session.scalars(
                select(CandidateSkill).where(CandidateSkill.profile_id == profile.id)
            )
        )
        experiences = list(
            session.scalars(
                select(CandidateExperience)
                .where(CandidateExperience.profile_id == profile.id)
                .order_by(CandidateExperience.start_date.desc().nullslast())
            )
        )
    role_tokens = tokens(profile.current_title if profile else None)
    for role in roles:
        role_tokens.update(tokens(role.title))
    skill_tokens = {skill.normalized_name for skill in skills}
    return {
        "profile": profile,
        "preference": preference,
        "roles": roles,
        "skills": skills,
        "experiences": experiences,
        "role_tokens": role_tokens,
        "skill_tokens": skill_tokens,
    }


def _recommendation_batch(
    session: Session,
    user: User,
    context: dict,
    jobs: list[Job],
    *,
    career_scores: dict[uuid.UUID, int],
    applied_ids: set[uuid.UUID],
    viewed_ids: set[str],
    now: datetime,
) -> list[dict]:
    preference: CandidatePreference | None = context["preference"]
    job_ids = [job.id for job in jobs]
    if not job_ids:
        return []
    company_ids = {job.company_id for job in jobs}
    companies = {
        company.id: company
        for company in session.scalars(
            select(Company).where(Company.id.in_(company_ids))
        )
    }
    locations: dict[uuid.UUID, JobLocation] = {}
    for location in session.scalars(
        select(JobLocation)
        .where(JobLocation.job_id.in_(job_ids))
        .order_by(JobLocation.id)
    ):
        locations.setdefault(location.job_id, location)
    compensations: dict[uuid.UUID, JobCompensation] = {}
    for compensation in session.scalars(
        select(JobCompensation)
        .where(JobCompensation.job_id.in_(job_ids))
        .order_by(JobCompensation.id)
    ):
        compensations.setdefault(compensation.job_id, compensation)
    skills_by_job: dict[uuid.UUID, list[JobSkill]] = defaultdict(list)
    for skill in session.scalars(
        select(JobSkill)
        .where(JobSkill.job_id.in_(job_ids))
        .order_by(JobSkill.required.desc(), JobSkill.name)
    ):
        skills_by_job[skill.job_id].append(skill)
    saved_ids = set(
        session.scalars(
            select(SavedJob.job_id).where(
                SavedJob.user_id == user.id, SavedJob.job_id.in_(job_ids)
            )
        )
    )
    sourced_ids = set(
        session.scalars(
            select(JobSourceLink.job_id).where(JobSourceLink.job_id.in_(job_ids))
        )
    )

    results: list[dict] = []
    preferred_location = (
        preference.location_text.lower().strip()
        if preference and preference.location_text
        else None
    )
    preferred_modes = {
        mode.upper() for mode in (preference.work_modes if preference else [])
    }
    minimum_compensation = preference.minimum_compensation if preference else None
    remote_sources = _remote_sources_for_jobs(session, jobs)
    candidate_country, candidate_regions = _candidate_geography(
        preference.location_text if preference else None
    )
    preferred_employment = {
        value.strip().upper()
        for value in (preference.employment_types if preference else [])
        if value and value.strip().upper() not in {"ANY", "ALL"}
    }
    relocation_open = bool(preference and preference.relocation_open)

    for job in jobs:
        # Do not recommend already-started applications. Hard user constraints are
        # applied before any fit or recency score is calculated.
        if job.id in applied_ids:
            continue
        company = companies.get(job.company_id)
        if company is None:
            continue
        location = locations.get(job.id)
        compensation = compensations.get(job.id)
        job_skills = skills_by_job.get(job.id, [])
        work_mode = location.work_mode.upper() if location else None
        if preferred_modes and (work_mode is None or work_mode not in preferred_modes):
            continue
        if preferred_employment and (
            not job.employment_type
            or job.employment_type.strip().upper() not in preferred_employment
        ):
            continue
        if preferred_location and not relocation_open:
            location_matches = bool(
                location
                and preferred_location in location.location_text.lower()
            )
            if not location_matches and work_mode != "REMOTE":
                continue
        else:
            location_matches = False
        if work_mode == "REMOTE" and "REMOTE" in preferred_modes and not relocation_open:
            source_evidence = remote_sources.get(job.id, ())
            eligibility = (
                assess_remote_sources(
                    canonical_job_id=str(job.id),
                    sources=source_evidence,
                    candidate_country=candidate_country,
                    candidate_regions=candidate_regions,
                )
                if source_evidence
                else assess_remote_eligibility(
                    work_mode=work_mode,
                    location=location.location_text if location else None,
                    candidate_country=candidate_country,
                    candidate_regions=candidate_regions,
                )
            )
            if eligibility.decision != "ELIGIBLE":
                continue
        if (
            minimum_compensation
            and compensation
            and compensation.maximum is not None
            and compensation.maximum < minimum_compensation
        ):
            continue
        title_tokens = tokens(job.title)
        job_skill_tokens = {skill.normalized_name for skill in job_skills}
        role_overlap = context["role_tokens"] & title_tokens
        skill_overlap = context["skill_tokens"] & job_skill_tokens

        score = 45
        strengths: list[str] = []
        gaps: list[str] = []
        if role_overlap:
            score += min(24, 8 + len(role_overlap) * 4)
            strengths.append(
                f"The role title overlaps with your target direction: {', '.join(sorted(role_overlap)[:3])}."
            )
        else:
            gaps.append("The title is adjacent to, rather than an exact match for, your target roles.")
        if skill_overlap:
            score += min(22, len(skill_overlap) * 6)
            strengths.append(
                f"Verified skills align: {', '.join(sorted(skill_overlap)[:4])}."
            )
        elif job_skills:
            gaps.append(
                f"Your verified profile does not yet show the role's leading skill: {job_skills[0].name}."
            )

        if location is not None and preferred_location:
            location_text = location.location_text.lower()
            if preferred_location in location_text:
                score += 8
                strengths.append("The location matches your stated preference.")
            elif location.work_mode.upper() == "REMOTE":
                score += 7
                strengths.append("The remote arrangement matches your work preference.")
            else:
                score -= 5
                gaps.append("The location or work arrangement is outside your first preference.")
        elif location is not None and location.work_mode.upper() in preferred_modes:
            score += 6
            strengths.append("The work arrangement matches your preference.")

        if minimum_compensation and compensation and compensation.maximum is not None:
            if compensation.maximum >= minimum_compensation:
                score += 8
                strengths.append("The published compensation range can meet your minimum target.")
            else:
                score -= 12
                gaps.append("The published compensation ceiling is below your minimum target.")
        elif minimum_compensation:
            gaps.append("The posting does not include enough compensation information to verify fit.")

        if job.seniority and context["profile"] and context["profile"].years_experience:
            if job.seniority.upper() in {"SENIOR", "MANAGER", "DIRECTOR", "LEAD"}:
                score += min(7, context["profile"].years_experience // 2)

        if not strengths:
            strengths.append("The role is active and reasonably close to your current search criteria.")
        if not gaps:
            gaps.append("Confirm team scope and first-year expectations during recruiter conversations.")

        deterministic_score = max(35, min(98, score))
        career_score = career_scores.get(job.id)
        score = (
            round(deterministic_score * 0.65 + career_score * 0.35)
            if career_score is not None
            else deterministic_score
        )
        saved = job.id in saved_ids
        recently_viewed = str(job.id) in viewed_ids
        if saved:
            score += 3
            strengths.append("You saved this opportunity for follow-up.")
        if recently_viewed:
            score -= 4
        last_seen = job.last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        age = now - last_seen
        freshness_adjustment = 5 if age <= timedelta(hours=3) else 3 if age <= timedelta(hours=24) else 1 if age <= timedelta(days=7) else 0
        score = max(0, min(100, score + freshness_adjustment))
        results.append(
            {
                "id": job.id,
                "job_id": str(job.id),
                "title": job.title,
                "company_name": company.canonical_name,
                "location": location.location_text if location else None,
                "work_mode": location.work_mode if location else None,
                "minimum_compensation": compensation.minimum if compensation else None,
                "maximum_compensation": compensation.maximum if compensation else None,
                "posted_at": job.posted_at,
                "last_seen_at": job.last_seen_at,
                "saved": saved,
                "applied": False,
                "recently_viewed": recently_viewed,
                "match_score": score,
                "deterministic_score": deterministic_score,
                "career_v2_score": career_score,
                "freshness_adjustment": freshness_adjustment,
                "summary": job.description,
                "explanation": strengths[0],
                "strengths": strengths[:4],
                "gaps": gaps[:3],
                "skills": [skill.name for skill in job_skills[:8]],
                "source_label": (
                    "Verified employer or ATS posting"
                    if job.id in sourced_ids
                    else "ApplyAI verified development posting"
                ),
                "data_origin": job.data_origin,
            }
        )
    return results


def recommendation_rows(session: Session, user: User, limit: int) -> list[dict]:
    context = candidate_context(session, user)
    now = datetime.now(timezone.utc)
    career_scores = {
        job_id: score
        for job_id, score in session.execute(
            select(CareerMatch.job_id, CareerMatch.final_score).where(
                CareerMatch.user_id == user.id,
                CareerMatch.engine_version == "applyai-hybrid-fit-v2",
            )
        )
    }
    applied_ids = set(
        session.scalars(select(Application.job_id).where(Application.user_id == user.id))
    )
    viewed_since = now - timedelta(days=14)
    viewed_ids = set(
        session.scalars(
            select(CandidateAnalyticsEvent.entity_id).where(
                CandidateAnalyticsEvent.user_id == user.id,
                CandidateAnalyticsEvent.event_type == "JOB_VIEWED",
                CandidateAnalyticsEvent.entity_type == "JOB",
                CandidateAnalyticsEvent.occurred_at >= viewed_since,
                CandidateAnalyticsEvent.entity_id.is_not(None),
            )
        )
    )
    ranked: list[dict] = []
    active_jobs = session.scalars(
        select(Job)
        .where(Job.status == "ACTIVE")
        .order_by(
            Job.posted_at.desc().nullslast(),
            Job.last_seen_at.desc(),
            Job.id.asc(),
        )
        .execution_options(yield_per=500)
    )
    while batch := list(islice(active_jobs, 500)):
        ranked.extend(
            _recommendation_batch(
                session,
                user,
                context,
                batch,
                career_scores=career_scores,
                applied_ids=applied_ids,
                viewed_ids=viewed_ids,
                now=now,
            )
        )
        ranked.sort(
            key=lambda item: (
                item["match_score"],
                item["posted_at"] or item["last_seen_at"],
                str(item["id"]),
            ),
            reverse=True,
        )
        del ranked[limit:]

    return ranked


@router.get("/recommendations")
def get_recommendations(
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    context = candidate_context(session, user)
    profile: CandidateProfile | None = context["profile"]
    preference: CandidatePreference | None = context["preference"]
    return {
        "ranking_scope": "ALL_ACTIVE_ELIGIBLE_JOBS_BEFORE_LIMIT",
        "profile_ready": profile is not None,
        "search_goal": {
            "target_roles": [role.title for role in context["roles"]],
            "location_text": preference.location_text if preference else None,
            "work_modes": preference.work_modes if preference else [],
            "minimum_compensation": (
                preference.minimum_compensation if preference else None
            ),
        },
        "items": recommendation_rows(session, user, limit),
    }


def get_owned_job(job_id: uuid.UUID, session: Session) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active job not found",
        )
    return job


def get_or_create_application(
    *, job: Job, user: User, session: Session
) -> Application:
    application = session.scalar(
        select(Application).where(
            Application.user_id == user.id,
            Application.job_id == job.id,
        )
    )
    if application is None:
        application = Application(
            user_id=user.id,
            job_id=job.id,
            current_status="PREPARING",
        )
        session.add(application)
        session.flush()
        session.add(
            ApplicationEvent(
                application_id=application.id,
                actor_user_id=user.id,
                from_status=None,
                to_status="PREPARING",
                metadata_json={"created_by": "resume_tailoring"},
            )
        )
    if session.get(SavedJob, {"user_id": user.id, "job_id": job.id}) is None:
        session.add(SavedJob(user_id=user.id, job_id=job.id))
    session.flush()
    return application


def generated_edits(
    *, job: Job, context: dict, job_skills: list[JobSkill]
) -> list[dict]:
    profile: CandidateProfile | None = context["profile"]
    experiences: list[CandidateExperience] = context["experiences"]
    candidate_skills: list[CandidateSkill] = context["skills"]
    first_experience = experiences[0] if experiences else None
    current_experience = (
        first_experience.description
        if first_experience and first_experience.description
        else "Describe the scope and measurable impact of your most relevant experience."
    )
    shared_skills = sorted(
        {skill.normalized_name for skill in candidate_skills}
        & {skill.normalized_name for skill in job_skills}
    )
    visible_skills = ", ".join(shared_skills[:4]) or "your verified platform skills"
    current_summary = (
        profile.summary
        if profile and profile.summary
        else "Summarize your verified experience and the outcomes you delivered."
    )
    team_fact = (
        first_experience.description
        if first_experience and first_experience.description
        else current_experience
    )
    return [
        {
            "index": 0,
            "current": current_experience,
            "suggested": (
                f"{current_experience.rstrip('.')} This experience demonstrates "
                f"relevant strength in {visible_skills}."
            ),
            "evidence": "Uses only the verified experience description and skills already saved in your profile.",
        },
        {
            "index": 1,
            "current": current_summary,
            "suggested": (
                f"{current_summary.rstrip('.')} Position this experience for the "
                f"{job.title} opportunity without adding responsibilities or results."
            ),
            "evidence": "Uses your verified profile summary and the selected job title; no new achievement is introduced.",
        },
        {
            "index": 2,
            "current": team_fact,
            "suggested": (
                f"{team_fact.rstrip('.')} Emphasize the parts most relevant to "
                f"{job.title}, while keeping the original scope and metrics unchanged."
            ),
            "evidence": "Keeps the original verified scope and metrics intact and changes only emphasis.",
        },
    ]


def tailoring_payload(
    *, job: Job, user: User, session: Session
) -> dict:
    context = candidate_context(session, user)
    job_skills = list(
        session.scalars(
            select(JobSkill)
            .where(JobSkill.job_id == job.id)
            .order_by(JobSkill.required.desc(), JobSkill.name)
        )
    )
    application = session.scalar(
        select(Application).where(
            Application.user_id == user.id,
            Application.job_id == job.id,
        )
    )
    persisted: dict[int, dict] = {}
    if application is not None:
        for answer in session.scalars(
            select(ApplicationAnswer).where(
                ApplicationAnswer.application_id == application.id,
                ApplicationAnswer.question.like(f"{TAILORING_PREFIX}:%"),
            )
        ):
            parts = answer.question.split(":", 2)
            if len(parts) != 3:
                continue
            try:
                index = int(parts[1])
            except ValueError:
                continue
            persisted[index] = {
                "text": answer.answer,
                "decision": parts[2],
            }

    edits = generated_edits(job=job, context=context, job_skills=job_skills)
    for edit in edits:
        saved = persisted.get(edit["index"])
        edit["text"] = saved["text"] if saved else edit["suggested"]
        edit["decision"] = saved["decision"] if saved else "PENDING"
    return {
        "job_id": job.id,
        "application_id": application.id if application else None,
        "job_title": job.title,
        "company_name": session.get(Company, job.company_id).canonical_name,
        "edits": edits,
    }


@router.get("/tailoring/{job_id}")
def get_tailoring(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    return tailoring_payload(job=job, user=user, session=session)


@router.put("/tailoring/{job_id}")
def save_tailoring(
    job_id: uuid.UUID,
    payload: TailoringWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    job = get_owned_job(job_id, session)
    application = get_or_create_application(job=job, user=user, session=session)
    session.execute(
        delete(ApplicationAnswer).where(
            ApplicationAnswer.application_id == application.id,
            ApplicationAnswer.question.like(f"{TAILORING_PREFIX}:%"),
        )
    )
    seen: set[int] = set()
    for edit in payload.edits:
        if edit.index in seen:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tailoring edit indexes must be unique",
            )
        seen.add(edit.index)
        session.add(
            ApplicationAnswer(
                application_id=application.id,
                user_id=user.id,
                question=f"{TAILORING_PREFIX}:{edit.index}:{edit.decision}",
                answer=edit.text.strip(),
                user_verified=edit.decision == "APPROVED",
            )
        )
    session.commit()
    return tailoring_payload(job=job, user=user, session=session)
