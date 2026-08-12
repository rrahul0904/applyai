from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.application_agent_models import ApplicationExecution, ApplicationQuestionMemory
from app.career_models import AIArtifact, ApplicationQuestionDraft, CoverLetter
from app.core.auth import get_current_user
from app.core.database import get_session
from app.core.internal_auth import require_internal_api
from app.models import (
    Application,
    ApplicationEvent,
    CandidatePreference,
    CandidateProfile,
    Job,
    JobSource,
    JobSourceLink,
    User,
)


router = APIRouter(prefix="/application-agent", tags=["application agent"])
internal_router = APIRouter(
    prefix="/internal/application-agent",
    tags=["internal-application-agent"],
    dependencies=[Depends(require_internal_api)],
)

ApprovalMode = Literal["REVIEW_ALL", "SMART", "AUTONOMOUS"]
FieldType = Literal["TEXT", "TEXTAREA", "SELECT", "RADIO", "CHECKBOX", "FILE", "UNKNOWN"]

SENSITIVE_KEYS = {
    "salary_expectation",
    "work_authorization",
    "sponsorship",
    "relocation",
    "legal_attestation",
    "background",
    "demographics",
    "veteran_status",
    "disability_status",
}


class ObservedField(BaseModel):
    field_id: str = Field(min_length=1, max_length=240)
    label: str = Field(min_length=1, max_length=1200)
    field_type: FieldType = "TEXT"
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=100)


class PrepareApplicationWrite(BaseModel):
    approval_mode: ApprovalMode = "SMART"
    observed_fields: list[ObservedField] = Field(default_factory=list, max_length=150)


class FieldReviewWrite(BaseModel):
    value: Any
    candidate_verified: bool = True
    remember: bool = False


class MemoryWrite(BaseModel):
    canonical_key: str = Field(min_length=1, max_length=120)
    question: str | None = Field(default=None, max_length=1200)
    answer: str = Field(min_length=1, max_length=5000)
    answer_type: str = Field(default="TEXT", max_length=32)
    sensitive: bool = False
    candidate_verified: bool = True


class BrowserCompletionWrite(BaseModel):
    status: Literal["CONFIRMED", "SUBMITTED", "HUMAN_ACTION_REQUIRED", "FAILED"]
    field_results: list[dict[str, Any]] = Field(default_factory=list)
    validation: dict[str, Any] = Field(default_factory=dict)
    confirmation_url: str | None = None
    confirmation_text: str | None = Field(default=None, max_length=8000)
    human_action: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, max_length=80)
    error_detail: str | None = Field(default=None, max_length=4000)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def _canonical_key(label: str) -> str:
    value = _normalize(label)
    checks: list[tuple[str, tuple[str, ...]]] = [
        ("sponsorship", ("sponsor", "sponsorship", "visa sponsorship")),
        ("work_authorization", ("authorized to work", "work authorization", "legally authorized")),
        ("salary_expectation", ("salary", "compensation", "expected pay", "pay expectation")),
        ("relocation", ("relocate", "relocation")),
        ("first_name", ("first name", "given name")),
        ("last_name", ("last name", "family name", "surname")),
        ("email", ("email", "e mail")),
        ("phone", ("phone", "mobile", "telephone")),
        ("linkedin", ("linkedin",)),
        ("location", ("current location", "location", "city state")),
        ("years_experience", ("years of experience", "years experience", "experience years")),
        ("current_title", ("current title", "job title", "current position")),
        ("motivation_role", ("why are you interested", "why this role", "interest in this role")),
        ("veteran_status", ("veteran",)),
        ("disability_status", ("disability", "disabled")),
        ("demographics", ("gender", "race", "ethnicity", "demographic")),
        ("background", ("background check", "criminal", "conviction")),
        ("legal_attestation", ("certify", "attest", "signature", "terms and conditions")),
    ]
    for key, phrases in checks:
        if any(phrase in value for phrase in phrases):
            return key
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"question_{digest}"


def _provider_name(connector_key: str | None) -> str:
    key = (connector_key or "").upper().replace("-", "_")
    for provider in (
        "GREENHOUSE",
        "LEVER",
        "WORKDAY",
        "ASHBY",
        "SMARTRECRUITERS",
        "ICIMS",
        "SUCCESSFACTORS",
    ):
        if provider in key:
            return provider
    return "GENERIC"


