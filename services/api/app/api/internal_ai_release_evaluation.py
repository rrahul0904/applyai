from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.release_evaluation import (
    FAIL_THRESHOLD,
    MIN_TRIGGER_PRECISION,
    MIN_TRIGGER_RECALL,
    PASS_THRESHOLD,
    evaluate_release,
)
from app.ai_evaluation_models import AIEvaluationReceipt
from app.core.database import get_session
from app.core.operator_auth import require_operator_or_internal

router = APIRouter(
    prefix="/internal/ai-release-evaluation",
    tags=["internal-ai-release-evaluation"],
    dependencies=[Depends(require_operator_or_internal)],
)


class ArmRun(BaseModel):
    case: str = Field(min_length=1, max_length=160)
    rep: int = Field(default=0, ge=0)
    passed: bool | None = None
    checks: list[tuple[str, bool]] = Field(default_factory=list)
    turns: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)


class TriggerCounts(BaseModel):
    tp: int = Field(default=0, ge=0)
    fn: int = Field(default=0, ge=0)
    fp: int = Field(default=0, ge=0)
    tn: int = Field(default=0, ge=0)


class ReleaseEvaluationRequest(BaseModel):
    subject_type: Literal["AGENT", "SKILL", "WORKFLOW", "PROMPT"]
    subject_name: str = Field(min_length=1, max_length=160)
    subject_version: str = Field(min_length=1, max_length=80)
    candidate_artifact: Any
    dataset_version: str = Field(min_length=1, max_length=120)
    baseline_runs: list[ArmRun] = Field(min_length=1)
    candidate_runs: list[ArmRun] = Field(min_length=1)
    triggers: TriggerCounts | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    pass_threshold: float = PASS_THRESHOLD
    fail_threshold: float = FAIL_THRESHOLD
    minimum_trigger_precision: float = Field(default=MIN_TRIGGER_PRECISION, ge=0, le=1)
    minimum_trigger_recall: float = Field(default=MIN_TRIGGER_RECALL, ge=0, le=1)
    evaluated_at: str | None = None
    notes: str | None = None


def _number(value: Any) -> float | None:
    return None if value is None else float(value)


def _serialize(row: AIEvaluationReceipt) -> dict[str, Any]:
    comparison = row.receipt_json.get("comparison", {})
    return {
        "id": str(row.id),
        "subject_type": row.subject_type,
        "subject_name": row.subject_name,
        "subject_version": row.subject_version,
        "content_digest": row.content_digest,
        "dataset_version": row.dataset_version,
        "verdict": row.verdict,
        "release_gate": row.release_gate,
        "execution_status": row.execution_status,
        "expected_rows": row.expected_rows,
        "scored_rows": row.scored_rows,
        "wins": row.wins,
        "losses": row.losses,
        "ties": row.ties,
        "net_lift": _number(row.net_lift),
        "sign_p": _number(row.sign_p),
        "trigger_precision": _number(row.trigger_precision),
        "trigger_recall": _number(row.trigger_recall),
        "baseline_cost_usd": _number(row.baseline_cost_usd),
        "candidate_cost_usd": _number(row.candidate_cost_usd),
        "cost_delta_usd": _number(row.cost_delta_usd),
        "baseline_duration_ms": _number(row.baseline_duration_ms),
        "candidate_duration_ms": _number(row.candidate_duration_ms),
        "duration_delta_ms": _number(row.duration_delta_ms),
        "receipt_digest": row.receipt_digest,
        "gate_reasons": row.receipt_json.get("gate_reasons", []),
        "comparison": comparison,
        "provenance": row.provenance_json,
        "receipt": row.receipt_json,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/evaluate", status_code=201)
def evaluate_candidate(
    payload: ReleaseEvaluationRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        receipt = evaluate_release(
            subject_type=payload.subject_type,
            subject_name=payload.subject_name,
            subject_version=payload.subject_version,
            candidate_artifact=payload.candidate_artifact,
            dataset_version=payload.dataset_version,
            baseline_runs=[run.model_dump() for run in payload.baseline_runs],
            candidate_runs=[run.model_dump() for run in payload.candidate_runs],
            trigger_counts=payload.triggers.model_dump() if payload.triggers else None,
            provenance=payload.provenance,
            pass_threshold=payload.pass_threshold,
            fail_threshold=payload.fail_threshold,
            minimum_trigger_precision=payload.minimum_trigger_precision,
            minimum_trigger_recall=payload.minimum_trigger_recall,
            evaluated_at=payload.evaluated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = session.scalar(
        select(AIEvaluationReceipt).where(
            AIEvaluationReceipt.receipt_digest == receipt["receipt_digest"]
        )
    )
    if existing is not None:
        return {"created": False, **_serialize(existing)}

    comparison = receipt["comparison"]
    triggers = receipt.get("triggers") or {}
    efficiency = receipt["efficiency"]
    row = AIEvaluationReceipt(
        subject_type=payload.subject_type,
        subject_name=payload.subject_name,
        subject_version=payload.subject_version,
        content_digest=receipt["subject"]["content_digest"],
        dataset_version=payload.dataset_version,
        verdict=receipt["verdict"],
        release_gate=receipt["release_gate"],
        execution_status=receipt["execution_status"],
        expected_rows=receipt["expected_rows"],
        scored_rows=receipt["scored_rows"],
        wins=comparison["win"],
        losses=comparison["loss"],
        ties=comparison["tie"],
        net_lift=Decimal(str(comparison["net_lift"])),
        sign_p=Decimal(str(comparison["sign_p"])),
        trigger_precision=(
            Decimal(str(triggers["precision"])) if triggers.get("precision") is not None else None
        ),
        trigger_recall=(
            Decimal(str(triggers["recall"])) if triggers.get("recall") is not None else None
        ),
        baseline_cost_usd=(
            Decimal(str(efficiency["baseline"]["cost_usd"]))
            if efficiency["baseline"]["cost_usd"] is not None else None
        ),
        candidate_cost_usd=(
            Decimal(str(efficiency["candidate"]["cost_usd"]))
            if efficiency["candidate"]["cost_usd"] is not None else None
        ),
        cost_delta_usd=(
            Decimal(str(efficiency["delta"]["cost_usd"]))
            if efficiency["delta"]["cost_usd"] is not None else None
        ),
        baseline_duration_ms=(
            Decimal(str(efficiency["baseline"]["duration_ms"]))
            if efficiency["baseline"]["duration_ms"] is not None else None
        ),
        candidate_duration_ms=(
            Decimal(str(efficiency["candidate"]["duration_ms"]))
            if efficiency["candidate"]["duration_ms"] is not None else None
        ),
        duration_delta_ms=(
            Decimal(str(efficiency["delta"]["duration_ms"]))
            if efficiency["delta"]["duration_ms"] is not None else None
        ),
        receipt_digest=receipt["receipt_digest"],
        receipt_json=receipt,
        provenance_json=receipt["provenance"],
        notes=payload.notes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"created": True, **_serialize(row)}


@router.get("/receipts")
def list_receipts(
    subject_name: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(AIEvaluationReceipt)
    if subject_name:
        query = query.where(AIEvaluationReceipt.subject_name == subject_name)
    rows = list(
        session.scalars(query.order_by(AIEvaluationReceipt.created_at.desc()).limit(limit))
    )
    return [_serialize(row) for row in rows]


@router.get("/receipts/{receipt_id}")
def get_receipt(
    receipt_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.get(AIEvaluationReceipt, receipt_id)
    if row is None:
        raise HTTPException(status_code=404, detail="AI evaluation receipt not found")
    return _serialize(row)
