"""MinIO S3 upload and signed download URL creation."""

from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from .config import ArtifactSettings

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")

try:
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:

    class BotoCoreError(Exception):
        pass

    class ClientError(BotoCoreError):
        pass


class S3Client(Protocol):
    def put_object(self, **kwargs: Any) -> Any: ...

    def generate_presigned_url(self, client_method: str, **kwargs: Any) -> str: ...


@dataclass(frozen=True)
class UploadResult:
    name: str
    content_type: str
    object_key: str
    url: str
    size_bytes: int
    checksum_sha256: str
    expires_at: str
    required: bool
    ok: bool
    error: str | None = None


def sanitize_name(name: str) -> str:
    return _SAFE_NAME.sub("_", Path(name).name or "artifact.bin")[:200]


def build_object_key(
    settings: ArtifactSettings, run_id: str, checksum_sha256: str, name: str
) -> str:
    safe_run_id = _SAFE_NAME.sub("_", run_id.strip())[:120] or "run"
    parts = [
        part
        for part in (
            settings.prefix,
            "instances",
            settings.instance_id,
            "runs",
            safe_run_id,
        )
        if part
    ]
    return "/".join((*parts, f"{checksum_sha256}-{sanitize_name(name)}"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _content_type(path: Path) -> str:
    content_type, _ = mimetypes.guess_type(path.name)
    return content_type or "application/octet-stream"


def _build_s3_client(settings: ArtifactSettings) -> S3Client:
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for the hermes-output-artifacts plugin"
        ) from exc
    return boto3.client(
        "s3",
        endpoint_url=settings.endpoint,
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        region_name=settings.region,
        config=Config(
            s3={"addressing_style": settings.addressing_style},
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=60,
        ),
    )


class MinioUploader:
    def __init__(
        self, settings: ArtifactSettings, client: S3Client | None = None
    ) -> None:
        self._settings = settings
        self._client = client

    def upload(self, run_id: str, path: Path, required: bool) -> UploadResult:
        path = Path(path)
        name = sanitize_name(path.name)
        content_type = _content_type(path)
        if not path.is_file():
            return UploadResult(
                name,
                content_type,
                "",
                "",
                0,
                "",
                "",
                required,
                False,
                "not a regular file",
            )
        size_bytes = path.stat().st_size
        if size_bytes > self._settings.max_single_bytes:
            return UploadResult(
                name,
                content_type,
                "",
                "",
                size_bytes,
                "",
                "",
                required,
                False,
                f"artifact exceeds max_single_bytes={self._settings.max_single_bytes}",
            )
        checksum_sha256 = _sha256(path)
        object_key = build_object_key(self._settings, run_id, checksum_sha256, name)
        expires_at = (
            datetime.now(UTC)
            + timedelta(seconds=self._settings.presign_expires_seconds)
        ).isoformat()
        try:
            client = self._client or _build_s3_client(self._settings)
            with path.open("rb") as file_handle:
                client.put_object(
                    Bucket=self._settings.bucket,
                    Key=object_key,
                    Body=file_handle,
                    ContentType=content_type,
                    ContentLength=size_bytes,
                    Metadata={"sha256": checksum_sha256, "run_id": run_id},
                )
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._settings.bucket, "Key": object_key},
                ExpiresIn=self._settings.presign_expires_seconds,
            )
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                raise ValueError("MinIO did not return an absolute presigned URL")
            return UploadResult(
                name,
                content_type,
                object_key,
                url,
                size_bytes,
                checksum_sha256,
                expires_at,
                required,
                True,
            )
        except (BotoCoreError, ClientError, OSError, ValueError, RuntimeError) as exc:
            return UploadResult(
                name,
                content_type,
                object_key,
                "",
                size_bytes,
                checksum_sha256,
                "",
                required,
                False,
                str(exc),
            )
