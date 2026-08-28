from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, Sequence


class InterviewMode(StrEnum):
    BEHAVIORAL = "behavioral"
    TECHNICAL = "technical"
    CODING = "coding"
    SQL = "sql"
    SYSTEM_DESIGN = "system_design"


@dataclass(frozen=True, slots=True)
class InterviewEvidence:
    kind: str
    reference: str
    summary: str


@dataclass(frozen=True, slots=True)
class InterviewRequest:
    candidate_id: str
    job_id: str
    mode: InterviewMode
    target_role: str
    verified_skills: tuple[str, ...] = ()
    evidence: tuple[InterviewEvidence, ...] = ()
    difficulty: str = "adaptive"


@dataclass(frozen=True, slots=True)
class InterviewQuestion:
    id: str
    prompt: str
    mode: InterviewMode
    difficulty: str
    evidence_refs: tuple[str, ...] = ()
    execution_required: bool = False


@dataclass(frozen=True, slots=True)
class InterviewSession:
    provider: str
    provider_session_id: str
    questions: tuple[InterviewQuestion, ...]
    metadata: dict[str, object] = field(default_factory=dict)


class InterviewEngine(Protocol):
    """Stable boundary between ApplyAI's candidate workflow and assessment engines.

    ApplyAI owns candidate/job identity, consent, evidence and product UX. An external
    engine may generate or execute technical assessments, but it must not become an
    alternate candidate identity/application authority.
    """

    def create_session(self, request: InterviewRequest) -> InterviewSession: ...


class DeterministicInterviewEngine:
    """Safe built-in fallback used when no reviewed assessment provider is enabled."""

    provider = "applyai-deterministic"

    def create_session(self, request: InterviewRequest) -> InterviewSession:
        skills = request.verified_skills[:3] or (request.target_role,)
        questions: list[InterviewQuestion] = []
        for index, skill in enumerate(skills, start=1):
            if request.mode == InterviewMode.BEHAVIORAL:
                prompt = (
                    f"Describe a verified example where you used {skill}. Explain the "
                    "situation, your direct contribution, result, and what you learned."
                )
            elif request.mode == InterviewMode.SYSTEM_DESIGN:
                prompt = (
                    f"Design a production system involving {skill}. State requirements, "
                    "trade-offs, failure modes, security boundaries, and observability."
                )
            else:
                prompt = (
                    f"Explain how you would solve a realistic {request.target_role} problem "
                    f"using {skill}. Make assumptions explicit and discuss verification."
                )
            questions.append(
                InterviewQuestion(
                    id=f"local-{request.mode.value}-{index}",
                    prompt=prompt,
                    mode=request.mode,
                    difficulty=request.difficulty,
                    evidence_refs=tuple(item.reference for item in request.evidence),
                    execution_required=request.mode in {InterviewMode.CODING, InterviewMode.SQL},
                )
            )
        return InterviewSession(
            provider=self.provider,
            provider_session_id=f"local:{request.candidate_id}:{request.job_id}:{request.mode.value}",
            questions=tuple(questions),
            metadata={"evidence_locked": True, "external_execution": False},
        )


@dataclass(frozen=True, slots=True)
class RigorProviderConfig:
    base_url: str
    audience: str = "applyai"
    enabled: bool = False


class RigorInterviewEngine:
    """Contract placeholder for Rigor Interview Systems Lab.

    This intentionally does not perform network calls. Enabling Rigor requires a reviewed,
    authenticated API contract plus explicit consent and deployment configuration. Candidate
    code execution must remain inside Rigor's isolated execution boundary, never the ApplyAI
    API process.
    """

    provider = "rigor"

    def __init__(self, config: RigorProviderConfig) -> None:
        self.config = config

    def create_session(self, request: InterviewRequest) -> InterviewSession:
        if not self.config.enabled:
            raise RuntimeError("RIGOR_PROVIDER_DISABLED")
        raise RuntimeError("RIGOR_REMOTE_CONTRACT_NOT_CONFIGURED")


def choose_interview_engine(
    *,
    prefer_rigor: bool,
    rigor: RigorInterviewEngine | None = None,
) -> InterviewEngine:
    if prefer_rigor and rigor is not None and rigor.config.enabled:
        return rigor
    return DeterministicInterviewEngine()
