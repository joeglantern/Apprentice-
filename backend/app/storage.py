"""Object storage. Contabo S3 in production, MinIO locally, same client either way."""

from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath
from typing import BinaryIO, Protocol

import aioboto3

from app.config import Settings, get_settings

log = logging.getLogger(__name__)
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str | None) -> str:
    """Basename only, restricted charset, never empty, never a dot-only name."""
    base = PurePosixPath((name or "").replace("\\", "/")).name
    base = _SAFE.sub("_", base).lstrip(".")[:120]
    return base or "file"


def asset_file_key(source_project: str, asset_id: str, original_name: str | None) -> str:
    safe_project = _SAFE.sub("_", source_project)[:80] or "project"
    return f"assets/{safe_project}/{asset_id}/{safe_filename(original_name)}"


class Storage(Protocol):
    async def put(self, key: str, body: BinaryIO, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = aioboto3.Session()

    def _client(self):  # noqa: ANN202 - aioboto3 returns a context manager
        return self.session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key,
            aws_secret_access_key=self.settings.s3_secret_key,
            region_name=self.settings.s3_region,
        )

    async def ensure_bucket(self) -> None:
        async with self._client() as s3:
            try:
                await s3.head_bucket(Bucket=self.settings.s3_bucket)
            except Exception:  # noqa: BLE001 - botocore raises a generic ClientError
                log.info("creating bucket %s", self.settings.s3_bucket)
                await s3.create_bucket(Bucket=self.settings.s3_bucket)

    async def put(self, key: str, body: BinaryIO, content_type: str) -> None:
        async with self._client() as s3:
            await s3.upload_fileobj(
                body,
                self.settings.s3_bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )

    async def get(self, key: str) -> bytes:
        async with self._client() as s3:
            obj = await s3.get_object(Bucket=self.settings.s3_bucket, Key=key)
            return await obj["Body"].read()

    async def delete(self, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=self.settings.s3_bucket, Key=key)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage(get_settings())
    return _storage
