from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.agents.enums import ExecutionClass, ScoutDecision, VerificationDecision


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    base_delay_seconds: int = Field(default=5, ge=1, le=300)


class AgentDefinition(BaseModel):
    name: str
    version: str
    description: str
    execution_class: ExecutionClass
    allowed_tools: frozenset[str] = frozenset()
    denied_tools: frozenset[str] = frozenset()
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    max_steps: int = Field(default=8, ge=1, le=50)
    timeout_seconds: int = Field(default=120, ge=5, le=1800)
    max_input_tokens: int = Field(default=20_000, ge=0)
    max_output_tokens: int = Field(default=4_000, ge=0)
    max_cost_usd: Decimal = Field(default=Decimal("0.25"), ge=0)
    retry_policy: RetryPolicy = RetryPolicy()
    requires_human_approval: bool = False
    approval_policy: str | None = None
    provider_strategy: str = "configured"
    model_config_name: str = "default"
    queue_class: str = "agent-fast"
    priority: int = Field(default=50, ge=0, le=100)
    prompt_version: str = "v1"
    schema_version: str = "v1"
    enabled: bool = True

    model_config = {"arbitrary_types_allowed": True}


class AgentInput(BaseModel):
    candidate_id: str
    job_id: str | None = None
    workflow_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class JobScoutInput(AgentInput):
    job_id: str


class JobScoutDecision(BaseModel):
    decision: ScoutDecision
    overall_score: int = Field(ge=0, le=100)
    eligibility_status: str
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    compensation_fit: str
    location_fit: str
    work_authorization_fit: str
    career_goal_fit: str
    evidence_refs: list[str] = Field(min_length=1)
    recommendation_reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class JobResearchInput(AgentInput):
    job_id: str


class JobResearchResult(BaseModel):
    status: str = "VERIFIED"
    role_summary: str
    company_summary: str
    role_expectations: list[str] = Field(default_factory=list)
    candidate_strengths: list[str] = Field(default_factory=list)
    candidate_risks: list[str] = Field(default_factory=list)
    skill_requirements: list[str] = Field(default_factory=list)
    salary_evidence: list[dict[str, Any]] = Field(default_factory=list)
    location_policy: str
    remote_policy: str
    company_signals: list[str] = Field(default_factory=list)
    application_requirements: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(min_length=1)
    freshness: str


class ResumeTailorInput(AgentInput):
    job_id: str


class ResumeEdit(BaseModel):
    source_text: str
    suggested_text: str
    reason: str
    evidence_refs: list[str] = Field(min_length=1)
    risk_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class TailoredResumeArtifact(BaseModel):
    strategy_summary: str
    edits: list[ResumeEdit]
    evidence_refs: list[str] = Field(min_length=1)


class ResumeVerifierInput(AgentInput):
    job_id: str
    resume_artifact_id: str | None = None


class VerificationIssue(BaseModel):
    severity: str
    claim: str
    issue_type: str
    evidence_refs: list[str] = Field(default_factory=list)
    recommended_fix: str


class ResumeVerificationResult(BaseModel):
    decision: VerificationDecision
    issues: list[VerificationIssue] = Field(default_factory=list)
    evidence_refs: list[str] = Field(min_length=1)
    summary: str


AgentHandler = Callable[[Any, Any, Any], BaseModel]
