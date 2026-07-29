import io
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.queue import Task, TaskQueue, get_task_queue
from app.core.storage import ObjectStorageProvider, get_object_storage
from app.models import Resume, ResumeExtraction, ResumeVersion, User
from app.schemas import (
    ProfileResponse,
    ProfileReviewWrite,
    ResumeExtractionResponse,
    ResumeVersionResponse,
)
from app.resumes.processor import process_resume_version
from app.api.profiles import put_profile


router = APIRouter(prefix="/resumes", tags=["resumes"])
ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


@router.get("", response_model=list[ResumeVersionResponse])
def list_resumes(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ResumeVersion]:
    return list(
        session.scalars(
            select(ResumeVersion)
            .where(ResumeVersion.user_id == user.id)
            .order_by(ResumeVersion.created_at.desc())
        )
    )


@router.get("/{resume_id}", response_model=ResumeVersionResponse)
def get_resume(
    resume_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ResumeVersion:
    version = session.scalar(
        select(ResumeVersion)
        .join(Resume, Resume.id == ResumeVersion.resume_id)
        .where(Resume.id == resume_id, Resume.user_id == user.id)
        .order_by(ResumeVersion.version_number.desc())
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return version


@router.post("", response_model=ResumeVersionResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    storage: ObjectStorageProvider = Depends(get_object_storage),
    queue: TaskQueue = Depends(get_task_queue),
    settings: Settings = Depends(get_settings),
) -> ResumeVersion:
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    expected_extension = ALLOWED_TYPES.get(file.content_type or "")
    if expected_extension is None or extension != expected_extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume must be a PDF or DOCX file with a matching content type",
        )

    content = await file.read(settings.max_resume_bytes + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume file is empty")
    if len(content) > settings.max_resume_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Resume file exceeds the 5 MB limit",
        )

    resume = Resume(user_id=user.id, name=Path(filename).stem, is_master=True)
    session.add(resume)
    session.flush()
    next_version = (
        session.scalar(
            select(func.coalesce(func.max(ResumeVersion.version_number), 0)).where(
                ResumeVersion.resume_id == resume.id
            )
        )
        or 0
    ) + 1
    version_id = uuid.uuid4()
    storage_key = f"users/{user.id}/resumes/{resume.id}/versions/{version_id}{extension}"
    version = ResumeVersion(
        id=version_id,
        resume_id=resume.id,
        user_id=user.id,
        version_number=next_version,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        storage_key=storage_key,
        file_size=len(content),
        upload_status="UPLOADED",
        processing_status="QUEUED",
    )

    try:
        storage.put(
            key=storage_key,
            content=io.BytesIO(content),
            content_type=version.content_type,
        )
        session.add(version)
        session.commit()
        queue.enqueue(
            Task(
                task_type="RESUME_PARSE",
                payload={"resume_version_id": str(version.id), "user_id": str(user.id)},
                idempotency_key=f"resume-parse:{version.id}",
            )
        )
        # Local/test development can process immediately. Production is required by
        # Settings validation to use SQS, so untrusted document work never runs in
        # the API container there.
        if settings.task_queue_provider == "memory":
            background_tasks.add_task(process_resume_version, version.id, storage)
    except Exception:
        session.rollback()
        storage.delete(key=storage_key)
        raise

    session.refresh(version)
    return version


@router.get("/{resume_id}/extraction", response_model=ResumeExtractionResponse)
def get_resume_extraction(
    resume_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ResumeExtraction:
    extraction = session.scalar(
        select(ResumeExtraction)
        .join(ResumeVersion, ResumeVersion.id == ResumeExtraction.resume_version_id)
        .join(Resume, Resume.id == ResumeVersion.resume_id)
        .where(Resume.id == resume_id, Resume.user_id == user.id)
        .order_by(ResumeExtraction.created_at.desc())
    )
    if extraction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "EXTRACTION_NOT_FOUND", "message": "Resume extraction is not ready"},
        )
    return extraction


@router.post("/{resume_id}/confirm", response_model=ProfileResponse)
def confirm_resume_profile(
    resume_id: uuid.UUID,
    payload: ProfileReviewWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProfileResponse:
    version = session.scalar(
        select(ResumeVersion)
        .join(Resume, Resume.id == ResumeVersion.resume_id)
        .where(Resume.id == resume_id, Resume.user_id == user.id)
        .order_by(ResumeVersion.version_number.desc())
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    extraction = session.scalar(
        select(ResumeExtraction)
        .where(ResumeExtraction.resume_version_id == version.id)
        .order_by(ResumeExtraction.created_at.desc())
    )
    if extraction is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Extraction is not ready")
    profile = put_profile(payload=payload, user=user, session=session)
    extraction.status = "COMPLETED"
    version.processing_status = "COMPLETED"
    session.commit()
    return profile
