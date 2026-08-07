from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import time
import uuid

import httpx
from fastapi.testclient import TestClient

from app.ai.provider import DeterministicAIProvider
from app.core.config import get_settings
from app.core.email import send_email
from app.core.queue import Task, get_task_queue_for_type, sqs_client
from app.core.storage import S3ObjectStorageProvider
from app.main import app


DEV_EMAIL = "local.cleanroom@example.test"


def dev_headers() -> dict[str, str]:
    return {
        "x-applyai-dev-secret": os.environ["DEV_AUTH_SECRET"],
        "x-applyai-dev-user": DEV_EMAIL,
    }


def assert_local_s3() -> None:
    settings = get_settings()
    storage = S3ObjectStorageProvider(settings)
    key = f"cleanroom/{uuid.uuid4()}.txt"
    content = b"ApplyAI local clean-room S3 smoke"
    storage.put(key=key, content=io.BytesIO(content), content_type="text/plain")
    metadata = storage.head(key=key)
    assert metadata.size == len(content)
    assert storage.get(key=key) == content

    presigned_key = f"cleanroom/{uuid.uuid4()}-presigned.txt"
    url = storage.create_presigned_put(key=presigned_key, content_type="text/plain", expires_in_seconds=300)
    response = httpx.put(
        url,
        content=content,
        headers={"content-type": "text/plain", "x-amz-server-side-encryption": "AES256"},
        timeout=10.0,
    )
    response.raise_for_status()
    assert storage.get(key=presigned_key) == content
    storage.delete(key=key)
    storage.delete(key=presigned_key)


def assert_local_sqs() -> None:
    settings = get_settings()
    marker = str(uuid.uuid4())
    queue = get_task_queue_for_type(settings, task_type="LOCAL_CERT_SMOKE")
    queue.enqueue(Task(task_type="LOCAL_CERT_SMOKE", payload={"marker": marker}, idempotency_key=f"local-cert:{marker}"))
    client = sqs_client(region=settings.sqs_region)
    response = client.receive_message(QueueUrl=settings.sqs_queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=2)
    messages = response.get("Messages", [])
    assert messages, "LocalStack SQS did not return the smoke message"
    body = json.loads(messages[0]["Body"])
    assert body["payload"]["marker"] == marker
    client.delete_message(QueueUrl=settings.sqs_queue_url, ReceiptHandle=messages[0]["ReceiptHandle"])


def assert_local_email() -> None:
    subject = f"ApplyAI clean-room {uuid.uuid4()}"
    delivery = send_email(to_address=DEV_EMAIL, subject=subject, text_body="Mailpit delivery smoke")
    assert delivery.delivered
    base = os.getenv("MAILPIT_API_URL", "http://127.0.0.1:8025").rstrip("/")
    for _ in range(20):
        response = httpx.get(f"{base}/api/v1/messages", timeout=5.0)
        response.raise_for_status()
        if subject in response.text:
            return
        time.sleep(0.25)
    raise AssertionError("Mailpit did not capture the ApplyAI smoke email")


def assert_deterministic_ai() -> None:
    provider = DeterministicAIProvider()
    result = provider.generate_json(
        system_prompt="Return evidence-safe structured output.",
        user_payload={
            "evidence_catalog": {"profile.summary": "Verified summary", "job.description": "Data role"},
            "deterministic_match": {"match_score": 82, "decision": "PRIORITIZE"},
            "candidate": {"summary": "Verified summary"},
            "job": {"title": "Data Engineer", "company_name": "Example"},
        },
        task_type="AI_DEEP_MATCH",
        safety_identifier="local-cleanroom",
        output_schema={},
    )
    assert result.model == "deterministic-evidence-v1"
    assert result.output["ai_score"] == 82
    assert result.input_tokens is None and result.output_tokens is None


def stripe_signature(raw: bytes, secret: str) -> str:
    timestamp = int(time.time())
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + raw, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def assert_local_api_and_stripe() -> None:
    with TestClient(app) as client:
        ready = client.get("/ready")
        assert ready.status_code == 200, ready.text

        me = client.get("/api/v1/me", headers=dev_headers())
        assert me.status_code == 200, me.text
        user = me.json()
        user_id = user["id"]

        checkout = client.post("/api/v1/billing/checkout", headers=dev_headers(), json={"plan": "PRO"})
        assert checkout.status_code == 200, checkout.text
        checkout_payload = checkout.json()
        assert checkout_payload["provider"] == "stripe"
        assert checkout_payload["checkout_session_id"]

        webhook_secret = os.environ["STRIPE_WEBHOOK_SECRET"]
        event = {
            "id": f"evt_local_{uuid.uuid4().hex}",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": f"cs_local_{uuid.uuid4().hex}",
                    "customer": "cus_local_cleanroom",
                    "subscription": "sub_local_cleanroom",
                    "metadata": {"user_id": user_id, "plan": "PRO"},
                }
            },
        }
        raw = json.dumps(event, separators=(",", ":")).encode()
        webhook = client.post(
            "/api/v1/billing/webhook",
            content=raw,
            headers={"content-type": "application/json", "Stripe-Signature": stripe_signature(raw, webhook_secret)},
        )
        assert webhook.status_code == 200, webhook.text

        subscription = client.get("/api/v1/billing/subscription", headers=dev_headers())
        assert subscription.status_code == 200, subscription.text
        assert subscription.json()["plan"] == "PRO"
        assert subscription.json()["provider"] == "STRIPE"

        portal = client.post("/api/v1/billing/portal", headers=dev_headers())
        assert portal.status_code == 200, portal.text
        assert "portal_url" in portal.json()


def main() -> None:
    checks = [
        ("S3/LocalStack", assert_local_s3),
        ("SQS/LocalStack", assert_local_sqs),
        ("SMTP/Mailpit", assert_local_email),
        ("deterministic AI", assert_deterministic_ai),
        ("dev auth + Stripe mock + signed webhook", assert_local_api_and_stripe),
    ]
    for name, check in checks:
        check()
        print(f"PASS {name}")
    print("PASS ApplyAI local integration smoke")


if __name__ == "__main__":
    main()
