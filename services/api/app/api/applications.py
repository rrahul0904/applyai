import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_session
from app.models import Application, ApplicationEvent, ApplicationNote, Job, User
from app.schemas import (
    ApplicationCreate,
    ApplicationEventResponse,
    ApplicationNoteResponse,
    ApplicationNoteWrite,
    ApplicationResponse,
    ApplicationStatusWrite,
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


def response_for(application: Application, session: Session) -> ApplicationResponse:
    events = list(
        session.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application.id)
            .order_by(ApplicationEvent.created_at)
        )
    )
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


@router.get("", response_model=list[ApplicationResponse])
def list_applications(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ApplicationResponse]:
    applications = list(
        session.scalars(
            select(Application)
            .where(Application.user_id == user.id)
            .order_by(Application.updated_at.desc())
        )
    )
    return [response_for(application, session) for application in applications]


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
    if job.status in {"CLOSED", "ARCHIVED"}:
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
