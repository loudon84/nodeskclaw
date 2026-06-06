import pytest

from app.services import storage_service


async def _collect(chunks):
    data = bytearray()
    async for chunk in chunks:
        data.extend(chunk)
    return bytes(data)


@pytest.fixture(autouse=True)
def local_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(storage_service.settings, "UPLOAD_STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage_service.settings, "LOCAL_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(storage_service.settings, "S3_ENDPOINT", "")
    monkeypatch.setattr(storage_service.settings, "S3_BUCKET", "")
    monkeypatch.setattr(storage_service.settings, "S3_ACCESS_KEY_ID", "")
    monkeypatch.setattr(storage_service.settings, "S3_SECRET_ACCESS_KEY", "")


@pytest.mark.asyncio
async def test_download_stream_supports_byte_ranges():
    key = await storage_service.upload_file(
        b"0123456789",
        "range.txt",
        "text/plain",
        "ws-range",
    )

    download = await storage_service.get_download_stream(key, "bytes=2-5")

    assert download.range.is_partial is True
    assert download.range.content_range == "bytes 2-5/10"
    assert download.range.length == 4
    assert await _collect(download.chunks) == b"2345"


@pytest.mark.asyncio
async def test_download_stream_rejects_invalid_ranges():
    key = await storage_service.upload_file(
        b"0123456789",
        "range.txt",
        "text/plain",
        "ws-range",
    )

    with pytest.raises(storage_service.DownloadRangeNotSatisfiableError) as exc:
        await storage_service.get_download_stream(key, "bytes=20-30")

    assert exc.value.size == 10


@pytest.mark.asyncio
async def test_copy_file_streams_to_new_local_object():
    source_key = await storage_service.upload_file(
        b"copy-content",
        "source.txt",
        "text/plain",
        "ws-copy",
    )

    target_key = await storage_service.copy_file(
        source_key,
        "target.txt",
        "text/plain",
        "ws-copy",
    )

    assert target_key != source_key
    assert await storage_service.download_file(target_key) == b"copy-content"
