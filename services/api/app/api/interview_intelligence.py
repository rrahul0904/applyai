from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.core.operator_auth import require_operator_or_internal
from app.interview_intelligence_models import (
    InterviewCommunityPost,
    InterviewIntelligenceQuestion,
    InterviewIntelligenceReport,
    InterviewIntelligenceWorkspace,
    InterviewQuestionAttempt,
    InterviewQuestionEvidence,
    InterviewStory,
)
from app.interview_intelligence_service import (
    build_lifecycle,
    build_podcast_scripts,
    evidence_confidence,
    readiness,
    report_fingerprint,
    slugify,
    staged_hint,
)
from app.models import CandidateProfile, CandidateSkill, Company, Job, JobSkill, User

router = APIRouter(prefix="/interview-intelligence", tags=["interview intelligence"])
internal_router = APIRouter(
    prefix="/internal/interview-intelligence",
    tags=["internal interview intelligence"],
    dependencies=[Depends(require_operator_or_internal)],
)

TRACKS = ("CODING", "SQL", "SYSTEM_DESIGN", "ML_SYSTEM_DESIGN", "OOD", "BEHAVIORAL")
DIFFICULTIES = ("EASY", "MEDIUM", "HARD")


class WorkspaceWrite(BaseModel):
    interview_date: datetime | None = None
    interviewer_name: str | None = Field(default=None, max_length=240)
    interviewer_title: str | None = Field(default=None, max_length=240)
    interviewer_url: HttpUrl | None = None
    regenerate: bool = False


class PhaseNotesWrite(BaseModel):
    notes: str = Field(max_length=20_000)


class PhaseReflectionWrite(BaseModel):
    how_it_went: str | None = Field(default=None, max_length=6000)
    surprise: str | None = Field(default=None, max_length=6000)
    difficult_questions: list[str] = Field(default_factory=list, max_length=20)
    learned_about_team: str | None = Field(default=None, max_length=6000)
    prepare_differently: str | None = Field(default=None, max_length=6000)


class StoryWrite(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    categories: list[str] = Field(default_factory=list, max_length=20)
    situation: str | None = Field(default=None, max_length=8000)
    task: str | None = Field(default=None, max_length=8000)
    action: str | None = Field(default=None, max_length=12_000)
    result: str | None = Field(default=None, max_length=8000)
    metrics: list[str] = Field(default_factory=list, max_length=30)
    skills: list[str] = Field(default_factory=list, max_length=50)
    source_fact_ids: list[str] = Field(default_factory=list, max_length=50)
    verified: bool = False


class AttemptWrite(BaseModel):
    question_id: uuid.UUID
    job_id: uuid.UUID | None = None
    answer_text: str | None = Field(default=None, max_length=100_000)
    code_text: str | None = Field(default=None, max_length=100_000)


class AttemptUpdate(BaseModel):
    answer_text: str | None = Field(default=None, max_length=100_000)
    code_text: str | None = Field(default=None, max_length=100_000)
    status: Literal["IN_PROGRESS", "COMPLETED", "ABANDONED"] | None = None


class CoachWrite(BaseModel):
    question_id: uuid.UUID
    answer: str | None = Field(default=None, max_length=100_000)
    hint_level: int = Field(default=0, ge=0, le=20)


class ReportWrite(BaseModel):
    company: str | None = Field(default=None, max_length=240)
    role: str | None = Field(default=None, max_length=240)
    interview_stage: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=320)
    body: str = Field(min_length=20, max_length=50_000)
    reported_at: datetime | None = None
    source_reference: str | None = Field(default=None, max_length=320)

    @field_validator("reported_at")
    @classmethod
    def reject_future_reported_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = value if value.tzinfo is not None and value.utcoffset() is not None else value.replace(tzinfo=timezone.utc)
        if normalized > datetime.now(timezone.utc):
            raise ValueError("reported_at cannot be in the future")
        return normalized


