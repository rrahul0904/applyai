from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping, Sequence

from app.career_rubric import CandidateEvidence, JobRequirement

VERIFIED_PROVENANCE = frozenset({"USER_VERIFIED", "CANDIDATE_VERIFIED", "VERIFIED"})


@dataclass(frozen=True)
class CareerRubricInputBundle:
    candidate_revision: str
    job_revision: str
    requirements: tuple[JobRequirement, ...]
    evidence: tuple[CandidateEvidence, ...]


def _canonical_revision(prefix: str, payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return f"{prefix}-sha256:{hashlib.sha256(encoded).hexdigest()}"


def _normalized(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def build_rubric_inputs_from_career_context(
    context: Mapping[str, object],
    *,
    requirement_dimensions: Mapping[str, str] | None = None,
    evidence_links: Mapping[str, Sequence[str]] | None = None,
) -> CareerRubricInputBundle:
    """Translate ApplyAI's existing career AI context into rubric kernel inputs.

    The adapter is intentionally conservative:
    - structured job skills are mapped to the functional-knowledge dimension;
    - exact, user-verified candidate skill matches can support those skill requirements;
    - free-text job requirements are included only when a caller explicitly assigns a
      rubric dimension;
    - free-text candidate evidence supports requirements only when the caller explicitly
      supplies evidence links.

    This keeps dimension/evidence inference outside the deterministic trust boundary.
    """

    candidate = context.get("candidate")
    job = context.get("job")
    if not isinstance(candidate, dict) or not isinstance(job, dict):
        raise ValueError("career context must contain candidate and job objects")

    explicit_dimensions = dict(requirement_dimensions or {})
    explicit_links = {
        key: tuple(value) for key, value in (evidence_links or {}).items()
    }

    requirements: list[JobRequirement] = []
    job_skill_requirement_ids_by_name: dict[str, list[str]] = {}

    for raw_skill in job.get("skills") or []:
        if not isinstance(raw_skill, dict):
            continue
        skill_id = str(raw_skill.get("id") or "").strip()
        skill_name = str(raw_skill.get("name") or "").strip()
        if not skill_id or not skill_name:
            continue
        requirement_id = f"job.skill.{skill_id}"
        requirements.append(
            JobRequirement(
                id=requirement_id,
                dimension_id="functional_knowledge",
                text=skill_name,
                required=bool(raw_skill.get("required", True)),
            )
        )
        job_skill_requirement_ids_by_name.setdefault(
            _normalized(skill_name), []
        ).append(requirement_id)

    for raw_requirement in job.get("requirements") or []:
        if not isinstance(raw_requirement, dict):
            continue
        raw_id = str(raw_requirement.get("id") or "").strip()
        text = str(raw_requirement.get("text") or "").strip()
        if not raw_id or not text:
            continue
        requirement_id = f"job.requirement.{raw_id}"
        dimension_id = explicit_dimensions.get(requirement_id)
        if not dimension_id:
            continue
        requirements.append(
            JobRequirement(
                id=requirement_id,
                dimension_id=dimension_id,
                text=text,
                required=bool(raw_requirement.get("required", True)),
            )
        )

    known_requirement_ids = {item.id for item in requirements}
    evidence: list[CandidateEvidence] = []

    for raw_skill in candidate.get("skills") or []:
        if not isinstance(raw_skill, dict):
            continue
        evidence_id = f"candidate.skill.{str(raw_skill.get('id') or '').strip()}"
        skill_name = str(raw_skill.get("name") or "").strip()
        provenance = str(raw_skill.get("provenance") or "").upper()
        if evidence_id.endswith(".") or not skill_name:
            continue
        supported = tuple(
            sorted(job_skill_requirement_ids_by_name.get(_normalized(skill_name), []))
        )
        evidence.append(
            CandidateEvidence(
                id=evidence_id,
                text=skill_name,
                requirement_ids=supported,
                verified=provenance in VERIFIED_PROVENANCE,
            )
        )

    free_text_sources = (
        ("candidate.experience", candidate.get("experiences") or []),
        ("candidate.career_fact", candidate.get("career_memory") or []),
    )
    for prefix, rows in free_text_sources:
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_id = str(row.get("id") or "").strip()
            if not raw_id:
                continue
            evidence_id = f"{prefix}.{raw_id}"
            links = tuple(
                sorted(
                    requirement_id
                    for requirement_id in explicit_links.get(evidence_id, ())
                    if requirement_id in known_requirement_ids
                )
            )
            if prefix == "candidate.experience":
                text = " | ".join(
                    part
                    for part in (
                        str(row.get("company_name") or "").strip(),
                        str(row.get("title") or "").strip(),
                        str(row.get("description") or "").strip(),
                    )
                    if part
                )
                provenance = str(row.get("provenance") or "").upper()
                verified = provenance in VERIFIED_PROVENANCE
            else:
                text = " | ".join(
                    part
                    for part in (
                        str(row.get("category") or "").strip(),
                        str(row.get("title") or "").strip(),
                        str(row.get("fact_text") or "").strip(),
                    )
                    if part
                )
                # build_career_ai_context only includes user-verified, non-archived career facts.
                verified = True
            if not text:
                continue
            evidence.append(
                CandidateEvidence(
                    id=evidence_id,
                    text=text,
                    requirement_ids=links,
                    verified=verified,
                )
            )

    return CareerRubricInputBundle(
        candidate_revision=_canonical_revision("candidate", candidate),
        job_revision=_canonical_revision("job", job),
        requirements=tuple(sorted(requirements, key=lambda item: item.id)),
        evidence=tuple(sorted(evidence, key=lambda item: item.id)),
    )
