from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import ForbiddenError, NotFoundError
from app.services import file_reference_service


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


def _ref(**overrides):
    data = {
        "id": "ref-1",
        "workspace_id": "ws-1",
        "message_id": "msg-1",
        "source": "shared_file",
        "file_id": "file-1",
        "display_name": "report.pdf",
        "file_size": 123,
        "content_type": "application/pdf",
        "scan_status": "blocked",
        "status": "available",
        "sort_order": 0,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


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


async def test_create_agent_grants_returns_workspace_scoped_stable_download_url(monkeypatch) -> None:
    monkeypatch.setattr(
        file_reference_service,
        "get_agent_file_download_base_url",
        lambda: "https://backend.example.com/api/v1",
    )
    db = _SequenceDb([
        _ScalarsResult([_ref()]),
        _ScalarResult(None),
    ])

    payload = await file_reference_service.create_agent_grants_for_message(
        db,
        workspace_id="ws-1",
        message_id="msg-1",
        recipient_agent_id="agent-1",
    )

    assert payload[0]["download_url"] == (
        "https://backend.example.com/api/v1/workspaces/ws-1/"
        "agent-file-grants/grant-1/download"
    )
    assert payload[0]["download_url_kind"] == "agent_grant"
    assert payload[0]["file_id"] == "file-1"
    assert payload[0]["scan_status"] == "blocked"
    assert db.added[0].recipient_agent_id == "agent-1"
    assert db.flushed is True


async def test_get_agent_grant_for_download_rejects_wrong_workspace() -> None:
    db = _SequenceDb([_ScalarResult(None)])

    with pytest.raises(NotFoundError) as exc:
        await file_reference_service.get_agent_grant_for_download(
            db,
            workspace_id="other-ws",
            grant_id="grant-1",
            agent=SimpleNamespace(id="agent-1", workspace_id="ws-1"),
        )

    assert exc.value.message_key == "errors.upload.file_access_grant_not_found"


async def test_get_agent_grant_for_download_rejects_recipient_mismatch() -> None:
    db = _SequenceDb([_ScalarResult(_grant(recipient_agent_id="agent-2"))])

    with pytest.raises(ForbiddenError) as exc:
        await file_reference_service.get_agent_grant_for_download(
            db,
            workspace_id="ws-1",
            grant_id="grant-1",
            agent=SimpleNamespace(id="agent-1", workspace_id="ws-1"),
        )

    assert exc.value.message_key == "errors.upload.file_access_agent_mismatch"


async def test_get_agent_grant_for_download_accepts_recipient_agent() -> None:
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


async def test_mark_agent_grant_accessed_updates_audit_counters() -> None:
    grant = _grant(access_count=2)
    db = _SequenceDb([])

    await file_reference_service.mark_agent_grant_accessed(db, grant)

    assert grant.last_accessed_at is not None
    assert grant.access_count == 3
    assert db.committed is True
