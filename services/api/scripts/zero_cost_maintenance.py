"""Run bounded maintenance without an always-on worker.

Designed for manual execution or a short-lived GitHub Actions job. It never prints credentials or
candidate content.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.storage import get_object_storage
from app.durability_models import ResumeUploadIntent
from app.workers.postgres import drain_bounded


def cleanup_expired_uploads(*, maximum: int = 100) -> tuple[int, int]:
    storage = get_object_storage(get_settings())
    deleted = 0
    failed = 0
    with SessionLocal() as session:
        rows = list(
            session.scalars(
                select(ResumeUploadIntent)
                .where(
                    ResumeUploadIntent.status.in_(["PENDING", "EXPIRED"]),
                    ResumeUploadIntent.expires_at < datetime.now(UTC),
                )
                .order_by(ResumeUploadIntent.expires_at, ResumeUploadIntent.id)
                .with_for_update(skip_locked=True)
                .limit(maximum)
            )
        )
        for row in rows:
            try:
                storage.delete(key=row.storage_key)
                row.status = "CLEANED"
                deleted += 1
            except (BotoCoreError, ClientError, OSError):
                failed += 1
        session.commit()
    return deleted, failed


def main() -> None:
    settings = get_settings()
    tasks_processed = 0
    if settings.task_queue_provider == "postgres":
        tasks_processed = drain_bounded(settings, maximum_tasks=25)
    uploads_deleted, cleanup_failures = cleanup_expired_uploads()
    print(
        json.dumps(
            {
                "tasks_processed": tasks_processed,
                "expired_uploads_deleted": uploads_deleted,
                "cleanup_failures": cleanup_failures,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
