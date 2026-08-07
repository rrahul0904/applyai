from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.career_memory_models import CandidateCareerFact
from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import User


router = APIRouter(prefix="/career-memory", tags=["career memory"])

CareerFactCategory = Literal[
    "ACHIEVEMENT",
    "PROJECT",
    "METRIC",
    "RESPONSIBILITY",
    "CERTIFICATION",
    "LEADERSHIP_STORY",
    "INTERVIEW_FEEDBACK",
    "CAREER_GOAL",
]


class CareerFactWrite(BaseModel):
    category: CareerFactCategory
    title: str | None = Field(default=None, max_length=255)
    fact_text: str = Field(min_length=1, max_length=8000)
    tags: list[str] = Field(default_factory=list, max_length=24)
    occurred_at: date | None = None


class CareerFactUpdate(BaseModel):
    category: CareerFactCategory | None = None
    title: str | None = Field(default=None, max_length=255)
    fact_text: str | None = Field(default=None, min_length=1, max_length=8000)
    tags: list[str] | None = Field(default=None, max_length=24)
    occurred_at: date | None = None
    user_verified: bool | None = None


class CareerFactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    title: str | None
    fact_text: str
    source_kind: str
    source_ref: str | None
    provenance: str
    user_verified: bool
    tags: list[str]
    occurred_at: date | None
    created_at: datetime
    updated_at: datetime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _owned_fact(session: Session, user: User, fact_id: uuid.UUID) -> CandidateCareerFact:
    fact = session.scalar(
        select(CandidateCareerFact).where(
            CandidateCareerFact.id == fact_id,
            CandidateCareerFact.user_id == user.id,
            CandidateCareerFact.archived_at.is_(None),
        )
    )
    if fact is None:
        raise HTTPException(status_code=404, detail="Career memory fact not found")
    return fact


@router.get("", response_model=list[CareerFactResponse])
def list_career_facts(
    category: CareerFactCategory | None = Query(default=None),
    include_unverified: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=250),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = select(CandidateCareerFact).where(
        CandidateCareerFact.user_id == user.id,
        CandidateCareerFact.archived_at.is_(None),
    )
    if category:
        query = query.where(CandidateCareerFact.category == category)
    if not include_unverified:
        query = query.where(CandidateCareerFact.user_verified.is_(True))
    return list(
        session.scalars(
            query.order_by(
                CandidateCareerFact.occurred_at.desc().nullslast(),
                CandidateCareerFact.updated_at.desc(),
            ).limit(limit)
        )
    )


@router.post("", response_model=CareerFactResponse, status_code=status.HTTP_201_CREATED)
def create_career_fact(
    payload: CareerFactWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    fact = CandidateCareerFact(
        user_id=user.id,
        category=payload.category,
        title=payload.title,
        fact_text=payload.fact_text.strip(),
        source_kind="USER",
        provenance="USER_VERIFIED",
        user_verified=True,
        tags=sorted({tag.strip() for tag in payload.tags if tag.strip()}),
        occurred_at=payload.occurred_at,
    )
    session.add(fact)
    session.commit()
    session.refresh(fact)
    return fact


@router.patch("/{fact_id}", response_model=CareerFactResponse)
def update_career_fact(
    fact_id: uuid.UUID,
    payload: CareerFactUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    fact = _owned_fact(session, user, fact_id)
    changes = payload.model_dump(exclude_unset=True)
    if "category" in changes:
        fact.category = changes["category"]
    if "title" in changes:
        fact.title = changes["title"]
    if "fact_text" in changes:
        fact.fact_text = changes["fact_text"].strip()
    if "tags" in changes:
        fact.tags = sorted({tag.strip() for tag in changes["tags"] if tag.strip()})
    if "occurred_at" in changes:
        fact.occurred_at = changes["occurred_at"]
    if "user_verified" in changes:
        fact.user_verified = changes["user_verified"]
        fact.provenance = "USER_VERIFIED" if fact.user_verified else "USER_REVIEW_REQUIRED"
    session.commit()
    session.refresh(fact)
    return fact


@router.delete("/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_career_fact(
    fact_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    fact = _owned_fact(session, user, fact_id)
    fact.archived_at = utcnow()
    session.commit()


@router.get("/summary")
def career_memory_summary(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    rows = list(
        session.execute(
            select(
                CandidateCareerFact.category,
                func.count(CandidateCareerFact.id),
            )
            .where(
                CandidateCareerFact.user_id == user.id,
                CandidateCareerFact.archived_at.is_(None),
                CandidateCareerFact.user_verified.is_(True),
            )
            .group_by(CandidateCareerFact.category)
            .order_by(CandidateCareerFact.category)
        )
    )
    counts = {category: int(count) for category, count in rows}
    return {
        "verified_fact_count": sum(counts.values()),
        "by_category": counts,
    }
