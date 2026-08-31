from __future__ import annotations

import io
import json
import os
import uuid

from app.core.config import Settings
from app.core.storage import S3ObjectStorageProvider


def main() -> None:
    required = [
        "S3_ENDPOINT_URL",
        "S3_BUCKET",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        print(
            json.dumps(
                {
                    "status": "BLOCKED_EXTERNAL_CONFIGURATION",
                    "missing": missing,
                },
                sort_keys=True,
            )
        )
        raise SystemExit(2)

    settings = Settings(
        app_env="development",
        object_storage_provider="s3",
        s3_endpoint_url=os.environ["S3_ENDPOINT_URL"],
        s3_bucket=os.environ["S3_BUCKET"],
        s3_region=os.getenv("S3_REGION", "auto"),
        s3_access_key_id=os.environ["S3_ACCESS_KEY_ID"],
        s3_secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
        s3_server_side_encryption=os.getenv("S3_SERVER_SIDE_ENCRYPTION", "none"),
    )
    storage = S3ObjectStorageProvider(settings)
    key = f"acceptance/{uuid.uuid4()}.txt"
    payload = b"ApplyAI R2 private storage acceptance\n"
    try:
        storage.put(key=key, content=io.BytesIO(payload), content_type="text/plain")
        metadata = storage.head(key=key)
        content = storage.get(key=key)
        if content != payload:
            raise RuntimeError("R2 round-trip content mismatch")
        if metadata.size != len(payload):
            raise RuntimeError("R2 round-trip size mismatch")
        presigned = storage.create_presigned_put(
            key=f"acceptance/{uuid.uuid4()}.txt",
            content_type="text/plain",
            expires_in_seconds=300,
        )
        if not presigned.startswith("https://"):
            raise RuntimeError("R2 presigned URL was not HTTPS")
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "bucket": settings.s3_bucket,
                    "round_trip_bytes": metadata.size,
                    "presigned_put_https": True,
                    "raw_object_public_url_tested": False,
                    "server_side_encryption_header": (
                        "AES256"
                        if settings.s3_server_side_encryption.casefold() == "aes256"
                        else None
                    ),
                },
                sort_keys=True,
            )
        )
    finally:
        try:
            storage.delete(key=key)
        except Exception:
            pass


if __name__ == "__main__":
    main()
