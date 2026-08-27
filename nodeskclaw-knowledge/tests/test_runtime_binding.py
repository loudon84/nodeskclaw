"""Runtime Binding backfill and resolve tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.models.enums import RuntimeBindingStatus
from app.services import runtime_binding_service


@pytest.mark.asyncio
async def test_backfill_creates_binding_for_dataset_id(monkeypatch):
    kb = SimpleNamespace(
        id="kb1",
        org_id="o1",
        ragflow_dataset_id="ds1",
        deleted_at=None,
    )
    scalars = MagicMock()
    scalars.all.return_value = [kb]
    result = MagicMock()
    result.scalars.return_value = scalars
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()

    monkeypatch.setattr(runtime_binding_service, "get_binding", AsyncMock(return_value=None))
    upsert = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(runtime_binding_service, "upsert_ragflow_dataset_binding", upsert)

    stats = await runtime_binding_service.backfill_from_knowledge_bases(db)
    assert stats["created"] == 1
    assert stats["updated"] == 0
    upsert.assert_awaited_once()


@pytest.mark.asyncio
async def test_backfill_idempotent_when_binding_matches(monkeypatch):
    kb = SimpleNamespace(id="kb1", org_id="o1", ragflow_dataset_id="ds1", deleted_at=None)
    scalars = MagicMock()
    scalars.all.return_value = [kb]
    result = MagicMock()
    result.scalars.return_value = scalars
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()

    existing = SimpleNamespace(resource_id="ds1")
    monkeypatch.setattr(runtime_binding_service, "get_binding", AsyncMock(return_value=existing))

    stats1 = await runtime_binding_service.backfill_from_knowledge_bases(db)
    stats2 = await runtime_binding_service.backfill_from_knowledge_bases(db)
    assert stats1 == stats2
    assert stats1["skipped"] == 1
    assert stats1["created"] == 0


@pytest.mark.asyncio
async def test_get_dataset_id_prefers_binding_when_flag_enabled(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED", True)
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id="legacy", deleted_at=None)
    binding = SimpleNamespace(resource_id="from-binding", status=RuntimeBindingStatus.ready.value)
    monkeypatch.setattr(runtime_binding_service, "get_binding", AsyncMock(return_value=binding))
    db = AsyncMock()
    assert await runtime_binding_service.get_dataset_id(db, kb) == "from-binding"


@pytest.mark.asyncio
async def test_get_dataset_id_falls_back_to_legacy_when_flag_disabled(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED", False)
    kb = SimpleNamespace(id="kb1", ragflow_dataset_id="legacy", deleted_at=None)
    db = AsyncMock()
    assert await runtime_binding_service.get_dataset_id(db, kb) == "legacy"


@pytest.mark.asyncio
async def test_require_dataset_id_raises_when_missing(monkeypatch):
    monkeypatch.setattr(
        runtime_binding_service,
        "get_dataset_id",
        AsyncMock(return_value=None),
    )
    from app.core.exceptions import BadRequestError

    with pytest.raises(BadRequestError) as exc:
        await runtime_binding_service.require_dataset_id(AsyncMock(), SimpleNamespace(id="kb1"))
    assert exc.value.message_key == "errors.knowledge.kb_not_ready"


@pytest.mark.asyncio
async def test_require_dataset_id_returns_id(monkeypatch):
    monkeypatch.setattr(
        runtime_binding_service,
        "get_dataset_id",
        AsyncMock(return_value="ds-ready"),
    )
    assert await runtime_binding_service.require_dataset_id(AsyncMock(), SimpleNamespace(id="kb1")) == "ds-ready"


@pytest.mark.asyncio
async def test_probe_and_persist_updates_binding(monkeypatch):
    binding = SimpleNamespace(
        knowledge_base_id="kb1",
        capabilities={"supports_chunk": True},
        runtime_version=None,
        last_capability_probe_at=None,
        last_capability_probe_error=None,
    )
    monkeypatch.setattr(runtime_binding_service, "get_binding", AsyncMock(return_value=binding))
    client = AsyncMock()
    client.system_health = AsyncMock(return_value=True)
    client.get_system_version = AsyncMock(return_value="0.17.0")
    adapter = AsyncMock()
    adapter.client = client
    adapter.get_probe_snapshot = lambda: (None, None)
    db = AsyncMock()
    db.flush = AsyncMock()
    result = await runtime_binding_service.probe_and_persist_binding_capabilities(
        db,
        knowledge_base_id="kb1",
        adapter=adapter,
    )
    assert result.probe_error is None
    assert result.capabilities["supports_chunk"]["build_supported"] is True
    assert binding.last_capability_probe_at is not None
    assert binding.last_capability_probe_error is None
