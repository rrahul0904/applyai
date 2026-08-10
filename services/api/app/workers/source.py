from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.agents.triggers import queue_scouts_for_job, source_agent_trigger_config
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.queue import sqs_client
from app.durability_models import JobIngestionRun
from app.job_quality_models import IngestionCostObservation
from app.job_source_models import JobSourceRegistry
from app.jobs.registry import run_registered_source
from app.jobs.verifier import verify_job_source_url
from app.models import Job, JobSource, JobSourceLink
from app.workers.discovery import process_message as process_discovery_message


logger = logging.getLogger("applyai.source_worker")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _queue_new_job_agents(
    *,
    session,
    source: JobSourceRegistry,
    run: JobIngestionRun,
    counts: dict[str, int],
    settings: Settings,
) -> int:
    enabled, candidate_limit = source_agent_trigger_config(source.configuration)
    if not enabled or counts.get("created", 0) <= 0:
        return 0
    created_job_ids = list(
        session.scalars(
            select(Job.id)
            .join(JobSourceLink, JobSourceLink.job_id == Job.id)
            .join(JobSource, JobSource.id == JobSourceLink.job_source_id)
            .where(
                JobSource.checkpoint["source_registry_id"].astext == str(source.id),
                Job.first_seen_at >= run.started_at,
                Job.status == "ACTIVE",
            )
            .distinct()
            .order_by(Job.id)
            .limit(max(1, counts.get("created", 0) * 2))
        )
    )
    queued = 0
    for job_id in created_job_ids:
        queued += len(
            queue_scouts_for_job(
                session,
                job_id=job_id,
                trigger_type="JOB_CREATED",
                settings=settings,
                max_candidates=candidate_limit,
            )
        )
    return queued


def process_source_ingest(payload: dict, settings: Settings) -> bool:
    try:
        source_id = uuid.UUID(str(payload.get("source_id")))
    except (TypeError, ValueError):
        return True
    lease_token = str(payload.get("lease_token") or f"source-retry:{source_id}")
    dispatched_at = _parse_datetime(payload.get("dispatched_at"))

    with SessionLocal() as session:
        source = session.get(JobSourceRegistry, source_id)
        if source is None:
            return True
        if dispatched_at and source.last_success_at and source.last_success_at >= dispatched_at:
            return True
        now = utcnow()
        if source.locked_by and source.locked_by != lease_token and source.lease_expires_at and source.lease_expires_at >= now:
            return False
        source.locked_at = now
        source.locked_by = lease_token
        source.lease_expires_at = now + timedelta(seconds=settings.job_source_lease_seconds)
        session.commit()

    started = time.monotonic()
    try:
        counts = run_registered_source(source_id, settings=settings, expected_worker_id=lease_token)
    except Exception:
        logger.exception("source_ingest_failed", extra={"source_id": str(source_id)})
        return False

    worker_seconds = Decimal(str(round(time.monotonic() - started, 4)))
    queued_agent_runs = 0
    with SessionLocal() as session:
        source = session.get(JobSourceRegistry, source_id)
        run = session.scalar(
            select(JobIngestionRun)
            .where(JobIngestionRun.source_id == source_id)
            .order_by(JobIngestionRun.started_at.desc(), JobIngestionRun.id.desc())
            .limit(1)
        )
        if run is not None:
            existing = session.scalar(select(IngestionCostObservation).where(IngestionCostObservation.run_id == run.id))
            if existing is None:
                session.add(
                    IngestionCostObservation(
                        run_id=run.id,
                        source_id=source_id,
                        worker_seconds=worker_seconds,
                        network_bytes=0,
                        source_postings=counts["fetched"],
                        canonical_changes=counts["created"] + counts["updated"] + counts["closed"],
                        estimated_cost_usd=None,
                    )
                )
            if source is not None:
                queued_agent_runs = _queue_new_job_agents(
                    session=session,
                    source=source,
                    run=run,
                    counts=counts,
                    settings=settings,
                )
            session.commit()
    logger.info(
        "source_ingest_completed",
        extra={
            "source_id": str(source_id),
            "duration_seconds": float(worker_seconds),
            "counts": counts,
            "queued_agent_runs": queued_agent_runs,
        },
    )
    return True


def process_message(body: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        return False
    task_type = message.get("task_type")
    payload = message.get("payload") or {}
    if task_type == "SOURCE_INGEST":
        return process_source_ingest(payload, settings)
    if task_type == "SOURCE_VERIFY":
        try:
            source_id = uuid.UUID(str(payload.get("job_source_id")))
        except (TypeError, ValueError):
            return True
        try:
            verify_job_source_url(source_id, settings=settings)
            return True
        except Exception:
            logger.exception("source_verify_failed", extra={"job_source_id": str(source_id)})
            return False
    if task_type == "SOURCE_DISCOVERY":
        return process_discovery_message(body, settings)
    return True


def _heartbeat(client, queue_url: str, receipt_handle: str, settings: Settings, stop: threading.Event) -> None:
    while not stop.wait(settings.source_sqs_visibility_heartbeat_seconds):
        try:
            client.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=settings.source_sqs_visibility_timeout_seconds,
            )
        except Exception:
            logger.exception("source_worker_visibility_extension_failed")
            return


def run_worker(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    queue_url = settings.source_sqs_queue_url or settings.sqs_queue_url
    if settings.task_queue_provider != "sqs" or not queue_url:
        raise RuntimeError("Source worker requires an SQS source queue")
    client = sqs_client(region=settings.sqs_region)
    logger.info("source_worker_started")
    while True:
        response = client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=settings.sqs_wait_time_seconds,
            VisibilityTimeout=settings.source_sqs_visibility_timeout_seconds,
            AttributeNames=["ApproximateReceiveCount"],
        )
        for message in response.get("Messages", []):
            receipt_handle = message["ReceiptHandle"]
            stop = threading.Event()
            heartbeat = threading.Thread(
                target=_heartbeat,
                args=(client, queue_url, receipt_handle, settings, stop),
                daemon=True,
            )
            heartbeat.start()
            acknowledged = False
            try:
                acknowledged = process_message(message.get("Body", ""), settings)
            except Exception:
                logger.exception("source_worker_unexpected_failure")
            finally:
                stop.set()
                heartbeat.join(timeout=1)
            if acknowledged:
                client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


if __name__ == "__main__":
    run_worker()
