from __future__ import annotations

import html
import secrets
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.interview_intelligence_models import (
    InterviewPhase,
    InterviewPodcastEpisode,
    InterviewPracticeAttempt,
    InterviewPracticeQuestion,
    InterviewPreparation,
    InterviewResearchSource,
    InterviewStory,
)
from app.interview_intelligence_service import (
    PHASES,
    build_analysis,
    evaluate_answer,
    load_context,
    phase_content,
    podcast_episodes,
    readiness_from_scores,
)
from app.models import Job, User

router = APIRouter(prefix="/interview-intelligence", tags=["interview intelligence"])


class InterviewSetupWrite(BaseModel):
    country: str | None = Field(default=None, max_length=120)
    interview_date: datetime | None = None
    current_phase_number: int = Field(default=1, ge=1, le=4)
    interviewer_name: str | None = Field(default=None, max_length=240)
    interviewer_title: str | None = Field(default=None, max_length=240)
    interviewer_url: HttpUrl | None = None
    regenerate: bool = False


class PhaseNotesWrite(BaseModel):
    notes: str = Field(max_length=20000)


class PhaseReflectionWrite(BaseModel):
    how_it_went: str | None = Field(default=None, max_length=6000)
    surprise: str | None = Field(default=None, max_length=6000)
    difficult_questions: list[str] = Field(default_factory=list, max_length=20)
    learned_about_team: str | None = Field(default=None, max_length=6000)
    prepare_differently: str | None = Field(default=None, max_length=6000)


class AttemptWrite(BaseModel):
    answer_text: str = Field(min_length=1, max_length=30000)
    transcript_source: str = Field(default="TEXT", max_length=32)
    duration_seconds: int | None = Field(default=None, ge=0, le=7200)


