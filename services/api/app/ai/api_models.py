from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AIJobRunResponse(BaseModel):
    id: uuid.UUID
    task_type: str
    job_id: uuid.UUID | None
    application_id: uuid.UUID | None
    status: str
    provider: str
    model: str
    prompt_version: str
    schema_version: str
    input_hash: str
    output: dict[str, Any] | None
    evidence_refs: list[str]
    attempt_count: int
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    error_code: str | None
    created_at: datetime
    completed_at: datetime | None


class AIArtifactResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    job_id: uuid.UUID | None
    application_id: uuid.UUID | None
    artifact_type: str
    status: str
    version: int
    content: dict[str, Any]
    evidence: dict[str, Any]
    candidate_verified: bool
    created_at: datetime


class AIArtifactListResponse(BaseModel):
    items: list[AIArtifactResponse]


class ResumeRevisionReviewResponse(BaseModel):
    tailoring_id: uuid.UUID
    position: int
    decision: str
    text: str | None
    status: str


class CoverLetterReviewResponse(BaseModel):
    id: uuid.UUID
    body: str
    candidate_verified: bool


class QuestionDraftReviewResponse(BaseModel):
    id: uuid.UUID
    question: str
    answer: str | None
    candidate_verified: bool


class ArtifactFeedbackResponse(BaseModel):
    id: uuid.UUID
    artifact_id: uuid.UUID
    action: str


class CareerMatchV2Response(BaseModel):
    job_id: uuid.UUID
    deterministic_score: int = Field(ge=0, le=100)
    ai_score: int | None = Field(default=None, ge=0, le=100)
    final_score: int = Field(ge=0, le=100)
    fit_band: str
    decision: str
    confidence: str
    engine_version: str
    factors: list[dict[str, Any]]
    evidence: dict[str, Any]
    updated_at: datetime


class CareerMatchV2ListResponse(BaseModel):
    items: list[CareerMatchV2Response]
