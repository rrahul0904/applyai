from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

import boto3
from fastapi import Depends

from app.core.config import Settings, get_settings


class ObjectStorageProvider(ABC):
    @abstractmethod
    def put(self, *, key: str, content: BinaryIO, content_type: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, *, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, *, key: str) -> bytes:
        raise NotImplementedError


class LocalObjectStorageProvider(ObjectStorageProvider):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put(self, *, key: str, content: BinaryIO, content_type: str) -> None:
        del content_type
        destination = (self.root / key).resolve()
        if self.root not in destination.parents:
            raise ValueError("Invalid storage key")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as output:
            while chunk := content.read(1024 * 1024):
                output.write(chunk)

    def delete(self, *, key: str) -> None:
        destination = (self.root / key).resolve()
        if self.root not in destination.parents:
            raise ValueError("Invalid storage key")
        destination.unlink(missing_ok=True)

    def get(self, *, key: str) -> bytes:
        source = (self.root / key).resolve()
        if self.root not in source.parents:
            raise ValueError("Invalid storage key")
        return source.read_bytes()


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


def get_object_storage(
    settings: Settings = Depends(get_settings),
) -> ObjectStorageProvider:
    if settings.object_storage_provider == "s3":
        return S3ObjectStorageProvider(settings)
    return LocalObjectStorageProvider(settings.local_storage_path)
