from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings


@dataclass(frozen=True)
class ProviderResult:
    output: dict[str, Any]
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int | None = None


class AIProviderError(RuntimeError):
    pass


class TransientAIProviderError(AIProviderError):
    pass


class BaseAIProvider:
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        task_type: str,
        safety_identifier: str,
        output_schema: dict[str, Any],
    ) -> ProviderResult:
        raise NotImplementedError


class DeterministicAIProvider(BaseAIProvider):
    """Development/test provider with predictable evidence-safe output.

    It intentionally does not pretend to be an LLM. Production can switch to
    `openai` without changing task persistence, API contracts, or worker logic.
    """

    def __init__(self, model: str = "deterministic-evidence-v1") -> None:
        self.model = model

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        task_type: str,
        safety_identifier: str,
        output_schema: dict[str, Any],
    ) -> ProviderResult:
        del system_prompt, safety_identifier, output_schema
        evidence = user_payload.get("evidence_catalog") or {}
        refs = list(evidence)[:12] or ["job.description"]
        deterministic = user_payload.get("deterministic_match") or {}
        profile = user_payload.get("candidate") or {}
        job = user_payload.get("job") or {}
        experience = (profile.get("experiences") or [{}])[0]
        source_text = (
            experience.get("description")
            or profile.get("summary")
            or "Verified candidate experience"
        )
        title = job.get("title") or "this role"
        company = job.get("company_name") or "the company"
        score = int(deterministic.get("match_score") or 50)
        priority = deterministic.get("decision") or (
            "CONSIDER" if score >= 65 else "STRETCH"
        )

        if task_type == "AI_DEEP_MATCH":
            output = {
                "ai_score": score,
                "priority": priority,
                "summary": (
                    f"The verified profile has meaningful evidence for {title}; use "
                    "the deterministic factors as the baseline and validate the "
                    "remaining gaps before applying."
                ),
                "strengths": deterministic.get("strengths")
                or ["Verified candidate evidence is available."],
                "gaps": deterministic.get("risks") or [],
                "interview_risks": deterministic.get("risks")
                or ["Confirm scope and expectations in interview."],
                "recommended_actions": [
                    "Review the evidence-backed gaps before finalizing application materials."
                ],
                "evidence_refs": refs,
            }
        elif task_type == "AI_RESUME_TAILOR":
            output = {
                "strategy_summary": (
                    "Keep the resume factual while emphasizing verified experience "
                    f"most relevant to {title}."
                ),
                "edits": [
                    {
                        "source_text": source_text,
                        "suggested_text": source_text,
                        "reason": (
                            "Preserve verified wording as the safe baseline; candidate "
                            "review can refine emphasis without adding unsupported claims."
                        ),
                        "evidence_refs": refs[:3],
                        "risk_flags": [],
                        "confidence": 1.0,
                    }
                ],
                "evidence_refs": refs,
            }
        elif task_type == "AI_APPLICATION_COPILOT":
            output = {
                "cover_letter": (
                    f"Dear {company} Hiring Team,\n\nI am interested in the {title} "
                    "opportunity. My verified background aligns with the role through "
                    "the experience and skills documented in my ApplyAI profile. I would "
                    "welcome the opportunity to discuss the team's priorities and where "
                    "my experience can contribute.\n\nThank you for your consideration."
                ),
                "cover_letter_evidence_refs": refs,
                "questions": [
                    {
                        "question": "Why are you interested in this role?",
                        "answer": (
                            f"I am interested in the {title} role because it aligns with "
                            "the verified experience and target direction in my profile."
                        ),
                        "evidence_refs": refs[:4],
                    }
                ],
                "recruiter_message": (
                    f"I am interested in the {title} opportunity at {company}. My verified "
                    "background appears relevant, and I would appreciate the chance to "
                    "learn more about the role and team priorities."
                ),
                "recruiter_message_evidence_refs": refs,
                "strategy_notes": ["Candidate review is required before use."],
                "evidence_refs": refs,
            }
        elif task_type == "AI_INTERVIEW_PREP":
            questions = []
            for index in range(3):
                questions.append(
                    {
                        "question": (
                            f"Tell me about verified experience relevant to {title}."
                            if index == 0
                            else f"How would you approach priority {index} in this role?"
                        ),
                        "why_it_matters": (
                            "This tests whether the candidate can connect verified "
                            "experience to the role without overstating evidence."
                        ),
                        "answer_outline": source_text,
                        "evidence_refs": refs[:4],
                    }
                )
            output = {
                "strategy_summary": (
                    "Anchor every answer in verified experience, acknowledge gaps directly, "
                    "and use the interview to clarify scope and first-year expectations."
                ),
                "likely_questions": questions,
                "questions_to_ask": [
                    "What are the most important outcomes in the first six months?",
                    "How is success measured for this role?",
                    "What are the largest current team or platform constraints?",
                ],
                "skill_gap_plan": deterministic.get("risks") or [],
                "evidence_refs": refs,
            }
        else:
            raise AIProviderError(f"Unsupported deterministic AI task: {task_type}")
        return ProviderResult(output=output, model=self.model, latency_ms=0)


class OpenAIResponsesProvider(BaseAIProvider):
    """Responses API client with strict JSON-schema output and no stored response."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise AIProviderError("OPENAI_API_KEY_MISSING")
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        self.timeout_seconds = settings.ai_request_timeout_seconds
        self.base_url = settings.openai_base_url.rstrip("/")
        self.reasoning_effort = settings.openai_reasoning_effort

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str:
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        texts: list[str] = []
        for item in payload.get("output") or []:
            if item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if (
                    content.get("type") in {"output_text", "text"}
                    and content.get("text")
                ):
                    texts.append(str(content["text"]))
        if not texts:
            raise AIProviderError("MODEL_OUTPUT_MISSING")
        return "\n".join(texts)

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        task_type: str,
        safety_identifier: str,
        output_schema: dict[str, Any],
    ) -> ProviderResult:
        started = time.perf_counter()
        request_body = {
            "model": self.model,
            "instructions": system_prompt,
            "input": json.dumps(
                {"task_type": task_type, "context": user_payload},
                separators=(",", ":"),
                ensure_ascii=False,
            ),
            "reasoning": {"effort": self.reasoning_effort},
            "text": {
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": task_type.lower(),
                    "schema": output_schema,
                    "strict": True,
                },
            },
            "store": False,
            "safety_identifier": safety_identifier,
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/v1/responses",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code == 429 or status_code >= 500:
                raise TransientAIProviderError(
                    f"OPENAI_HTTP_{status_code}"
                ) from exc
            raise AIProviderError(f"OPENAI_HTTP_{status_code}") from exc
        except httpx.RequestError as exc:
            raise TransientAIProviderError("OPENAI_TRANSPORT_ERROR") from exc
        except ValueError as exc:
            raise AIProviderError("OPENAI_INVALID_RESPONSE") from exc

        raw_text = self._output_text(payload).strip()
        try:
            output = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise AIProviderError("MODEL_OUTPUT_NOT_JSON") from exc

        usage = payload.get("usage") or {}
        return ProviderResult(
            output=output,
            model=str(payload.get("model") or self.model),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            latency_ms=round((time.perf_counter() - started) * 1000),
        )


def get_ai_provider(settings: Settings) -> BaseAIProvider:
    if settings.ai_provider == "openai":
        return OpenAIResponsesProvider(settings)
    if settings.ai_provider == "deterministic":
        return DeterministicAIProvider()
    raise AIProviderError(f"Unsupported AI_PROVIDER: {settings.ai_provider}")
