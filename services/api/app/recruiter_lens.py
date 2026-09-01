from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.api.candidate_workspace import candidate_context, tokens
from app.api.career_product import _job_context
from app.models import User

ENGINE_VERSION = "applyai-recruiter-lens-v1"
MAX_CRITERIA = 12
MAX_CONCERNS = 5
MAX_QUESTIONS = 6
ALLOWED_MODES = {
    "DEFAULT_RECRUITER",
    "STRICT_MUST_HAVE",
    "HIRING_MANAGER",
    "TECHNICAL",
    "CUSTOM",
}

STOP_WORDS = {
    "and", "are", "but", "for", "from", "have", "into", "our", "that", "the",
    "their", "this", "with", "will", "your", "years", "year", "experience",
    "required", "preferred", "ability", "strong", "using", "work", "working",
    "knowledge", "skills",
}


@dataclass(frozen=True)
class EvidenceSegment:
    kind: str
    label: str
    text: str
    token_set: set[str]


def _meaningful_tokens(value: str | None) -> set[str]:
    return {token for token in tokens(value) if token not in STOP_WORDS}


def _truncate(value: str, limit: int = 240) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _evidence_segments(candidate: dict[str, Any]) -> list[EvidenceSegment]:
    segments: list[EvidenceSegment] = []
    profile = candidate["profile"]
    if profile is not None:
        if profile.current_title:
            segments.append(EvidenceSegment("PROFILE_TITLE", "Current title", profile.current_title, _meaningful_tokens(profile.current_title)))
        if profile.summary:
            segments.append(EvidenceSegment("PROFILE_SUMMARY", "Verified profile summary", profile.summary, _meaningful_tokens(profile.summary)))
    for role in candidate["roles"][:6]:
        segments.append(EvidenceSegment("TARGET_ROLE", "Target role", role.title, _meaningful_tokens(role.title)))
    for skill in candidate["skills"][:40]:
        segments.append(EvidenceSegment("VERIFIED_SKILL", "Verified skill", skill.name, _meaningful_tokens(skill.name)))
    for experience in candidate["experiences"][:12]:
        heading = " · ".join(item for item in [experience.title, experience.company_name] if item)
        detail = experience.description or ""
        combined = ": ".join(item for item in [heading, detail] if item)
        if combined:
            segments.append(EvidenceSegment("VERIFIED_EXPERIENCE", heading or "Verified experience", combined, _meaningful_tokens(combined)))
    return segments


def _best_evidence(criterion_tokens: set[str], segments: list[EvidenceSegment]) -> tuple[EvidenceSegment | None, float]:
    if not criterion_tokens:
        return None, 0.0
    best: EvidenceSegment | None = None
    best_ratio = 0.0
    for segment in segments:
        overlap = criterion_tokens & segment.token_set
        if not overlap:
            continue
        ratio = len(overlap) / max(1, len(criterion_tokens))
        if ratio > best_ratio:
            best = segment
            best_ratio = ratio
    return best, best_ratio


def _status_from_ratio(ratio: float, *, exact: bool = False) -> str:
    if exact or ratio >= 0.60:
        return "SUPPORTED"
    if ratio >= 0.25:
        return "PARTIAL"
    return "NOT_EVIDENCED"


def _criterion(
    *, criterion_id: str, label: str, category: str, required: bool,
    candidate_skill_names: set[str], normalized_skill: str | None,
    segments: list[EvidenceSegment], weight: float | None = None,
) -> dict[str, Any]:
    criterion_tokens = _meaningful_tokens(label)
    exact = bool(normalized_skill and normalized_skill in candidate_skill_names)
    evidence, ratio = _best_evidence(criterion_tokens, segments)
    status = _status_from_ratio(ratio, exact=exact)
    if exact and evidence is None and normalized_skill:
        evidence = next((segment for segment in segments if segment.kind == "VERIFIED_SKILL" and normalized_skill in segment.token_set), None)
    return {
        "id": criterion_id,
        "label": label,
        "category": category,
        "required": required,
        "weight": weight,
        "status": status,
        "evidence": ({"kind": evidence.kind, "label": evidence.label, "snippet": _truncate(evidence.text)} if evidence and status != "NOT_EVIDENCED" else None),
    }


