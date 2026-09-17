from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.operator_auth import require_operator_or_internal
from app.reverse_engineering import (
    CLASSIFIER_VERSION,
    ApplyAIFit,
    FitScope,
    TopicStatus,
    classify_topic,
    fit_metadata,
    taxonomy_payload,
)
from app.reverse_engineering_models import ReverseEngineeringTopic

router = APIRouter(
    prefix="/internal/reverse-engineering",
    tags=["internal-reverse-engineering"],
    dependencies=[Depends(require_operator_or_internal)],
)


class ClassifyRequest(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    summary: str = ""
    capabilities: list[str] = Field(default_factory=list)


class TopicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    source_url: str | None = None
    source_type: str = Field(default="PUBLIC_RESEARCH", max_length=48)
    summary: str = ""
    applyai_fit: ApplyAIFit | None = None
    fit_scope: FitScope | None = None
    destination: str | None = Field(default=None, max_length=80)
    rationale: str | None = None
    candidate_journey_stages: list[str] | None = None
    qualifying_capabilities: list[str] = Field(default_factory=list)
    excluded_capabilities: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)
    status: TopicStatus = TopicStatus.RESEARCHED
    implementation_target: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class TopicPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    source_url: str | None = None
    source_type: str | None = Field(default=None, max_length=48)
    summary: str | None = None
    applyai_fit: ApplyAIFit | None = None
    fit_scope: FitScope | None = None
    destination: str | None = Field(default=None, max_length=80)
    rationale: str | None = None
    candidate_journey_stages: list[str] | None = None
    qualifying_capabilities: list[str] | None = None
    excluded_capabilities: list[str] | None = None
    evidence_urls: list[str] | None = None
    status: TopicStatus | None = None
    implementation_target: str | None = None
    metadata_json: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_required_columns(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        nullable_fields = {"source_url", "implementation_target"}
        rejected = sorted(
            field
            for field, field_value in value.items()
            if field_value is None and field not in nullable_fields
        )
        if rejected:
            raise ValueError(
                "null is not allowed for required topic fields: " + ", ".join(rejected)
            )
        return value


def _serialize(topic: ReverseEngineeringTopic) -> dict[str, Any]:
    return {
        "id": str(topic.id),
        "title": topic.title,
        "source_url": topic.source_url,
        "source_type": topic.source_type,
        "summary": topic.summary,
        "applyai_fit": topic.applyai_fit,
        "fit_scope": topic.fit_scope,
        "destination": topic.destination,
        "rationale": topic.rationale,
        "classifier_version": topic.classifier_version,
        "classification_source": topic.classification_source,
        "candidate_journey_stages": topic.candidate_journey_stages,
        "qualifying_capabilities": topic.qualifying_capabilities,
        "excluded_capabilities": topic.excluded_capabilities,
        "evidence_urls": topic.evidence_urls,
        "status": topic.status,
        "implementation_target": topic.implementation_target,
        "metadata_json": topic.metadata_json,
        "created_at": topic.created_at.isoformat() if topic.created_at else None,
        "updated_at": topic.updated_at.isoformat() if topic.updated_at else None,
    }


def _unique_source_or_409(
    session: Session,
    source_url: str | None,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    if not source_url:
        return
    query = select(ReverseEngineeringTopic.id).where(ReverseEngineeringTopic.source_url == source_url)
    if exclude_id is not None:
        query = query.where(ReverseEngineeringTopic.id != exclude_id)
    if session.scalar(query.limit(1)) is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "DUPLICATE_RESEARCH_SOURCE", "message": "This source is already registered"},
        )


def _manual_classification(payload: TopicCreate) -> dict[str, Any]:
    fit = payload.applyai_fit
    if fit is None:
        return classify_topic(
            title=payload.title,
            summary=payload.summary,
            capabilities=payload.qualifying_capabilities,
        )
    metadata = fit_metadata(fit)
    return {
        "classifier_version": CLASSIFIER_VERSION,
        "applyai_fit": fit.value,
        "fit_scope": (payload.fit_scope or FitScope(metadata["default_scope"])).value,
        "destination": payload.destination or metadata["destination"],
        "rationale": payload.rationale or f"Operator classified this topic as {metadata['label']}.",
        "candidate_journey_stages": payload.candidate_journey_stages or [],
    }


@router.get("/taxonomy")
def taxonomy() -> dict[str, Any]:
    return taxonomy_payload()


@router.post("/classify")
def classify(payload: ClassifyRequest) -> dict[str, Any]:
    return classify_topic(
        title=payload.title,
        summary=payload.summary,
        capabilities=payload.capabilities,
    )


