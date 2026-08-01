import io
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.profiles import save_profile
from app.core.auth import get_current_user
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.outbox import add_task_outbox_event, publish_outbox_once
from app.core.queue import Task, TaskQueue, get_task_queue
from app.core.storage import ObjectStorageProvider, get_object_storage
from app.durability_models import ResumeUploadIntent
from app.models import Resume, ResumeExtraction, ResumeVersion, User
from app.schemas import (
    ProfileResponse,
    ProfileReviewWrite,
    ResumeExtractionResponse,
    ResumeUploadIntentResponse,
    ResumeUploadIntentWrite,
    ResumeVersionResponse,
)
from app.resumes.processor import process_resume_version


router = APIRouter(prefix="/resumes", tags=["resumes"])
ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


def validate_resume_identity(
    *,
    filename: str,
    content_type: str,
    file_size: int,
    settings: Settings,
) -> tuple[str, str]:
    safe_filename = Path(filename).name
    extension = Path(safe_filename).suffix.lower()
    expected_extension = ALLOWED_TYPES.get(content_type)
    if expected_extension is None or extension != expected_extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resume must be a PDF or DOCX file with a matching content type",
        )
    if file_size <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resume file is empty")
    if file_size > settings.max_resume_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Resume file exceeds the {settings.max_resume_bytes} byte limit",
        )
    return safe_filename, extension


def get_or_create_master_resume(
    session: Session,
    *,
    user: User,
    filename: str,
) -> Resume:
    resume = session.scalar(
        select(Resume)
        .where(Resume.user_id == user.id, Resume.is_master.is_(True))
        .with_for_update()
    )
    if resume is not None:
        return resume

    try:
        with session.begin_nested():
            resume = Resume(user_id=user.id, name=Path(filename).stem, is_master=True)
            session.add(resume)
            session.flush()
            return resume
    except IntegrityError:
        resume = session.scalar(
            select(Resume)
            .where(Resume.user_id == user.id, Resume.is_master.is_(True))
            .with_for_update()
        )
        if resume is None:
            raise
        return resume


def create_pending_version(
    session: Session,
    *,
    user: User,
    filename: str,
    content_type: str,
    file_size: int,
    extension: str,
) -> ResumeVersion:
    """Create a server-upload version for local/development proxy uploads only."""
    resume = get_or_create_master_resume(session, user=user, filename=filename)
    session.execute(select(Resume.id).where(Resume.id == resume.id).with_for_update())
    next_version = (
        session.scalar(
            select(func.coalesce(func.max(ResumeVersion.version_number), 0)).where(
                ResumeVersion.resume_id == resume.id
            )
        )
        or 0
    ) + 1
    version_id = uuid.uuid4()
    storage_key = f"candidate/{user.id}/resume/{resume.id}/{version_id}{extension}"
    version = ResumeVersion(
        id=version_id,
        resume_id=resume.id,
        user_id=user.id,
        version_number=next_version,
        filename=filename,
        content_type=content_type,
        storage_key=storage_key,
        file_size=file_size,
        upload_status="PENDING_UPLOAD",
        processing_status="PENDING_UPLOAD",
    )
    session.add(version)
    session.flush()
    return version


def finalize_uploaded_version(session: Session, *, version: ResumeVersion, user: User) -> None:
    if version.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if version.upload_status != "PENDING_UPLOAD":
        return
    version.upload_status = "UPLOADED"
    version.processing_status = "QUEUED"
    add_task_outbox_event(
        session,
        task=Task(
            task_type="RESUME_PARSE",
            payload={"resume_version_id": str(version.id), "user_id": str(user.id)},
            idempotency_key=f"resume-parse:{version.id}",
        ),
        aggregate_type="RESUME_VERSION",
        aggregate_id=version.id,
    )


def create_direct_upload_intent(
    session: Session,
    *,
    user: User,
    filename: str,
    content_type: str,
    file_size: int,
    extension: str,
    expires_in_seconds: int,
) -> ResumeUploadIntent:
    """Persist upload authorization without creating a canonical ResumeVersion yet."""
    resume = get_or_create_master_resume(session, user=user, filename=filename)
    version_id = uuid.uuid4()
    storage_key = f"candidate/{user.id}/resume/{resume.id}/{version_id}{extension}"
    intent = ResumeUploadIntent(
        user_id=user.id,
        resume_id=resume.id,
        resume_version_id=version_id,
        filename=filename,
        content_type=content_type,
        file_size=file_size,
        storage_key=storage_key,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
        status="PENDING",
    )
    session.add(intent)
    session.flush()
    return intent


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


