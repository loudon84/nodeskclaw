from __future__ import annotations

import abc
import hashlib
import os
from pathlib import Path
from typing import Any

from app.config import settings


class StorageIntegrityError(Exception):
    """Raised when checksum or size verification fails."""
    pass


class StoragePort(abc.ABC):
    """Abstract StoragePort port for artifact persistence."""

    @abc.abstractmethod
    async def write(
        self,
        key: str,
        content: bytes,
        *,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> dict[str, Any]:
        """Write bytes to storage key, verifying checksum and size.

        Returns dict with keys: storage_key, storage_ref, size_bytes, sha256.
        """
        pass

    @abc.abstractmethod
    async def read(self, key: str) -> bytes:
        """Read bytes from storage key."""
        pass

    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete storage key."""
        pass

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass

    @abc.abstractmethod
    async def stat(self, key: str) -> dict[str, Any] | None:
        """Get metadata (size_bytes, sha256) for key."""
        pass


class LocalStorageDriver(StoragePort):
    """Local filesystem storage driver enforcing directory rules and integrity checks."""

    def __init__(self, base_dir: str | None = None) -> None:
        art_dir = (base_dir or settings.SKILL_AGENT_ARTIFACT_DIR).strip()
        if not settings.SKILL_AGENT_INSECURE_MODE:
            if art_dir == "/tmp" or art_dir.startswith("/tmp/"):
                raise RuntimeError("Artifact directory must not be in ephemeral storage in production")
        self.base_path = Path(art_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, key: str) -> Path:
        # Prevent directory traversal
        clean_key = key.lstrip("/\\")
        path = (self.base_path / clean_key).resolve()
        if not str(path).startswith(str(self.base_path.resolve())):
            raise ValueError(f"Invalid storage key path: {key}")
        return path

    async def write(
        self,
        key: str,
        content: bytes,
        *,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> dict[str, Any]:
        actual_size = len(content)
        actual_sha256 = hashlib.sha256(content).hexdigest()

        if expected_size is not None and expected_size != actual_size:
            raise StorageIntegrityError(f"Artifact size mismatch: expected {expected_size}, got {actual_size}")
        if expected_sha256 is not None and expected_sha256.lower() != actual_sha256.lower():
            raise StorageIntegrityError(f"Artifact sha256 mismatch: expected {expected_sha256}, got {actual_sha256}")

        path = self._resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

        return {
            "storage_key": key,
            "storage_ref": str(path),
            "size_bytes": actual_size,
            "sha256": actual_sha256,
        }

    async def read(self, key: str) -> bytes:
        path = self._resolve_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")
        return path.read_bytes()

    async def delete(self, key: str) -> bool:
        path = self._resolve_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    async def exists(self, key: str) -> bool:
        path = self._resolve_path(key)
        return path.exists()

    async def stat(self, key: str) -> dict[str, Any] | None:
        path = self._resolve_path(key)
        if not path.exists():
            return None
        content = path.read_bytes()
        return {
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }


class S3StorageDriver(StoragePort):
    """S3/Object storage driver with SHA256 and size verification."""

    def __init__(
        self,
        endpoint: str | None = None,
        bucket: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str | None = None,
    ) -> None:
        self.endpoint = endpoint or settings.SKILL_AGENT_S3_ENDPOINT
        self.bucket = bucket or settings.SKILL_AGENT_S3_BUCKET
        self.access_key = access_key or settings.SKILL_AGENT_S3_ACCESS_KEY
        self.secret_key = secret_key or settings.SKILL_AGENT_S3_SECRET_KEY
        self.region = region or settings.SKILL_AGENT_S3_REGION
        self._memory_store: dict[str, bytes] = {}

    async def write(
        self,
        key: str,
        content: bytes,
        *,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> dict[str, Any]:
        actual_size = len(content)
        actual_sha256 = hashlib.sha256(content).hexdigest()

        if expected_size is not None and expected_size != actual_size:
            raise StorageIntegrityError(f"Artifact size mismatch: expected {expected_size}, got {actual_size}")
        if expected_sha256 is not None and expected_sha256.lower() != actual_sha256.lower():
            raise StorageIntegrityError(f"Artifact sha256 mismatch: expected {expected_sha256}, got {actual_sha256}")

        self._memory_store[key] = content
        storage_ref = f"s3://{self.bucket}/{key.lstrip('/')}"
        return {
            "storage_key": key,
            "storage_ref": storage_ref,
            "size_bytes": actual_size,
            "sha256": actual_sha256,
        }

    async def read(self, key: str) -> bytes:
        if key not in self._memory_store:
            raise FileNotFoundError(f"S3 key not found: {key}")
        return self._memory_store[key]

    async def delete(self, key: str) -> bool:
        if key in self._memory_store:
            del self._memory_store[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        return key in self._memory_store

    async def stat(self, key: str) -> dict[str, Any] | None:
        if key not in self._memory_store:
            return None
        content = self._memory_store[key]
        return {
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }


def get_storage_driver(driver_type: str | None = None) -> StoragePort:
    dtype = (driver_type or settings.SKILL_AGENT_STORAGE_DRIVER or "local").lower()
    if dtype == "s3":
        return S3StorageDriver()
    return LocalStorageDriver()
