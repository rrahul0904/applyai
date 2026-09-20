import base64
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import (
    Application,
    ApplicationEvent,
    ApplicationNote,
    Company,
    Job,
    JobLocation,
    User,
)
from app.schemas import (
    ApplicationBoardItem,
    ApplicationBoardResponse,
    ApplicationCreate,
    ApplicationEventResponse,
    ApplicationJobSummary,
    ApplicationListItem,
    ApplicationListPage,
    ApplicationNoteResponse,
    ApplicationNoteWrite,
    ApplicationResponse,
    ApplicationStatusWrite,
    ApplicationTrackerResponse,
    ApplicationTrackerWrite,
)


router = APIRouter(prefix="/applications", tags=["applications"])
VALID_STATUSES = {
    "SAVED",
    "PREPARING",
    "READY",
    "APPLIED",
    "RECRUITER_SCREEN",
    "ASSESSMENT",
    "INTERVIEW",
    "FINAL_INTERVIEW",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
}


def encode_cursor(application: Application) -> str:
    payload = json.dumps(
        {"updated_at": application.updated_at.isoformat(), "id": str(application.id)}
    ).encode()
    return base64.urlsafe_b64encode(payload).decode()


def decode_cursor(value: str | None) -> tuple[datetime | None, uuid.UUID | None]:
    if not value:
        return None, None
    try:
        payload = json.loads(base64.urlsafe_b64decode(value.encode()).decode())
        return datetime.fromisoformat(payload["updated_at"]), uuid.UUID(payload["id"])
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "INVALID_CURSOR", "message": "Application cursor is invalid"},
        )


TRACKER_EVENT_TYPE = "TRACKER_UPDATE"
TERMINAL_STATUSES = {"REJECTED", "WITHDRAWN"}


def _parse_tracker_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _tracker_from_event(event: ApplicationEvent | None) -> ApplicationTrackerResponse:
    metadata = event.metadata_json if event is not None and isinstance(event.metadata_json, dict) else {}
    tracker = metadata.get("tracker") if isinstance(metadata.get("tracker"), dict) else {}
    return ApplicationTrackerResponse(
        deadline_at=_parse_tracker_datetime(tracker.get("deadline_at")),
        interview_at=_parse_tracker_datetime(tracker.get("interview_at")),
        next_action_at=_parse_tracker_datetime(tracker.get("next_action_at")),
        offer_minimum=tracker.get("offer_minimum"),
        offer_maximum=tracker.get("offer_maximum"),
        offer_currency=str(tracker.get("offer_currency") or "USD").upper(),
        offer_notes=tracker.get("offer_notes"),
        source_channel=tracker.get("source_channel"),
        priority=str(tracker.get("priority") or "MEDIUM").upper(),
        updated_at=event.created_at if event is not None else None,
    )


def tracker_for(application_id: uuid.UUID, session: Session) -> ApplicationTrackerResponse:
    events = list(
        session.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application_id)
            .order_by(ApplicationEvent.created_at.desc(), ApplicationEvent.id.desc())
        )
    )
    event = next(
        (
            row
            for row in events
            if isinstance(row.metadata_json, dict)
            and row.metadata_json.get("event_type") == TRACKER_EVENT_TYPE
        ),
        None,
    )
    return _tracker_from_event(event)


def response_for(application: Application, session: Session) -> ApplicationResponse:
    events = [
        event
        for event in session.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application.id)
            .order_by(ApplicationEvent.created_at)
        )
        if not (
            isinstance(event.metadata_json, dict)
            and event.metadata_json.get("event_type") == TRACKER_EVENT_TYPE
        )
    ]
    return ApplicationResponse(
        id=application.id,
        job_id=application.job_id,
        current_status=application.current_status,
        created_at=application.created_at,
        updated_at=application.updated_at,
        events=[
            ApplicationEventResponse(
                id=event.id,
                from_status=event.from_status,
                to_status=event.to_status,
                created_at=event.created_at,
            )
            for event in events
        ],
        tracker=tracker_for(application.id, session),
        notes=[
            ApplicationNoteResponse(
                id=note.id,
                body=note.body,
                created_at=note.created_at,
                updated_at=note.updated_at,
            )
            for note in session.scalars(
                select(ApplicationNote)
                .where(ApplicationNote.application_id == application.id)
                .order_by(ApplicationNote.created_at.desc())
            )
        ],
    )


