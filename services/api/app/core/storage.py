from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import boto3
from fastapi import Depends

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
    def __init__(self, settings: Settings) -> None:
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required for the S3 storage provider")
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url,
        )

    @property
    def supports_direct_upload(self) -> bool:
        return True

    def create_presigned_put(
        self,
        *,
        key: str,
        content_type: str,
        expires_in_seconds: int,
    ) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type,
                "ServerSideEncryption": "AES256",
            },
            ExpiresIn=expires_in_seconds,
            HttpMethod="PUT",
        )

    def put(self, *, key: str, content: BinaryIO, content_type: str) -> None:
        self.client.upload_fileobj(
            content,
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type, "ServerSideEncryption": "AES256"},
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


def get_object_storage(
    settings: Settings = Depends(get_settings),
) -> ObjectStorageProvider:
    if settings.object_storage_provider == "s3":
        return S3ObjectStorageProvider(settings)
    return LocalObjectStorageProvider(settings.local_storage_path)
