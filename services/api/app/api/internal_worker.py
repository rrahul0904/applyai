from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.workers.postgres import drain_bounded

router = APIRouter(prefix="/internal/worker", tags=["internal-worker"])


def require_worker_drain_secret(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Settings:
    expected = settings.worker_drain_secret
    authorization = request.headers.get("authorization", "")
    scheme, _, supplied = authorization.partition(" ")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WORKER_DRAIN_NOT_CONFIGURED",
                "message": "Scheduled worker drain is not configured",
            },
        )
    if (
        scheme.lower() != "bearer"
        or not supplied
        or not secrets.compare_digest(supplied, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "WORKER_DRAIN_UNAUTHORIZED",
                "message": "Worker drain authorization is required",
            },
        )
    return settings


@router.post("/drain")
def drain_worker(
    settings: Settings = Depends(require_worker_drain_secret),
) -> dict[str, int | str]:
    if settings.task_queue_provider != "postgres":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "WORKER_QUEUE_NOT_READY",
                "message": "Bounded worker drain requires the PostgreSQL task queue",
            },
        )
    completed = drain_bounded(settings, maximum_tasks=settings.worker_drain_batch_size)
    return {
        "status": "ok",
        "completed_tasks": completed,
        "maximum_tasks": settings.worker_drain_batch_size,
    }
