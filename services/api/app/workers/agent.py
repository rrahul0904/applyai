from __future__ import annotations

import json
import logging
import threading
import time
import uuid

from app.agent_models import AgentRun
from app.agents.runtime import execute_agent_run
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.core.queue import resolve_agent_queue_url, sqs_client


logger = logging.getLogger("applyai.agent_worker")
_PROVIDER_CIRCUIT_FAILURE_THRESHOLD = 3
_PROVIDER_CIRCUIT_COOLDOWN_SECONDS = 60.0
_circuit_lock = threading.Lock()
_circuit_failures: dict[str, int] = {}
_circuit_open_until: dict[str, float] = {}


def _circuit_is_open(provider: str) -> bool:
    if provider == "deterministic":
        return False
    with _circuit_lock:
        until = _circuit_open_until.get(provider, 0.0)
        if until <= time.monotonic():
            _circuit_open_until.pop(provider, None)
            if until:
                _circuit_failures[provider] = 0
            return False
        return True


def _note_transient_provider_failure(provider: str) -> None:
    if provider == "deterministic":
        return
    with _circuit_lock:
        failures = _circuit_failures.get(provider, 0) + 1
        _circuit_failures[provider] = failures
        if failures >= _PROVIDER_CIRCUIT_FAILURE_THRESHOLD:
            _circuit_open_until[provider] = time.monotonic() + _PROVIDER_CIRCUIT_COOLDOWN_SECONDS


def _note_provider_success(provider: str) -> None:
    if provider == "deterministic":
        return
    with _circuit_lock:
        _circuit_failures[provider] = 0
        _circuit_open_until.pop(provider, None)


def _run_error_code(run_id: uuid.UUID) -> str | None:
    with SessionLocal() as session:
        row = session.get(AgentRun, run_id)
        return row.error_code if row else None


def process_message(body: str, settings: Settings) -> bool:
    try:
        message = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("agent_worker_invalid_json")
        return False
    if message.get("task_type") != "AGENT_RUN":
        logger.warning("agent_worker_unsupported_task", extra={"task_type": message.get("task_type")})
        return True
    run_value = (message.get("payload") or {}).get("run_id")
    try:
        run_id = uuid.UUID(str(run_value))
    except (TypeError, ValueError):
        logger.warning("agent_worker_invalid_run_id")
        return False

    if _circuit_is_open(settings.ai_provider):
        logger.warning("agent_provider_circuit_open", extra={"provider": settings.ai_provider})
        # Leave the message unacknowledged. SQS visibility supplies backpressure while
        # the local worker circuit cools down; no model fallback is attempted.
        return False

    worker_id = f"agent-worker:{uuid.uuid4()}"
    completed_or_terminal = execute_agent_run(run_id, settings, worker_id=worker_id)
    if completed_or_terminal:
        _note_provider_success(settings.ai_provider)
        return True

    # The runtime has already persisted a bounded retry and corresponding outbox event.
    # Inspect only the small error code to decide whether this worker should trip the
    # provider circuit; never duplicate the run payload in logs or memory.
    if _run_error_code(run_id) == "AI_PROVIDER_TRANSIENT":
        _note_transient_provider_failure(settings.ai_provider)
    # Acknowledge the original delivery so it cannot race the explicit durable retry.
    return True


def _visibility_heartbeat(*, client, queue_url: str, receipt_handle: str, settings: Settings, stop: threading.Event) -> None:
    while not stop.wait(settings.agent_sqs_visibility_heartbeat_seconds):
        try:
            client.change_message_visibility(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
                VisibilityTimeout=settings.agent_sqs_visibility_timeout_seconds,
            )
        except Exception:
            logger.exception("agent_worker_visibility_extension_failed")
            return


def run_worker(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    queue_url = resolve_agent_queue_url(settings)
    if settings.task_queue_provider != "sqs" or not queue_url:
        raise RuntimeError("Agent worker requires TASK_QUEUE_PROVIDER=sqs and a resolvable dedicated agent queue")
    client = sqs_client(region=settings.sqs_region)
    logger.info("agent_worker_started", extra={"visibility_timeout": settings.agent_sqs_visibility_timeout_seconds})
    while True:
        response = client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=settings.sqs_wait_time_seconds,
            VisibilityTimeout=settings.agent_sqs_visibility_timeout_seconds,
            AttributeNames=["ApproximateReceiveCount"],
        )
        for message in response.get("Messages", []):
            receipt_handle = message["ReceiptHandle"]
            stop = threading.Event()
            heartbeat = threading.Thread(
                target=_visibility_heartbeat,
                kwargs={"client": client, "queue_url": queue_url, "receipt_handle": receipt_handle, "settings": settings, "stop": stop},
                daemon=True,
            )
            heartbeat.start()
            acknowledged = False
            try:
                acknowledged = process_message(message.get("Body", ""), settings)
            except Exception:
                logger.exception("agent_worker_unexpected_failure")
            finally:
                stop.set()
                heartbeat.join(timeout=1)
            if acknowledged:
                client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)


if __name__ == "__main__":
    run_worker()
