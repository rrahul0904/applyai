import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.config import Config
from fastapi import Depends
from sqlalchemy import func, select

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class StorageObjectMetadata:
    size: int
    content_type: str | None
    etag: str | None = None


class ObjectStorageProvider(ABC):
    @property
    def supports_direct_upload(self) -> bool:
        return False

    def direct_upload_headers(self, *, content_type: str) -> dict[str, str]:
        return {"content-type": content_type}

    def create_presigned_put(
        self,
        *,
        key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> str:
        raise RuntimeError("Direct upload is not supported by this storage provider")

    @abstractmethod
    def put(self, *, key: str, content: BinaryIO, content_type: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, *, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, *, key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def head(self, *, key: str) -> StorageObjectMetadata:
        raise NotImplementedError


class LocalObjectStorageProvider(ObjectStorageProvider):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid storage key")
        return path

    def put(self, *, key: str, content: BinaryIO, content_type: str) -> None:
        del content_type
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            while chunk := content.read(1024 * 1024):
                output.write(chunk)

    def delete(self, *, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def get(self, *, key: str) -> bytes:
        return self._path(key).read_bytes()

    def head(self, *, key: str) -> StorageObjectMetadata:
        source = self._path(key)
        stat = source.stat()
        return StorageObjectMetadata(size=stat.st_size, content_type=None)


class S3ObjectStorageProvider(ObjectStorageProvider):
    """S3-compatible private object storage used by AWS S3 and Cloudflare R2.

    AWS deployments keep SSE-S3 (`AES256`) enabled. R2 deployments set
    `S3_SERVER_SIDE_ENCRYPTION=none`; R2 encrypts objects at rest but its S3 API does not accept
    the AWS `x-amz-server-side-encryption: AES256` PutObject header.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required for the S3 storage provider")
        self.bucket = settings.s3_bucket
        addressing_style = os.getenv("S3_ADDRESSING_STYLE", "auto").strip().lower()
        if addressing_style not in {"auto", "path", "virtual"}:
            raise RuntimeError("S3_ADDRESSING_STYLE must be auto, path, or virtual")

        credentials: dict[str, str] = {}
        if settings.s3_access_key_id and settings.s3_secret_access_key:
            credentials = {
                "aws_access_key_id": settings.s3_access_key_id,
                "aws_secret_access_key": settings.s3_secret_access_key,
            }
        self.server_side_encryption = settings.s3_server_side_encryption.strip()
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": addressing_style},
            ),
            **credentials,
        )

    @property
    def supports_direct_upload(self) -> bool:
        return True

    @property
    def _uses_sse_s3(self) -> bool:
        return self.server_side_encryption.casefold() == "aes256"

    def _put_params(self, *, key: str, content_type: str) -> dict[str, str]:
        params = {
            "Bucket": self.bucket,
            "Key": key,
            "ContentType": content_type,
        }
        if self._uses_sse_s3:
            params["ServerSideEncryption"] = "AES256"
        return params

    def direct_upload_headers(self, *, content_type: str) -> dict[str, str]:
        headers = {"content-type": content_type}
        if self._uses_sse_s3:
            headers["x-amz-server-side-encryption"] = "AES256"
        return headers

    def create_presigned_put(
        self,
        *,
        key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params=self._put_params(key=key, content_type=content_type),
            ExpiresIn=expires_in_seconds,
            HttpMethod="PUT",
        )

    def put(self, *, key: str, content: BinaryIO, content_type: str) -> None:
        extra_args = {"ContentType": content_type}
        if self._uses_sse_s3:
            extra_args["ServerSideEncryption"] = "AES256"
        self.client.upload_fileobj(
            content,
            self.bucket,
            key,
            ExtraArgs=extra_args,
        )

    def delete(self, *, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def get(self, *, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def head(self, *, key: str) -> StorageObjectMetadata:
        response = self.client.head_object(Bucket=self.bucket, Key=key)
        return StorageObjectMetadata(
            size=int(response["ContentLength"]),
            content_type=response.get("ContentType"),
            etag=response.get("ETag"),
        )


class DatabaseObjectStorageProvider(ObjectStorageProvider):
    """Hard-capped object storage inside the pilot's Neon Free Postgres project."""

    def __init__(self, settings: Settings) -> None:
        self.hard_limit_bytes = settings.max_database_object_storage_bytes

    def put(self, *, key: str, content: BinaryIO, content_type: str) -> None:
        from app.core.database import SessionLocal
        from app.zero_cost_models import DatabaseObject

        payload = content.read()
        with SessionLocal() as session:
            existing = session.get(DatabaseObject, key)
            existing_size = existing.size if existing is not None else 0
            current_size = int(
                session.scalar(select(func.coalesce(func.sum(DatabaseObject.size), 0))) or 0
            )
            if current_size - existing_size + len(payload) > self.hard_limit_bytes:
                raise RuntimeError("ZERO_COST_OBJECT_STORAGE_LIMIT")
            if existing is None:
                session.add(
                    DatabaseObject(
                        key=key,
                        content_type=content_type,
                        size=len(payload),
                        content=payload,
                    )
                )
            else:
                existing.content_type = content_type
                existing.size = len(payload)
                existing.content = payload
            session.commit()

    def delete(self, *, key: str) -> None:
        from app.core.database import SessionLocal
        from app.zero_cost_models import DatabaseObject

        with SessionLocal() as session:
            existing = session.get(DatabaseObject, key)
            if existing is not None:
                session.delete(existing)
                session.commit()

    def get(self, *, key: str) -> bytes:
        from app.core.database import SessionLocal
        from app.zero_cost_models import DatabaseObject

        with SessionLocal() as session:
            existing = session.get(DatabaseObject, key)
            if existing is None:
                raise FileNotFoundError(key)
            return bytes(existing.content)

    def head(self, *, key: str) -> StorageObjectMetadata:
        from app.core.database import SessionLocal
        from app.zero_cost_models import DatabaseObject

        with SessionLocal() as session:
            existing = session.get(DatabaseObject, key)
            if existing is None:
                raise FileNotFoundError(key)
            return StorageObjectMetadata(
                size=existing.size,
                content_type=existing.content_type,
            )


def get_object_storage(
    settings: Settings = Depends(get_settings),
) -> ObjectStorageProvider:
    if settings.object_storage_provider == "s3":
        return S3ObjectStorageProvider(settings)
    if settings.object_storage_provider == "postgres":
        return DatabaseObjectStorageProvider(settings)
    return LocalObjectStorageProvider(settings.local_storage_path)
