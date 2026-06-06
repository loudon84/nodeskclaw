"""Tests for Agent file download authorization."""
from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.services import file_reference_service, file_scan_service


class _ScalarResult:
    def __init__(self, value) -> None:
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ScalarsResult:
    def __init__(self, values: list) -> None:
        self._values = values

    def scalars(self):
        return self

    def all(self) -> list:
        return self._values


class _SequenceDb:
    def __init__(self, results: list) -> None:
        self._results = list(results)
        self.added: list = []
        self.flushed = False
        self.committed = False

    async def execute(self, _stmt):
        return self._results.pop(0)

    def add(self, obj) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushed = True
        for index, obj in enumerate(self.added, 1):
            if not getattr(obj, "id", None):
                obj.id = f"grant-{index}"

    async def commit(self) -> None:
        self.committed = True


def _grant(**overrides):
    data = {
        "id": "grant-1",
        "workspace_id": "ws-1",
        "message_id": "msg-1",
        "file_reference_id": "ref-1",
        "recipient_agent_id": "agent-1",
        "source": "shared_file",
        "file_id": "file-1",
        "display_name": "report.pdf",
        "file_size": 123,
        "content_type": "application/pdf",
        "permissions": ["download"],
        "status": "active",
        "revoked_at": None,
        "deleted_at": None,
        "last_accessed_at": None,
        "access_count": 0,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_assert_download_allowed_blocks_pending_scan() -> None:
    """Agent download must be rejected when scan_status is pending."""
    with pytest.raises(ForbiddenError) as exc:
        file_scan_service.assert_download_allowed("pending")

    assert exc.value.message_key == "errors.upload.file_scan_pending"


def test_assert_download_allowed_blocks_blocked_file() -> None:
    """Agent download must be rejected when file is blocked by scanner."""
    with pytest.raises(ForbiddenError) as exc:
        file_scan_service.assert_download_allowed("blocked")

    assert exc.value.message_key == "errors.upload.file_scan_blocked"


def test_assert_download_allowed_blocks_failed_scan() -> None:
    """Agent download must be rejected when scan failed."""
    with pytest.raises(ForbiddenError) as exc:
        file_scan_service.assert_download_allowed("failed")

    assert exc.value.message_key == "errors.upload.file_scan_failed"


def test_assert_download_allowed_permits_clean() -> None:
    """Download should succeed for clean files."""
    file_scan_service.assert_download_allowed("clean")


def test_assert_download_allowed_permits_skipped() -> None:
    """Download should succeed for skipped scan."""
    file_scan_service.assert_download_allowed("skipped")


async def test_agent_grant_rejects_missing_grant() -> None:
    """Grant not found should raise NotFoundError."""
    db = _SequenceDb([_ScalarResult(None)])

    with pytest.raises(NotFoundError) as exc:
        await file_reference_service.get_agent_grant_for_download(
            db,
            workspace_id="ws-1",
            grant_id="nonexistent",
            agent=SimpleNamespace(id="agent-1", workspace_id="ws-1"),
        )

    assert exc.value.message_key == "errors.upload.file_access_grant_not_found"


async def test_agent_grant_rejects_revoked_grant() -> None:
    """Revoked grant should raise ForbiddenError."""
    grant = _grant(revoked_at=datetime.now(timezone.utc))
    db = _SequenceDb([_ScalarResult(grant)])

    with pytest.raises(ForbiddenError) as exc:
        await file_reference_service.get_agent_grant_for_download(
            db,
            workspace_id="ws-1",
            grant_id="grant-1",
            agent=SimpleNamespace(id="agent-1", workspace_id="ws-1"),
        )

    assert "revoked" in exc.value.message_key or "grant" in exc.value.message_key


async def test_agent_grant_rejects_different_agent() -> None:
    """Agent ID mismatch should raise ForbiddenError."""
    grant = _grant(recipient_agent_id="agent-2")
    db = _SequenceDb([_ScalarResult(grant)])

    with pytest.raises(ForbiddenError) as exc:
        await file_reference_service.get_agent_grant_for_download(
            db,
            workspace_id="ws-1",
            grant_id="grant-1",
            agent=SimpleNamespace(id="agent-1", workspace_id="ws-1"),
        )

    assert exc.value.message_key == "errors.upload.file_access_agent_mismatch"


async def test_agent_grant_accepts_matching_agent() -> None:
    """Correct agent should get the grant back."""
    grant = _grant()
    db = _SequenceDb([
        _ScalarResult(grant),
        _ScalarResult(None),
        _ScalarResult("msg-1"),
    ])

    result = await file_reference_service.get_agent_grant_for_download(
        db,
        workspace_id="ws-1",
        grant_id="grant-1",
        agent=SimpleNamespace(id="agent-1", workspace_id="ws-1"),
    )

    assert result is grant


async def test_create_grants_includes_download_url(monkeypatch) -> None:
    """Generated grants include absolute stable download URLs."""
    monkeypatch.setattr(
        file_reference_service,
        "get_agent_file_download_base_url",
        lambda: "https://api.example.com/api/v1",
    )
    ref = SimpleNamespace(
        id="ref-1",
        workspace_id="ws-1",
        message_id="msg-1",
        source="shared_file",
        file_id="file-1",
        display_name="data.csv",
        file_size=456,
        content_type="text/csv",
        scan_status="clean",
        status="available",
        sort_order=0,
    )
    db = _SequenceDb([
        _ScalarsResult([ref]),
        _ScalarResult(None),
    ])

    payload = await file_reference_service.create_agent_grants_for_message(
        db,
        workspace_id="ws-1",
        message_id="msg-1",
        recipient_agent_id="agent-1",
    )

    assert len(payload) == 1
    assert payload[0]["download_url"].startswith("https://api.example.com/api/v1/")
    assert "agent-file-grants" in payload[0]["download_url"]
    assert payload[0]["file_id"] == "file-1"
    assert payload[0]["scan_status"] == "clean"


async def test_mark_grant_accessed_increments_counter() -> None:
    """Access tracking increments count and sets timestamp."""
    grant = _grant(access_count=5)
    db = _SequenceDb([])

    await file_reference_service.mark_agent_grant_accessed(db, grant)

    assert grant.access_count == 6
    assert grant.last_accessed_at is not None
    assert db.committed is True