class CommunityPostWrite(BaseModel):
    company: str | None = Field(default=None, max_length=240)
    category: Literal["INTERVIEW_EXPERIENCE", "COMPENSATION", "CAREER_DEVELOPMENT", "COMPANY_CULTURE", "OTHER"] = "INTERVIEW_EXPERIENCE"
    title: str = Field(min_length=5, max_length=320)
    body: str = Field(min_length=20, max_length=30_000)


class CommunityReplyWrite(BaseModel):
    body: str = Field(min_length=2, max_length=12_000)


class ModerationWrite(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]


class EvidenceLinkWrite(BaseModel):
    question_id: uuid.UUID
    confidence: int = Field(default=75, ge=0, le=100)
    evidence_notes: str | None = Field(default=None, max_length=8000)


class QuestionAdminWrite(BaseModel):
    title: str = Field(min_length=5, max_length=320)
    slug: str | None = Field(default=None, max_length=240)
    track: Literal["CODING", "SQL", "SYSTEM_DESIGN", "ML_SYSTEM_DESIGN", "OOD", "BEHAVIORAL"]
    difficulty: Literal["EASY", "MEDIUM", "HARD"] = "MEDIUM"
    summary: str = Field(min_length=20, max_length=10_000)
    prompt: str = Field(min_length=20, max_length=30_000)
    companies: list[str] = Field(default_factory=list, max_length=50)
    stages: list[str] = Field(default_factory=list, max_length=20)
    skills: list[str] = Field(default_factory=list, max_length=50)
    patterns: list[str] = Field(default_factory=list, max_length=50)
    hints: list[str] = Field(default_factory=list, max_length=20)
    follow_ups: list[str] = Field(default_factory=list, max_length=20)
    solution_outline: list[str] = Field(default_factory=list, max_length=30)
    frequency_score: int = Field(default=0, ge=0, le=100)
    published: bool = False


def _candidate_skills(session: Session, user: User) -> list[str]:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    if profile is None:
        return []
    return [
        skill.normalized_name
        for skill in session.scalars(select(CandidateSkill).where(CandidateSkill.profile_id == profile.id))
    ]


def _required_skills(session: Session, job_id: uuid.UUID) -> list[str]:
    return [
        skill.normalized_name
        for skill in session.scalars(
            select(JobSkill).where(JobSkill.job_id == job_id).order_by(JobSkill.required.desc(), JobSkill.name)
        )
    ]


def _company_name(session: Session, job: Job) -> str:
    company = session.get(Company, job.company_id)
    return company.canonical_name if company is not None else "the company"


def _workspace(session: Session, user: User, job_id: uuid.UUID) -> InterviewIntelligenceWorkspace:
    item = session.scalar(
        select(InterviewIntelligenceWorkspace).where(
            InterviewIntelligenceWorkspace.user_id == user.id,
            InterviewIntelligenceWorkspace.job_id == job_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Interview intelligence workspace not found")
    return item


def _serialize_workspace(item: InterviewIntelligenceWorkspace) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "job_id": str(item.job_id),
        "current_phase_number": item.current_phase_number,
        "interview_date": item.interview_date,
        "interviewer": {
            "name": item.interviewer_name,
            "title": item.interviewer_title,
            "url": item.interviewer_url,
        },
        "lifecycle": item.lifecycle_json,
        "readiness": item.readiness_json,
        "podcasts": item.podcast_json,
        "research_sources": item.research_sources_json,
        "status": item.status,
        "updated_at": item.updated_at,
    }


def _serialize_question(item: InterviewIntelligenceQuestion) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "slug": item.slug,
        "title": item.title,
        "track": item.track,
        "difficulty": item.difficulty,
        "summary": item.summary,
        "prompt": item.prompt,
        "companies": item.company_labels or [],
        "stages": item.stages or [],
        "skills": item.skills or [],
        "patterns": item.patterns or [],
        "hints": item.hints or [],
        "follow_ups": item.follow_ups or [],
        "solution_outline": item.solution_outline or [],
        "frequency_score": item.frequency_score,
        "confidence": item.confidence,
        "report_count": item.report_count,
        "last_reported_at": item.last_reported_at,
        "published": item.published,
    }


