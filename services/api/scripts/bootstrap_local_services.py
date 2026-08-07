from __future__ import annotations

import json
import os
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


ROOT = Path(__file__).resolve().parents[3]
LOCAL_DIR = ROOT / ".local"
ENV_FILE = LOCAL_DIR / "runtime.env"
REGION = os.getenv("AWS_REGION", "us-east-1")
ENDPOINT = os.getenv("LOCALSTACK_ENDPOINT_URL", "http://127.0.0.1:4566")
BUCKET = os.getenv("LOCAL_S3_BUCKET", "applyai-local-resumes")


def ensure_bucket(s3) -> None:
    try:
        s3.head_bucket(Bucket=BUCKET)
    except ClientError:
        s3.create_bucket(Bucket=BUCKET)
    s3.put_bucket_cors(
        Bucket=BUCKET,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedMethods": ["PUT", "GET", "HEAD"],
                    "AllowedOrigins": ["http://127.0.0.1:3000", "http://localhost:3000"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )


def ensure_queue(sqs, name: str, *, dlq_arn: str | None = None) -> str:
    attributes = {"VisibilityTimeout": "60"}
    if dlq_arn:
        attributes["RedrivePolicy"] = json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"})
    try:
        return sqs.get_queue_url(QueueName=name)["QueueUrl"]
    except ClientError:
        return sqs.create_queue(QueueName=name, Attributes=attributes)["QueueUrl"]


def queue_arn(sqs, queue_url: str) -> str:
    return sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]


def main() -> None:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)

    s3 = boto3.client(
        "s3",
        region_name=REGION,
        endpoint_url=ENDPOINT,
        config=Config(s3={"addressing_style": "path"}),
    )
    sqs = boto3.client("sqs", region_name=REGION, endpoint_url=ENDPOINT)

    ensure_bucket(s3)

    urls: dict[str, str] = {}
    for family in ("resume", "source", "ai"):
        dlq_url = ensure_queue(sqs, f"applyai-local-{family}-dlq")
        urls[f"{family}_dlq"] = dlq_url
        urls[family] = ensure_queue(sqs, f"applyai-local-{family}", dlq_arn=queue_arn(sqs, dlq_url))

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    values = {
        "ENVIRONMENT": "development",
        "DATABASE_URL": "postgresql+psycopg://applyai:applyai@127.0.0.1:55432/applyai_cleanroom",
        "TEST_DATABASE_URL": "postgresql+psycopg://applyai:applyai@127.0.0.1:55432/applyai_cleanroom",
        "E2E_DATABASE_URL": "postgresql+psycopg://applyai:applyai@127.0.0.1:55432/applyai_cleanroom",
        "WEB_ORIGIN": "http://127.0.0.1:3000",
        "AUTH_PROVIDER": "dev-test",
        "DEV_AUTH_ENABLED": "true",
        "DEV_AUTH_SECRET": "applyai-local-development-secret-2026",
        "INTERNAL_API_TOKEN": "applyai-local-internal-token-2026",
        "OBJECT_STORAGE_PROVIDER": "s3",
        "S3_BUCKET": BUCKET,
        "S3_REGION": REGION,
        "S3_ENDPOINT_URL": ENDPOINT,
        "S3_ADDRESSING_STYLE": "path",
        "TASK_QUEUE_PROVIDER": "sqs",
        "SQS_REGION": REGION,
        "SQS_ENDPOINT_URL": ENDPOINT,
        "SQS_QUEUE_URL": urls["resume"],
        "SQS_DLQ_URL": urls["resume_dlq"],
        "SOURCE_SQS_QUEUE_URL": urls["source"],
        "SOURCE_SQS_DLQ_URL": urls["source_dlq"],
        "AI_SQS_QUEUE_URL": urls["ai"],
        "AI_SQS_DLQ_URL": urls["ai_dlq"],
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_DEFAULT_REGION": REGION,
        "AI_PROVIDER": "deterministic",
        "BILLING_PROVIDER": "stripe",
        "STRIPE_API_BASE_URL": "http://127.0.0.1:12111",
        "STRIPE_SECRET_KEY": "sk_test_applyai_local",
        "STRIPE_PRICE_PRO": "price_applyai_local_pro",
        "STRIPE_PRICE_TEAM": "price_applyai_local_team",
        "STRIPE_WEBHOOK_SECRET": "whsec_applyai_local_cleanroom",
        "EMAIL_PROVIDER": "smtp",
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": "1025",
        "SMTP_STARTTLS": "false",
        "EMAIL_FROM": "no-reply@applyai.local",
        "MAILPIT_API_URL": "http://127.0.0.1:8025",
    }
    ENV_FILE.write_text("\n".join(f"export {key}={value}" for key, value in values.items()) + "\n", encoding="utf-8")
    print(f"Local clean-room resources are ready. Environment written to {ENV_FILE}")
    for family in ("resume", "source", "ai"):
        print(f"{family}: {urls[family]}")


if __name__ == "__main__":
    main()
