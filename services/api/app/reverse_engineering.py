from __future__ import annotations

from collections import defaultdict
from enum import StrEnum
import re
from typing import Any

CLASSIFIER_VERSION = "2026-09-17.1"


class ApplyAIFit(StrEnum):
    CORE = "CORE"
    PREPARE = "PREPARE"
    INTELLIGENCE = "INTELLIGENCE"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    INTEGRATION = "INTEGRATION"
    NOT_APPLYAI = "NOT_APPLYAI"


class FitScope(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


class TopicStatus(StrEnum):
    RESEARCHED = "RESEARCHED"
    PLANNED = "PLANNED"
    IMPLEMENTING = "IMPLEMENTING"
    INTEGRATED = "INTEGRATED"
    REJECTED = "REJECTED"


class JourneyStage(StrEnum):
    DISCOVER_JOBS = "DISCOVER_JOBS"
    UNDERSTAND_FIT = "UNDERSTAND_FIT"
    IMPROVE_RESUME_PROFILE = "IMPROVE_RESUME_PROFILE"
    APPLY = "APPLY"
    TRACK = "TRACK"
    LEARN_SKILL_GAPS = "LEARN_SKILL_GAPS"
    PREPARE_INTERVIEWS = "PREPARE_INTERVIEWS"
    PRACTICE_MOCKS = "PRACTICE_MOCKS"
    MEASURE_READINESS = "MEASURE_READINESS"
    CAREER_INTELLIGENCE = "CAREER_INTELLIGENCE"


FIT_RULES: dict[ApplyAIFit, dict[str, Any]] = {
    ApplyAIFit.CORE: {
        "label": "APPLYAI — CORE",
        "meaning": "Directly strengthens the ApplyAI candidate experience.",
        "examples": [
            "Job discovery and matching",
            "Resume/profile tailoring",
            "Application automation and tracking",
            "Recruiter lens",
        ],
        "default_scope": FitScope.FULL,
        "destination": "candidate-core",
    },
    ApplyAIFit.PREPARE: {
        "label": "APPLYAI — PREPARE",
        "meaning": "Builds learning, skill-gap, interview, practice, or readiness workflows.",
        "examples": [
            "AI tutor and learning paths",
            "Mock interviews",
            "Question banks",
            "Coding, SQL, and system-design practice",
        ],
        "default_scope": FitScope.FULL,
        "destination": "prepare",
    },
    ApplyAIFit.INTELLIGENCE: {
        "label": "APPLYAI — INTELLIGENCE",
        "meaning": "Adds decision intelligence around jobs, companies, recruiters, compensation, or careers.",
        "examples": [
            "Company intelligence",
            "Interview patterns",
            "Salary intelligence",
            "Career navigation",
        ],
        "default_scope": FitScope.FULL,
        "destination": "career-intelligence",
    },
    ApplyAIFit.INFRASTRUCTURE: {
        "label": "APPLYAI — INFRASTRUCTURE",
        "meaning": "Improves the quality, safety, evaluation, provenance, or observability of ApplyAI agents.",
        "examples": [
            "Agent and skill evaluation",
            "Regression gates",
            "Provenance",
            "Guardrails and observability",
        ],
        "default_scope": FitScope.PARTIAL,
        "destination": "platform-infrastructure",
    },
    ApplyAIFit.INTEGRATION: {
        "label": "APPLYAI — INTEGRATION",
        "meaning": "A specialist or external system that ApplyAI should consume instead of duplicating.",
        "examples": [
            "MCP interoperability",
            "External assessment engines",
            "Sandbox execution",
            "Specialized agents",
        ],
        "default_scope": FitScope.PARTIAL,
        "destination": "external-integration",
    },
    ApplyAIFit.NOT_APPLYAI: {
        "label": "NOT APPLYAI",
        "meaning": "Does not materially strengthen the candidate career journey or ApplyAI platform.",
        "examples": [
            "Trading",
            "Generic video generation",
            "SEO tools",
            "Unrelated SaaS",
        ],
        "default_scope": FitScope.NONE,
        "destination": "separate-product",
    },
}


SIGNALS: dict[ApplyAIFit, dict[str, int]] = {
    ApplyAIFit.CORE: {
        "job discovery": 5, "job search": 4, "job matching": 5, "job match": 4,
        "resume tailoring": 5, "resume optimization": 4, "resume": 2, "cover letter": 3,
        "application automation": 5, "auto apply": 5, "application tracking": 4,
        "application pipeline": 3, "recruiter lens": 5, "candidate profile": 3, "job import": 3,
    },
    ApplyAIFit.PREPARE: {
        "interview prep": 5, "interview preparation": 5, "mock interview": 5,
        "question bank": 4, "coding practice": 5, "sql practice": 5, "system design": 4,
        "skill gap": 4, "learning path": 4, "ai tutor": 5, "course": 2, "practice": 2,
    },
    ApplyAIFit.INTELLIGENCE: {
        "company intelligence": 5, "salary intelligence": 5, "interview pattern": 5,
        "interview intelligence": 5, "career intelligence": 5, "career navigation": 4,
        "job scoring": 4, "job judging": 4, "fit explanation": 4, "market intelligence": 3,
        "recruiter intelligence": 4,
    },
    ApplyAIFit.INFRASTRUCTURE: {
        "agent evaluation": 6, "skill evaluation": 6, "a/b evaluation": 5, "a/b test": 4,
        "baseline arm": 4, "candidate arm": 4, "regression detection": 5, "regression": 3,
        "provenance": 4, "guardrail": 4, "observability": 4, "evaluation receipt": 6,
        "release gate": 5, "trigger precision": 5, "trigger recall": 5,
        "latency measurement": 3, "cost measurement": 3,
    },
    ApplyAIFit.INTEGRATION: {
        "mcp": 6, "interoperability": 6, "external assessment": 5, "assessment engine": 4,
        "execution engine": 5, "external agent": 4, "connector": 2, "sdk": 2,
        "api integration": 3, "leetcode": 4, "rigor": 4, "sandbox execution": 4,
    },
    ApplyAIFit.NOT_APPLYAI: {
        "trading": 5, "crypto trading": 6, "video generation": 5, "image generation": 4,
        "seo": 4, "ecommerce": 4, "restaurant": 3, "recipe": 3, "music generation": 4,
    },
}


JOURNEY_SIGNALS: dict[JourneyStage, tuple[str, ...]] = {
    JourneyStage.DISCOVER_JOBS: ("job discovery", "job search", "job board", "listings", "job import"),
    JourneyStage.UNDERSTAND_FIT: ("job match", "job matching", "fit", "recruiter lens", "company intelligence", "job scoring"),
    JourneyStage.IMPROVE_RESUME_PROFILE: ("resume", "cover letter", "profile tailoring", "candidate profile"),
    JourneyStage.APPLY: ("auto apply", "apply to job", "application automation", "submission"),
    JourneyStage.TRACK: ("application tracking", "application pipeline", "follow up", "follow-up"),
    JourneyStage.LEARN_SKILL_GAPS: ("skill gap", "learning path", "course", "ai tutor"),
    JourneyStage.PREPARE_INTERVIEWS: ("interview prep", "interview preparation", "interview intelligence", "question bank"),
    JourneyStage.PRACTICE_MOCKS: ("mock interview", "coding practice", "sql practice", "system design", "practice"),
    JourneyStage.MEASURE_READINESS: ("readiness", "assessment", "evaluation", "scorecard", "benchmark"),
    JourneyStage.CAREER_INTELLIGENCE: ("career intelligence", "career navigation", "salary", "market intelligence"),
}


FIT_PRECEDENCE = (
    ApplyAIFit.CORE,
    ApplyAIFit.PREPARE,
    ApplyAIFit.INTELLIGENCE,
    ApplyAIFit.INFRASTRUCTURE,
    ApplyAIFit.INTEGRATION,
    ApplyAIFit.NOT_APPLYAI,
)


def _normalize(value: str) -> str:
    value = value.lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", value).strip()


def fit_metadata(fit: ApplyAIFit | str) -> dict[str, Any]:
    normalized = ApplyAIFit(fit)
    rule = FIT_RULES[normalized]
    return {
        "fit": normalized.value,
        "label": rule["label"],
        "meaning": rule["meaning"],
        "examples": list(rule["examples"]),
        "default_scope": rule["default_scope"].value,
        "destination": rule["destination"],
    }


def taxonomy_payload() -> dict[str, Any]:
    return {
        "classifier_version": CLASSIFIER_VERSION,
        "candidate_journey": [stage.value for stage in JourneyStage],
        "classifications": [fit_metadata(fit) for fit in FIT_PRECEDENCE],
        "summary_contract": [
            "ApplyAI Fit",
            "Why it qualifies or does not qualify",
            "Candidate journey stages",
            "Capabilities to absorb",
            "Capabilities to keep separate",
            "Implementation destination",
            "Implementation status",
        ],
    }


def classify_topic(
    *,
    title: str,
    summary: str = "",
    capabilities: list[str] | None = None,
) -> dict[str, Any]:
    capability_values = capabilities or []
    corpus = _normalize(" ".join([title, summary, *capability_values]))
    scores: defaultdict[ApplyAIFit, int] = defaultdict(int)
    matched: defaultdict[ApplyAIFit, list[str]] = defaultdict(list)

    for fit, terms in SIGNALS.items():
        for term, weight in terms.items():
            if _normalize(term) in corpus:
                scores[fit] += weight
                matched[fit].append(term)

    positive_score = max((scores[fit] for fit in FIT_PRECEDENCE if fit != ApplyAIFit.NOT_APPLYAI), default=0)
    if positive_score == 0 and scores[ApplyAIFit.NOT_APPLYAI] == 0:
        scores[ApplyAIFit.NOT_APPLYAI] = 1

    best_score = max(scores.values(), default=0)
    selected = next(fit for fit in FIT_PRECEDENCE if scores[fit] == best_score)
    metadata = fit_metadata(selected)

    journey_stages = [
        stage.value
        for stage, terms in JOURNEY_SIGNALS.items()
        if any(_normalize(term) in corpus for term in terms)
    ]
    if selected == ApplyAIFit.INFRASTRUCTURE and JourneyStage.MEASURE_READINESS.value not in journey_stages:
        if any(term in matched[selected] for term in ("agent evaluation", "skill evaluation", "evaluation receipt", "release gate")):
            journey_stages.append(JourneyStage.MEASURE_READINESS.value)

    selected_matches = matched[selected]
    if selected == ApplyAIFit.NOT_APPLYAI:
        if selected_matches:
            rationale = (
                "The strongest observed signals are outside ApplyAI's candidate journey "
                f"({', '.join(selected_matches[:4])}); keep this as a separate product."
            )
        else:
            rationale = (
                "No evidence in the supplied summary maps this topic to ApplyAI's candidate journey "
                "or platform-enabling capabilities. It should remain separate until stronger evidence exists."
            )
    else:
        rationale = (
            f"Classified as {metadata['label']} because the strongest signals are "
            f"{', '.join(selected_matches[:5]) or 'candidate-journey alignment'}. "
            f"Default implementation destination: {metadata['destination']}."
        )

    return {
        "classifier_version": CLASSIFIER_VERSION,
        "applyai_fit": selected.value,
        "fit_label": metadata["label"],
        "fit_scope": metadata["default_scope"],
        "destination": metadata["destination"],
        "rationale": rationale,
        "candidate_journey_stages": journey_stages,
        "matched_signals": {fit.value: list(matched[fit]) for fit in FIT_PRECEDENCE if matched[fit]},
        "scores": {fit.value: scores[fit] for fit in FIT_PRECEDENCE},
    }
