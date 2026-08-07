from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.prompts import TASK_PROMPTS
from app.ai.provider import AIProviderError, get_ai_provider
from app.ai.schemas import OUTPUT_MODELS
from app.career_models import (
    AIArtifact,
    AIJobRun,
    ApplicationQuestionDraft,
    CareerMatch,
    CoverLetter,
    ResumeTailoring,
    ResumeTailoringRevision,
)
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal


TERMINAL_STATUSES = {"COMPLETED", "FAILED"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stable_safety_identifier(user_id: object) -> str:
    return hashlib.sha256(f"applyai:{user_id}".encode("utf-8")).hexdigest()[:32]


def _collect_evidence_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("evidence_refs") and isinstance(item, list):
                refs.extend(str(ref) for ref in item)
            else:
                refs.extend(_collect_evidence_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.extend(_collect_evidence_refs(item))
    return refs


def _validate_evidence(output: dict[str, Any], input_json: dict[str, Any]) -> list[str]:
    allowed = set((input_json.get("evidence_catalog") or {}).keys())
    refs = _collect_evidence_refs(output)
    if not refs:
        raise AIProviderError("MODEL_OUTPUT_MISSING_EVIDENCE")
    unknown = sorted(set(refs) - allowed)
    if unknown:
        raise AIProviderError("MODEL_OUTPUT_UNKNOWN_EVIDENCE:" + ",".join(unknown[:5]))
    return sorted(set(refs))


def _estimated_cost(settings: Settings, *, input_tokens: int | None, output_tokens: int | None) -> Decimal | None:
    if input_tokens is None and output_tokens is None:
        return None
    input_cost = Decimal(str(settings.ai_input_cost_per_million_usd)) * Decimal(input_tokens or 0) / Decimal(1_000_000)
    output_cost = Decimal(str(settings.ai_output_cost_per_million_usd)) * Decimal(output_tokens or 0) / Decimal(1_000_000)
    return (input_cost + output_cost).quantize(Decimal("0.000001"))


def _artifact(
    session: Session,
    *,
    run: AIJobRun,
    artifact_type: str,
    content: dict[str, Any],
    evidence_refs: list[str],
) -> AIArtifact:
    existing = session.scalar(
        select(AIArtifact).where(
            AIArtifact.run_id == run.id,
            AIArtifact.artifact_type == artifact_type,
        )
    )
    if existing is not None:
        existing.content_json = content
        existing.evidence_json = {"refs": evidence_refs}
        existing.status = "NEEDS_REVIEW"
        return existing
    row = AIArtifact(
        run_id=run.id,
        user_id=run.user_id,
        job_id=run.job_id,
        application_id=run.application_id,
        artifact_type=artifact_type,
        status="NEEDS_REVIEW",
        content_json=content,
        evidence_json={"refs": evidence_refs},
    )
    session.add(row)
    session.flush()
    return row


def _score_band(score: int) -> tuple[str, str]:
    if score >= 80:
        return "STRONG", "PRIORITIZE"
    if score >= 65:
        return "GOOD", "CONSIDER"
    if score >= 50:
        return "PARTIAL", "STRETCH"
    return "WEAK", "SKIP"


def _materialize_deep_match(
    session: Session,
    *,
    run: AIJobRun,
    output: dict[str, Any],
    evidence_refs: list[str],
) -> None:
    _artifact(
        session,
        run=run,
        artifact_type="DEEP_MATCH",
        content=output,
        evidence_refs=evidence_refs,
    )
    deterministic = run.input_json.get("deterministic_match") or {}
    deterministic_score = int(deterministic.get("match_score") or 0)
    ai_score = int(output["ai_score"])
    final_score = round(deterministic_score * 0.65 + ai_score * 0.35)
    fit_band, decision = _score_band(final_score)
    engine_version = "applyai-hybrid-fit-v2"
    match = session.scalar(
        select(CareerMatch).where(
            CareerMatch.user_id == run.user_id,
            CareerMatch.job_id == run.job_id,
            CareerMatch.engine_version == engine_version,
        )
    )
    if match is None:
        match = CareerMatch(
            user_id=run.user_id,
            job_id=run.job_id,
            engine_version=engine_version,
            deterministic_score=deterministic_score,
            final_score=final_score,
            fit_band=fit_band,
            decision=decision,
            confidence=str(deterministic.get("confidence") or "MEDIUM"),
            factors_json=deterministic.get("breakdown") or [],
            evidence_json={"refs": evidence_refs},
        )
        session.add(match)
    match.model_run_id = run.id
    match.ai_score = ai_score
    match.final_score = final_score
    match.fit_band = fit_band
    match.decision = decision
    match.confidence = str(deterministic.get("confidence") or "MEDIUM")
    match.factors_json = deterministic.get("breakdown") or []
    match.evidence_json = {"refs": evidence_refs, "ai_summary": output.get("summary")}


def _materialize_resume_tailoring(
    session: Session,
    *,
    run: AIJobRun,
    output: dict[str, Any],
    evidence_refs: list[str],
) -> None:
    artifact = _artifact(
        session,
        run=run,
        artifact_type="RESUME_TAILORING",
        content=output,
        evidence_refs=evidence_refs,
    )
    tailoring = session.scalar(select(ResumeTailoring).where(ResumeTailoring.artifact_id == artifact.id))
    if tailoring is None:
        tailoring = ResumeTailoring(
            artifact_id=artifact.id,
            user_id=run.user_id,
            job_id=run.job_id,
            application_id=run.application_id,
            safety_policy="EVIDENCE_LOCKED",
            status="NEEDS_REVIEW",
        )
        session.add(tailoring)
        session.flush()
    else:
        session.execute(delete(ResumeTailoringRevision).where(ResumeTailoringRevision.tailoring_id == tailoring.id))
    for position, edit in enumerate(output["edits"]):
        session.add(
            ResumeTailoringRevision(
                tailoring_id=tailoring.id,
                position=position,
                original_text=edit["source_text"],
                suggested_text=edit["suggested_text"],
                reason=edit["reason"],
                evidence_refs=edit["evidence_refs"],
                risk_flags=edit.get("risk_flags") or [],
                confidence=Decimal(str(edit["confidence"])),
                candidate_decision="PENDING",
            )
        )


def _materialize_application_copilot(
    session: Session,
    *,
    run: AIJobRun,
    output: dict[str, Any],
    evidence_refs: list[str],
) -> None:
    artifact = _artifact(
        session,
        run=run,
        artifact_type="APPLICATION_COPILOT",
        content=output,
        evidence_refs=evidence_refs,
    )
    cover = session.scalar(select(CoverLetter).where(CoverLetter.artifact_id == artifact.id))
    if cover is None:
        cover = CoverLetter(
            artifact_id=artifact.id,
            user_id=run.user_id,
            job_id=run.job_id,
            application_id=run.application_id,
            body=output["cover_letter"],
            evidence_refs=output["cover_letter_evidence_refs"],
        )
        session.add(cover)
    else:
        cover.body = output["cover_letter"]
        cover.evidence_refs = output["cover_letter_evidence_refs"]
    session.execute(delete(ApplicationQuestionDraft).where(ApplicationQuestionDraft.artifact_id == artifact.id))
    for position, item in enumerate(output.get("questions") or []):
        session.add(
            ApplicationQuestionDraft(
                artifact_id=artifact.id,
                application_id=run.application_id,
                position=position,
                question=item["question"],
                draft=item["answer"],
                evidence_refs=item["evidence_refs"],
            )
        )


def _materialize_interview_prep(
    session: Session,
    *,
    run: AIJobRun,
    output: dict[str, Any],
    evidence_refs: list[str],
) -> None:
    _artifact(
        session,
        run=run,
        artifact_type="INTERVIEW_PREP",
        content=output,
        evidence_refs=evidence_refs,
    )


MATERIALIZERS = {
    "AI_DEEP_MATCH": _materialize_deep_match,
    "AI_RESUME_TAILOR": _materialize_resume_tailoring,
    "AI_APPLICATION_COPILOT": _materialize_application_copilot,
    "AI_INTERVIEW_PREP": _materialize_interview_prep,
}


def execute_ai_run(run_id: object, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    with SessionLocal() as session:
        run = session.get(AIJobRun, run_id)
        if run is None:
            return True
        if run.status == "COMPLETED":
            return True
        if run.task_type not in OUTPUT_MODELS or run.task_type not in TASK_PROMPTS:
            run.status = "FAILED"
            run.error_code = "UNSUPPORTED_AI_TASK"
            run.completed_at = utcnow()
            session.commit()
            return True
        run.status = "PROCESSING"
        run.attempt_count += 1
        run.started_at = utcnow()
        run.error_code = None
        run.error_summary = None
        session.commit()

    try:
        provider = get_ai_provider(settings)
        with SessionLocal() as session:
            run = session.get(AIJobRun, run_id)
            if run is None:
                return True
            provider_result = provider.generate_json(
                system_prompt=TASK_PROMPTS[run.task_type],
                user_payload=run.input_json,
                task_type=run.task_type,
                safety_identifier=_stable_safety_identifier(run.user_id),
            )
            validated = OUTPUT_MODELS[run.task_type].model_validate(provider_result.output)
            output = validated.model_dump(mode="json")
            evidence_refs = _validate_evidence(output, run.input_json)
            run.provider = settings.ai_provider
            run.model = provider_result.model
            run.output_json = output
            run.evidence_refs = evidence_refs
            run.input_tokens = provider_result.input_tokens
            run.output_tokens = provider_result.output_tokens
            run.latency_ms = provider_result.latency_ms
            run.estimated_cost_usd = _estimated_cost(
                settings,
                input_tokens=provider_result.input_tokens,
                output_tokens=provider_result.output_tokens,
            )
            MATERIALIZERS[run.task_type](
                session,
                run=run,
                output=output,
                evidence_refs=evidence_refs,
            )
            run.status = "COMPLETED"
            run.completed_at = utcnow()
            session.commit()
            return True
    except (AIProviderError, ValueError) as exc:
        with SessionLocal() as session:
            run = session.get(AIJobRun, run_id)
            if run is None:
                return True
            run.status = "FAILED"
            run.error_code = str(exc).split(":", 1)[0][:80] or type(exc).__name__
            run.error_summary = type(exc).__name__
            run.completed_at = utcnow()
            session.commit()
        return True
    except Exception:
        with SessionLocal() as session:
            run = session.get(AIJobRun, run_id)
            if run is not None:
                run.status = "QUEUED"
                run.error_code = "TRANSIENT_AI_FAILURE"
                run.error_summary = "Transient AI processing failure"
                session.commit()
        return False
