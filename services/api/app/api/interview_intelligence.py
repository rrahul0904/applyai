from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.interview_engine import DeterministicInterviewEngine, InterviewEvidence, InterviewMode, InterviewRequest
from app.interview_intelligence_models import (
    InterviewCommunityPost, InterviewCommunityReaction, InterviewCommunityReply,
    InterviewIntelligenceAttempt, InterviewIntelligenceQuestion, InterviewIntelligenceReport,
    InterviewPreparationPlan,
)
from app.interview_intelligence_service import personalized_plan, report_fingerprint, slugify, staged_hint
from app.models import CandidateProfile, CandidateSkill, Company, Job, JobSkill, User
from app.platform_models import InterviewPracticeSession

router = APIRouter(prefix="/interview-intelligence", tags=["interview intelligence"])
internal_router = APIRouter(prefix="/internal/interview-intelligence", tags=["internal-interview-intelligence"], dependencies=[Depends(require_internal_api)])
TRACKS = ("CODING", "SQL", "SYSTEM_DESIGN", "ML_SYSTEM_DESIGN", "OOD", "BEHAVIORAL")
DIFFICULTIES = ("EASY", "MEDIUM", "HARD")


def question_payload(item: InterviewIntelligenceQuestion) -> dict[str, Any]:
    return {"id": item.id, "slug": item.slug, "title": item.title, "track": item.track, "difficulty": item.difficulty, "summary": item.summary, "prompt": item.prompt, "companies": item.company_labels or [], "skills": item.skills or [], "patterns": item.patterns or [], "hints": item.hints or [], "follow_ups": item.follow_ups or [], "solution_outline": item.solution_outline or [], "test_cases": item.test_cases or [], "starter_code": item.starter_code or {}, "frequency_score": item.frequency_score, "confidence": item.confidence, "report_count": item.report_count, "last_reported_at": item.last_reported_at, "published": item.published}


def post_payload(item: InterviewCommunityPost, replies: list[InterviewCommunityReply] | None = None) -> dict[str, Any]:
    return {"id": item.id, "company": item.company_label, "category": item.category, "title": item.title, "body": item.body, "reaction_count": item.reaction_count, "reply_count": item.reply_count, "view_count": item.view_count, "created_at": item.created_at, "replies": [{"id": reply.id, "body": reply.body, "created_at": reply.created_at} for reply in (replies or [])]}


class AttemptWrite(BaseModel):
    question_id: uuid.UUID
    job_id: uuid.UUID | None = None
    language: str | None = Field(default=None, max_length=48)
    answer: str | None = Field(default=None, max_length=100_000)
    code: str | None = Field(default=None, max_length=100_000)


class AttemptUpdate(BaseModel):
    status: Literal["IN_PROGRESS", "COMPLETED", "ABANDONED"] | None = None
    language: str | None = Field(default=None, max_length=48)
    answer: str | None = Field(default=None, max_length=100_000)
    code: str | None = Field(default=None, max_length=100_000)
    feedback: dict[str, Any] | None = None
    score: int | None = Field(default=None, ge=0, le=100)


class ReportWrite(BaseModel):
    company: str | None = Field(default=None, max_length=240)
    role: str | None = Field(default=None, max_length=240)
    interview_stage: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=320)
    body: str = Field(min_length=20, max_length=50_000)
    reported_at: datetime | None = None
    source_reference: str | None = Field(default=None, max_length=320)


class CommunityPostWrite(BaseModel):
    company: str | None = Field(default=None, max_length=240)
    category: Literal["INTERVIEW_EXPERIENCE", "COMPENSATION", "CAREER_DEVELOPMENT", "COMPANY_CULTURE", "OTHER"] = "INTERVIEW_EXPERIENCE"
    title: str = Field(min_length=5, max_length=320)
    body: str = Field(min_length=20, max_length=30_000)


class CommunityReplyWrite(BaseModel):
    body: str = Field(min_length=2, max_length=12_000)


class CoachWrite(BaseModel):
    question_id: uuid.UUID
    answer: str | None = Field(default=None, max_length=100_000)
    hint_level: int = Field(default=0, ge=0, le=20)


