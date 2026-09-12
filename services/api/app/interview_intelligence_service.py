from __future__ import annotations

import hashlib
import math
import re
from datetime import datetime, timezone
from typing import Mapping, Sequence


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "item"


def report_fingerprint(*, source_type: str, source_url: str | None, company: str | None, role: str | None, body: str) -> str:
    normalized = "|".join([source_type.strip().lower(), (source_url or "").strip().lower(), (company or "").strip().lower(), (role or "").strip().lower(), re.sub(r"\s+", " ", body).strip().lower()])
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def evidence_confidence(*, independent_reports: int, source_diversity: int, age_days: int, moderation_approved: bool = True) -> int:
    if not moderation_approved:
        return 0
    reports = min(max(independent_reports, 0) / 5, 1) * 45
    diversity = min(max(source_diversity, 0) / 3, 1) * 25
    freshness = max(0, 1 - max(age_days, 0) / 180) * 30
    return max(0, min(100, round(reports + diversity + freshness)))


def freshness_score(last_reported_at: datetime | None, *, now: datetime | None = None) -> int:
    if last_reported_at is None:
        return 0
    current = now or datetime.now(timezone.utc)
    if last_reported_at.tzinfo is None:
        last_reported_at = last_reported_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (current - last_reported_at).total_seconds() / 86400)
    return max(0, min(100, round(100 * math.exp(-age_days / 60))))


def personalized_plan(*, job_title: str, candidate_skills: Sequence[str], required_skills: Sequence[str], question_tracks: Mapping[str, int]) -> dict[str, object]:
    candidate = {item.strip().lower() for item in candidate_skills if item.strip()}
    required = [item.strip() for item in required_skills if item.strip()]
    gaps = [skill for skill in required if skill.lower() not in candidate]
    strengths = [skill for skill in required if skill.lower() in candidate]
    if not required:
        strengths = list(candidate_skills[:5])
    weights = {"CODING": 25, "SQL": 15, "SYSTEM_DESIGN": 25, "ML_SYSTEM_DESIGN": 20, "OOD": 10, "BEHAVIORAL": 15}
    ranked = sorted(({"track": track, "available_questions": int(count), "priority": min(100, weights.get(track, 10) + min(int(count), 20) * 2)} for track, count in question_tracks.items() if int(count) > 0), key=lambda item: (int(item["priority"]), int(item["available_questions"])), reverse=True)
    readiness = max(35, min(95, 82 - min(35, len(gaps) * 7) + min(13, len(strengths) * 4)))
    actions = [{"order": index, "track": item["track"], "question_count": min(5, int(item["available_questions"])), "reason": f"Practice {str(item['track']).replace('_', ' ').title()} for {job_title}; current intelligence has {item['available_questions']} relevant questions."} for index, item in enumerate(ranked[:5], start=1)]
    if gaps:
        actions.insert(0, {"order": 0, "track": "SKILL_GAP", "question_count": 0, "reason": f"Close or prepare evidence for the leading gaps: {', '.join(gaps[:4])}."})
    return {"readiness_score": readiness, "strengths": strengths[:8], "gaps": gaps[:8], "actions": actions}


def staged_hint(*, hints: Sequence[str], requested_level: int, answer: str | None = None) -> dict[str, object]:
    if not hints:
        return {"level": 0, "hint": "State your assumptions, define the invariant or decision criteria, then test the hardest edge case.", "next_level": 0}
    level = max(0, min(requested_level, len(hints) - 1))
    prefix = "Keep your current approach, but make the reasoning and verification explicit. " if answer and len(answer.strip()) > 30 else ""
    return {"level": level, "hint": prefix + hints[level], "next_level": min(level + 1, len(hints) - 1)}
