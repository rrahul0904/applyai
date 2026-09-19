from __future__ import annotations

import logging
import socket
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.api.career_radar import refresh_radar
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.models import User
from app.radar_watch_models import RadarWatch

logger = logging.getLogger("applyai.radar_watch_worker")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def claim_due_watch(now: datetime | None = None) -> uuid.UUID | None:
    moment = now or utcnow()
    with SessionLocal() as session:
        watch = session.scalar(
            select(RadarWatch)
            .where(RadarWatch.enabled.is_(True), RadarWatch.next_run_at <= moment)
            .order_by(RadarWatch.next_run_at, RadarWatch.created_at, RadarWatch.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if watch is None:
            return None
        watch.last_run_at = moment
        watch.last_run_status = "RUNNING"
        watch.last_error = None
        watch.next_run_at = moment + timedelta(minutes=watch.interval_minutes)
        session.commit()
        return watch.id


def execute_watch(watch_id: uuid.UUID, settings: Settings) -> int:
    try:
        with SessionLocal() as session:
            watch = session.get(RadarWatch, watch_id)
            if watch is None or not watch.enabled:
                return 0
            user = session.get(User, watch.user_id)
            if user is None:
                raise RuntimeError("RADAR_WATCH_USER_NOT_FOUND")
            result = refresh_radar(
                max_jobs=watch.max_jobs,
                lookback_days=watch.lookback_days,
                user=user,
                session=session,
                settings=settings,
            )
            scheduled = int(result["scheduled"])
            watch = session.get(RadarWatch, watch_id)
            if watch is not None:
                watch.last_run_status = "SUCCEEDED"
                watch.last_scheduled_jobs = scheduled
                watch.last_error = None
                session.commit()
            return scheduled
    except Exception as exc:
        with SessionLocal() as session:
            watch = session.get(RadarWatch, watch_id)
            if watch is not None:
                watch.last_run_status = "FAILED"
                watch.last_error = f"{type(exc).__name__}:{exc}"[:1000]
                session.commit()
        logger.exception("radar_watch_failed", extra={"watch_id": str(watch_id)})
        return 0


def run_once(settings: Settings) -> bool:
    watch_id = claim_due_watch()
    if watch_id is None:
        return False
    execute_watch(watch_id, settings)
    return True


def run_worker(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if settings.task_queue_provider != "postgres":
        raise RuntimeError("Radar watch worker requires TASK_QUEUE_PROVIDER=postgres")
    worker_id = f"{socket.gethostname()}:{uuid.uuid4()}"
    logger.info("radar_watch_worker_started", extra={"worker_id": worker_id})
    while True:
        worked = run_once(settings)
        if not worked:
            time.sleep(settings.radar_watch_poll_seconds)


if __name__ == "__main__":
    run_worker()