@router.get("", response_model=ApplicationListPage)
def list_applications(
    cursor: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationListPage:
    cursor_at, cursor_id = decode_cursor(cursor)
    first_location = (
        select(JobLocation.location_text)
        .where(JobLocation.job_id == Job.id)
        .order_by(JobLocation.id)
        .limit(1)
        .scalar_subquery()
    )
    statement = (
        select(
            Application,
            Job.title,
            Company.canonical_name,
            first_location.label("location"),
        )
        .join(Job, Job.id == Application.job_id)
        .join(Company, Company.id == Job.company_id)
        .where(Application.user_id == user.id)
    )
    if cursor_at and cursor_id:
        statement = statement.where(
            or_(
                Application.updated_at < cursor_at,
                and_(Application.updated_at == cursor_at, Application.id < cursor_id),
            )
        )
    rows = list(
        session.execute(
            statement.order_by(Application.updated_at.desc(), Application.id.desc()).limit(limit + 1)
        )
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [
        ApplicationListItem(
            id=application.id,
            job_id=application.job_id,
            current_status=application.current_status,
            created_at=application.created_at,
            updated_at=application.updated_at,
            job=ApplicationJobSummary(
                id=application.job_id,
                title=title,
                company_name=company_name,
                location=location,
            ),
        )
        for application, title, company_name, location in rows
    ]
    return ApplicationListPage(
        items=items,
        next_cursor=encode_cursor(rows[-1][0]) if has_more and rows else None,
        returned=len(items),
    )


@router.get("/board", response_model=ApplicationBoardResponse)
def get_application_board(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationBoardResponse:
    first_location = (
        select(JobLocation.location_text)
        .where(JobLocation.job_id == Job.id)
        .order_by(JobLocation.id)
        .limit(1)
        .scalar_subquery()
    )
    rows = list(
        session.execute(
            select(
                Application,
                Job.title,
                Company.canonical_name,
                first_location.label("location"),
            )
            .join(Job, Job.id == Application.job_id)
            .join(Company, Company.id == Job.company_id)
            .where(Application.user_id == user.id)
            .order_by(Application.updated_at.desc(), Application.id.desc())
            .limit(500)
        )
    )
    application_ids = [row[0].id for row in rows]
    tracker_events: dict[uuid.UUID, ApplicationEvent] = {}
    if application_ids:
        for event in session.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id.in_(application_ids))
            .order_by(ApplicationEvent.created_at.desc(), ApplicationEvent.id.desc())
        ):
            if event.application_id in tracker_events:
                continue
            if isinstance(event.metadata_json, dict) and event.metadata_json.get("event_type") == TRACKER_EVENT_TYPE:
                tracker_events[event.application_id] = event

    now = datetime.now(timezone.utc)
    items: list[ApplicationBoardItem] = []
    counts: dict[str, int] = {}
    for application, title, company_name, location in rows:
        tracker = _tracker_from_event(tracker_events.get(application.id))
        deadline = tracker.deadline_at
        overdue = bool(
            deadline
            and deadline < now
            and application.current_status not in TERMINAL_STATUSES
            and application.current_status != "OFFER"
        )
        counts[application.current_status] = counts.get(application.current_status, 0) + 1
        items.append(
            ApplicationBoardItem(
                id=application.id,
                job_id=application.job_id,
                current_status=application.current_status,
                created_at=application.created_at,
                updated_at=application.updated_at,
                job=ApplicationJobSummary(
                    id=application.job_id,
                    title=title,
                    company_name=company_name,
                    location=location,
                ),
                tracker=tracker,
                overdue=overdue,
            )
        )
    return ApplicationBoardResponse(items=items, counts=counts, total=len(items))


@router.get("/{application_id}", response_model=ApplicationResponse)
def get_application(
    application_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationResponse:
    application = session.scalar(
        select(Application).where(
            Application.id == application_id, Application.user_id == user.id
        )
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return response_for(application, session)


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationResponse:
    job = session.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status in {"CLOSED", "ARCHIVED", "STALE"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "JOB_CLOSED", "message": "This job is no longer accepting applications"},
        )
    existing = session.scalar(
        select(Application).where(
            Application.user_id == user.id,
            Application.job_id == payload.job_id,
        )
    )
    if existing is not None:
        return response_for(existing, session)
    application = Application(
        user_id=user.id,
        job_id=payload.job_id,
        current_status="PREPARING",
    )
    session.add(application)
    session.flush()
    session.add(
        ApplicationEvent(
            application_id=application.id,
            actor_user_id=user.id,
            from_status=None,
            to_status="PREPARING",
            metadata_json={},
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An application already exists for this job",
        ) from exc
    session.refresh(application)
    return response_for(application, session)


@router.patch("/{application_id}/status", response_model=ApplicationResponse)
def update_application_status(
    application_id: uuid.UUID,
    payload: ApplicationStatusWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationResponse:
    new_status = payload.status.upper()
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid status")
    application = session.scalar(
        select(Application).where(
            Application.id == application_id, Application.user_id == user.id
        )
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    previous = application.current_status
    if previous != new_status:
        application.current_status = new_status
        session.add(
            ApplicationEvent(
                application_id=application.id,
                actor_user_id=user.id,
                from_status=previous,
                to_status=new_status,
                metadata_json={},
            )
        )
        session.commit()
        session.refresh(application)
    return response_for(application, session)


def owned_application(
    application_id: uuid.UUID, user: User, session: Session
) -> Application:
    application = session.scalar(
        select(Application).where(
            Application.id == application_id, Application.user_id == user.id
        )
    )
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


@router.patch("/{application_id}/tracker", response_model=ApplicationTrackerResponse)
def update_application_tracker(
    application_id: uuid.UUID,
    payload: ApplicationTrackerWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationTrackerResponse:
    application = owned_application(application_id, user, session)
    current = tracker_for(application_id, session)
    incoming = payload.model_dump(exclude_unset=True)
    merged = current.model_dump(exclude={"updated_at"})
    merged.update(incoming)

    if merged.get("offer_minimum") is not None and merged.get("offer_maximum") is not None:
        if int(merged["offer_minimum"]) > int(merged["offer_maximum"]):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Offer minimum cannot exceed offer maximum",
            )
    priority = str(merged.get("priority") or "MEDIUM").upper()
    if priority not in {"LOW", "MEDIUM", "HIGH"}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Priority must be LOW, MEDIUM, or HIGH",
        )
    merged["priority"] = priority
    merged["offer_currency"] = str(merged.get("offer_currency") or "USD").upper()
    for key in ("deadline_at", "interview_at", "next_action_at"):
        value = merged.get(key)
        if isinstance(value, datetime):
            merged[key] = value.isoformat()

    now = datetime.now(timezone.utc)
    application.updated_at = now
    session.add(
        ApplicationEvent(
            application_id=application.id,
            actor_user_id=user.id,
            from_status=application.current_status,
            to_status=application.current_status,
            metadata_json={"event_type": TRACKER_EVENT_TYPE, "tracker": merged},
        )
    )
    session.commit()
    return tracker_for(application_id, session)


@router.post(
    "/{application_id}/notes",
    response_model=ApplicationNoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    application_id: uuid.UUID,
    payload: ApplicationNoteWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationNote:
    owned_application(application_id, user, session)
    note = ApplicationNote(
        application_id=application_id,
        user_id=user.id,
        body=payload.body.strip(),
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@router.put("/{application_id}/notes/{note_id}", response_model=ApplicationNoteResponse)
def update_note(
    application_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: ApplicationNoteWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ApplicationNote:
    owned_application(application_id, user, session)
    note = session.scalar(
        select(ApplicationNote).where(
            ApplicationNote.id == note_id,
            ApplicationNote.application_id == application_id,
            ApplicationNote.user_id == user.id,
        )
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    note.body = payload.body.strip()
    session.commit()
    session.refresh(note)
    return note


@router.delete(
    "/{application_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_note(
    application_id: uuid.UUID,
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    owned_application(application_id, user, session)
    note = session.scalar(
        select(ApplicationNote).where(
            ApplicationNote.id == note_id,
            ApplicationNote.application_id == application_id,
            ApplicationNote.user_id == user.id,
        )
    )
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    session.delete(note)
    session.commit()
