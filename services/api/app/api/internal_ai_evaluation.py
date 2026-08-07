from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.ai.evaluation import compare_variants, evaluate_suite
from app.core.internal_auth import require_internal_api

router = APIRouter(prefix="/internal/ai-evaluation", tags=["internal-ai-evaluation"], dependencies=[Depends(require_internal_api)])
GOLDEN_PATH = Path(__file__).parents[2] / "evals" / "career_intelligence_golden.json"


def load_golden() -> dict[str, Any]:
    with GOLDEN_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class EvaluationDataset(BaseModel):
    version: str = "candidate"
    ranking_cases: list[dict[str, Any]] = []
    evidence_cases: list[dict[str, Any]] = []


@router.get("/golden")
def evaluate_golden() -> dict[str, Any]:
    dataset = load_golden()
    return {"dataset_version": dataset.get("version"), **evaluate_suite(dataset)}


@router.post("/compare")
def compare_to_golden(payload: EvaluationDataset) -> dict[str, Any]:
    return compare_variants(load_golden(), payload.model_dump())