@router.get("/summary")
def registry_summary(session: Session = Depends(get_session)) -> dict[str, Any]:
    total = int(session.scalar(select(func.count()).select_from(ReverseEngineeringTopic)) or 0)
    rows = list(
        session.execute(
            select(
                ReverseEngineeringTopic.applyai_fit,
                ReverseEngineeringTopic.status,
                func.count(),
            ).group_by(ReverseEngineeringTopic.applyai_fit, ReverseEngineeringTopic.status)
        )
    )
    by_fit: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for fit, status, count in rows:
        by_fit[fit] = by_fit.get(fit, 0) + int(count)
        by_status[status] = by_status.get(status, 0) + int(count)
    return {
        "total": total,
        "by_fit": by_fit,
        "by_status": by_status,
        "classifier_version": CLASSIFIER_VERSION,
    }


@router.get("/topics")
def list_topics(
    q: str | None = Query(default=None, max_length=240),
    fit: ApplyAIFit | None = None,
    status: TopicStatus | None = None,
    limit: int = Query(default=100, ge=1, le=250),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(ReverseEngineeringTopic)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                ReverseEngineeringTopic.title.ilike(pattern),
                ReverseEngineeringTopic.summary.ilike(pattern),
                ReverseEngineeringTopic.rationale.ilike(pattern),
            )
        )
    if fit is not None:
        query = query.where(ReverseEngineeringTopic.applyai_fit == fit.value)
    if status is not None:
        query = query.where(ReverseEngineeringTopic.status == status.value)
    topics = list(
        session.scalars(
            query.order_by(ReverseEngineeringTopic.updated_at.desc(), ReverseEngineeringTopic.created_at.desc())
            .limit(limit)
        )
    )
    return [_serialize(topic) for topic in topics]


@router.post("/topics", status_code=201)
def create_topic(payload: TopicCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    _unique_source_or_409(session, payload.source_url)
    classification = _manual_classification(payload)
    manual = payload.applyai_fit is not None
    topic = ReverseEngineeringTopic(
        title=payload.title.strip(),
        source_url=payload.source_url,
        source_type=payload.source_type,
        summary=payload.summary,
        applyai_fit=classification["applyai_fit"],
        fit_scope=classification["fit_scope"],
        destination=classification["destination"],
        rationale=payload.rationale or classification["rationale"],
        classifier_version=classification["classifier_version"],
        classification_source="MANUAL" if manual else "AUTO",
        candidate_journey_stages=(
            payload.candidate_journey_stages
            if payload.candidate_journey_stages is not None
            else classification["candidate_journey_stages"]
        ),
        qualifying_capabilities=payload.qualifying_capabilities,
        excluded_capabilities=payload.excluded_capabilities,
        evidence_urls=payload.evidence_urls,
        status=payload.status.value,
        implementation_target=payload.implementation_target,
        metadata_json=payload.metadata_json,
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return _serialize(topic)


@router.patch("/topics/{topic_id}")
def update_topic(
    topic_id: uuid.UUID,
    payload: TopicPatch,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    topic = session.get(ReverseEngineeringTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Reverse-engineering topic not found")

    changes = payload.model_dump(exclude_unset=True)
    if "source_url" in changes:
        _unique_source_or_409(session, changes["source_url"], exclude_id=topic.id)

    manual_fit = changes.pop("applyai_fit", None)
    manual_scope = changes.pop("fit_scope", None)
    manual_destination = changes.pop("destination", None)
    if manual_fit is not None:
        metadata = fit_metadata(manual_fit)
        topic.applyai_fit = manual_fit.value
        topic.fit_scope = (
            manual_scope.value if manual_scope is not None else metadata["default_scope"]
        )
        topic.destination = manual_destination or metadata["destination"]
        topic.classification_source = "MANUAL"
        topic.classifier_version = CLASSIFIER_VERSION
        if "rationale" not in changes:
            topic.rationale = f"Operator classified this topic as {metadata['label']}."
    else:
        if manual_scope is not None:
            topic.fit_scope = manual_scope.value
            topic.classification_source = "MANUAL"
        if manual_destination is not None:
            topic.destination = manual_destination
            topic.classification_source = "MANUAL"

    for field, value in changes.items():
        if field == "status":
            value = value.value
        setattr(topic, field, value)

    session.commit()
    session.refresh(topic)
    return _serialize(topic)


@router.post("/topics/{topic_id}/reclassify")
def reclassify_topic(
    topic_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    topic = session.get(ReverseEngineeringTopic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Reverse-engineering topic not found")
    classification = classify_topic(
        title=topic.title,
        summary=topic.summary,
        capabilities=topic.qualifying_capabilities,
    )
    topic.applyai_fit = classification["applyai_fit"]
    topic.fit_scope = classification["fit_scope"]
    topic.destination = classification["destination"]
    topic.rationale = classification["rationale"]
    topic.candidate_journey_stages = classification["candidate_journey_stages"]
    topic.classifier_version = classification["classifier_version"]
    topic.classification_source = "AUTO"
    session.commit()
    session.refresh(topic)
    return _serialize(topic)
