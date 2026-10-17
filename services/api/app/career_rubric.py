from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

Coverage = Literal["strong", "partial", "weak", "absent", "unknown"]
FitState = Literal["aligned", "below", "unknown"]
GapType = Literal[
    "missing_evidence",
    "weak_specificity",
    "requirement_gap",
    "unknown",
]


@dataclass(frozen=True)
class RubricDimension:
    id: str
    label: str
    description: str


@dataclass(frozen=True)
class CareerRubric:
    version: str
    dimensions: tuple[RubricDimension, ...]


@dataclass(frozen=True)
class JobRequirement:
    id: str
    dimension_id: str
    text: str
    required: bool = True


@dataclass(frozen=True)
class CandidateEvidence:
    id: str
    text: str
    requirement_ids: tuple[str, ...] = ()
    verified: bool = True


@dataclass(frozen=True)
class RubricGap:
    dimension_id: str
    gap_type: GapType
    requirement_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    action: str


@dataclass(frozen=True)
class DimensionResult:
    dimension_id: str
    coverage: Coverage
    fit_state: FitState
    supported_requirement_ids: tuple[str, ...]
    unsupported_requirement_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    rationale: str
    gap: RubricGap | None


@dataclass(frozen=True)
class RubricAssessment:
    assessment_id: str
    candidate_revision: str
    job_revision: str
    rubric_version: str
    input_digest: str
    results: tuple[DimensionResult, ...]

    def is_stale(
        self,
        *,
        candidate_revision: str,
        job_revision: str,
        rubric_version: str,
    ) -> bool:
        return (
            self.candidate_revision != candidate_revision
            or self.job_revision != job_revision
            or self.rubric_version != rubric_version
        )


DEFAULT_CAREER_RUBRIC = CareerRubric(
    version="career-rubric-v1",
    dimensions=(
        RubricDimension(
            id="functional_knowledge",
            label="Functional / technical knowledge",
            description="Depth and breadth of knowledge explicitly required for the work.",
        ),
        RubricDimension(
            id="problem_complexity",
            label="Problem complexity",
            description="Ambiguity, novelty, and difficulty of problems the role must solve.",
        ),
        RubricDimension(
            id="decision_scope",
            label="Decision scope / autonomy",
            description=(
                "Independent judgment, ownership, and decision rights required by the role."
            ),
        ),
        RubricDimension(
            id="business_accountability",
            label="Business accountability / impact",
            description="Responsibility for measurable business or operational outcomes.",
        ),
        RubricDimension(
            id="leadership_influence",
            label="Leadership / influence",
            description="People, technical, stakeholder, or cross-functional influence.",
        ),
        RubricDimension(
            id="scale_context",
            label="Scale / operating context",
            description=(
                "System, data, customer, team, geographic, or financial scale when evidenced."
            ),
        ),
        RubricDimension(
            id="role_level_consistency",
            label="Role-level consistency",
            description="Whether the evidence supports the scope expected at the target seniority.",
        ),
    ),
)


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_inputs(
    rubric: CareerRubric,
    requirements: tuple[JobRequirement, ...],
    evidence: tuple[CandidateEvidence, ...],
) -> None:
    dimension_ids = {dimension.id for dimension in rubric.dimensions}
    if len(dimension_ids) != len(rubric.dimensions):
        raise ValueError("rubric dimension ids must be unique")

    requirement_ids = {item.id for item in requirements}
    if len(requirement_ids) != len(requirements):
        raise ValueError("job requirement ids must be unique")
    unknown_dimensions = sorted(
        {item.dimension_id for item in requirements} - dimension_ids
    )
    if unknown_dimensions:
        raise ValueError(
            f"requirements reference unknown dimensions: {', '.join(unknown_dimensions)}"
        )

    evidence_ids = {item.id for item in evidence}
    if len(evidence_ids) != len(evidence):
        raise ValueError("candidate evidence ids must be unique")

    unknown_requirement_refs = sorted(
        {
            requirement_id
            for item in evidence
            for requirement_id in item.requirement_ids
            if requirement_id not in requirement_ids
        }
    )
    if unknown_requirement_refs:
        raise ValueError(
            "candidate evidence references unknown requirements: "
            + ", ".join(unknown_requirement_refs)
        )


def _coverage(
    *,
    required_ids: set[str],
    optional_ids: set[str],
    supported_ids: set[str],
) -> Coverage:
    if not required_ids and not optional_ids:
        return "unknown"

    if required_ids:
        required_supported = len(required_ids & supported_ids)
        if required_supported == len(required_ids):
            return "strong"
        if required_supported == 0:
            return "absent"
        ratio = required_supported / len(required_ids)
        return "partial" if ratio >= 0.5 else "weak"

    optional_supported = len(optional_ids & supported_ids)
    if optional_supported == len(optional_ids):
        return "strong"
    if optional_supported == 0:
        return "absent"
    ratio = optional_supported / len(optional_ids)
    return "partial" if ratio >= 0.5 else "weak"


