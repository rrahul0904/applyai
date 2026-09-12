from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.candidate_workspace import candidate_context, get_owned_job
from app.api.career_product import _match_payload
from app.core.auth import get_current_user
from app.core.database import get_session
from app.interview_engine import InterviewMode, InterviewRequest, choose_interview_engine
from app.models import Application, Company, Job, JobSkill, User
from app.preparation_models import (
    CandidateSkillEvidence,
    CareerReadinessSnapshot,
    Course,
    CourseLesson,
    CourseModule,
    ExerciseAttempt,
    InterviewPack,
    InterviewPackSection,
    InterviewRecording,
    InterviewTurnRecord,
    JobSkillGap,
    LearningExercise,
    LearningPath,
    LearningPathSkill,
    LearningProgress,
    LessonConversation,
    MockInterviewSession,
    UsageLedger,
)

router = APIRouter(prefix="/career-v2", tags=["career preparation"])


class LessonChatWrite(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ExerciseAttemptWrite(BaseModel):
    response: str = Field(min_length=1, max_length=12000)


class LessonProgressWrite(BaseModel):
    completed: bool = True
    mastery_score: int | None = Field(default=None, ge=0, le=100)


class MockInterviewCreate(BaseModel):
    mode: Literal["behavioral", "technical", "coding", "sql", "system_design"] = "technical"
    channel: Literal["WRITTEN", "VOICE", "VIDEO"] = "WRITTEN"
    difficulty: str = Field(default="adaptive", min_length=1, max_length=32)


class InterviewAnswerWrite(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)


class RecordingWrite(BaseModel):
    media_type: Literal["AUDIO", "VIDEO"]
    storage_key: str = Field(min_length=1, max_length=2000)
    transcript_text: str | None = Field(default=None, max_length=30000)
    duration_seconds: int | None = Field(default=None, ge=0, le=14400)
    provider: str = Field(default="browser", min_length=1, max_length=64)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _tokens(value: str | None) -> set[str]:
    if not value:
        return set()
    return {token for token in re.findall(r"[a-z0-9+#.]+", value.lower()) if len(token) > 2}


def _usage(session: Session, user: User, feature: str, related_id: object | None = None, *, quantity: Decimal = Decimal("1"), unit: str = "request", metadata: dict | None = None) -> None:
    session.add(
        UsageLedger(
            user_id=user.id,
            feature=feature,
            unit=unit,
            quantity=quantity,
            related_id=str(related_id) if related_id is not None else None,
            metadata_json=metadata or {},
        )
    )


def _gap_payload(row: JobSkillGap) -> dict:
    return {
        "id": row.id,
        "skill": row.skill_name,
        "normalized_skill": row.normalized_skill,
        "requirement_level": row.requirement_level,
        "candidate_level": row.candidate_level,
        "severity": row.gap_severity,
        "priority": row.priority,
        "status": row.status,
        "reason": row.reason,
        "recommended_action": row.recommended_action,
        "confidence": float(row.confidence),
        "job_evidence": row.job_evidence_json,
        "candidate_evidence": row.candidate_evidence_json,
    }


def _analyze_skill_gaps(session: Session, user: User, job: Job) -> list[JobSkillGap]:
    context = candidate_context(session, user)
    candidate_skills = {skill.normalized_name: skill for skill in context["skills"]}
    learned = list(
        session.scalars(
            select(CandidateSkillEvidence).where(
                CandidateSkillEvidence.user_id == user.id,
                CandidateSkillEvidence.score.is_not(None),
                CandidateSkillEvidence.score >= 70,
            )
        )
    )
    learned_by_skill: dict[str, list[CandidateSkillEvidence]] = {}
    for evidence in learned:
        learned_by_skill.setdefault(evidence.normalized_skill, []).append(evidence)

    job_skills = list(
        session.scalars(
            select(JobSkill)
            .where(JobSkill.job_id == job.id)
            .order_by(JobSkill.required.desc(), JobSkill.name)
        )
    )
    active_keys: set[str] = set()
    results: list[JobSkillGap] = []
    for skill in job_skills:
        normalized = skill.normalized_name
        active_keys.add(normalized)
        verified = candidate_skills.get(normalized)
        learning_evidence = learned_by_skill.get(normalized, [])
        if verified is not None:
            candidate_level = (verified.proficiency or "VERIFIED").upper()
            severity = "NONE"
            priority = 0
            status_value = "CLOSED"
            reason = f"{skill.name} is already present in the verified candidate profile."
            action = "Maintain evidence and prepare concrete interview examples."
            candidate_evidence = [{"type": "PROFILE_SKILL", "skill_id": str(verified.id), "provenance": verified.provenance}]
        elif learning_evidence:
            best = max(int(item.score or 0) for item in learning_evidence)
            candidate_level = "PRACTICED"
            severity = "LOW" if best >= 80 else "MEDIUM"
            priority = 25 if skill.required else 10
            status_value = "IMPROVING"
            reason = f"{skill.name} is not profile-verified yet, but ApplyAI has learning evidence with a best score of {best}%."
            action = "Practice one interview example and add the skill to the profile only if it reflects real experience."
            candidate_evidence = [{"type": item.evidence_type, "source_id": item.source_id, "score": item.score} for item in learning_evidence[:5]]
        else:
            candidate_level = "NO_EVIDENCE"
            severity = "HIGH" if skill.required else "MEDIUM"
            priority = 100 if skill.required else 60
            status_value = "OPEN"
            reason = f"The role {'requires' if skill.required else 'prefers'} {skill.name}, and the candidate profile has no verified evidence for it."
            action = f"Complete the {skill.name} interview-readiness track and practice a role-specific question."
            candidate_evidence = []

        row = session.scalar(
            select(JobSkillGap).where(
                JobSkillGap.user_id == user.id,
                JobSkillGap.job_id == job.id,
                JobSkillGap.normalized_skill == normalized,
            )
        )
        if row is None:
            row = JobSkillGap(user_id=user.id, job_id=job.id, skill_name=skill.name, normalized_skill=normalized, reason=reason, recommended_action=action)
            session.add(row)
        row.skill_name = skill.name
        row.requirement_level = "REQUIRED" if skill.required else "PREFERRED"
        row.candidate_level = candidate_level
        row.gap_severity = severity
        row.priority = priority
        row.status = status_value
        row.reason = reason
        row.recommended_action = action
        row.confidence = Decimal("0.95") if verified is not None else Decimal("0.88")
        row.job_evidence_json = [{"type": "JOB_SKILL", "skill_id": str(skill.id), "required": skill.required}]
        row.candidate_evidence_json = candidate_evidence
        results.append(row)

    stale = list(
        session.scalars(
            select(JobSkillGap).where(JobSkillGap.user_id == user.id, JobSkillGap.job_id == job.id)
        )
    )
    for row in stale:
        if row.normalized_skill not in active_keys:
            session.delete(row)
    session.flush()
    return sorted(results, key=lambda item: (-item.priority, item.skill_name.lower()))


@router.post("/jobs/{job_id}/skill-analysis")
def analyze_skill_gaps(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    job = get_owned_job(job_id, session)
    gaps = _analyze_skill_gaps(session, user, job)
    _usage(session, user, "SKILL_GAP_ANALYSIS", job.id)
    session.commit()
    return {"job_id": job.id, "items": [_gap_payload(row) for row in gaps], "open_gap_count": sum(row.status in {"OPEN", "IMPROVING"} for row in gaps)}


@router.get("/jobs/{job_id}/skill-gaps")
def get_skill_gaps(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    job = get_owned_job(job_id, session)
    rows = list(session.scalars(select(JobSkillGap).where(JobSkillGap.user_id == user.id, JobSkillGap.job_id == job.id).order_by(JobSkillGap.priority.desc(), JobSkillGap.skill_name)))
    if not rows:
        rows = _analyze_skill_gaps(session, user, job)
        session.commit()
    return {"job_id": job.id, "items": [_gap_payload(row) for row in rows]}


def _lesson_content(skill: str, module_title: str, objective: str) -> tuple[str, str, list[str]]:
    key_points = [
        f"Define {skill} in the context of the target role.",
        f"Explain the production trade-offs behind {module_title.lower()}.",
        "Connect the concept to reliability, security, cost, and observability.",
    ]
    content = (
        f"## {module_title}\n\n"
        f"**Goal:** {objective}\n\n"
        f"For interview readiness, do not memorize a definition of **{skill}** in isolation. "
        "Start from the problem it solves, identify the operating constraints, then explain "
        "the design choice and how you would verify it in production.\n\n"
        "### Decision framework\n"
        "1. State requirements and assumptions.\n"
        "2. Choose the smallest design that meets them.\n"
        "3. Name one important trade-off or failure mode.\n"
        "4. Explain observability and verification.\n\n"
        f"Use this framework specifically for {skill}. Prefer examples from your real experience; "
        "if you do not have direct experience, say so and describe how you would validate the approach."
    )
    return content, f"A three-minute {skill} lesson focused on {module_title.lower()} and interview reasoning.", key_points


def _create_course(session: Session, user: User, job: Job, path: LearningPath, gap: JobSkillGap, position: int) -> Course:
    course = Course(
        learning_path_id=path.id,
        user_id=user.id,
        job_id=job.id,
        skill_name=gap.skill_name,
        normalized_skill=gap.normalized_skill,
        title=f"{gap.skill_name} for {job.title}",
        summary=f"A role-specific micro-course to close the {gap.skill_name} evidence gap before interviewing.",
        level="INTERVIEW_READY",
        estimated_minutes=18,
    )
    session.add(course)
    session.flush()
    modules = [
        ("Core mental model", f"Explain what {gap.skill_name} solves and when it is appropriate."),
        ("Production trade-offs", f"Reason about failure modes, security, cost, and operations for {gap.skill_name}."),
        ("Interview application", f"Use {gap.skill_name} in a realistic {job.title} scenario and defend the design."),
    ]
    exercise_types = ["QUIZ", "SCENARIO", "INTERVIEW"]
    for module_position, ((module_title, objective), exercise_type) in enumerate(zip(modules, exercise_types), start=1):
        module = CourseModule(course_id=course.id, position=module_position, title=module_title, objective=objective)
        session.add(module)
        session.flush()
        content, summary, key_points = _lesson_content(gap.skill_name, module_title, objective)
        lesson = CourseLesson(course_module_id=module.id, position=1, title=module_title, content_markdown=content, summary=summary, estimated_minutes=3, key_points_json=key_points, resources_json=[])
        session.add(lesson)
        session.flush()
        prompt = (
            f"For a {job.title} interview, explain {gap.skill_name} using the lesson's decision framework. "
            "State assumptions, one trade-off, one failure mode, and how you would verify the solution."
        )
        session.add(LearningExercise(course_lesson_id=lesson.id, exercise_type=exercise_type, prompt=prompt, difficulty="ADAPTIVE", rubric_json={"dimensions": ["correctness", "tradeoffs", "specificity", "verification"], "max_score": 100}, answer_key_json={"ideal_terms": [gap.normalized_skill, "trade-off", "failure", "verify", "observability"]}))
    return course


def _path_payload(session: Session, path: LearningPath) -> dict:
    skills = list(session.scalars(select(LearningPathSkill).where(LearningPathSkill.learning_path_id == path.id).order_by(LearningPathSkill.position)))
    courses = list(session.scalars(select(Course).where(Course.learning_path_id == path.id).order_by(Course.created_at)))
    return {
        "id": path.id,
        "job_id": path.job_id,
        "title": path.title,
        "status": path.status,
        "estimated_minutes": path.estimated_minutes,
        "completion_percent": path.completion_percent,
        "strategy": path.strategy_json,
        "skills": [{"skill": item.skill_name, "position": item.position, "target_level": item.target_level, "status": item.status} for item in skills],
        "courses": [{"id": course.id, "skill": course.skill_name, "title": course.title, "summary": course.summary, "estimated_minutes": course.estimated_minutes, "status": course.status} for course in courses],
    }


@router.post("/jobs/{job_id}/learning-path")
def create_learning_path(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    job = get_owned_job(job_id, session)
    gaps = [row for row in _analyze_skill_gaps(session, user, job) if row.status != "CLOSED"][:6]
    previous = session.scalar(select(LearningPath).where(LearningPath.user_id == user.id, LearningPath.job_id == job.id, LearningPath.status == "ACTIVE").order_by(LearningPath.version.desc()).limit(1))
    if previous is not None:
        return _path_payload(session, previous)
    version = int(session.scalar(select(func.coalesce(func.max(LearningPath.version), 0)).where(LearningPath.user_id == user.id, LearningPath.job_id == job.id)) or 0) + 1
    path = LearningPath(user_id=user.id, job_id=job.id, version=version, title=f"Interview readiness for {job.title}", status="ACTIVE", estimated_minutes=len(gaps) * 18, strategy_json={"principle": "Close the highest-impact evidence gaps first", "gap_count": len(gaps)})
    session.add(path)
    session.flush()
    for position, gap in enumerate(gaps, start=1):
        session.add(LearningPathSkill(learning_path_id=path.id, job_skill_gap_id=gap.id, skill_name=gap.skill_name, normalized_skill=gap.normalized_skill, position=position, target_level="INTERVIEW_READY"))
        _create_course(session, user, job, path, gap, position)
    _usage(session, user, "LEARNING_PATH_GENERATE", path.id)
    session.commit()
    return _path_payload(session, path)


@router.get("/learning-paths/{path_id}")
def get_learning_path(path_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    path = session.scalar(select(LearningPath).where(LearningPath.id == path_id, LearningPath.user_id == user.id))
    if path is None:
        raise HTTPException(status_code=404, detail="Learning path not found")
    return _path_payload(session, path)


@router.get("/courses/{course_id}")
def get_course(course_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    course = session.scalar(select(Course).where(Course.id == course_id, Course.user_id == user.id))
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    modules = list(session.scalars(select(CourseModule).where(CourseModule.course_id == course.id).order_by(CourseModule.position)))
    module_payload = []
    for module in modules:
        lessons = list(session.scalars(select(CourseLesson).where(CourseLesson.course_module_id == module.id).order_by(CourseLesson.position)))
        lesson_payload = []
        for lesson in lessons:
            progress = session.scalar(select(LearningProgress).where(LearningProgress.user_id == user.id, LearningProgress.course_lesson_id == lesson.id))
            exercises = list(session.scalars(select(LearningExercise).where(LearningExercise.course_lesson_id == lesson.id)))
            lesson_payload.append({"id": lesson.id, "title": lesson.title, "content_markdown": lesson.content_markdown, "summary": lesson.summary, "estimated_minutes": lesson.estimated_minutes, "key_points": lesson.key_points_json, "resources": lesson.resources_json, "completed": bool(progress and progress.completed), "mastery_score": progress.mastery_score if progress else None, "exercises": [{"id": exercise.id, "type": exercise.exercise_type, "prompt": exercise.prompt, "difficulty": exercise.difficulty} for exercise in exercises]})
        module_payload.append({"id": module.id, "position": module.position, "title": module.title, "objective": module.objective, "lessons": lesson_payload})
    return {"id": course.id, "job_id": course.job_id, "skill": course.skill_name, "title": course.title, "summary": course.summary, "level": course.level, "estimated_minutes": course.estimated_minutes, "modules": module_payload}


@router.put("/lessons/{lesson_id}/progress")
def set_lesson_progress(lesson_id: uuid.UUID, payload: LessonProgressWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    lesson = session.get(CourseLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    progress = session.scalar(select(LearningProgress).where(LearningProgress.user_id == user.id, LearningProgress.course_lesson_id == lesson.id))
    if progress is None:
        progress = LearningProgress(user_id=user.id, course_lesson_id=lesson.id)
        session.add(progress)
    progress.completed = payload.completed
    progress.mastery_score = payload.mastery_score
    progress.completed_at = _now() if payload.completed else None
    module = session.get(CourseModule, lesson.course_module_id)
    course = session.get(Course, module.course_id) if module else None
    if course and payload.completed and payload.mastery_score is not None:
        existing = session.scalar(select(CandidateSkillEvidence).where(CandidateSkillEvidence.user_id == user.id, CandidateSkillEvidence.evidence_type == "COURSE_MASTERY", CandidateSkillEvidence.source_id == str(lesson.id)))
        if existing is None:
            session.add(CandidateSkillEvidence(user_id=user.id, job_id=course.job_id, normalized_skill=course.normalized_skill, skill_name=course.skill_name, evidence_type="COURSE_MASTERY", source_id=str(lesson.id), score=payload.mastery_score, metadata_json={"course_id": str(course.id)}))
    session.commit()
    return {"lesson_id": lesson.id, "completed": progress.completed, "mastery_score": progress.mastery_score}


@router.post("/lessons/{lesson_id}/chat")
def lesson_chat(lesson_id: uuid.UUID, payload: LessonChatWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    lesson = session.get(CourseLesson, lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found")
    session.add(LessonConversation(user_id=user.id, course_lesson_id=lesson.id, role="user", content=payload.message.strip()))
    question_terms = _tokens(payload.message)
    relevant = [point for point in lesson.key_points_json if _tokens(point) & question_terms]
    grounding = relevant[:2] or lesson.key_points_json[:2]
    answer = (
        f"For **{lesson.title}**, anchor the answer in the decision framework rather than a memorized definition. "
        + (" ".join(grounding) + " " if grounding else "")
        + "For an interview, state the requirement first, name the trade-off, describe a failure mode, and finish with how you would verify the design. If this is outside your direct experience, say that explicitly rather than inventing experience."
    )
    session.add(LessonConversation(user_id=user.id, course_lesson_id=lesson.id, role="assistant", content=answer))
    _usage(session, user, "LESSON_TUTOR", lesson.id)
    session.commit()
    return {"lesson_id": lesson.id, "answer": answer, "grounded_in": grounding, "provider": "applyai-deterministic-fallback"}


@router.post("/exercises/{exercise_id}/attempts")
def submit_exercise(exercise_id: uuid.UUID, payload: ExerciseAttemptWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    exercise = session.get(LearningExercise, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    response = payload.response.strip()
    terms = {str(item).lower() for item in exercise.answer_key_json.get("ideal_terms", [])}
    response_lower = response.lower()
    term_hits = sum(term in response_lower for term in terms)
    specificity = min(20, len(re.findall(r"\b\d+[\w%.-]*\b", response)) * 5)
    structure = 15 if len(response.split()) >= 60 else 10 if len(response.split()) >= 30 else 5
    score = min(100, 35 + term_hits * 8 + specificity + structure)
    feedback = {
        "dimensions": {"concept_coverage": min(100, 40 + term_hits * 12), "specificity": specificity * 5, "structure": min(100, structure * 6)},
        "strengths": ["You connected the answer to the requested scenario."] if len(response.split()) >= 30 else [],
        "improvements": ["Name a concrete trade-off and how you would verify the result."] if "trade" not in response_lower or "verif" not in response_lower else [],
        "safe_coaching": "Use only experience you can defend; hypothetical design reasoning is fine when labeled as hypothetical.",
    }
    attempt = ExerciseAttempt(user_id=user.id, learning_exercise_id=exercise.id, response_text=response, score=score, feedback_json=feedback)
    session.add(attempt)
    _usage(session, user, "EXERCISE_EVALUATE", exercise.id)
    session.commit()
    return {"attempt_id": attempt.id, "score": score, "feedback": feedback}


def _create_interview_pack(session: Session, user: User, job: Job) -> InterviewPack:
    existing = session.scalar(select(InterviewPack).where(InterviewPack.user_id == user.id, InterviewPack.job_id == job.id, InterviewPack.status == "READY").order_by(InterviewPack.version.desc()).limit(1))
    if existing is not None:
        return existing
    gaps = _analyze_skill_gaps(session, user, job)
    context = candidate_context(session, user)
    company = session.get(Company, job.company_id)
    version = int(session.scalar(select(func.coalesce(func.max(InterviewPack.version), 0)).where(InterviewPack.user_id == user.id, InterviewPack.job_id == job.id)) or 0) + 1
    top_gaps = [gap.skill_name for gap in gaps if gap.status != "CLOSED"][:5]
    matched = [gap.skill_name for gap in gaps if gap.status == "CLOSED"][:5]
    pack = InterviewPack(user_id=user.id, job_id=job.id, version=version, title=f"{job.title} interview book", strategy_summary=f"Prepare evidence-backed examples for {', '.join(matched) or 'your strongest verified skills'} and explicitly close or discuss gaps in {', '.join(top_gaps) or 'the remaining requirements'}.", evidence_refs=[f"job:{job.id}", f"candidate:{user.id}"])
    session.add(pack)
    session.flush()
    experiences = context["experiences"][:4]
    sections = [
        ("TECHNICAL_CHEATSHEET", "Technical cheatsheet", {"focus_skills": matched + top_gaps, "framework": ["requirements", "architecture", "trade-offs", "failure modes", "security", "observability", "cost"]}),
        ("TECHNICAL_QA", "Technical Q&A", {"questions": [f"How would you use {skill} in a production {job.title} environment?" for skill in (matched + top_gaps)[:8]]}),
        ("PRACTICAL_TASKS", "Practical exercises", {"tasks": [f"Design a production scenario for {skill}; include scale assumptions, failure recovery and observability." for skill in (matched + top_gaps)[:5]]}),
        ("BEHAVIORAL", "Behavioral preparation", {"questions": ["Tell me about a difficult technical decision and its trade-offs.", "Describe a time you changed direction after new evidence.", "Tell me about a disagreement with a stakeholder and the outcome."]}),
        ("RESUME_DEEP_DIVE", "Resume deep dive", {"questions": [f"At {item.company_name}, what was your direct contribution as {item.title}, and what evidence shows the result?" for item in experiences]}),
        ("QUESTIONS_TO_ASK", "Questions to ask", {"questions": [f"What outcomes define success for this {job.title} role in the first 90 days?", "Which technical constraints create the most risk for the team today?", f"How does {company.canonical_name if company else 'the team'} evaluate architecture and engineering trade-offs?"]}),
    ]
    for position, (section_type, title, content) in enumerate(sections, start=1):
        session.add(InterviewPackSection(interview_pack_id=pack.id, section_type=section_type, title=title, position=position, content_json=content))
    _usage(session, user, "INTERVIEW_PACK_GENERATE", pack.id)
    session.flush()
    return pack


def _pack_payload(session: Session, pack: InterviewPack) -> dict:
    sections = list(session.scalars(select(InterviewPackSection).where(InterviewPackSection.interview_pack_id == pack.id).order_by(InterviewPackSection.position)))
    return {"id": pack.id, "job_id": pack.job_id, "title": pack.title, "strategy_summary": pack.strategy_summary, "status": pack.status, "sections": [{"type": section.section_type, "title": section.title, "content": section.content_json} for section in sections]}


@router.post("/jobs/{job_id}/interview-pack")
def create_interview_pack(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    job = get_owned_job(job_id, session)
    pack = _create_interview_pack(session, user, job)
    session.commit()
    return _pack_payload(session, pack)


@router.get("/jobs/{job_id}/interview-pack")
def get_interview_pack(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    get_owned_job(job_id, session)
    pack = session.scalar(select(InterviewPack).where(InterviewPack.user_id == user.id, InterviewPack.job_id == job_id).order_by(InterviewPack.version.desc()).limit(1))
    if pack is None:
        raise HTTPException(status_code=404, detail="Interview pack not generated")
    return _pack_payload(session, pack)


def _session_owned(session: Session, user: User, session_id: uuid.UUID) -> MockInterviewSession:
    row = session.scalar(select(MockInterviewSession).where(MockInterviewSession.id == session_id, MockInterviewSession.user_id == user.id))
    if row is None:
        raise HTTPException(status_code=404, detail="Mock interview not found")
    return row


def _session_payload(session: Session, row: MockInterviewSession) -> dict:
    turns = list(session.scalars(select(InterviewTurnRecord).where(InterviewTurnRecord.interview_session_id == row.id).order_by(InterviewTurnRecord.position)))
    current = next((turn for turn in turns if turn.answer_text is None), None)
    return {
        "id": row.id,
        "job_id": row.job_id,
        "mode": row.mode,
        "channel": row.channel,
        "difficulty": row.difficulty,
        "status": row.status,
        "provider": row.provider,
        "overall_score": row.overall_score,
        "category_scores": row.category_scores_json,
        "feedback": row.final_feedback_json,
        "current_question": {"turn_id": current.id, "question": current.question, "position": current.position} if current else None,
        "turns": [{"id": turn.id, "position": turn.position, "question": turn.question, "answer": turn.answer_text, "score": turn.score, "evaluation": turn.evaluation_json, "follow_up": turn.follow_up} for turn in turns],
    }


@router.post("/jobs/{job_id}/mock-interviews")
def create_mock_interview(job_id: uuid.UUID, payload: MockInterviewCreate, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    job = get_owned_job(job_id, session)
    pack = _create_interview_pack(session, user, job)
    context = candidate_context(session, user)
    mode = InterviewMode(payload.mode)
    engine = choose_interview_engine(prefer_rigor=False)
    interview = engine.create_session(InterviewRequest(candidate_id=str(user.id), job_id=str(job.id), mode=mode, target_role=job.title, verified_skills=tuple(skill.name for skill in context["skills"][:8]), difficulty=payload.difficulty))
    row = MockInterviewSession(user_id=user.id, job_id=job.id, interview_pack_id=pack.id, mode=payload.mode, channel=payload.channel, difficulty=payload.difficulty.upper(), status="IN_PROGRESS", provider=interview.provider, provider_session_id=interview.provider_session_id, total_questions=len(interview.questions))
    session.add(row)
    session.flush()
    for position, question in enumerate(interview.questions, start=1):
        session.add(InterviewTurnRecord(interview_session_id=row.id, position=position, question_id=question.id, question=question.prompt, follow_up=False))
    _usage(session, user, "MOCK_INTERVIEW_START", row.id, metadata={"channel": payload.channel, "mode": payload.mode})
    session.commit()
    return _session_payload(session, row)


def _evaluate_answer(question: str, answer: str, mode: str) -> tuple[int, dict]:
    words = answer.split()
    q_tokens = _tokens(question)
    a_tokens = _tokens(answer)
    overlap = len(q_tokens & a_tokens)
    has_numbers = bool(re.search(r"\b\d+[\w%.-]*\b", answer))
    tradeoff = any(term in answer.lower() for term in ("trade-off", "tradeoff", "because", "however", "instead"))
    verification = any(term in answer.lower() for term in ("verify", "monitor", "metric", "test", "observability", "validate"))
    behavioral_structure = sum(term in answer.lower() for term in ("situation", "task", "action", "result"))
    score = 35 + min(20, len(words) // 5) + min(15, overlap * 3) + (10 if has_numbers else 0) + (10 if tradeoff else 0) + (10 if verification else 0)
    if mode == "behavioral":
        score += min(10, behavioral_structure * 3)
    score = max(0, min(100, score))
    improvements = []
    if len(words) < 50:
        improvements.append("Add enough detail to show your reasoning and direct contribution.")
    if not tradeoff:
        improvements.append("Name a trade-off or why you chose this approach over an alternative.")
    if not verification:
        improvements.append("Explain how you verified the result or would know the design is working.")
    if not has_numbers and mode == "behavioral":
        improvements.append("Use a measurable result when you have verified evidence for one.")
    return score, {"dimensions": {"clarity": min(100, 50 + len(words) // 2), "specificity": 80 if has_numbers else 55, "reasoning": 85 if tradeoff else 55, "verification": 85 if verification else 50}, "improvements": improvements, "coaching": "Do not invent experience or metrics; label hypothetical reasoning as hypothetical."}


@router.post("/interviews/{session_id}/answers")
def answer_mock_interview(session_id: uuid.UUID, payload: InterviewAnswerWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    row = _session_owned(session, user, session_id)
    if row.status != "IN_PROGRESS":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interview is not in progress")
    turn = session.scalar(select(InterviewTurnRecord).where(InterviewTurnRecord.interview_session_id == row.id, InterviewTurnRecord.answer_text.is_(None)).order_by(InterviewTurnRecord.position).limit(1))
    if turn is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No unanswered question remains")
    score, evaluation = _evaluate_answer(turn.question, payload.answer, row.mode)
    turn.answer_text = payload.answer.strip()
    turn.score = score
    turn.evaluation_json = evaluation
    turn.answered_at = _now()
    row.current_question_index += 1
    unanswered = int(session.scalar(select(func.count()).select_from(InterviewTurnRecord).where(InterviewTurnRecord.interview_session_id == row.id, InterviewTurnRecord.answer_text.is_(None))) or 0)
    if score < 70 and unanswered <= 1 and row.total_questions < 8:
        max_position = int(session.scalar(select(func.coalesce(func.max(InterviewTurnRecord.position), 0)).where(InterviewTurnRecord.interview_session_id == row.id)) or 0)
        session.add(InterviewTurnRecord(interview_session_id=row.id, position=max_position + 1, question_id=f"followup-{turn.question_id}", question="Go one level deeper: what was the most important trade-off or failure mode in that answer, and how would you verify the outcome?", follow_up=True))
        row.total_questions += 1
    _usage(session, user, "INTERVIEW_ANSWER_SCORE", row.id)
    session.commit()
    return _session_payload(session, row)


@router.post("/interviews/{session_id}/recordings")
def save_recording(session_id: uuid.UUID, payload: RecordingWrite, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    row = _session_owned(session, user, session_id)
    recording = InterviewRecording(interview_session_id=row.id, media_type=payload.media_type, storage_key=payload.storage_key, transcript_text=payload.transcript_text, duration_seconds=payload.duration_seconds, provider=payload.provider)
    session.add(recording)
    _usage(session, user, "INTERVIEW_MEDIA_MINUTES", row.id, quantity=Decimal(str(round((payload.duration_seconds or 0) / 60, 4))), unit="minute", metadata={"media_type": payload.media_type})
    session.commit()
    return {"recording_id": recording.id, "media_type": recording.media_type, "duration_seconds": recording.duration_seconds, "transcript_available": bool(recording.transcript_text)}


@router.post("/interviews/{session_id}/complete")
def complete_mock_interview(session_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    row = _session_owned(session, user, session_id)
    answered = list(session.scalars(select(InterviewTurnRecord).where(InterviewTurnRecord.interview_session_id == row.id, InterviewTurnRecord.answer_text.is_not(None)).order_by(InterviewTurnRecord.position)))
    if not answered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Answer at least one question before completing the interview")
    scores = [int(turn.score or 0) for turn in answered]
    overall = round(sum(scores) / len(scores))
    row.overall_score = overall
    row.category_scores_json = {"content": overall, "reasoning": round(sum(int((turn.evaluation_json.get("dimensions") or {}).get("reasoning", 0)) for turn in answered) / len(answered)), "verification": round(sum(int((turn.evaluation_json.get("dimensions") or {}).get("verification", 0)) for turn in answered) / len(answered))}
    weak = [turn.question for turn in answered if (turn.score or 0) < 70]
    row.final_feedback_json = {"strengths": ["You completed a role-specific evidence-aware mock interview."], "focus_next": weak[:3] or ["Repeat the strongest technical area at a harder difficulty."], "recommended_next_action": "Review low-scoring answers, complete linked skill lessons, then run a second mock interview."}
    row.status = "COMPLETED"
    row.completed_at = _now()
    _usage(session, user, "MOCK_INTERVIEW_COMPLETE", row.id)
    session.commit()
    return _session_payload(session, row)


@router.get("/interviews/{session_id}/report")
def interview_report(session_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    row = _session_owned(session, user, session_id)
    return _session_payload(session, row)


def _learning_score(session: Session, user: User, job_id: uuid.UUID) -> int:
    lesson_ids = list(session.scalars(select(CourseLesson.id).join(CourseModule, CourseModule.id == CourseLesson.course_module_id).join(Course, Course.id == CourseModule.course_id).where(Course.user_id == user.id, Course.job_id == job_id)))
    if not lesson_ids:
        return 0
    progress = list(session.scalars(select(LearningProgress).where(LearningProgress.user_id == user.id, LearningProgress.course_lesson_id.in_(lesson_ids))))
    completed = [item for item in progress if item.completed]
    completion = len(completed) / len(lesson_ids)
    mastery_values = [int(item.mastery_score) for item in completed if item.mastery_score is not None]
    mastery = (sum(mastery_values) / len(mastery_values) / 100) if mastery_values else completion
    return round(min(1.0, completion * 0.6 + mastery * 0.4) * 100)


def _application_score(session: Session, user: User, job_id: uuid.UUID) -> int:
    application = session.scalar(select(Application).where(Application.user_id == user.id, Application.job_id == job_id))
    if application is None:
        return 0
    return {"PREPARING": 35, "READY": 80, "SUBMITTED": 100, "INTERVIEW": 100, "OFFER": 100}.get(application.current_status.upper(), 60)


def _interview_score(session: Session, user: User, job_id: uuid.UUID) -> int:
    scores = list(session.scalars(select(MockInterviewSession.overall_score).where(MockInterviewSession.user_id == user.id, MockInterviewSession.job_id == job_id, MockInterviewSession.status == "COMPLETED", MockInterviewSession.overall_score.is_not(None)).order_by(MockInterviewSession.completed_at.desc()).limit(3)))
    return round(sum(scores) / len(scores)) if scores else 0


@router.get("/jobs/{job_id}/readiness")
def get_readiness(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    job = get_owned_job(job_id, session)
    match = _match_payload(session, user, job)
    match_score = int(match["match_score"])
    application_score = _application_score(session, user, job.id)
    learning_score = _learning_score(session, user, job.id)
    interview_score = _interview_score(session, user, job.id)
    overall = round(match_score * 0.35 + application_score * 0.20 + learning_score * 0.20 + interview_score * 0.25)
    breakdown = {"match": {"score": match_score, "weight": 35}, "application": {"score": application_score, "weight": 20}, "learning": {"score": learning_score, "weight": 20}, "interview": {"score": interview_score, "weight": 25}}
    latest = session.scalar(select(CareerReadinessSnapshot).where(CareerReadinessSnapshot.user_id == user.id, CareerReadinessSnapshot.job_id == job.id).order_by(CareerReadinessSnapshot.created_at.desc()).limit(1))
    if latest is None or latest.overall_score != overall or latest.breakdown_json != breakdown:
        session.add(CareerReadinessSnapshot(user_id=user.id, job_id=job.id, match_score=match_score, application_score=application_score, learning_score=learning_score, interview_score=interview_score, overall_score=overall, breakdown_json=breakdown))
        session.commit()
    gaps = list(session.scalars(select(JobSkillGap).where(JobSkillGap.user_id == user.id, JobSkillGap.job_id == job.id, JobSkillGap.status != "CLOSED").order_by(JobSkillGap.priority.desc()).limit(5)))
    next_actions = []
    if gaps:
        next_actions.append(f"Close the highest-impact skill gap: {gaps[0].skill_name}.")
    if learning_score < 80:
        next_actions.append("Complete the role-specific learning path and practice exercises.")
    if interview_score < 75:
        next_actions.append("Run a mock interview and review the lowest-scoring answer.")
    if application_score < 80:
        next_actions.append("Finish and verify the application package.")
    return {"job_id": job.id, "overall_score": overall, "band": "READY" if overall >= 80 else "BUILDING" if overall >= 60 else "EARLY", "breakdown": breakdown, "top_skill_gaps": [_gap_payload(row) for row in gaps], "next_actions": next_actions[:4]}


@router.get("/jobs/{job_id}/progress")
def get_progress(job_id: uuid.UUID, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    get_owned_job(job_id, session)
    snapshots = list(session.scalars(select(CareerReadinessSnapshot).where(CareerReadinessSnapshot.user_id == user.id, CareerReadinessSnapshot.job_id == job_id).order_by(CareerReadinessSnapshot.created_at)))
    return {"job_id": job_id, "snapshots": [{"created_at": item.created_at, "overall_score": item.overall_score, "match_score": item.match_score, "application_score": item.application_score, "learning_score": item.learning_score, "interview_score": item.interview_score} for item in snapshots]}