@router.post("/upload-intents", response_model=ResumeUploadIntentResponse)
def create_resume_upload_intent(
    payload: ResumeUploadIntentWrite,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    storage: ObjectStorageProvider = Depends(get_object_storage),
    settings: Settings = Depends(get_settings),
) -> ResumeUploadIntentResponse:
    filename, extension = validate_resume_identity(
        filename=payload.filename,
        content_type=payload.content_type,
        file_size=payload.file_size,
        settings=settings,
    )
    if not storage.supports_direct_upload:
        return ResumeUploadIntentResponse(upload_mode="PROXY")

    intent = create_direct_upload_intent(
        session,
        user=user,
        filename=filename,
        content_type=payload.content_type,
        file_size=payload.file_size,
        extension=extension,
        expires_in_seconds=settings.s3_upload_expiration_seconds,
    )
    try:
        upload_url = storage.create_presigned_put(
            key=intent.storage_key,
            content_type=intent.content_type,
            expires_in_seconds=settings.s3_upload_expiration_seconds,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return ResumeUploadIntentResponse(
        upload_mode="DIRECT_S3",
        resume_id=intent.resume_id,
        resume_version_id=intent.resume_version_id,
        upload_url=upload_url,
        upload_headers={
            "content-type": intent.content_type,
            "x-amz-server-side-encryption": "AES256",
        },
        expires_in_seconds=settings.s3_upload_expiration_seconds,
    )


@router.post(
    "/versions/{version_id}/upload-complete",
    response_model=ResumeVersionResponse,
)
def complete_resume_upload(
    version_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
    storage: ObjectStorageProvider = Depends(get_object_storage),
    queue: TaskQueue = Depends(get_task_queue),
    settings: Settings = Depends(get_settings),
) -> ResumeVersion:
    intent = session.scalar(
        select(ResumeUploadIntent)
        .where(
            ResumeUploadIntent.resume_version_id == version_id,
            ResumeUploadIntent.user_id == user.id,
        )
        .with_for_update()
    )
    if intent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume upload not found")

    if intent.status == "COMPLETED":
        completed_version = session.scalar(
            select(ResumeVersion).where(
                ResumeVersion.id == version_id,
                ResumeVersion.user_id == user.id,
            )
        )
        if completed_version is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "UPLOAD_STATE_INVALID", "message": "Completed upload has no resume version"},
            )
        return completed_version

    now = datetime.now(timezone.utc)
    if intent.expires_at <= now:
        intent.status = "EXPIRED"
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"code": "UPLOAD_EXPIRED", "message": "Resume upload intent has expired"},
        )

    try:
        metadata = storage.head(key=intent.storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "UPLOAD_NOT_FOUND", "message": "Uploaded resume object was not found"},
        ) from exc
    if metadata.size != intent.file_size:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "UPLOAD_SIZE_MISMATCH", "message": "Uploaded resume size did not match intent"},
        )
    if metadata.content_type and metadata.content_type != intent.content_type:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "UPLOAD_TYPE_MISMATCH", "message": "Uploaded resume type did not match intent"},
        )

    resume = session.scalar(
        select(Resume)
        .where(Resume.id == intent.resume_id, Resume.user_id == user.id)
        .with_for_update()
    )
    if resume is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    next_version = (
        session.scalar(
            select(func.coalesce(func.max(ResumeVersion.version_number), 0)).where(
                ResumeVersion.resume_id == resume.id
            )
        )
        or 0
    ) + 1
    version = ResumeVersion(
        id=intent.resume_version_id,
        resume_id=resume.id,
        user_id=user.id,
        version_number=next_version,
        filename=intent.filename,
        content_type=intent.content_type,
        storage_key=intent.storage_key,
        file_size=intent.file_size,
        upload_status="PENDING_UPLOAD",
        processing_status="PENDING_UPLOAD",
    )
    session.add(version)
    finalize_uploaded_version(session, version=version, user=user)
    intent.status = "COMPLETED"
    intent.completed_at = now
    session.commit()
    session.refresh(version)

    if settings.task_queue_provider == "memory":
        publish_outbox_once(settings, queue=queue)
        background_tasks.add_task(process_resume_version, version.id, storage)
    return version


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
    if storage.supports_direct_upload:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DIRECT_UPLOAD_REQUIRED", "message": "Use direct resume upload"},
        )

    filename = Path(file.filename or "").name
    content = await file.read(settings.max_resume_bytes + 1)
    filename, extension = validate_resume_identity(
        filename=filename,
        content_type=file.content_type or "",
        file_size=len(content),
        settings=settings,
    )
    version = create_pending_version(
        session,
        user=user,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        extension=extension,
    )
    try:
        storage.put(
            key=version.storage_key,
            content=io.BytesIO(content),
            content_type=version.content_type,
        )
        finalize_uploaded_version(session, version=version, user=user)
        session.commit()
    except Exception:
        session.rollback()
        storage.delete(key=version.storage_key)
        raise

    session.refresh(version)
    publish_outbox_once(settings, queue=queue)
    background_tasks.add_task(process_resume_version, version.id, storage)
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
        .order_by(ResumeVersion.version_number.desc())
    )
    if extraction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Extraction not found")
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
        .with_for_update()
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    extraction = session.scalar(
        select(ResumeExtraction)
        .where(ResumeExtraction.resume_version_id == version.id)
        .order_by(ResumeExtraction.created_at.desc())
        .with_for_update()
    )
    if extraction is None or extraction.status not in {"NEEDS_REVIEW", "COMPLETED"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resume extraction is not ready for confirmation",
        )

    profile = save_profile(
        payload=payload,
        user=user,
        session=session,
        commit=False,
    )
    extraction.status = "COMPLETED"
    extraction.error_code = None
    version.processing_status = "COMPLETED"
    session.commit()
    return profile
