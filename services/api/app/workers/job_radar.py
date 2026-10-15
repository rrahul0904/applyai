from __future__ import annotations

import json
import logging
import uuid

from app.core.config import Settings
from app.core.database import SessionLocal
from app.job_radar_models import JobScan
from app.job_radar_service import run_job_scan

logger = logging.getLogger("applyai.job_radar_worker")


def process_message(body: str, _settings: Settings) -> bool:
    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("job_radar_worker_invalid_json")
        return False
    if message.get("task_type") != "JOB_RADAR_SCAN":
        logger.warning(
            "job_radar_worker_unsupported_task",
            extra={"task_type": message.get("task_type")},
        )
        return True
    scan_value = (message.get("payload") or {}).get("scan_id")
    try:
        scan_id = uuid.UUID(str(scan_value))
    except (TypeError, ValueError):
        logger.warning("job_radar_worker_invalid_scan_id")
        return False

    with SessionLocal() as session:
        scan = session.get(JobScan, scan_id)
        if scan is None:
            logger.info("job_radar_worker_missing_scan", extra={"scan_id": str(scan_id)})
            return True
        return run_job_scan(session, scan_id=scan_id)