def _owned_application(session: Session, user: User, application_id: uuid.UUID) -> Application:
    row = session.scalar(
        select(Application).where(
            Application.id == application_id,
            Application.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return row


def _owned_execution(session: Session, user: User, execution_id: uuid.UUID) -> ApplicationExecution:
    row = session.scalar(
        select(ApplicationExecution).where(
            ApplicationExecution.id == execution_id,
            ApplicationExecution.user_id == user.id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Application execution not found")
    return row


def _source_for_job(session: Session, job_id: uuid.UUID) -> JobSource | None:
    return session.scalar(
        select(JobSource)
        .join(JobSourceLink, JobSourceLink.job_source_id == JobSource.id)
        .where(JobSourceLink.job_id == job_id)
        .order_by(JobSourceLink.is_primary.desc(), JobSource.last_seen_at.desc())
        .limit(1)
    )


def _latest_artifact(session: Session, user_id: uuid.UUID, job_id: uuid.UUID, artifact_type: str) -> AIArtifact | None:
    return session.scalar(
        select(AIArtifact)
        .where(
            AIArtifact.user_id == user_id,
            AIArtifact.job_id == job_id,
            AIArtifact.artifact_type == artifact_type,
            AIArtifact.superseded_at.is_(None),
        )
        .order_by(AIArtifact.version.desc(), AIArtifact.created_at.desc())
        .limit(1)
    )


def _known_candidate_values(session: Session, user: User) -> dict[str, dict[str, Any]]:
    profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user.id))
    preference = session.scalar(select(CandidatePreference).where(CandidatePreference.user_id == user.id))
    values: dict[str, dict[str, Any]] = {
        "first_name": {"value": user.first_name, "confidence": 1.0, "source_kind": "IDENTITY", "source_ref": f"user:{user.id}"},
        "last_name": {"value": user.last_name, "confidence": 1.0, "source_kind": "IDENTITY", "source_ref": f"user:{user.id}"},
        "email": {"value": user.email, "confidence": 1.0, "source_kind": "IDENTITY", "source_ref": f"user:{user.id}"},
    }
    if profile is not None:
        values["current_title"] = {
            "value": profile.current_title,
            "confidence": 0.99,
            "source_kind": "CANDIDATE_PROFILE",
            "source_ref": f"profile:{profile.id}",
        }
        values["years_experience"] = {
            "value": str(profile.years_experience) if profile.years_experience is not None else None,
            "confidence": 0.99,
            "source_kind": "CANDIDATE_PROFILE",
            "source_ref": f"profile:{profile.id}",
        }
    if preference is not None:
        values["location"] = {
            "value": preference.location_text,
            "confidence": 0.98,
            "source_kind": "CANDIDATE_PREFERENCE",
            "source_ref": f"preference:{preference.id}",
        }
        values["relocation"] = {
            "value": "Yes" if preference.relocation_open else "No",
            "confidence": 0.95,
            "source_kind": "CANDIDATE_PREFERENCE",
            "source_ref": f"preference:{preference.id}",
        }
        if preference.minimum_compensation is not None:
            values["salary_expectation"] = {
                "value": str(preference.minimum_compensation),
                "confidence": 0.95,
                "source_kind": "CANDIDATE_PREFERENCE",
                "source_ref": f"preference:{preference.id}",
            }
    return values


def _draft_similarity(label: str, question: str) -> float:
    left = set(_normalize(label).split())
    right = set(_normalize(question).split())
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _best_draft(field: ObservedField, drafts: list[ApplicationQuestionDraft]) -> ApplicationQuestionDraft | None:
    matches = sorted(
        ((_draft_similarity(field.label, row.question), row) for row in drafts),
        key=lambda item: item[0],
        reverse=True,
    )
    return matches[0][1] if matches and matches[0][0] >= 0.45 else None


def _memory_map(session: Session, user_id: uuid.UUID) -> dict[str, ApplicationQuestionMemory]:
    rows = list(
        session.scalars(
            select(ApplicationQuestionMemory).where(ApplicationQuestionMemory.user_id == user_id)
        )
    )
    return {row.canonical_key: row for row in rows}


def _build_field(
    *,
    field: ObservedField,
    approval_mode: str,
    known: dict[str, dict[str, Any]],
    memories: dict[str, ApplicationQuestionMemory],
    drafts: list[ApplicationQuestionDraft],
) -> dict[str, Any]:
    canonical = _canonical_key(field.label)
    sensitive = canonical in SENSITIVE_KEYS
    value: Any = None
    confidence = 0.0
    source_kind = "UNKNOWN"
    source_ref: str | None = None
    evidence_refs: list[str] = []
    candidate_verified = False

    memory = memories.get(canonical)
    if memory is not None:
        value = memory.answer
        confidence = float(memory.confidence)
        source_kind = "ANSWER_MEMORY"
        source_ref = str(memory.id)
        candidate_verified = memory.candidate_verified
    elif canonical in known and known[canonical].get("value") not in (None, ""):
        item = known[canonical]
        value = item["value"]
        confidence = float(item["confidence"])
        source_kind = str(item["source_kind"])
        source_ref = str(item["source_ref"])
        evidence_refs = [source_ref]
    else:
        draft = _best_draft(field, drafts)
        if draft is not None:
            value = draft.candidate_text if draft.candidate_verified and draft.candidate_text else draft.draft
            confidence = 1.0 if draft.candidate_verified else 0.82
            source_kind = "APPLICATION_COPILOT"
            source_ref = str(draft.id)
            evidence_refs = list(draft.evidence_refs or [])
            candidate_verified = draft.candidate_verified

    missing = field.required and (value is None or str(value).strip() == "")
    requires_review = False
    if not missing:
        if approval_mode == "REVIEW_ALL":
            requires_review = True
        elif sensitive and not candidate_verified:
            requires_review = True
        elif confidence < 0.70:
            requires_review = True
        elif confidence < 0.95 and not candidate_verified:
            requires_review = True

    if missing:
        field_status = "NEEDS_INPUT"
    elif requires_review:
        field_status = "REVIEW_REQUIRED"
    else:
        field_status = "READY"

    return {
        "field_id": field.field_id,
        "label": field.label,
        "canonical_key": canonical,
        "field_type": field.field_type,
        "required": field.required,
        "options": field.options,
        "value": value,
        "confidence": round(confidence, 4),
        "source_kind": source_kind,
        "source_ref": source_ref,
        "evidence_refs": evidence_refs,
        "sensitive": sensitive,
        "candidate_verified": candidate_verified,
        "requires_review": requires_review,
        "status": field_status,
    }


def _recompute(execution: ApplicationExecution) -> None:
    fields = list(execution.fields or [])
    execution.missing_fields = [
        {"field_id": row["field_id"], "label": row["label"], "canonical_key": row["canonical_key"]}
        for row in fields
        if row.get("required") and (row.get("value") is None or str(row.get("value")).strip() == "")
    ]
    execution.review_items = [
        {
            "type": "FIELD",
            "field_id": row["field_id"],
            "label": row["label"],
            "canonical_key": row["canonical_key"],
            "sensitive": bool(row.get("sensitive")),
            "confidence": float(row.get("confidence") or 0),
        }
        for row in fields
        if row.get("requires_review") and not row.get("candidate_verified")
    ]
    if execution.missing_fields:
        execution.state = "NEEDS_INPUT"
    elif execution.review_items:
        execution.state = "REVIEW_REQUIRED"
    elif execution.approved_at is not None:
        execution.state = "READY_FOR_EXECUTION"
    else:
        execution.state = "READY_FOR_APPROVAL"


def _execution_payload(row: ApplicationExecution) -> dict[str, Any]:
    return {
        "id": row.id,
        "application_id": row.application_id,
        "job_id": row.job_id,
        "attempt_number": row.attempt_number,
        "approval_mode": row.approval_mode,
        "ats_provider": row.ats_provider,
        "target_url": row.target_url,
        "state": row.state,
        "fields": row.fields,
        "review_items": row.review_items,
        "missing_fields": row.missing_fields,
        "documents": row.documents,
        "validation": row.validation,
        "browser_handoff": row.browser_handoff,
        "confirmation_url": row.confirmation_url,
        "confirmation_text": row.confirmation_text,
        "approved_at": row.approved_at,
        "started_at": row.started_at,
        "submitted_at": row.submitted_at,
        "confirmed_at": row.confirmed_at,
        "error_code": row.error_code,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


@router.get("/memory")
def list_answer_memory(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = list(
        session.scalars(
            select(ApplicationQuestionMemory)
            .where(ApplicationQuestionMemory.user_id == user.id)
            .order_by(ApplicationQuestionMemory.updated_at.desc())
        )
    )
    return [
        {
            "id": row.id,
            "canonical_key": row.canonical_key,
            "question_variants": row.question_variants,
            "answer": row.answer,
            "answer_type": row.answer_type,
            "confidence": float(row.confidence),
            "sensitive": row.sensitive,
            "candidate_verified": row.candidate_verified,
            "last_used_at": row.last_used_at,
        }
        for row in rows
    ]


@router.put("/memory/{canonical_key}")
def save_answer_memory(
    canonical_key: str,
    body: MemoryWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if canonical_key != body.canonical_key:
        raise HTTPException(status_code=422, detail="Canonical key mismatch")
    row = session.scalar(
        select(ApplicationQuestionMemory).where(
            ApplicationQuestionMemory.user_id == user.id,
            ApplicationQuestionMemory.canonical_key == canonical_key,
        )
    )
    variants = [body.question.strip()] if body.question and body.question.strip() else []
    if row is None:
        row = ApplicationQuestionMemory(
            user_id=user.id,
            canonical_key=canonical_key,
            normalized_question=_normalize(body.question or "") or None,
            question_variants=variants,
            answer=body.answer,
            answer_type=body.answer_type,
            confidence=Decimal("1.0000") if body.candidate_verified else Decimal("0.8500"),
            sensitive=body.sensitive,
            candidate_verified=body.candidate_verified,
            source_kind="CANDIDATE",
        )
        session.add(row)
    else:
        row.answer = body.answer
        row.answer_type = body.answer_type
        row.sensitive = body.sensitive
        row.candidate_verified = body.candidate_verified
        row.confidence = Decimal("1.0000") if body.candidate_verified else Decimal("0.8500")
        if variants:
            row.question_variants = sorted(set((row.question_variants or []) + variants))
            row.normalized_question = _normalize(body.question or "") or row.normalized_question
    session.commit()
    session.refresh(row)
    return {"id": row.id, "canonical_key": row.canonical_key, "candidate_verified": row.candidate_verified}


@router.post("/applications/{application_id}/prepare", status_code=status.HTTP_201_CREATED)
def prepare_application(
    application_id: uuid.UUID,
    body: PrepareApplicationWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    application = _owned_application(session, user, application_id)
    job = session.get(Job, application.job_id)
    if job is None or job.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="The job is not active")

    copilot = _latest_artifact(session, user.id, job.id, "APPLICATION_COPILOT")
    if copilot is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "APPLICATION_COPILOT_REQUIRED",
                "message": "Generate the application copilot package before preparing browser execution.",
            },
        )

    drafts = list(
        session.scalars(
            select(ApplicationQuestionDraft)
            .where(ApplicationQuestionDraft.artifact_id == copilot.id)
            .order_by(ApplicationQuestionDraft.position)
        )
    )
    cover = session.scalar(select(CoverLetter).where(CoverLetter.artifact_id == copilot.id))
    resume = _latest_artifact(session, user.id, job.id, "RESUME_TAILORING")
    source = _source_for_job(session, job.id)
    known = _known_candidate_values(session, user)
    memories = _memory_map(session, user.id)

    observed = list(body.observed_fields)
    if not observed:
        observed = [
            ObservedField(field_id="first_name", label="First name", required=True),
            ObservedField(field_id="last_name", label="Last name", required=True),
            ObservedField(field_id="email", label="Email", required=True),
            ObservedField(field_id="current_title", label="Current title"),
            ObservedField(field_id="location", label="Current location"),
        ]
        observed.extend(
            ObservedField(
                field_id=f"question_{row.position}",
                label=row.question,
                field_type="TEXTAREA",
                required=True,
            )
            for row in drafts
        )

    fields = [
        _build_field(
            field=field,
            approval_mode=body.approval_mode,
            known=known,
            memories=memories,
            drafts=drafts,
        )
        for field in observed
    ]
    attempt = int(
        session.scalar(
            select(func.count())
            .select_from(ApplicationExecution)
            .where(ApplicationExecution.application_id == application.id)
        )
        or 0
    ) + 1
    execution = ApplicationExecution(
        user_id=user.id,
        application_id=application.id,
        job_id=job.id,
        application_copilot_artifact_id=copilot.id,
        attempt_number=attempt,
        approval_mode=body.approval_mode,
        ats_provider=_provider_name(source.connector_key if source else None),
        target_url=source.source_url if source else None,
        state="DISCOVERED",
        fields=fields,
        documents={
            "resume": {
                "artifact_id": str(resume.id) if resume else None,
                "status": resume.status if resume else "MISSING",
                "candidate_verified": bool(resume.candidate_verified) if resume else False,
            },
            "cover_letter": {
                "id": str(cover.id) if cover else None,
                "artifact_id": str(copilot.id),
                "candidate_verified": bool(cover.candidate_verified) if cover else False,
                "body": cover.body if cover else None,
            },
        },
        validation={"prepared_from_application_copilot": True, "copilot_artifact_id": str(copilot.id)},
    )
    _recompute(execution)
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return _execution_payload(execution)


@router.get("/applications/{application_id}/executions/latest")
def latest_execution(
    application_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    _owned_application(session, user, application_id)
    row = session.scalar(
        select(ApplicationExecution)
        .where(
            ApplicationExecution.application_id == application_id,
            ApplicationExecution.user_id == user.id,
        )
        .order_by(ApplicationExecution.attempt_number.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Application execution not found")
    return _execution_payload(row)


@router.patch("/executions/{execution_id}/fields/{field_id}")
def review_field(
    execution_id: uuid.UUID,
    field_id: str,
    body: FieldReviewWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    execution = _owned_execution(session, user, execution_id)
    if execution.state in {"BROWSER_RUNNING", "SUBMITTED", "CONFIRMED"}:
        raise HTTPException(status_code=409, detail="Application execution can no longer be edited")
    fields = [dict(row) for row in (execution.fields or [])]
    target = next((row for row in fields if row.get("field_id") == field_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Application field not found")
    target["value"] = body.value
    target["candidate_verified"] = body.candidate_verified
    target["confidence"] = 1.0 if body.candidate_verified else max(float(target.get("confidence") or 0), 0.70)
    target["source_kind"] = "CANDIDATE_REVIEW"
    target["source_ref"] = str(execution.id)
    target["requires_review"] = not body.candidate_verified
    target["status"] = "READY" if body.candidate_verified else "REVIEW_REQUIRED"
    execution.fields = fields

    if body.remember and body.candidate_verified and body.value not in (None, ""):
        canonical = str(target["canonical_key"])
        memory = session.scalar(
            select(ApplicationQuestionMemory).where(
                ApplicationQuestionMemory.user_id == user.id,
                ApplicationQuestionMemory.canonical_key == canonical,
            )
        )
        if memory is None:
            memory = ApplicationQuestionMemory(
                user_id=user.id,
                canonical_key=canonical,
                normalized_question=_normalize(str(target["label"])),
                question_variants=[str(target["label"])],
                answer=str(body.value),
                answer_type=str(target.get("field_type") or "TEXT"),
                confidence=Decimal("1.0000"),
                sensitive=bool(target.get("sensitive")),
                candidate_verified=True,
                source_kind="CANDIDATE_APPROVED",
                source_ref=str(execution.id),
                last_used_at=utcnow(),
            )
            session.add(memory)
        else:
            memory.answer = str(body.value)
            memory.confidence = Decimal("1.0000")
            memory.candidate_verified = True
            memory.sensitive = bool(target.get("sensitive"))
            memory.source_kind = "CANDIDATE_APPROVED"
            memory.source_ref = str(execution.id)
            memory.last_used_at = utcnow()
            memory.question_variants = sorted(set((memory.question_variants or []) + [str(target["label"])]))

    execution.approved_at = None
    _recompute(execution)
    session.commit()
    session.refresh(execution)
    return _execution_payload(execution)


@router.post("/executions/{execution_id}/approve")
def approve_execution(
    execution_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    execution = _owned_execution(session, user, execution_id)
    _recompute(execution)
    if execution.missing_fields:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "APPLICATION_FIELDS_MISSING", "fields": execution.missing_fields},
        )
    if execution.review_items:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "APPLICATION_REVIEW_REQUIRED", "items": execution.review_items},
        )
    execution.approved_at = utcnow()
    execution.state = "READY_FOR_EXECUTION"
    session.commit()
    session.refresh(execution)
    return _execution_payload(execution)


@router.post("/executions/{execution_id}/execute")
def execute_application(
    execution_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    execution = _owned_execution(session, user, execution_id)
    if execution.state != "READY_FOR_EXECUTION" or execution.approved_at is None:
        raise HTTPException(status_code=409, detail="Candidate approval is required before browser execution")
    if not execution.target_url:
        raise HTTPException(status_code=422, detail="No employer application URL is available")
    execution.state = "BROWSER_QUEUED"
    execution.browser_handoff = {
        "driver": execution.ats_provider,
        "target_url": execution.target_url,
        "allow_submit": True,
        "captcha_policy": "HUMAN_ACTION_REQUIRED",
        "security_challenge_policy": "HUMAN_ACTION_REQUIRED",
        "success_policy": "CONFIRMATION_REQUIRED",
        "queued_at": utcnow().isoformat(),
    }
    session.commit()
    session.refresh(execution)
    return _execution_payload(execution)


@internal_router.get("/executions/next")
def claim_browser_execution(session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.scalar(
        select(ApplicationExecution)
        .where(ApplicationExecution.state == "BROWSER_QUEUED")
        .order_by(ApplicationExecution.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if row is None:
        return {"execution": None}
    row.state = "BROWSER_RUNNING"
    row.started_at = row.started_at or utcnow()
    session.commit()
    session.refresh(row)
    return {
        "execution": {
            "id": str(row.id),
            "application_id": str(row.application_id),
            "job_id": str(row.job_id),
            "ats_provider": row.ats_provider,
            "target_url": row.target_url,
            "fields": [item for item in row.fields if item.get("value") not in (None, "")],
            "documents": row.documents,
            "policy": row.browser_handoff,
        }
    }


@internal_router.post("/executions/{execution_id}/complete")
def complete_browser_execution(
    execution_id: uuid.UUID,
    body: BrowserCompletionWrite,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    row = session.scalar(
        select(ApplicationExecution)
        .where(ApplicationExecution.id == execution_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Application execution not found")
    if row.state not in {"BROWSER_RUNNING", "BROWSER_QUEUED", "HUMAN_ACTION_REQUIRED", "SUBMITTED"}:
        raise HTTPException(status_code=409, detail="Execution is not waiting for a browser result")

    row.validation = {**(row.validation or {}), **body.validation, "field_results": body.field_results}
    if body.status == "FAILED":
        row.state = "FAILED"
        row.error_code = body.error_code or "BROWSER_EXECUTION_FAILED"
        row.error_detail = body.error_detail
    elif body.status == "HUMAN_ACTION_REQUIRED":
        row.state = "HUMAN_ACTION_REQUIRED"
        row.browser_handoff = {**(row.browser_handoff or {}), "human_action": body.human_action}
    elif body.status == "SUBMITTED":
        row.state = "SUBMITTED"
        row.submitted_at = row.submitted_at or utcnow()
    else:
        row.state = "CONFIRMED"
        row.submitted_at = row.submitted_at or utcnow()
        row.confirmed_at = utcnow()
        row.confirmation_url = body.confirmation_url
        row.confirmation_text = body.confirmation_text
        application = session.get(Application, row.application_id)
        if application is not None and application.current_status != "APPLIED":
            previous = application.current_status
            application.current_status = "APPLIED"
            session.add(
                ApplicationEvent(
                    application_id=application.id,
                    actor_user_id=row.user_id,
                    from_status=previous,
                    to_status="APPLIED",
                    metadata_json={
                        "application_execution_id": str(row.id),
                        "channel": "APPLYAI_BROWSER_AGENT",
                        "confirmation_url": body.confirmation_url,
                    },
                )
            )
    session.commit()
    session.refresh(row)
    return {"id": row.id, "state": row.state, "confirmed_at": row.confirmed_at}


@internal_router.get("/executions")
def list_browser_executions(
    state: str | None = Query(default=None, max_length=48),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    query = select(ApplicationExecution)
    if state:
        query = query.where(ApplicationExecution.state == state)
    rows = list(session.scalars(query.order_by(ApplicationExecution.created_at.desc()).limit(limit)))
    return [_execution_payload(row) for row in rows]