def _recompute_question(session: Session, question: InterviewIntelligenceQuestion) -> None:
    reports = list(
        session.scalars(
            select(InterviewIntelligenceReport)
            .join(InterviewQuestionEvidence, InterviewQuestionEvidence.report_id == InterviewIntelligenceReport.id)
            .where(
                InterviewQuestionEvidence.question_id == question.id,
                InterviewIntelligenceReport.moderation_status == "APPROVED_LINKED",
            )
        )
    )
    labels = list(question.baseline_company_labels or [])
    for report in reports:
        if report.company_label and report.company_label not in labels:
            labels.append(report.company_label)
    question.company_labels = labels
    question.report_count = len(reports)
    question.frequency_score = min(100, int(question.baseline_frequency_score or 0) + len(reports) * 5)
    dates = [report.reported_at or report.created_at for report in reports if report.reported_at or report.created_at]
    question.last_reported_at = max(dates) if dates else None
    question.confidence = evidence_confidence(question.report_count, question.last_reported_at)


def _score_attempt(question: InterviewIntelligenceQuestion, answer: str | None, code: str | None) -> tuple[int, dict]:
    response = (answer or code or "").strip()
    if not response:
        return 0, {"summary": "No answer was supplied."}
    words = len(response.split())
    expected = {token.lower() for token in (question.skills or []) + (question.patterns or [])}
    response_lower = response.lower()
    covered = sum(1 for token in expected if token and token in response_lower)
    score = min(100, 35 + min(35, words // 4) + min(30, covered * 10))
    return score, {
        "summary": "Answer scored with deterministic completeness and topic-coverage checks; use ApplyAI mocks for richer coaching.",
        "word_count": words,
        "covered_topics": covered,
        "expected_topics": len(expected),
    }


@router.get("/capabilities")
def capabilities() -> dict[str, Any]:
    return {
        "tracks": list(TRACKS),
        "features": {
            "job_lifecycle": True,
            "question_bank": True,
            "company_collections": True,
            "recency_confidence": True,
            "company_question_bank_filters": True,
            "interview_stage_filter": True,
            "freshness_sort": True,
            "per_question_progress": True,
            "durable_attempts": True,
            "staged_coaching": True,
            "candidate_reports": True,
            "community": True,
            "star_story_bank": True,
            "flashcards": True,
            "retrospectives": True,
            "podcast_scripts": True,
            "embedded_code_execution": False,
        },
        "execution_boundary": "external-isolated-integration",
        "clean_room": True,
    }


@router.post("/workspaces/{job_id}", status_code=status.HTTP_201_CREATED)
def bootstrap_workspace(
    job_id: uuid.UUID,
    payload: WorkspaceWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    item = session.scalar(
        select(InterviewIntelligenceWorkspace).where(
            InterviewIntelligenceWorkspace.user_id == user.id,
            InterviewIntelligenceWorkspace.job_id == job_id,
        )
    )
    if item is None:
        item = InterviewIntelligenceWorkspace(user_id=user.id, job_id=job_id)
        session.add(item)
        session.flush()
    fields_set = payload.model_fields_set
    if "interview_date" in fields_set:
        item.interview_date = payload.interview_date
    if "interviewer_name" in fields_set:
        item.interviewer_name = payload.interviewer_name
    if "interviewer_title" in fields_set:
        item.interviewer_title = payload.interviewer_title
    if "interviewer_url" in fields_set:
        item.interviewer_url = str(payload.interviewer_url) if payload.interviewer_url else None
    company = _company_name(session, job)
    lifecycle = build_lifecycle(
        job_title=job.title,
        company=company,
        candidate_skills=_candidate_skills(session, user),
        required_skills=_required_skills(session, job_id),
        prior=item.lifecycle_json,
    )
    item.lifecycle_json = lifecycle
    item.podcast_json = build_podcast_scripts(job_title=job.title, company=company, lifecycle=lifecycle)
    item.readiness_json = readiness(current_phase=item.current_phase_number, lifecycle=lifecycle)
    item.status = "READY"
    session.commit()
    session.refresh(item)
    return _serialize_workspace(item)


@router.get("/workspaces/{job_id}")
def get_workspace(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return _serialize_workspace(_workspace(session, user, job_id))


@router.put("/workspaces/{job_id}/phases/{phase_number}/notes")
def update_phase_notes(
    job_id: uuid.UUID,
    phase_number: int,
    payload: PhaseNotesWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    item = _workspace(session, user, job_id)
    lifecycle = dict(item.lifecycle_json or {})
    phases = [dict(phase) for phase in lifecycle.get("phases", [])]
    matched = False
    for phase in phases:
        if int(phase.get("phase_number", 0)) == phase_number:
            phase["notes"] = payload.notes
            matched = True
            break
    if not matched:
        raise HTTPException(status_code=404, detail="Interview phase not found")
    lifecycle["phases"] = phases
    item.lifecycle_json = lifecycle
    item.readiness_json = readiness(current_phase=item.current_phase_number, lifecycle=lifecycle)
    session.commit()
    session.refresh(item)
    return _serialize_workspace(item)


@router.post("/workspaces/{job_id}/phases/{phase_number}/reflection")
def submit_phase_reflection(
    job_id: uuid.UUID,
    phase_number: int,
    payload: PhaseReflectionWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    item = _workspace(session, user, job_id)
    if phase_number != item.current_phase_number:
        raise HTTPException(status_code=409, detail="Only the current interview phase can be completed")
    lifecycle = dict(item.lifecycle_json or {})
    phases = [dict(phase) for phase in lifecycle.get("phases", [])]
    matched = False
    carry = list(lifecycle.get("carry_forward") or [])
    reflection = payload.model_dump()
    for phase in phases:
        if int(phase.get("phase_number", 0)) == phase_number:
            phase["reflection"] = reflection
            additions = [value for value in [payload.prepare_differently, *payload.difficult_questions] if value]
            existing = list(phase.get("carry_forward") or [])
            for value in additions:
                if value not in existing:
                    existing.append(value)
                if value not in carry:
                    carry.append(value)
            phase["carry_forward"] = existing
            matched = True
            break
    if not matched:
        raise HTTPException(status_code=404, detail="Interview phase not found")
    lifecycle["phases"] = phases
    lifecycle["carry_forward"] = carry
    item.lifecycle_json = lifecycle
    item.current_phase_number = min(4, item.current_phase_number + 1)
    item.status = "COMPLETE" if phase_number == 4 else "READY"
    item.readiness_json = readiness(current_phase=item.current_phase_number, lifecycle=lifecycle)
    session.commit()
    session.refresh(item)
    return _serialize_workspace(item)


@router.get("/stories")
def list_stories(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    items = list(session.scalars(select(InterviewStory).where(InterviewStory.user_id == user.id).order_by(InterviewStory.updated_at.desc()).limit(100)))
    return [
        {"id": str(item.id), "title": item.title, "categories": item.categories, "situation": item.situation, "task": item.task, "action": item.action, "result": item.result, "metrics": item.metrics, "skills": item.skills, "source_fact_ids": item.source_fact_ids, "verified": item.verified}
        for item in items
    ]


@router.post("/stories", status_code=status.HTTP_201_CREATED)
def create_story(payload: StoryWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = InterviewStory(user_id=user.id, **payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": str(item.id), "title": item.title, "verified": item.verified}


@router.get("/questions")
def list_questions(
    q: str | None = Query(default=None, max_length=200),
    company: str | None = Query(default=None, max_length=240),
    track: str | None = None,
    difficulty: str | None = None,
    stage: str | None = Query(default=None, max_length=120),
    reported_within_days: int | None = Query(default=None, ge=1, le=730),
    sort: Literal["frequency", "recent", "confidence"] = "frequency",
    min_confidence: int = Query(default=0, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=100),
    _user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if track and track not in TRACKS:
        raise HTTPException(status_code=422, detail="Unsupported interview track")
    if difficulty and difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=422, detail="Unsupported difficulty")
    statement = select(InterviewIntelligenceQuestion).where(InterviewIntelligenceQuestion.published.is_(True))
    if track:
        statement = statement.where(InterviewIntelligenceQuestion.track == track)
    if difficulty:
        statement = statement.where(InterviewIntelligenceQuestion.difficulty == difficulty)
    if min_confidence:
        statement = statement.where(InterviewIntelligenceQuestion.confidence >= min_confidence)
    if reported_within_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=reported_within_days)
        statement = statement.where(InterviewIntelligenceQuestion.last_reported_at >= cutoff)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(InterviewIntelligenceQuestion.title.ilike(pattern), InterviewIntelligenceQuestion.summary.ilike(pattern), InterviewIntelligenceQuestion.prompt.ilike(pattern)))
    if company:
        statement = statement.where(
            text(
                "EXISTS ("
                "SELECT 1 FROM jsonb_array_elements_text(interview_intelligence_questions.company_labels) AS company_label(value) "
                "WHERE lower(company_label.value) = :company_key"
                ")"
            )
        ).params(company_key=company.strip().lower())
    if stage:
        statement = statement.where(
            text(
                "EXISTS ("
                "SELECT 1 FROM jsonb_array_elements_text(interview_intelligence_questions.stages) AS stage_label(value) "
                "WHERE lower(stage_label.value) = :stage_key"
                ")"
            )
        ).params(stage_key=stage.strip().lower())
    total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    if sort == "recent":
        ordering = (InterviewIntelligenceQuestion.last_reported_at.desc().nulls_last(), InterviewIntelligenceQuestion.frequency_score.desc())
    elif sort == "confidence":
        ordering = (InterviewIntelligenceQuestion.confidence.desc(), InterviewIntelligenceQuestion.frequency_score.desc())
    else:
        ordering = (InterviewIntelligenceQuestion.frequency_score.desc(), InterviewIntelligenceQuestion.confidence.desc())
    items = list(session.scalars(statement.order_by(*ordering).limit(limit)))
    return {"items": [_serialize_question(item) for item in items], "total": total}


@router.get("/questions/{slug}")
def get_question(slug: str, _user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.scalar(select(InterviewIntelligenceQuestion).where(InterviewIntelligenceQuestion.slug == slug, InterviewIntelligenceQuestion.published.is_(True)))
    if item is None:
        raise HTTPException(status_code=404, detail="Interview question not found")
    return _serialize_question(item)


@router.get("/companies")
def company_collections(_user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    items = list(session.scalars(select(InterviewIntelligenceQuestion).where(InterviewIntelligenceQuestion.published.is_(True)).limit(2000)))
    stats: dict[str, dict[str, Any]] = {}
    for item in items:
        for company in item.company_labels or []:
            entry = stats.setdefault(company, {"name": company, "slug": slugify(company), "question_count": 0, "report_count": 0, "tracks": Counter(), "stages": Counter()})
            entry["question_count"] += 1
            entry["report_count"] += item.report_count
            entry["tracks"][item.track] += 1
            for stage in item.stages or []:
                entry["stages"][stage] += 1
    return sorted(({**entry, "tracks": dict(entry["tracks"]), "stages": dict(entry["stages"])} for entry in stats.values()), key=lambda item: (item["question_count"], item["report_count"]), reverse=True)


@router.post("/attempts", status_code=status.HTTP_201_CREATED)
def create_attempt(payload: AttemptWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    question = session.get(InterviewIntelligenceQuestion, payload.question_id)
    if question is None or not question.published:
        raise HTTPException(status_code=404, detail="Interview question not found")
    if payload.job_id is not None and session.get(Job, payload.job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    score, feedback = _score_attempt(question, payload.answer_text, payload.code_text)
    item = InterviewQuestionAttempt(user_id=user.id, question_id=question.id, job_id=payload.job_id, answer_text=payload.answer_text, code_text=payload.code_text, status="COMPLETED", score=score, feedback_json=feedback)
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": str(item.id), "status": item.status, "score": item.score, "feedback": item.feedback_json}


@router.get("/progress")
def progress(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    question_rows = session.execute(
        select(
            InterviewQuestionAttempt.question_id,
            func.count(InterviewQuestionAttempt.id).label("attempts"),
            func.max(InterviewQuestionAttempt.score).label("best_score"),
        )
        .where(InterviewQuestionAttempt.user_id == user.id)
        .group_by(InterviewQuestionAttempt.question_id)
    ).all()

    latest_ranked = (
        select(
            InterviewQuestionAttempt.question_id.label("question_id"),
            InterviewQuestionAttempt.score.label("score"),
            func.row_number()
            .over(
                partition_by=InterviewQuestionAttempt.question_id,
                order_by=(InterviewQuestionAttempt.created_at.desc(), InterviewQuestionAttempt.id.desc()),
            )
            .label("row_number"),
        )
        .where(
            InterviewQuestionAttempt.user_id == user.id,
            InterviewQuestionAttempt.score.is_not(None),
        )
        .subquery()
    )
    latest_scores = {
        row.question_id: row.score
        for row in session.execute(
            select(latest_ranked.c.question_id, latest_ranked.c.score).where(latest_ranked.c.row_number == 1)
        )
    }

    track_rows = session.execute(
        select(
            InterviewIntelligenceQuestion.track,
            func.count(InterviewQuestionAttempt.id).label("attempts"),
            func.coalesce(func.sum(InterviewQuestionAttempt.score), 0).label("score_total"),
            func.count(InterviewQuestionAttempt.score).label("scored"),
        )
        .join(
            InterviewIntelligenceQuestion,
            InterviewIntelligenceQuestion.id == InterviewQuestionAttempt.question_id,
        )
        .where(InterviewQuestionAttempt.user_id == user.id)
        .group_by(InterviewIntelligenceQuestion.track)
    ).all()

    by_question = {
        str(row.question_id): {
            "attempts": int(row.attempts),
            "best_score": int(row.best_score) if row.best_score is not None else None,
            "latest_score": int(latest_scores[row.question_id]) if latest_scores.get(row.question_id) is not None else None,
        }
        for row in question_rows
    }
    by_track = {
        row.track: {
            "attempts": int(row.attempts),
            "average_score": round(int(row.score_total) / int(row.scored)) if row.scored else 0,
        }
        for row in track_rows
    }
    total_attempts = sum(item["attempts"] for item in by_question.values())
    return {"total_attempts": total_attempts, "by_track": by_track, "by_question": by_question}


@router.post("/coach")
def coach(payload: CoachWrite, _user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    question = session.get(InterviewIntelligenceQuestion, payload.question_id)
    if question is None or not question.published:
        raise HTTPException(status_code=404, detail="Interview question not found")
    return {**staged_hint(question.hints or [], payload.hint_level, payload.answer), "provider": "applyai-evidence-coach", "question_id": str(question.id)}


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def submit_report(payload: ReportWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    fingerprint = report_fingerprint(company=payload.company, role=payload.role, stage=payload.interview_stage, body=payload.body)
    existing = session.scalar(select(InterviewIntelligenceReport).where(InterviewIntelligenceReport.fingerprint == fingerprint))
    if existing is not None:
        return {"id": str(existing.id), "moderation_status": existing.moderation_status, "duplicate": True}
    item = InterviewIntelligenceReport(contributor_user_id=user.id, company_label=payload.company, role=payload.role, interview_stage=payload.interview_stage, title=payload.title, body=payload.body, fingerprint=fingerprint, source_reference=payload.source_reference, reported_at=payload.reported_at)
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": str(item.id), "moderation_status": item.moderation_status, "duplicate": False}


@router.get("/community")
def list_community(
    company: str | None = None,
    category: str | None = None,
    _user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    statement = select(InterviewCommunityPost).where(InterviewCommunityPost.moderation_status == "PUBLISHED")
    if company:
        statement = statement.where(InterviewCommunityPost.company_label.ilike(company))
    if category:
        statement = statement.where(InterviewCommunityPost.category == category)
    items = list(session.scalars(statement.order_by(InterviewCommunityPost.created_at.desc()).limit(100)))
    return [{"id": str(item.id), "company": item.company_label, "category": item.category, "title": item.title, "body": item.body, "replies": item.replies_json, "reaction_count": len(item.reaction_user_ids or []), "created_at": item.created_at} for item in items]


@router.post("/community", status_code=status.HTTP_201_CREATED)
def create_community_post(payload: CommunityPostWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = InterviewCommunityPost(user_id=user.id, company_label=payload.company, category=payload.category, title=payload.title, body=payload.body)
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": str(item.id), "title": item.title, "reaction_count": 0, "replies": []}


@router.post("/community/{post_id}/replies", status_code=status.HTTP_201_CREATED)
def create_community_reply(post_id: uuid.UUID, payload: CommunityReplyWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.scalar(
        select(InterviewCommunityPost)
        .where(InterviewCommunityPost.id == post_id)
        .with_for_update()
    )
    if item is None or item.moderation_status != "PUBLISHED":
        raise HTTPException(status_code=404, detail="Community post not found")
    replies = list(item.replies_json or [])
    reply = {"id": str(uuid.uuid4()), "user_id": str(user.id), "body": payload.body, "created_at": datetime.now(timezone.utc).isoformat()}
    replies.append(reply)
    item.replies_json = replies[-200:]
    session.commit()
    return reply


@router.post("/community/{post_id}/react")
def react(post_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.scalar(
        select(InterviewCommunityPost)
        .where(InterviewCommunityPost.id == post_id)
        .with_for_update()
    )
    if item is None or item.moderation_status != "PUBLISHED":
        raise HTTPException(status_code=404, detail="Community post not found")
    users = list(item.reaction_user_ids or [])
    user_id = str(user.id)
    if user_id in users:
        users = [value for value in users if value != user_id]
        reacted = False
    else:
        users.append(user_id)
        reacted = True
    item.reaction_user_ids = users
    session.commit()
    return {"reacted": reacted, "reaction_count": len(users)}


@internal_router.get("/reports")
def moderation_queue(
    moderation_status: str | None = Query(default=None, max_length=48),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    statement = select(InterviewIntelligenceReport)
    if moderation_status:
        statement = statement.where(InterviewIntelligenceReport.moderation_status == moderation_status)
    else:
        statement = statement.where(InterviewIntelligenceReport.moderation_status.in_(("REVIEW_REQUIRED", "APPROVED_UNLINKED")))
    items = list(session.scalars(statement.order_by(InterviewIntelligenceReport.created_at).limit(500)))
    return [{"id": str(item.id), "company": item.company_label, "role": item.role, "interview_stage": item.interview_stage, "title": item.title, "body": item.body, "moderation_status": item.moderation_status, "created_at": item.created_at} for item in items]


@internal_router.post("/reports/{report_id}/moderate")
def moderate_report(report_id: uuid.UUID, payload: ModerationWrite, session: Session = Depends(get_session)) -> dict[str, Any]:
    item = session.get(InterviewIntelligenceReport, report_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Interview report not found")
    evidence_rows = list(
        session.scalars(
            select(InterviewQuestionEvidence).where(
                InterviewQuestionEvidence.report_id == item.id
            )
        )
    )
    if payload.decision == "APPROVED":
        item.moderation_status = "APPROVED_LINKED" if evidence_rows else "APPROVED_UNLINKED"
    else:
        affected_question_ids = {evidence.question_id for evidence in evidence_rows}
        for evidence in evidence_rows:
            session.delete(evidence)
        session.flush()
        item.moderation_status = "REJECTED"
        for question_id in affected_question_ids:
            question = session.get(InterviewIntelligenceQuestion, question_id)
            if question is not None:
                _recompute_question(session, question)
    session.commit()
    return {"id": str(item.id), "moderation_status": item.moderation_status}


@internal_router.post("/reports/{report_id}/evidence")
def link_report(report_id: uuid.UUID, payload: EvidenceLinkWrite, session: Session = Depends(get_session)) -> dict[str, Any]:
    report = session.get(InterviewIntelligenceReport, report_id)
    question = session.get(InterviewIntelligenceQuestion, payload.question_id)
    if report is None or question is None:
        raise HTTPException(status_code=404, detail="Report or interview question not found")
    if report.moderation_status not in {"APPROVED_UNLINKED", "APPROVED_LINKED"}:
        raise HTTPException(status_code=409, detail="Only approved reports can become question evidence")
    existing = session.scalar(select(InterviewQuestionEvidence).where(InterviewQuestionEvidence.question_id == question.id, InterviewQuestionEvidence.report_id == report.id))
    if existing is None:
        session.add(InterviewQuestionEvidence(question_id=question.id, report_id=report.id, confidence=payload.confidence, evidence_notes=payload.evidence_notes))
        session.flush()
    report.moderation_status = "APPROVED_LINKED"
    _recompute_question(session, question)
    session.commit()
    return {"report_id": str(report.id), "question": _serialize_question(question), "moderation_status": report.moderation_status}


@internal_router.delete("/evidence/{evidence_id}")
def unlink_evidence(evidence_id: uuid.UUID, session: Session = Depends(get_session)) -> dict[str, Any]:
    evidence = session.get(InterviewQuestionEvidence, evidence_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="Interview evidence not found")
    question = session.get(InterviewIntelligenceQuestion, evidence.question_id)
    report = session.get(InterviewIntelligenceReport, evidence.report_id)
    session.delete(evidence)
    session.flush()
    if report is not None:
        remaining = int(session.scalar(select(func.count()).select_from(InterviewQuestionEvidence).where(InterviewQuestionEvidence.report_id == report.id)) or 0)
        report.moderation_status = "APPROVED_LINKED" if remaining else "APPROVED_UNLINKED"
    if question is not None:
        _recompute_question(session, question)
    session.commit()
    return {"deleted": True, "report_status": report.moderation_status if report else None, "question": _serialize_question(question) if question else None}


@internal_router.post("/questions", status_code=status.HTTP_201_CREATED)
def create_question(payload: QuestionAdminWrite, session: Session = Depends(get_session)) -> dict[str, Any]:
    labels = list(dict.fromkeys(payload.companies))
    item = InterviewIntelligenceQuestion(
        slug=payload.slug or slugify(payload.title),
        title=payload.title,
        track=payload.track,
        difficulty=payload.difficulty,
        summary=payload.summary,
        prompt=payload.prompt,
        baseline_company_labels=labels,
        company_labels=labels,
        stages=list(dict.fromkeys(payload.stages)),
        skills=payload.skills,
        patterns=payload.patterns,
        hints=payload.hints,
        follow_ups=payload.follow_ups,
        solution_outline=payload.solution_outline,
        baseline_frequency_score=payload.frequency_score,
        frequency_score=payload.frequency_score,
        confidence=30,
        published=payload.published,
    )
    session.add(item)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Interview question slug already exists") from exc
    session.refresh(item)
    return _serialize_question(item)


@internal_router.get("/metrics")
def metrics(session: Session = Depends(get_session)) -> dict[str, int]:
    count = lambda model: int(session.scalar(select(func.count()).select_from(model)) or 0)
    return {
        "questions": count(InterviewIntelligenceQuestion),
        "reports": count(InterviewIntelligenceReport),
        "attempts": count(InterviewQuestionAttempt),
        "workspaces": count(InterviewIntelligenceWorkspace),
        "stories": count(InterviewStory),
        "community_posts": count(InterviewCommunityPost),
    }