class ResearchSourceWrite(BaseModel):
    source_kind: str = Field(default="USER_RESEARCH", max_length=48)
    title: str = Field(min_length=1, max_length=320)
    url: HttpUrl | None = None
    snippet: str | None = Field(default=None, max_length=12000)
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class StoryWrite(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    categories: list[str] = Field(default_factory=list, max_length=20)
    situation: str | None = Field(default=None, max_length=8000)
    task: str | None = Field(default=None, max_length=8000)
    action: str | None = Field(default=None, max_length=12000)
    result: str | None = Field(default=None, max_length=8000)
    metrics: list[str] = Field(default_factory=list, max_length=30)
    skills: list[str] = Field(default_factory=list, max_length=50)
    source_fact_ids: list[str] = Field(default_factory=list, max_length=50)
    verified: bool = False


def _owned_preparation(session: Session, user: User, job_id: uuid.UUID) -> InterviewPreparation:
    item = session.scalar(
        select(InterviewPreparation).where(
            InterviewPreparation.user_id == user.id,
            InterviewPreparation.job_id == job_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Interview preparation not found")
    return item


def _owned_phase(
    session: Session, user: User, phase_id: uuid.UUID
) -> tuple[InterviewPreparation, InterviewPhase]:
    phase = session.get(InterviewPhase, phase_id)
    if phase is None:
        raise HTTPException(status_code=404, detail="Interview phase not found")
    prep = session.scalar(
        select(InterviewPreparation).where(
            InterviewPreparation.id == phase.preparation_id,
            InterviewPreparation.user_id == user.id,
        )
    )
    if prep is None:
        raise HTTPException(status_code=404, detail="Interview phase not found")
    return prep, phase


def _serialize_question(item: InterviewPracticeQuestion) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "mode": item.mode,
        "prompt": item.prompt,
        "model_answer": item.model_answer,
        "rubric": item.rubric,
        "followups": item.followups,
        "display_order": item.display_order,
    }


def _serialize_preparation(session: Session, prep: InterviewPreparation) -> dict[str, Any]:
    job = session.get(Job, prep.job_id)
    phases = list(
        session.scalars(
            select(InterviewPhase)
            .where(InterviewPhase.preparation_id == prep.id)
            .order_by(InterviewPhase.phase_number)
        )
    )
    phase_payload: list[dict[str, Any]] = []
    for phase in phases:
        questions = list(
            session.scalars(
                select(InterviewPracticeQuestion)
                .where(InterviewPracticeQuestion.phase_id == phase.id)
                .order_by(InterviewPracticeQuestion.display_order)
            )
        )
        phase_payload.append(
            {
                "id": str(phase.id),
                "phase_number": phase.phase_number,
                "phase_type": phase.phase_type,
                "title": phase.title,
                "status": phase.status,
                "prep": phase.prep,
                "quiz": phase.quiz,
                "flashcards": phase.flashcards,
                "notes": phase.notes,
                "reflection": phase.reflection,
                "cheat_sheet": phase.cheat_sheet,
                "readiness": phase.readiness,
                "questions": [_serialize_question(item) for item in questions],
            }
        )
    episodes = list(
        session.scalars(
            select(InterviewPodcastEpisode)
            .where(InterviewPodcastEpisode.preparation_id == prep.id)
            .order_by(InterviewPodcastEpisode.episode_number)
        )
    )
    sources = list(
        session.scalars(
            select(InterviewResearchSource)
            .where(InterviewResearchSource.preparation_id == prep.id)
            .order_by(InterviewResearchSource.created_at.desc())
        )
    )
    return {
        "id": str(prep.id),
        "job_id": str(prep.job_id),
        "job": {
            "title": job.title if job else "Interview",
            "description": job.description if job else "",
        },
        "status": prep.status,
        "country": prep.country,
        "interview_date": prep.interview_date,
        "current_phase_number": prep.current_phase_number,
        "interviewer": {
            "name": prep.interviewer_name,
            "title": prep.interviewer_title,
            "url": prep.interviewer_url,
            "brief": prep.interviewer_brief,
        },
        "company_research": prep.company_research,
        "role_analysis": prep.role_analysis,
        "resume_analysis": prep.resume_analysis,
        "market_benchmark": prep.market_benchmark,
        "readiness": prep.readiness,
        "private_feed_token": prep.private_feed_token,
        "phases": phase_payload,
        "episodes": [
            {
                "id": str(item.id),
                "episode_number": item.episode_number,
                "title": item.title,
                "summary": item.summary,
                "script": item.script,
                "duration_estimate_minutes": item.duration_estimate_minutes,
                "audio_url": item.audio_url,
                "status": item.status,
            }
            for item in episodes
        ],
        "research_sources": [
            {
                "id": str(item.id),
                "source_kind": item.source_kind,
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "source_metadata": item.source_metadata,
                "created_at": item.created_at,
            }
            for item in sources
        ],
    }


def _refresh_readiness(session: Session, prep: InterviewPreparation) -> None:
    phases = list(
        session.scalars(select(InterviewPhase).where(InterviewPhase.preparation_id == prep.id))
    )
    phase_ids = [phase.id for phase in phases]
    question_ids = (
        list(
            session.scalars(
                select(InterviewPracticeQuestion.id).where(
                    InterviewPracticeQuestion.phase_id.in_(phase_ids)
                )
            )
        )
        if phase_ids
        else []
    )
    scores = (
        list(
            session.scalars(
                select(InterviewPracticeAttempt.score).where(
                    InterviewPracticeAttempt.user_id == prep.user_id,
                    InterviewPracticeAttempt.question_id.in_(question_ids),
                )
            )
        )
        if question_ids
        else []
    )
    completed_reflections = sum(1 for phase in phases if phase.reflection)
    completed_notes = sum(1 for phase in phases if (phase.notes or "").strip())
    prep.readiness = readiness_from_scores(
        scores, completed_reflections, completed_notes, len(phases)
    )
    for phase in phases:
        ids = list(
            session.scalars(
                select(InterviewPracticeQuestion.id).where(
                    InterviewPracticeQuestion.phase_id == phase.id
                )
            )
        )
        phase_scores = (
            list(
                session.scalars(
                    select(InterviewPracticeAttempt.score).where(
                        InterviewPracticeAttempt.user_id == prep.user_id,
                        InterviewPracticeAttempt.question_id.in_(ids),
                    )
                )
            )
            if ids
            else []
        )
        phase.readiness = {
            "score": round(sum(phase_scores) / len(phase_scores)) if phase_scores else 45,
            "attempt_count": len(phase_scores),
        }


def _upsert_questions(
    session: Session,
    phase: InterviewPhase,
    generated_questions: list[dict[str, Any]],
) -> None:
    """Refresh question content without changing IDs or deleting attempt history."""
    existing = {
        item.display_order: item
        for item in session.scalars(
            select(InterviewPracticeQuestion).where(
                InterviewPracticeQuestion.phase_id == phase.id
            )
        )
    }
    for payload in generated_questions:
        display_order = int(payload["display_order"])
        item = existing.get(display_order)
        if item is None:
            session.add(InterviewPracticeQuestion(phase_id=phase.id, **payload))
            continue
        item.mode = str(payload["mode"])
        item.prompt = str(payload["prompt"])
        item.model_answer = str(payload["model_answer"])
        item.rubric = dict(payload.get("rubric") or {})
        item.followups = list(payload.get("followups") or [])


def _upsert_episodes(
    session: Session,
    prep: InterviewPreparation,
    generated_episodes: list[dict[str, Any]],
) -> None:
    existing = {
        item.episode_number: item
        for item in session.scalars(
            select(InterviewPodcastEpisode).where(
                InterviewPodcastEpisode.preparation_id == prep.id
            )
        )
    }
    for payload in generated_episodes:
        episode_number = int(payload["episode_number"])
        item = existing.get(episode_number)
        if item is None:
            session.add(InterviewPodcastEpisode(preparation_id=prep.id, **payload))
            continue
        item.title = str(payload["title"])
        item.summary = str(payload["summary"])
        item.script = list(payload.get("script") or [])
        item.duration_estimate_minutes = int(payload.get("duration_estimate_minutes") or 10)
        # Preserve hosted audio when refreshing only the written preparation.
        if not item.audio_url:
            item.status = "SCRIPT_READY"


def _generate(session: Session, prep: InterviewPreparation, user: User) -> None:
    try:
        ctx = load_context(session, user.id, prep.job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    analysis = build_analysis(ctx)
    prep.company_research = analysis["company_research"]
    prep.role_analysis = analysis["role_analysis"]
    prep.resume_analysis = analysis["resume_analysis"]
    prep.market_benchmark = analysis["market_benchmark"]
    prep.interviewer_brief = {
        "name": prep.interviewer_name,
        "title": prep.interviewer_title,
        "profile_url": prep.interviewer_url,
        "likely_priorities": analysis["role_analysis"].get("likely_focus", [])[:5],
        "questions_to_ask": [
            "What problem would you most like the person in this role to solve first?",
            "How do you evaluate excellent performance on this team?",
            "Which trade-offs are hardest for the team right now?",
        ],
        "evidence_note": (
            "Interviewer-specific claims are not invented. Add reviewed public-source "
            "evidence when available."
        ),
    }

    existing_phases = {
        item.phase_number: item
        for item in session.scalars(
            select(InterviewPhase).where(InterviewPhase.preparation_id == prep.id)
        )
    }
    for phase_number, phase_type, title in PHASES:
        generated = phase_content(ctx, phase_number, phase_type, title)
        phase = existing_phases.get(phase_number)
        if phase is None:
            phase = InterviewPhase(
                preparation_id=prep.id,
                phase_number=phase_number,
                phase_type=phase_type,
                title=title,
                status="CURRENT" if phase_number == prep.current_phase_number else "UPCOMING",
            )
            session.add(phase)
            session.flush()
        prior_notes = phase.notes
        prior_reflection = phase.reflection
        phase.phase_type = phase_type
        phase.title = title
        phase.status = (
            "CURRENT"
            if phase_number == prep.current_phase_number
            else ("COMPLETE" if phase_number < prep.current_phase_number else "UPCOMING")
        )
        phase.prep = generated["prep"]
        phase.quiz = generated["quiz"]
        phase.flashcards = generated["flashcards"]
        phase.cheat_sheet = generated["cheat_sheet"]
        phase.notes = prior_notes
        phase.reflection = prior_reflection
        _upsert_questions(session, phase, generated["questions"])

    _upsert_episodes(session, prep, podcast_episodes(ctx, analysis))
    prep.status = "READY"
    _refresh_readiness(session, prep)


@router.get("/{job_id}")
def get_preparation(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    prep = _owned_preparation(session, user, job_id)
    _refresh_readiness(session, prep)
    session.commit()
    return _serialize_preparation(session, prep)


@router.post("/{job_id}/bootstrap", status_code=status.HTTP_201_CREATED)
def bootstrap_preparation(
    job_id: uuid.UUID,
    payload: InterviewSetupWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if session.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    prep = session.scalar(
        select(InterviewPreparation).where(
            InterviewPreparation.user_id == user.id,
            InterviewPreparation.job_id == job_id,
        )
    )
    created = prep is None
    if prep is None:
        prep = InterviewPreparation(
            user_id=user.id,
            job_id=job_id,
            private_feed_token=secrets.token_urlsafe(32),
        )
        session.add(prep)
        session.flush()
    prep.country = payload.country
    prep.interview_date = payload.interview_date
    prep.current_phase_number = payload.current_phase_number
    prep.interviewer_name = payload.interviewer_name
    prep.interviewer_title = payload.interviewer_title
    prep.interviewer_url = str(payload.interviewer_url) if payload.interviewer_url else None
    has_phases = bool(
        session.scalar(
            select(func.count())
            .select_from(InterviewPhase)
            .where(InterviewPhase.preparation_id == prep.id)
        )
    )
    if created or payload.regenerate or not has_phases:
        _generate(session, prep, user)
    else:
        for phase in session.scalars(
            select(InterviewPhase).where(InterviewPhase.preparation_id == prep.id)
        ):
            phase.status = (
                "CURRENT"
                if phase.phase_number == prep.current_phase_number
                else (
                    "COMPLETE"
                    if phase.phase_number < prep.current_phase_number
                    else "UPCOMING"
                )
            )
        prep.interviewer_brief = {
            **(prep.interviewer_brief or {}),
            "name": prep.interviewer_name,
            "title": prep.interviewer_title,
            "profile_url": prep.interviewer_url,
        }
        _refresh_readiness(session, prep)
    session.commit()
    session.refresh(prep)
    return _serialize_preparation(session, prep)


@router.post("/{job_id}/regenerate")
def regenerate_preparation(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    prep = _owned_preparation(session, user, job_id)
    _generate(session, prep, user)
    session.commit()
    return _serialize_preparation(session, prep)


@router.put("/phases/{phase_id}/notes")
def save_phase_notes(
    phase_id: uuid.UUID,
    payload: PhaseNotesWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    prep, phase = _owned_phase(session, user, phase_id)
    phase.notes = payload.notes
    _refresh_readiness(session, prep)
    session.commit()
    return {"id": str(phase.id), "notes": phase.notes, "readiness": prep.readiness}


@router.post("/phases/{phase_id}/reflection")
def save_phase_reflection(
    phase_id: uuid.UUID,
    payload: PhaseReflectionWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    prep, phase = _owned_phase(session, user, phase_id)
    phase.reflection = payload.model_dump()
    phase.status = "COMPLETE"
    next_phase = session.scalar(
        select(InterviewPhase).where(
            InterviewPhase.preparation_id == prep.id,
            InterviewPhase.phase_number == phase.phase_number + 1,
        )
    )
    if next_phase is not None:
        prep.current_phase_number = next_phase.phase_number
        next_phase.status = "CURRENT"
        carry_forward = [
            *payload.difficult_questions,
            *([payload.prepare_differently] if payload.prepare_differently else []),
        ]
        next_phase.prep = {
            **(next_phase.prep or {}),
            "carry_forward": carry_forward[:10],
        }
    _refresh_readiness(session, prep)
    session.commit()
    return {
        "reflection": phase.reflection,
        "next_phase_number": prep.current_phase_number,
        "readiness": prep.readiness,
    }


@router.post("/questions/{question_id}/attempts", status_code=status.HTTP_201_CREATED)
def create_attempt(
    question_id: uuid.UUID,
    payload: AttemptWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    question = session.get(InterviewPracticeQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Practice question not found")
    prep, phase = _owned_phase(session, user, question.phase_id)
    score, feedback = evaluate_answer(
        payload.answer_text, question.model_answer, question.followups
    )
    attempt = InterviewPracticeAttempt(
        user_id=user.id,
        question_id=question.id,
        answer_text=payload.answer_text,
        transcript_source=payload.transcript_source,
        duration_seconds=payload.duration_seconds,
        score=score,
        feedback=feedback,
    )
    session.add(attempt)
    session.flush()
    _refresh_readiness(session, prep)
    session.commit()
    return {
        "id": str(attempt.id),
        "score": score,
        "feedback": feedback,
        "phase_readiness": phase.readiness,
        "overall_readiness": prep.readiness,
    }


@router.get("/questions/{question_id}/attempts")
def list_attempts(
    question_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    question = session.get(InterviewPracticeQuestion, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Practice question not found")
    _owned_phase(session, user, question.phase_id)
    items = list(
        session.scalars(
            select(InterviewPracticeAttempt)
            .where(
                InterviewPracticeAttempt.question_id == question_id,
                InterviewPracticeAttempt.user_id == user.id,
            )
            .order_by(InterviewPracticeAttempt.created_at.desc())
        )
    )
    return [
        {
            "id": str(item.id),
            "answer_text": item.answer_text,
            "transcript_source": item.transcript_source,
            "duration_seconds": item.duration_seconds,
            "score": item.score,
            "feedback": item.feedback,
            "created_at": item.created_at,
        }
        for item in items
    ]


@router.post("/{job_id}/research-sources", status_code=status.HTTP_201_CREATED)
def add_research_source(
    job_id: uuid.UUID,
    payload: ResearchSourceWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    prep = _owned_preparation(session, user, job_id)
    item = InterviewResearchSource(
        preparation_id=prep.id,
        source_kind=payload.source_kind,
        title=payload.title,
        url=str(payload.url) if payload.url else None,
        snippet=payload.snippet,
        source_metadata=payload.source_metadata,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {
        "id": str(item.id),
        "title": item.title,
        "url": item.url,
        "source_kind": item.source_kind,
    }


@router.get("/stories/all")
def list_stories(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    items = list(
        session.scalars(
            select(InterviewStory)
            .where(InterviewStory.user_id == user.id)
            .order_by(InterviewStory.updated_at.desc())
        )
    )
    return [
        {
            "id": str(item.id),
            "title": item.title,
            "categories": item.categories,
            "situation": item.situation,
            "task": item.task,
            "action": item.action,
            "result": item.result,
            "metrics": item.metrics,
            "skills": item.skills,
            "source_fact_ids": item.source_fact_ids,
            "verified": item.verified,
        }
        for item in items
    ]


@router.post("/stories", status_code=status.HTTP_201_CREATED)
def create_story(
    payload: StoryWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    item = InterviewStory(user_id=user.id, **payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"id": str(item.id), "title": item.title, "verified": item.verified}


@router.put("/stories/{story_id}")
def update_story(
    story_id: uuid.UUID,
    payload: StoryWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    item = session.scalar(
        select(InterviewStory).where(
            InterviewStory.id == story_id,
            InterviewStory.user_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Interview story not found")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    session.commit()
    return {"id": str(item.id), "title": item.title, "verified": item.verified}


@router.delete("/stories/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(
    story_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    item = session.scalar(
        select(InterviewStory).where(
            InterviewStory.id == story_id,
            InterviewStory.user_id == user.id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Interview story not found")
    session.delete(item)
    session.commit()


@router.get("/feed/{token}.xml", include_in_schema=False)
def private_podcast_feed(
    token: str,
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    prep = session.scalar(
        select(InterviewPreparation).where(
            InterviewPreparation.private_feed_token == token
        )
    )
    if prep is None:
        raise HTTPException(status_code=404, detail="Private feed not found")
    job = session.get(Job, prep.job_id)
    episodes = list(
        session.scalars(
            select(InterviewPodcastEpisode)
            .where(InterviewPodcastEpisode.preparation_id == prep.id)
            .order_by(InterviewPodcastEpisode.episode_number)
        )
    )
    channel_title = html.escape(
        f"ApplyAI Interview Prep — {job.title if job else 'Interview'}"
    )
    items: list[str] = []
    for episode in episodes:
        episode_link = (
            str(request.base_url).rstrip("/")
            + f"/interview/{prep.job_id}?episode={episode.episode_number}"
        )
        enclosure = (
            f'<enclosure url="{html.escape(episode.audio_url)}" type="audio/mpeg" />'
            if episode.audio_url
            else ""
        )
        transcript = " ".join(
            str(segment.get("text", ""))
            for segment in (episode.script or [])
            if isinstance(segment, dict)
        )
        items.append(
            "<item>"
            f'<guid isPermaLink="false">applyai-{episode.id}</guid>'
            f"<title>{html.escape(episode.title)}</title>"
            f"<description>{html.escape(transcript)}</description>"
            f"<link>{html.escape(episode_link)}</link>"
            f"{enclosure}"
            "</item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<title>{channel_title}</title>"
        "<description>Private, job-specific ApplyAI interview preparation feed.</description>"
        f"{''.join(items)}"
        "</channel></rss>"
    )
    return Response(content=xml, media_type="application/rss+xml")
