from __future__ import annotations

import abc
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.config import settings


class StorageIntegrityError(Exception):
    """Raised when checksum or size verification fails."""


class StorageProbeError(Exception):
    """Raised when readiness storage probe fails."""


PROBE_KEY_PREFIX = ".health-probe/"


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
        pass

    @abc.abstractmethod
    async def read(self, key: str) -> bytes:
        pass

    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        pass

    @abc.abstractmethod
    async def exists(self, key: str) -> bool:
        pass

    @abc.abstractmethod
    async def stat(self, key: str) -> dict[str, Any] | None:
        pass

    async def close(self) -> None:
        return None

    async def probe_isolation(self) -> dict[str, Any]:
        key = f"{PROBE_KEY_PREFIX}{uuid.uuid4().hex}"
        content = os.urandom(32)
        expected_sha256 = hashlib.sha256(content).hexdigest()
        expected_size = len(content)
        cleanup_failed = False
        try:
            wrote = await self.write(
                key,
                content,
                expected_sha256=expected_sha256,
                expected_size=expected_size,
            )
            read_back = await self.read(key)
            meta = await self.stat(key)
            if read_back != content:
                raise StorageIntegrityError("probe read content mismatch")
            if meta is None:
                raise StorageIntegrityError("probe stat missing after write")
            if meta["size_bytes"] != expected_size:
                raise StorageIntegrityError("probe stat size mismatch")
            if meta["sha256"].lower() != expected_sha256.lower():
                raise StorageIntegrityError("probe stat sha256 mismatch")
            if wrote.get("sha256", "").lower() != expected_sha256.lower():
                raise StorageIntegrityError("probe write sha256 mismatch")
            if wrote.get("size_bytes") != expected_size:
                raise StorageIntegrityError("probe write size mismatch")
            deleted = await self.delete(key)
            if not deleted:
                cleanup_failed = True
            if await self.exists(key):
                cleanup_failed = True
            return {
                "ok": True,
                "key": key,
                "size_bytes": expected_size,
                "sha256": expected_sha256,
                "cleanup_failed": cleanup_failed,
            }
        except Exception as exc:
            cleanup_error: Exception | None = None
            try:
                deleted = await self.delete(key)
                if not deleted and await self.exists(key):
                    cleanup_failed = True
            except Exception as cleanup_exc:
                cleanup_failed = True
                cleanup_error = cleanup_exc
            detail = f"{exc}; cleanup_failed={cleanup_failed}"
            if cleanup_error is not None:
                detail = f"{detail}; cleanup_error={cleanup_error}"
            raise StorageProbeError(detail) from exc


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


def _signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "aws4_request")


def _s3_uri_encode(component: str) -> str:
    return quote(component, safe="/-_.~")


class _S3HttpClient:
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> None:
        if not endpoint:
            raise ValueError("S3 endpoint is not configured")
        if not access_key or not secret_key:
            raise ValueError("S3 credentials are not configured")
        self.endpoint = endpoint.rstrip("/")
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region if region and region != "auto" else "us-east-1"
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))

    def _object_url(self, key: str) -> str:
        clean_key = key.lstrip("/")
        return f"{self.endpoint}/{self.bucket}/{_s3_uri_encode(clean_key)}"

    async def _request(self, method: str, key: str, body: bytes | None = None) -> httpx.Response:
        url = self._object_url(key)
        parsed = urlparse(url)
        host = parsed.netloc
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        date_stamp = amz_date[:8]
        payload = body or b""
        payload_hash = hashlib.sha256(payload).hexdigest()
        canonical_uri = f"/{self.bucket}/{_s3_uri_encode(key.lstrip('/'))}"
        canonical_headers = f"host:{host}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amz_date}\n"
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            [method, canonical_uri, "", canonical_headers, signed_headers, payload_hash]
        )
        credential_scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signing_key = _signing_key(self.secret_key, date_stamp, self.region, "s3")
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        authorization = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        headers = {
            "Host": host,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
            "Authorization": authorization,
        }
        if body is not None:
            headers["Content-Length"] = str(len(body))
        return await self._client.request(method, url, content=body, headers=headers)

    async def put_object(self, key: str, body: bytes) -> None:
        response = await self._request("PUT", key, body)
        if response.status_code not in (200, 201):
            raise StorageIntegrityError(f"S3 PUT failed: status={response.status_code}")

    async def get_object(self, key: str) -> bytes:
        response = await self._request("GET", key)
        if response.status_code == 404:
            raise FileNotFoundError(f"S3 key not found: {key}")
        if response.status_code != 200:
            raise StorageIntegrityError(f"S3 GET failed: status={response.status_code}")
        return response.content

    async def head_object(self, key: str) -> dict[str, Any] | None:
        response = await self._request("HEAD", key)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise StorageIntegrityError(f"S3 HEAD failed: status={response.status_code}")
        content_length = response.headers.get("content-length")
        etag = (response.headers.get("etag") or "").strip('"')
        size_bytes = int(content_length) if content_length is not None else None
        return {"size_bytes": size_bytes, "sha256": None, "etag": etag}

    async def delete_object(self, key: str) -> bool:
        response = await self._request("DELETE", key)
        if response.status_code in (200, 204, 404):
            return response.status_code != 404
        raise StorageIntegrityError(f"S3 DELETE failed: status={response.status_code}")

    async def close(self) -> None:
        await self._client.aclose()


class S3StorageDriver(StoragePort):
    """S3-compatible storage driver with SHA256 and size verification."""

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
        self._client = _S3HttpClient(
            self.endpoint,
            self.bucket,
            self.access_key,
            self.secret_key,
            self.region,
        )

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

        await self._client.put_object(key, content)
        storage_ref = f"s3://{self.bucket}/{key.lstrip('/')}"
        return {
            "storage_key": key,
            "storage_ref": storage_ref,
            "size_bytes": actual_size,
            "sha256": actual_sha256,
        }

    async def read(self, key: str) -> bytes:
        return await self._client.get_object(key)

    async def delete(self, key: str) -> bool:
        return await self._client.delete_object(key)

    async def exists(self, key: str) -> bool:
        meta = await self._client.head_object(key)
        return meta is not None

    async def stat(self, key: str) -> dict[str, Any] | None:
        meta = await self._client.head_object(key)
        if meta is None:
            return None
        content = await self.read(key)
        return {
            "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

    async def close(self) -> None:
        await self._client.close()


def get_storage_driver(driver_type: str | None = None) -> StoragePort:
    dtype = (driver_type or settings.SKILL_AGENT_STORAGE_DRIVER or "local").lower()
    if dtype == "s3":
        return S3StorageDriver()
    return LocalStorageDriver()
