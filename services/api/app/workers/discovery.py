from __future__ import annotations

import json
import logging
import uuid

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.job_source_models import JobSourceDiscovery
from app.jobs.company_discovery import process_company_discovery_record
from app.jobs.discovery import process_discovery_record


logger = logging.getLogger("applyai.discovery_worker")
TERMINAL_ACK_STATUSES = {"VERIFIED", "DISCOVERED", "REJECTED", "BLOCKED"}


def process_message(body: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("discovery_worker_invalid_json")
        return False

    task_type = message.get("task_type")
    if task_type not in {"JOB_URL_IMPORT", "SOURCE_DISCOVERY"}:
        return False
    discovery_value = (message.get("payload") or {}).get("discovery_id")
    try:
        discovery_id = uuid.UUID(str(discovery_value))
    except (TypeError, ValueError):
        logger.warning("discovery_worker_invalid_discovery_id")
        return False

    with SessionLocal() as session:
        record = session.get(JobSourceDiscovery, discovery_id)
        if record is None:
            logger.warning("discovery_worker_missing_record", extra={"discovery_id": str(discovery_id)})
            return True
        if record.status in TERMINAL_ACK_STATUSES:
            return True

    if task_type == "SOURCE_DISCOVERY":
        process_company_discovery_record(discovery_id, settings=settings)
    else:
        process_discovery_record(discovery_id, settings=settings)

    with SessionLocal() as session:
        record = session.get(JobSourceDiscovery, discovery_id)
        if record is None:
            return True
        if record.status in TERMINAL_ACK_STATUSES:
            logger.info(
                "discovery_worker_completed",
                extra={
                    "discovery_id": str(discovery_id),
                    "status": record.status,
                    "task_type": task_type,
                },
            )
            return True
        # FAILED remains retryable and eventually reaches the configured SQS DLQ.
        return False