def _criteria_for_job(
    session: Session,
    user: User,
    job,
    *,
    custom_criteria: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    candidate = candidate_context(session, user)
    context = _job_context(session, job)
    segments = _evidence_segments(candidate)
    candidate_skill_names = {skill.normalized_name for skill in candidate["skills"] if skill.normalized_name}

    if custom_criteria:
        rows = []
        for index, item in enumerate(custom_criteria[:MAX_CRITERIA]):
            label = str(item.get("label", "")).strip()
            if not label:
                continue
            rows.append(_criterion(
                criterion_id=f"custom-{index}", label=label, category="CUSTOM_CRITERION",
                required=bool(item.get("required", True)), candidate_skill_names=candidate_skill_names,
                normalized_skill=None, segments=segments, weight=float(item.get("weight", 1.0)),
            ))
        if rows:
            return rows

    rows: list[dict[str, Any]] = []
    skills = list(context["skills"])
    required_skills = [skill for skill in skills if skill.required]
    preferred_skills = [skill for skill in skills if not skill.required]
    for index, skill in enumerate(required_skills):
        rows.append(_criterion(criterion_id=f"required-skill-{index}", label=skill.name, category="REQUIRED_SKILL", required=True, candidate_skill_names=candidate_skill_names, normalized_skill=skill.normalized_name, segments=segments))
    for index, skill in enumerate(preferred_skills):
        if len(rows) >= MAX_CRITERIA:
            break
        rows.append(_criterion(criterion_id=f"preferred-skill-{index}", label=skill.name, category="PREFERRED_SKILL", required=False, candidate_skill_names=candidate_skill_names, normalized_skill=skill.normalized_name, segments=segments))
    requirements = list(context["requirements"])
    ordered_requirements = [item for item in requirements if item.required] + [item for item in requirements if not item.required]
    for index, requirement in enumerate(ordered_requirements):
        if len(rows) >= MAX_CRITERIA:
            break
        rows.append(_criterion(
            criterion_id=f"requirement-{index}", label=requirement.text,
            category="REQUIRED_REQUIREMENT" if requirement.required else "PREFERRED_REQUIREMENT",
            required=bool(requirement.required), candidate_skill_names=candidate_skill_names,
            normalized_skill=None, segments=segments,
        ))
    if not rows:
        rows.append(_criterion(criterion_id="role-alignment", label=job.title, category="ROLE_ALIGNMENT", required=True, candidate_skill_names=candidate_skill_names, normalized_skill=None, segments=segments))
    return rows[:MAX_CRITERIA]


def _mode_weight(item: dict[str, Any], mode: str) -> float:
    explicit = item.get("weight")
    if explicit is not None:
        return max(0.1, min(float(explicit), 5.0))
    category = str(item.get("category", ""))
    required = bool(item.get("required"))
    if mode == "STRICT_MUST_HAVE":
        return 3.0 if required else 0.5
    if mode == "HIRING_MANAGER":
        return 2.5 if "REQUIREMENT" in category else 1.5 if required else 1.0
    if mode == "TECHNICAL":
        return 3.0 if "SKILL" in category else 1.25 if required else 0.75
    return 2.0 if required else 1.0


def _score(criteria: list[dict[str, Any]], mode: str) -> int:
    values = {"SUPPORTED": 1.0, "PARTIAL": 0.55, "NOT_EVIDENCED": 0.0}
    weighted = 0.0
    total_weight = 0.0
    for item in criteria:
        weight = _mode_weight(item, mode)
        weighted += values[item["status"]] * weight
        total_weight += weight
    return round(100 * weighted / total_weight) if total_weight else 0


def _tier(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def _confidence(criteria: list[dict[str, Any]]) -> str:
    evidence_count = sum(1 for item in criteria if item["evidence"] is not None)
    if len(criteria) >= 8 and evidence_count >= 5:
        return "HIGH"
    if len(criteria) >= 4 and evidence_count >= 2:
        return "MEDIUM"
    return "LOW"


def _concerns(criteria: list[dict[str, Any]]) -> list[dict[str, str]]:
    priority = {(True, "NOT_EVIDENCED"): 0, (True, "PARTIAL"): 1, (False, "NOT_EVIDENCED"): 2, (False, "PARTIAL"): 3, (True, "SUPPORTED"): 4, (False, "SUPPORTED"): 5}
    concerns: list[dict[str, str]] = []
    for item in sorted(criteria, key=lambda row: priority[(bool(row["required"]), row["status"])]):
        if item["status"] == "SUPPORTED":
            continue
        message = (
            f"Your saved evidence is adjacent to {item['label']}, but the resume/profile does not make that requirement fully explicit."
            if item["status"] == "PARTIAL"
            else f"ApplyAI could not find verified evidence for {item['label']} in your saved career profile."
        )
        concerns.append({"criterion_id": item["id"], "severity": "HIGH" if item["required"] else "MEDIUM", "message": message})
        if len(concerns) >= MAX_CONCERNS:
            break
    return concerns


def _questions(criteria: list[dict[str, Any]], mode: str) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    prefix = {
        "TECHNICAL": "Go technically deep:",
        "HIRING_MANAGER": "Focus on scope, judgment, and outcomes:",
        "STRICT_MUST_HAVE": "Clarify the must-have requirement:",
    }.get(mode, "Clarify truthfully:")
    for item in criteria:
        if item["status"] == "SUPPORTED":
            continue
        question = (
            f"{prefix} Your background shows adjacent evidence for {item['label']}. What verified example best demonstrates that capability, what was your specific role, and how would you explain the gap without overstating your experience?"
            if item["status"] == "PARTIAL"
            else f"{prefix} The role appears to value {item['label']}, but it is not explicit in your saved evidence. Do you have a truthful adjacent example you can explain without overstating your experience?"
        )
        questions.append({"criterion_id": item["id"], "focus": item["label"], "question": question})
        if len(questions) >= MAX_QUESTIONS:
            break
    return questions


def build_recruiter_lens(
    session: Session,
    user: User,
    job,
    *,
    mode: str = "DEFAULT_RECRUITER",
    custom_criteria: list[dict[str, Any]] | None = None,
    criteria_set_id: str | None = None,
) -> dict[str, Any]:
    normalized_mode = mode.upper()
    if normalized_mode not in ALLOWED_MODES:
        normalized_mode = "DEFAULT_RECRUITER"
    criteria = _criteria_for_job(session, user, job, custom_criteria=custom_criteria)
    score = _score(criteria, normalized_mode)
    counts = {
        "supported": sum(1 for item in criteria if item["status"] == "SUPPORTED"),
        "partial": sum(1 for item in criteria if item["status"] == "PARTIAL"),
        "not_evidenced": sum(1 for item in criteria if item["status"] == "NOT_EVIDENCED"),
    }
    return {
        "engine_version": ENGINE_VERSION,
        "mode": normalized_mode,
        "criteria_set_id": criteria_set_id,
        "score": score,
        "tier": _tier(score),
        "confidence": _confidence(criteria),
        "criteria_source": "CANDIDATE_CUSTOM" if custom_criteria else "STRUCTURED_JOB_POSTING",
        "counts": counts,
        "criteria": criteria,
        "concerns": _concerns(criteria),
        "interview_questions": _questions(criteria, normalized_mode),
        "report": {
            "print_friendly": True,
            "generated_for_candidate_self_assessment": True,
            "share_requires_candidate_control": True,
        },
        "disclaimer": "Recruiter Lens is a candidate-side screening simulation based on the job posting and your saved verified evidence. It is not an employer score, hiring probability, or automated employment decision.",
        "policy": {
            "candidate_self_assessment": True,
            "employer_prediction": False,
            "identity_fields_used": False,
            "evidence_policy": "VERIFIED_EVIDENCE_ONLY",
            "protected_characteristic_criteria_allowed": False,
        },
    }