class QuestionAdminWrite(BaseModel):
    title: str = Field(min_length=5, max_length=320)
    slug: str | None = Field(default=None, max_length=240)
    track: Literal["CODING", "SQL", "SYSTEM_DESIGN", "ML_SYSTEM_DESIGN", "OOD", "BEHAVIORAL"]
    difficulty: Literal["EASY", "MEDIUM", "HARD"] = "MEDIUM"
    summary: str = Field(min_length=20, max_length=10_000)
    prompt: str = Field(min_length=20, max_length=30_000)
    companies: list[str] = Field(default_factory=list, max_length=50)
    skills: list[str] = Field(default_factory=list, max_length=50)
    patterns: list[str] = Field(default_factory=list, max_length=50)
    hints: list[str] = Field(default_factory=list, max_length=20)
    follow_ups: list[str] = Field(default_factory=list, max_length=20)
    solution_outline: list[str] = Field(default_factory=list, max_length=30)
    test_cases: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    starter_code: dict[str, str] = Field(default_factory=dict)
    frequency_score: int = Field(default=0, ge=0, le=100)
    confidence: int = Field(default=0, ge=0, le=100)
    report_count: int = Field(default=0, ge=0)
    last_reported_at: datetime | None = None
    published: bool = False


class ModerationWrite(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    extraction_confidence: int | None = Field(default=None, ge=0, le=100)


@router.get("/capabilities")
def capabilities() -> dict[str, Any]:
    return {"tracks": list(TRACKS), "features": {"question_bank": True, "company_collections": True, "recency_confidence": True, "progress_tracking": True, "personalized_job_plan": True, "mock_interview": True, "community": True, "candidate_reports": True, "staged_coaching": True, "local_code_execution": False}, "execution_boundary": "isolated-provider-required", "clean_room": True}


@router.get("/questions")
def list_questions(q: str | None = Query(default=None, max_length=200), company: str | None = Query(default=None, max_length=240), track: str | None = None, difficulty: str | None = None, min_confidence: int = Query(default=0, ge=0, le=100), reported_since: datetime | None = None, sort: Literal["FREQUENCY", "RECENT", "CONFIDENCE"] = "FREQUENCY", offset: int = Query(default=0, ge=0), limit: int = Query(default=25, ge=1, le=100), _user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    if track and track not in TRACKS: raise HTTPException(status_code=422, detail="Unsupported interview track")
    if difficulty and difficulty not in DIFFICULTIES: raise HTTPException(status_code=422, detail="Unsupported difficulty")
    statement = select(InterviewIntelligenceQuestion).where(InterviewIntelligenceQuestion.published.is_(True))
    if track: statement = statement.where(InterviewIntelligenceQuestion.track == track)
    if difficulty: statement = statement.where(InterviewIntelligenceQuestion.difficulty == difficulty)
    if min_confidence: statement = statement.where(InterviewIntelligenceQuestion.confidence >= min_confidence)
    if reported_since: statement = statement.where(InterviewIntelligenceQuestion.last_reported_at >= reported_since)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(InterviewIntelligenceQuestion.title.ilike(pattern), InterviewIntelligenceQuestion.summary.ilike(pattern), InterviewIntelligenceQuestion.prompt.ilike(pattern)))
    order = {"FREQUENCY": (InterviewIntelligenceQuestion.frequency_score.desc(), InterviewIntelligenceQuestion.report_count.desc()), "RECENT": (InterviewIntelligenceQuestion.last_reported_at.desc().nullslast(), InterviewIntelligenceQuestion.frequency_score.desc()), "CONFIDENCE": (InterviewIntelligenceQuestion.confidence.desc(), InterviewIntelligenceQuestion.report_count.desc())}[sort]
    items = list(session.scalars(statement.order_by(*order).limit(2000)))
    if company:
        key = company.strip().lower(); items = [item for item in items if any(label.lower() == key for label in (item.company_labels or []))]
    total = len(items); page = items[offset:offset + limit]
    return {"items": [question_payload(item) for item in page], "total": total, "offset": offset, "limit": limit, "next_offset": offset + len(page) if offset + len(page) < total else None}


@router.get("/questions/{slug}")
def get_question(slug: str, _user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.scalar(select(InterviewIntelligenceQuestion).where(InterviewIntelligenceQuestion.slug == slug, InterviewIntelligenceQuestion.published.is_(True)))
    if item is None: raise HTTPException(status_code=404, detail="Interview question not found")
    return question_payload(item)


@router.get("/companies")
def company_collections(_user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    items = list(session.scalars(select(InterviewIntelligenceQuestion).where(InterviewIntelligenceQuestion.published.is_(True)).order_by(InterviewIntelligenceQuestion.frequency_score.desc()).limit(2000)))
    stats: dict[str, dict[str, Any]] = {}
    for item in items:
        for company in item.company_labels or []:
            entry = stats.setdefault(company, {"name": company, "slug": slugify(company), "question_count": 0, "report_count": 0, "tracks": Counter()})
            entry["question_count"] += 1; entry["report_count"] += item.report_count; entry["tracks"][item.track] += 1
    return sorted(({**entry, "tracks": dict(entry["tracks"])} for entry in stats.values()), key=lambda item: (item["question_count"], item["report_count"]), reverse=True)


@router.get("/companies/{company_slug}")
def company_collection(company_slug: str, _user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    all_questions = list(session.scalars(select(InterviewIntelligenceQuestion).where(InterviewIntelligenceQuestion.published.is_(True)).order_by(InterviewIntelligenceQuestion.frequency_score.desc()).limit(2000)))
    matching = [item for item in all_questions if any(slugify(label) == company_slug for label in (item.company_labels or []))]
    if not matching: raise HTTPException(status_code=404, detail="Interview company collection not found")
    company_name = next(label for label in matching[0].company_labels if slugify(label) == company_slug)
    return {"name": company_name, "slug": company_slug, "question_count": len(matching), "report_count": sum(item.report_count for item in matching), "tracks": dict(Counter(item.track for item in matching)), "questions": [question_payload(item) for item in matching[:100]]}


@router.post("/attempts", status_code=status.HTTP_201_CREATED)
def create_attempt(payload: AttemptWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    question = session.get(InterviewIntelligenceQuestion, payload.question_id)
    if question is None or not question.published: raise HTTPException(status_code=404, detail="Interview question not found")
    if payload.job_id is not None and session.get(Job, payload.job_id) is None: raise HTTPException(status_code=404, detail="Job not found")
    item = InterviewIntelligenceAttempt(user_id=user.id, question_id=question.id, job_id=payload.job_id, language=payload.language, answer=payload.answer, code=payload.code)
    session.add(item); session.commit(); session.refresh(item)
    return {"id": item.id, "status": item.status, "created_at": item.created_at}


@router.put("/attempts/{attempt_id}")
def update_attempt(attempt_id: uuid.UUID, payload: AttemptUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.scalar(select(InterviewIntelligenceAttempt).where(InterviewIntelligenceAttempt.id == attempt_id, InterviewIntelligenceAttempt.user_id == user.id))
    if item is None: raise HTTPException(status_code=404, detail="Interview attempt not found")
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(item, key, value)
    session.commit(); session.refresh(item)
    return {"id": item.id, "status": item.status, "score": item.score, "feedback": item.feedback, "updated_at": item.updated_at}


@router.get("/progress")
def progress(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    attempts = list(session.scalars(select(InterviewIntelligenceAttempt).where(InterviewIntelligenceAttempt.user_id == user.id).order_by(InterviewIntelligenceAttempt.updated_at.desc()).limit(1000)))
    ids = {item.question_id for item in attempts}
    questions = {item.id: item for item in session.scalars(select(InterviewIntelligenceQuestion).where(InterviewIntelligenceQuestion.id.in_(ids)))} if ids else {}
    by_track: dict[str, dict[str, int]] = {}
    for attempt in attempts:
        track = questions.get(attempt.question_id).track if questions.get(attempt.question_id) else "UNKNOWN"
        stats = by_track.setdefault(track, {"attempts": 0, "completed": 0, "scored": 0, "score_total": 0})
        stats["attempts"] += 1; stats["completed"] += int(attempt.status == "COMPLETED")
        if attempt.score is not None: stats["scored"] += 1; stats["score_total"] += attempt.score
    for stats in by_track.values():
        stats["average_score"] = round(stats["score_total"] / stats["scored"]) if stats["scored"] else 0; del stats["score_total"]; del stats["scored"]
    return {"total_attempts": len(attempts), "completed": sum(1 for item in attempts if item.status == "COMPLETED"), "by_track": by_track}


@router.post("/coach")
def coach(payload: CoachWrite, _user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    question = session.get(InterviewIntelligenceQuestion, payload.question_id)
    if question is None or not question.published: raise HTTPException(status_code=404, detail="Interview question not found")
    return {**staged_hint(hints=question.hints or [], requested_level=payload.hint_level, answer=payload.answer), "provider": "applyai-evidence-coach", "question_id": question.id}


def candidate_skills(session: Session, user: User) -> list[str]:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is None: return []
    return [skill.normalized_name for skill in session.scalars(select(CandidateSkill).where(CandidateSkill.profile_id == profile.id))]


def track_counts(session: Session, company_name: str | None) -> dict[str, int]:
    items = list(session.scalars(select(InterviewIntelligenceQuestion).where(InterviewIntelligenceQuestion.published.is_(True)).limit(2000)))
    if company_name:
        company_items = [item for item in items if any(label.lower() == company_name.lower() for label in (item.company_labels or []))]
        if company_items: items = company_items
    return dict(Counter(item.track for item in items))


@router.post("/plans/{job_id}")
def create_or_refresh_plan(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if job is None: raise HTTPException(status_code=404, detail="Job not found")
    company = session.get(Company, job.company_id)
    required = [skill.normalized_name for skill in session.scalars(select(JobSkill).where(JobSkill.job_id == job.id).order_by(JobSkill.required.desc(), JobSkill.name))]
    data = personalized_plan(job_title=job.title, candidate_skills=candidate_skills(session, user), required_skills=required, question_tracks=track_counts(session, company.canonical_name if company else None))
    item = session.scalar(select(InterviewPreparationPlan).where(InterviewPreparationPlan.user_id == user.id, InterviewPreparationPlan.job_id == job.id))
    if item is None: item = InterviewPreparationPlan(user_id=user.id, job_id=job.id); session.add(item)
    item.readiness_score = int(data["readiness_score"]); item.strengths = list(data["strengths"]); item.gaps = list(data["gaps"]); item.actions = list(data["actions"]); item.status = "ACTIVE"
    session.commit(); session.refresh(item)
    return {"id": item.id, "job_id": item.job_id, "job_title": job.title, "company": company.canonical_name if company else None, "readiness_score": item.readiness_score, "strengths": item.strengths, "gaps": item.gaps, "actions": item.actions, "updated_at": item.updated_at}


@router.get("/plans/{job_id}")
def get_plan(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.scalar(select(InterviewPreparationPlan).where(InterviewPreparationPlan.user_id == user.id, InterviewPreparationPlan.job_id == job_id))
    if item is None: raise HTTPException(status_code=404, detail="Interview preparation plan not found")
    job = session.get(Job, job_id); company = session.get(Company, job.company_id) if job else None
    return {"id": item.id, "job_id": item.job_id, "job_title": job.title if job else None, "company": company.canonical_name if company else None, "readiness_score": item.readiness_score, "strengths": item.strengths, "gaps": item.gaps, "actions": item.actions, "updated_at": item.updated_at}


@router.post("/mock/{job_id}/start", status_code=status.HTTP_201_CREATED)
def start_mock_interview(job_id: uuid.UUID, mode: Literal["BEHAVIORAL", "TECHNICAL", "CODING", "SQL", "SYSTEM_DESIGN"] = "TECHNICAL", user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if job is None: raise HTTPException(status_code=404, detail="Job not found")
    skills = tuple(candidate_skills(session, user)[:8]); evidence = tuple(InterviewEvidence(kind="verified_skill", reference=f"skill:{skill}", summary=skill) for skill in skills[:5])
    generated = DeterministicInterviewEngine().create_session(InterviewRequest(candidate_id=str(user.id), job_id=str(job.id), mode=InterviewMode(mode.lower()), target_role=job.title, verified_skills=skills, evidence=evidence))
    responses = [{"question_id": item.id, "prompt": item.prompt, "mode": item.mode.value, "difficulty": item.difficulty, "evidence_refs": list(item.evidence_refs), "execution_required": item.execution_required, "answer": None} for item in generated.questions]
    practice = InterviewPracticeSession(user_id=user.id, job_id=job.id, mode=mode, responses=responses, feedback={"provider": generated.provider})
    session.add(practice); session.commit(); session.refresh(practice)
    return {"id": practice.id, "job_id": practice.job_id, "mode": practice.mode, "provider": generated.provider, "questions": responses, "execution_boundary": "external-isolated-provider" if mode in {"CODING", "SQL"} else "not-required"}


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def submit_report(payload: ReportWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    fingerprint = report_fingerprint(source_type="USER_SUBMISSION", source_url=None, company=payload.company, role=payload.role, body=payload.body)
    existing = session.scalar(select(InterviewIntelligenceReport).where(InterviewIntelligenceReport.fingerprint == fingerprint))
    if existing is not None: return {"id": existing.id, "moderation_status": existing.moderation_status, "duplicate": True}
    item = InterviewIntelligenceReport(contributor_user_id=user.id, source_type="USER_SUBMISSION", source_reference=payload.source_reference, company_label=payload.company, role=payload.role, interview_stage=payload.interview_stage, title=payload.title, body=payload.body, fingerprint=fingerprint, license_status="USER_SUBMITTED", moderation_status="REVIEW_REQUIRED", reported_at=payload.reported_at)
    session.add(item); session.commit(); session.refresh(item)
    return {"id": item.id, "moderation_status": item.moderation_status, "duplicate": False}


@router.get("/community")
def list_community(category: str | None = None, company: str | None = None, sort: Literal["NEWEST", "HOT"] = "NEWEST", limit: int = Query(default=50, ge=1, le=100), _user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    statement = select(InterviewCommunityPost).where(InterviewCommunityPost.moderation_status == "PUBLISHED")
    if category: statement = statement.where(InterviewCommunityPost.category == category)
    if company: statement = statement.where(InterviewCommunityPost.company_label.ilike(company))
    order = (InterviewCommunityPost.reaction_count + InterviewCommunityPost.reply_count * 2 + InterviewCommunityPost.view_count / 20).desc() if sort == "HOT" else InterviewCommunityPost.created_at.desc()
    return [post_payload(item) for item in session.scalars(statement.order_by(order).limit(limit))]


@router.post("/community", status_code=status.HTTP_201_CREATED)
def create_community_post(payload: CommunityPostWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = InterviewCommunityPost(user_id=user.id, company_label=payload.company, category=payload.category, title=payload.title, body=payload.body, moderation_status="PUBLISHED")
    session.add(item); session.commit(); session.refresh(item); return post_payload(item)


@router.get("/community/{post_id}")
def get_community_post(post_id: uuid.UUID, _user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.get(InterviewCommunityPost, post_id)
    if item is None or item.moderation_status != "PUBLISHED": raise HTTPException(status_code=404, detail="Community post not found")
    item.view_count += 1
    replies = list(session.scalars(select(InterviewCommunityReply).where(InterviewCommunityReply.post_id == post_id, InterviewCommunityReply.moderation_status == "PUBLISHED").order_by(InterviewCommunityReply.created_at)))
    session.commit(); return post_payload(item, replies)


@router.post("/community/{post_id}/replies", status_code=status.HTTP_201_CREATED)
def create_reply(post_id: uuid.UUID, payload: CommunityReplyWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    post = session.get(InterviewCommunityPost, post_id)
    if post is None or post.moderation_status != "PUBLISHED": raise HTTPException(status_code=404, detail="Community post not found")
    reply = InterviewCommunityReply(post_id=post_id, user_id=user.id, body=payload.body); post.reply_count += 1; session.add(reply); session.commit(); session.refresh(reply)
    return {"id": reply.id, "body": reply.body, "created_at": reply.created_at}


@router.post("/community/{post_id}/react")
def react(post_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    post = session.get(InterviewCommunityPost, post_id)
    if post is None or post.moderation_status != "PUBLISHED": raise HTTPException(status_code=404, detail="Community post not found")
    existing = session.scalar(select(InterviewCommunityReaction).where(InterviewCommunityReaction.post_id == post_id, InterviewCommunityReaction.user_id == user.id, InterviewCommunityReaction.reaction == "UPVOTE"))
    if existing is None: session.add(InterviewCommunityReaction(post_id=post_id, user_id=user.id)); post.reaction_count += 1; reacted = True
    else: session.delete(existing); post.reaction_count = max(0, post.reaction_count - 1); reacted = False
    session.commit(); return {"reacted": reacted, "reaction_count": post.reaction_count}


@internal_router.get("/metrics")
def internal_metrics(session: Session = Depends(get_session)) -> dict[str, int]:
    count = lambda model: int(session.scalar(select(func.count()).select_from(model)) or 0)
    return {"questions": count(InterviewIntelligenceQuestion), "reports": count(InterviewIntelligenceReport), "attempts": count(InterviewIntelligenceAttempt), "plans": count(InterviewPreparationPlan), "community_posts": count(InterviewCommunityPost)}


@internal_router.get("/reports")
def moderation_queue(moderation_status: str = Query(default="REVIEW_REQUIRED", max_length=48), limit: int = Query(default=100, ge=1, le=500), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    items = list(session.scalars(select(InterviewIntelligenceReport).where(InterviewIntelligenceReport.moderation_status == moderation_status).order_by(InterviewIntelligenceReport.created_at).limit(limit)))
    return [{"id": item.id, "source_type": item.source_type, "company": item.company_label, "role": item.role, "interview_stage": item.interview_stage, "title": item.title, "body": item.body, "license_status": item.license_status, "moderation_status": item.moderation_status, "created_at": item.created_at} for item in items]


@internal_router.post("/reports/{report_id}/moderate")
def moderate_report(report_id: uuid.UUID, payload: ModerationWrite, session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.get(InterviewIntelligenceReport, report_id)
    if item is None: raise HTTPException(status_code=404, detail="Interview report not found")
    item.moderation_status = payload.decision
    if payload.extraction_confidence is not None: item.extraction_confidence = payload.extraction_confidence
    session.commit(); return {"id": item.id, "moderation_status": item.moderation_status}


@internal_router.post("/questions", status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionAdminWrite, session: Session = Depends(get_session)) -> dict[str, Any]:
    item = InterviewIntelligenceQuestion(slug=payload.slug or slugify(payload.title), title=payload.title, track=payload.track, difficulty=payload.difficulty, summary=payload.summary, prompt=payload.prompt, company_labels=payload.companies, skills=payload.skills, patterns=payload.patterns, hints=payload.hints, follow_ups=payload.follow_ups, solution_outline=payload.solution_outline, test_cases=payload.test_cases, starter_code=payload.starter_code, frequency_score=payload.frequency_score, confidence=payload.confidence, report_count=payload.report_count, last_reported_at=payload.last_reported_at, published=payload.published)
    session.add(item)
    try: session.commit()
    except IntegrityError as exc: session.rollback(); raise HTTPException(status_code=409, detail="Interview question slug already exists") from exc
    session.refresh(item); return question_payload(item)


@internal_router.put("/questions/{question_id}")
def update_question(question_id: uuid.UUID, payload: QuestionAdminWrite, session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.get(InterviewIntelligenceQuestion, question_id)
    if item is None: raise HTTPException(status_code=404, detail="Interview question not found")
    values = payload.model_dump(); item.slug = values.pop("slug") or slugify(payload.title); item.company_labels = values.pop("companies")
    for key, value in values.items(): setattr(item, key, value)
    session.commit(); session.refresh(item); return question_payload(item)
