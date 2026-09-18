from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Iterable, Sequence


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "item"


def normalize_phrase(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9+#.]+", value.lower()))


def phrase_tokens(value: str) -> set[str]:
    return {token for token in normalize_phrase(value).split() if token}


def skill_is_present(required_skill: str, candidate_skills: Iterable[str]) -> bool:
    """Require the complete required skill phrase/tokens within one candidate skill."""
    required = normalize_phrase(required_skill)
    if not required:
        return True
    required_tokens = phrase_tokens(required)
    for raw in candidate_skills:
        candidate = normalize_phrase(raw)
        if not candidate:
            continue
        if required == candidate or required in candidate:
            return True
        tokens = phrase_tokens(candidate)
        if required_tokens and required_tokens.issubset(tokens):
            return True
    return False


def report_fingerprint(*, company: str | None, role: str | None, stage: str | None, body: str) -> str:
    normalized = "|".join(
        [
            normalize_phrase(company or ""),
            normalize_phrase(role or ""),
            normalize_phrase(stage or ""),
            re.sub(r"\s+", " ", body).strip().lower(),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def freshness_score(last_reported_at: datetime | None, *, now: datetime | None = None) -> int:
    if last_reported_at is None:
        return 0
    current = now or datetime.now(timezone.utc)
    if last_reported_at.tzinfo is None:
        last_reported_at = last_reported_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (current - last_reported_at).total_seconds() / 86400)
    return max(0, min(100, round(100 * math.exp(-age_days / 90))))


def evidence_confidence(report_count: int, last_reported_at: datetime | None) -> int:
    count_component = min(max(report_count, 0), 6) * 10
    freshness = freshness_score(last_reported_at)
    return max(10, min(100, round(30 + count_component + freshness * 0.4)))


def staged_hint(hints: Sequence[str], requested_level: int, answer: str | None = None) -> dict[str, object]:
    if not hints:
        return {
            "level": 0,
            "hint": "State your assumptions, name the decision criteria, then test the hardest edge case.",
            "next_level": 0,
        }
    level = max(0, min(requested_level, len(hints) - 1))
    prefix = (
        "Keep the approach, but make the reasoning and verification explicit. "
        if answer and len(answer.strip()) > 30
        else ""
    )
    return {
        "level": level,
        "hint": prefix + hints[level],
        "next_level": min(level + 1, len(hints) - 1),
    }


PHASES = (
    (1, "RECRUITER", "Recruiter screen"),
    (2, "HIRING_MANAGER", "Hiring manager"),
    (3, "TECHNICAL_CASE", "Technical / case"),
    (4, "EXECUTIVE_CULTURE", "Executive / culture"),
)


def _phase_questions(phase_type: str, job_title: str, company: str, gaps: Sequence[str]) -> list[dict]:
    leading_gap = gaps[0] if gaps else "the role's hardest requirement"
    common = {
        "RECRUITER": [
            f"Walk me through why {job_title} at {company} is the right next move for you.",
            "Which part of your background is most relevant to this role?",
            "What are you optimizing for in your next team and role?",
        ],
        "HIRING_MANAGER": [
            f"Describe a project that best demonstrates readiness for {leading_gap}.",
            "Tell me about a decision you made with incomplete information.",
            "How do you measure whether your work changed an outcome?",
        ],
        "TECHNICAL_CASE": [
            f"Design an approach to a realistic {job_title} problem and explain the trade-offs.",
            f"How would you de-risk a project where {leading_gap} is the main uncertainty?",
            "What would you instrument, test, and monitor before calling the solution production-ready?",
        ],
        "EXECUTIVE_CULTURE": [
            "Tell me about a time you changed a senior stakeholder's mind with evidence.",
            "Which operating principle do you protect even when delivery pressure is high?",
            "What should we remember about your impact after this interview process?",
        ],
    }
    prompts = common[phase_type]
    return [
        {
            "order": index,
            "prompt": prompt,
            "evidence_guidance": "Anchor the answer in a verified Career Memory fact, measurable result, or explicit assumption.",
        }
        for index, prompt in enumerate(prompts, start=1)
    ]


def build_lifecycle(*, job_title: str, company: str, candidate_skills: Sequence[str], required_skills: Sequence[str], prior: dict | None = None) -> dict:
    prior = prior or {}
    gaps = [skill for skill in required_skills if not skill_is_present(skill, candidate_skills)]
    strengths = [skill for skill in required_skills if skill_is_present(skill, candidate_skills)]
    prior_phases = {int(item.get("phase_number", 0)): item for item in prior.get("phases", []) if isinstance(item, dict)}
    phases: list[dict] = []
    carry_forward: list[str] = []
    for phase_number, phase_type, title in PHASES:
        old = prior_phases.get(phase_number, {})
        existing_carry = list(old.get("carry_forward") or [])
        carry_forward.extend(item for item in existing_carry if item not in carry_forward)
        questions = _phase_questions(phase_type, job_title, company, gaps)
        phases.append(
            {
                "phase_number": phase_number,
                "phase_type": phase_type,
                "title": title,
                "prep": {
                    "focus": [
                        f"Connect your evidence to {job_title} outcomes.",
                        *(f"Prepare evidence for {skill}." for skill in gaps[:2]),
                    ],
                    "strengths": strengths[:5],
                    "gaps": gaps[:5],
                },
                "questions": questions,
                "quiz": [
                    {"question": f"What is the strongest evidence you have for {questions[0]['prompt']}", "answer": "Use a specific verified example and quantify the result."},
                    {"question": "What is the biggest unsupported claim in your current answer?", "answer": "Replace it with evidence or label it as an assumption."},
                ],
                "flashcards": [
                    {"front": skill, "back": f"Prepare one concrete example showing {skill} in context."}
                    for skill in (gaps[:2] or strengths[:2] or [job_title])
                ],
                "cheat_sheet": {
                    "role": job_title,
                    "company": company,
                    "top_gaps": gaps[:4],
                    "top_strengths": strengths[:4],
                    "questions_to_ask": [
                        "What problem should this person solve first?",
                        "How do you evaluate excellent performance in the first six months?",
                    ],
                },
                "notes": old.get("notes", ""),
                "reflection": old.get("reflection", {}),
                "carry_forward": existing_carry,
            }
        )
    return {
        "job_title": job_title,
        "company": company,
        "gaps": gaps[:10],
        "strengths": strengths[:10],
        "phases": phases,
        "carry_forward": carry_forward,
    }


def build_podcast_scripts(*, job_title: str, company: str, lifecycle: dict) -> list[dict]:
    gaps = lifecycle.get("gaps", [])
    strengths = lifecycle.get("strengths", [])
    topics = [
        ("Role brief", f"What {job_title} at {company} is likely to require and how to frame your evidence."),
        ("Evidence rehearsal", f"Lead with these strengths: {', '.join(strengths[:4]) or 'verified experience'}."),
        ("Gap rehearsal", f"Prepare a truthful plan for: {', '.join(gaps[:4]) or 'the hardest role requirement'}."),
        ("Interview loop", "Rehearse recruiter, hiring manager, technical/case, and executive/culture transitions."),
        ("Final warm-up", "Review concise outcomes, trade-offs, questions to ask, and the evidence you can defend."),
    ]
    return [
        {
            "episode_number": index,
            "title": title,
            "summary": summary,
            "script": [
                {"speaker": "Coach", "text": summary},
                {"speaker": "Candidate", "text": "State one example, one measurable outcome, and one lesson."},
                {"speaker": "Coach", "text": "Keep unsupported claims out; use verified evidence or explicit assumptions."},
            ],
            "playback": "browser-speech-synthesis",
        }
        for index, (title, summary) in enumerate(topics, start=1)
    ]


def readiness(*, current_phase: int, lifecycle: dict, practice_average: int | None = None) -> dict:
    phases = lifecycle.get("phases", [])
    reflected = sum(1 for phase in phases if phase.get("reflection"))
    noted = sum(1 for phase in phases if str(phase.get("notes") or "").strip())
    evidence_score = min(35, len(lifecycle.get("strengths", [])) * 7)
    workflow_score = min(35, reflected * 7 + noted * 3 + max(0, current_phase - 1) * 5)
    practice = 15 if practice_average is None else max(0, min(30, round(practice_average * 0.3)))
    score = max(25, min(100, 20 + evidence_score + workflow_score + practice))
    return {
        "score": score,
        "band": "READY" if score >= 80 else "BUILDING" if score >= 60 else "EARLY",
        "phase": current_phase,
        "reflections_completed": reflected,
        "notes_completed": noted,
        "practice_average": practice_average,
    }
