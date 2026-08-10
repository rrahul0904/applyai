from __future__ import annotations

from decimal import Decimal

from app.agents.contracts import (
    AgentDefinition,
    JobResearchInput,
    JobResearchResult,
    JobScoutDecision,
    JobScoutInput,
    ResumeTailorInput,
    ResumeVerifierInput,
    ResumeVerificationResult,
    TailoredResumeArtifact,
)
from app.agents.enums import ExecutionClass


AGENT_REGISTRY: dict[tuple[str, str], AgentDefinition] = {}


def register(definition: AgentDefinition) -> AgentDefinition:
    key = (definition.name, definition.version)
    if key in AGENT_REGISTRY:
        raise ValueError(f"Duplicate agent definition: {definition.name}:{definition.version}")
    if definition.allowed_tools & definition.denied_tools:
        raise ValueError(f"Agent cannot both allow and deny tools: {definition.name}")
    AGENT_REGISTRY[key] = definition
    return definition


def get_agent_definition(name: str, version: str | None = None) -> AgentDefinition:
    if version is not None:
        definition = AGENT_REGISTRY.get((name, version))
        if definition is None:
            raise KeyError(f"Unknown agent definition: {name}:{version}")
        if not definition.enabled:
            raise PermissionError(f"Agent is disabled: {name}:{version}")
        return definition
    matches = [definition for (agent_name, _), definition in AGENT_REGISTRY.items() if agent_name == name]
    if not matches:
        raise KeyError(f"Unknown agent: {name}")
    enabled = [item for item in matches if item.enabled]
    if not enabled:
        raise PermissionError(f"Agent is disabled: {name}")
    return sorted(enabled, key=lambda item: item.version)[-1]


register(
    AgentDefinition(
        name="job_scout",
        version="v1",
        description="Prioritize a canonical job for one candidate using bounded evidence-backed reasoning.",
        execution_class=ExecutionClass.READ,
        allowed_tools=frozenset({
            "candidate.profile.read",
            "candidate.evidence.read",
            "career_memory.read",
            "job.read",
            "application.read",
        }),
        denied_tools=frozenset({"application.submit", "email.send", "candidate.evidence.write"}),
        input_schema=JobScoutInput,
        output_schema=JobScoutDecision,
        max_steps=6,
        timeout_seconds=90,
        max_cost_usd=Decimal("0.08"),
        queue_class="agent-fast",
        priority=70,
        prompt_version="job-scout-v1",
        schema_version="job-scout-schema-v1",
    )
)
register(
    AgentDefinition(
        name="job_research",
        version="v1",
        description="Create provenance-aware candidate-specific job and company intelligence.",
        execution_class=ExecutionClass.READ,
        allowed_tools=frozenset({
            "candidate.profile.read",
            "candidate.evidence.read",
            "career_memory.read",
            "job.read",
            "company.read",
        }),
        denied_tools=frozenset({"application.submit", "email.send"}),
        input_schema=JobResearchInput,
        output_schema=JobResearchResult,
        max_steps=8,
        timeout_seconds=120,
        max_cost_usd=Decimal("0.12"),
        queue_class="agent-research",
        priority=60,
        prompt_version="job-research-v1",
        schema_version="job-research-schema-v1",
    )
)
register(
    AgentDefinition(
        name="resume_tailor",
        version="v1",
        description="Tailor verified resume evidence to a target job without changing candidate truth.",
        execution_class=ExecutionClass.PREPARE,
        allowed_tools=frozenset({
            "candidate.profile.read",
            "candidate.evidence.read",
            "career_memory.read",
            "job.read",
            "resume.master.read",
            "artifact.read",
        }),
        denied_tools=frozenset({"application.submit", "email.send", "candidate.evidence.write"}),
        input_schema=ResumeTailorInput,
        output_schema=TailoredResumeArtifact,
        max_steps=8,
        timeout_seconds=120,
        max_cost_usd=Decimal("0.20"),
        queue_class="agent-generation",
        priority=65,
        prompt_version="resume-tailor-agent-v1",
        schema_version="resume-tailor-agent-schema-v1",
    )
)
register(
    AgentDefinition(
        name="resume_verifier",
        version="v1",
        description="Independently challenge a tailored resume against verified candidate evidence.",
        execution_class=ExecutionClass.READ,
        allowed_tools=frozenset({
            "candidate.evidence.read",
            "job.read",
            "resume.master.read",
            "artifact.read",
        }),
        denied_tools=frozenset({"application.submit", "email.send", "candidate.evidence.write"}),
        input_schema=ResumeVerifierInput,
        output_schema=ResumeVerificationResult,
        max_steps=6,
        timeout_seconds=90,
        max_cost_usd=Decimal("0.10"),
        queue_class="agent-generation",
        priority=75,
        prompt_version="resume-verifier-v1",
        schema_version="resume-verifier-schema-v1",
    )
)