def _gap_for(
    *,
    dimension_id: str,
    coverage: Coverage,
    unsupported_requirement_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
) -> RubricGap | None:
    if coverage == "strong":
        return None
    if coverage == "unknown":
        return RubricGap(
            dimension_id=dimension_id,
            gap_type="unknown",
            requirement_ids=(),
            evidence_ids=evidence_ids,
            action="Collect clearer role requirements before drawing a fit conclusion.",
        )
    if coverage == "absent":
        return RubricGap(
            dimension_id=dimension_id,
            gap_type="missing_evidence",
            requirement_ids=unsupported_requirement_ids,
            evidence_ids=evidence_ids,
            action=(
                "Look for verified candidate evidence that supports the unmet requirement; "
                "if none exists, treat it as a real requirement gap."
            ),
        )
    return RubricGap(
        dimension_id=dimension_id,
        gap_type="weak_specificity",
        requirement_ids=unsupported_requirement_ids,
        evidence_ids=evidence_ids,
        action=(
            "Clarify existing verified evidence for the unmet requirement without adding "
            "new scope, skills, metrics, or outcomes."
        ),
    )


def assess_career_rubric(
    *,
    candidate_revision: str,
    job_revision: str,
    rubric: CareerRubric = DEFAULT_CAREER_RUBRIC,
    requirements: tuple[JobRequirement, ...],
    evidence: tuple[CandidateEvidence, ...],
) -> RubricAssessment:
    """Create a deterministic evidence-linked role assessment.

    This kernel intentionally does not infer semantics from free text. A requirement must
    already be assigned to a rubric dimension, and candidate evidence must explicitly link
    to requirement ids. Free-text fields are treated as opaque evidence, so titles,
    keyword stuffing, or prompt-like text cannot manufacture support.
    """

    if not candidate_revision.strip():
        raise ValueError("candidate_revision is required")
    if not job_revision.strip():
        raise ValueError("job_revision is required")
    if not rubric.version.strip():
        raise ValueError("rubric version is required")

    _validate_inputs(rubric, requirements, evidence)

    verified_evidence = tuple(item for item in evidence if item.verified)
    results: list[DimensionResult] = []

    for dimension in rubric.dimensions:
        dimension_requirements = tuple(
            item for item in requirements if item.dimension_id == dimension.id
        )
        required_ids = {item.id for item in dimension_requirements if item.required}
        optional_ids = {item.id for item in dimension_requirements if not item.required}
        dimension_requirement_ids = required_ids | optional_ids

        supporting_evidence = tuple(
            item
            for item in verified_evidence
            if dimension_requirement_ids.intersection(item.requirement_ids)
        )
        supported_ids = {
            requirement_id
            for item in supporting_evidence
            for requirement_id in item.requirement_ids
            if requirement_id in dimension_requirement_ids
        }
        unsupported_ids = tuple(
            sorted(dimension_requirement_ids - supported_ids)
        )
        evidence_ids = tuple(sorted(item.id for item in supporting_evidence))
        coverage = _coverage(
            required_ids=required_ids,
            optional_ids=optional_ids,
            supported_ids=supported_ids,
        )
        fit_state: FitState
        if coverage == "strong":
            fit_state = "aligned"
        elif coverage in {"weak", "absent"}:
            fit_state = "below"
        else:
            fit_state = "unknown"

        if coverage == "unknown":
            rationale = "No role requirement is mapped to this dimension; fit remains unknown."
        elif coverage == "strong":
            rationale = (
                f"Verified evidence supports all {len(dimension_requirement_ids)} "
                "mapped role requirement(s) in this dimension."
            )
        else:
            rationale = (
                f"Verified evidence supports {len(supported_ids)} of "
                f"{len(dimension_requirement_ids)} mapped role requirement(s); "
                f"{len(unsupported_ids)} remain unsupported."
            )

        results.append(
            DimensionResult(
                dimension_id=dimension.id,
                coverage=coverage,
                fit_state=fit_state,
                supported_requirement_ids=tuple(sorted(supported_ids)),
                unsupported_requirement_ids=unsupported_ids,
                evidence_ids=evidence_ids,
                rationale=rationale,
                gap=_gap_for(
                    dimension_id=dimension.id,
                    coverage=coverage,
                    unsupported_requirement_ids=unsupported_ids,
                    evidence_ids=evidence_ids,
                ),
            )
        )

    canonical_input = {
        "candidate_revision": candidate_revision,
        "job_revision": job_revision,
        "rubric": asdict(rubric),
        "requirements": [asdict(item) for item in sorted(requirements, key=lambda row: row.id)],
        "evidence": [asdict(item) for item in sorted(evidence, key=lambda row: row.id)],
    }
    input_digest = _canonical_digest(canonical_input)
    return RubricAssessment(
        assessment_id=f"cra_{input_digest[:24]}",
        candidate_revision=candidate_revision,
        job_revision=job_revision,
        rubric_version=rubric.version,
        input_digest=input_digest,
        results=tuple(results),
    )
