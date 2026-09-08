from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock

import pytest

from app.services.storage_port import (
    LocalStorageDriver,
    S3StorageDriver,
    StorageIntegrityError,
    StoragePort,
    StorageProbeError,
)


@pytest.mark.asyncio
async def test_probe_isolation_local_roundtrip(tmp_path):
    driver = LocalStorageDriver(base_dir=str(tmp_path))
    result = await driver.probe_isolation()
    assert result["ok"] is True
    assert result["cleanup_failed"] is False
    probe_dir = tmp_path / ".health-probe"
    assert not probe_dir.exists() or not any(probe_dir.iterdir())


@pytest.mark.asyncio
async def test_probe_isolation_detects_read_mismatch(tmp_path, monkeypatch):
    driver = LocalStorageDriver(base_dir=str(tmp_path))

    async def _bad_read(key: str) -> bytes:
        return b"wrong"

    monkeypatch.setattr(driver, "read", _bad_read)
    with pytest.raises(StorageProbeError):
        await driver.probe_isolation()


@pytest.mark.asyncio
async def test_local_storage_integrity_checks(tmp_path):
    driver = LocalStorageDriver(base_dir=str(tmp_path))
    content = b"sample-binary-payload"
    import hashlib

    correct_sha256 = hashlib.sha256(content).hexdigest()
    res = await driver.write(
        "r1/a1.bin",
        content,
        expected_sha256=correct_sha256,
        expected_size=len(content),
    )
    assert res["size_bytes"] == len(content)
    assert res["sha256"] == correct_sha256

    with pytest.raises(StorageIntegrityError, match="sha256 mismatch"):
        await driver.write("r1/a2.bin", content, expected_sha256="bad-sha256")

    with pytest.raises(StorageIntegrityError, match="size mismatch"):
        await driver.write("r1/a3.bin", content, expected_size=999)


@pytest.mark.asyncio
async def test_s3_stat_hashes_bytes_instead_of_trusting_etag():
    driver = S3StorageDriver(
        endpoint="http://minio.test",
        bucket="artifacts",
        access_key="access",
        secret_key="secret",
        region="us-east-1",
    )
    content = b"authoritative-content"
    driver._client.head_object = AsyncMock(
        return_value={"size_bytes": len(content), "sha256": "0" * 64, "etag": "0" * 64}
    )
    driver._client.get_object = AsyncMock(return_value=content)

    metadata = await driver.stat("run-1/output.bin")

    assert metadata == {"size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    driver._client.get_object.assert_awaited_once_with("run-1/output.bin")
    await driver.close()


@pytest.mark.asyncio
async def test_probe_surfaces_cleanup_failure_after_primary_failure():
    class CleanupFailingStorage(StoragePort):
        async def write(self, key, content, **kwargs):
            return {"size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}

        async def read(self, key):
            raise RuntimeError("primary read failure")

        async def delete(self, key):
            raise RuntimeError("cleanup delete failure")

        async def exists(self, key):
            return True

        async def stat(self, key):
            return None

    with pytest.raises(StorageProbeError, match="cleanup_failed"):
        await CleanupFailingStorage().probe_isolation()


@pytest.mark.asyncio
async def test_s3_driver_close_releases_http_client():
    driver = S3StorageDriver(
        endpoint="http://minio.test",
        bucket="artifacts",
        access_key="access",
        secret_key="secret",
        region="us-east-1",
    )
    driver._client.close = AsyncMock()

    await driver.close()

    driver._client.close.assert_awaited_once()
