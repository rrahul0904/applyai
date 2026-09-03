from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.durability_models import ResumeProcessingAttempt, ResumeUploadIntent
from app.models import ResumeVersion, User


@dataclass(frozen=True)
class ResumeStorageUsage:
    user_versions: int
    user_pending_uploads: int
    user_reserved_bytes: int
    global_reserved_bytes: int
    monthly_class_a_operations: int
    monthly_class_b_operations: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _month_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def resume_storage_usage(session: Session, *, user: User) -> ResumeStorageUsage:
    """Return conservative R2 usage derived from canonical database records.

    Uncompleted upload intents remain reserved until the cleanup job proves the corresponding
    object was deleted. This intentionally prefers temporarily refusing an upload over silently
    crossing a provider free-tier boundary.
    """

    uncompleted = ResumeUploadIntent.status != "COMPLETED"
    user_versions = int(
        session.scalar(
            select(func.count()).select_from(ResumeVersion).where(ResumeVersion.user_id == user.id)
        )
        or 0
    )
    user_pending_uploads = int(
        session.scalar(
            select(func.count())
            .select_from(ResumeUploadIntent)
            .where(ResumeUploadIntent.user_id == user.id, uncompleted)
        )
        or 0
    )
    user_version_bytes = int(
        session.scalar(
            select(func.coalesce(func.sum(ResumeVersion.file_size), 0)).where(
                ResumeVersion.user_id == user.id
            )
        )
        or 0
    )
    user_pending_bytes = int(
        session.scalar(
            select(func.coalesce(func.sum(ResumeUploadIntent.file_size), 0)).where(
                ResumeUploadIntent.user_id == user.id,
                uncompleted,
            )
        )
        or 0
    )
    global_version_bytes = int(
        session.scalar(select(func.coalesce(func.sum(ResumeVersion.file_size), 0))) or 0
    )
    global_pending_bytes = int(
        session.scalar(
            select(func.coalesce(func.sum(ResumeUploadIntent.file_size), 0)).where(uncompleted)
        )
        or 0
    )
    month_start = _month_start()
    class_a = int(
        session.scalar(
            select(func.count())
            .select_from(ResumeUploadIntent)
            .where(ResumeUploadIntent.created_at >= month_start)
        )
        or 0
    )
    completed_heads = int(
        session.scalar(
            select(func.count())
            .select_from(ResumeUploadIntent)
            .where(
                ResumeUploadIntent.completed_at.is_not(None),
                ResumeUploadIntent.completed_at >= month_start,
            )
        )
        or 0
    )
    parser_reads = int(
        session.scalar(
            select(func.count())
            .select_from(ResumeProcessingAttempt)
            .where(ResumeProcessingAttempt.started_at >= month_start)
        )
        or 0
    )
    return ResumeStorageUsage(
        user_versions=user_versions,
        user_pending_uploads=user_pending_uploads,
        user_reserved_bytes=user_version_bytes + user_pending_bytes,
        global_reserved_bytes=global_version_bytes + global_pending_bytes,
        monthly_class_a_operations=class_a,
        monthly_class_b_operations=completed_heads + parser_reads,
    )


def resume_upload_block_reason(
    usage: ResumeStorageUsage,
    *,
    requested_bytes: int,
    settings: Settings,
) -> tuple[str, str] | None:
    if usage.user_versions + usage.user_pending_uploads >= settings.max_resume_versions_per_user:
        return "USER_VERSION_LIMIT", "The pilot allows five retained resume versions per account"
    if usage.user_reserved_bytes + requested_bytes > settings.max_resume_storage_bytes_per_user:
        return "USER_STORAGE_LIMIT", "The pilot allows 25 MB of resume storage per account"
    if usage.global_reserved_bytes + requested_bytes > settings.object_storage_hard_limit_bytes:
        return (
            "OBJECT_STORAGE_LIMIT",
            "Resume uploads are temporarily paused at the zero-cost storage limit",
        )
    if settings.object_storage_provider == "s3":
        if usage.monthly_class_a_operations >= settings.max_monthly_r2_class_a_operations:
            return (
                "R2_CLASS_A_LIMIT",
                "Resume uploads are temporarily paused at the monthly operation limit",
            )
        if usage.monthly_class_b_operations >= settings.max_monthly_r2_class_b_operations:
            return (
                "R2_CLASS_B_LIMIT",
                "Resume uploads are temporarily paused at the monthly operation limit",
            )
    return None
