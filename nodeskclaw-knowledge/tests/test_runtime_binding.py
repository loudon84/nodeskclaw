"""Runtime Binding backfill and resolve tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.models.enums import RuntimeBindingStatus
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.services import runtime_binding_service
from tests.test_runtime_adapter import _mock_probe_client


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
    client = _mock_probe_client()
    adapter = RagflowRuntimeAdapter(client=client)
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


def test_runtime_dataset_name():
    kb = SimpleNamespace(id="kb-123", name="My KB")
    assert runtime_binding_service.runtime_dataset_name(kb) == "nk:kb-123:My KB"


@pytest.mark.asyncio
async def test_create_dataset_idempotent_recovers_existing_dataset(monkeypatch):
    kb = SimpleNamespace(id="kb1", name="demo", org_id="o1")
    adapter = AsyncMock()
    adapter.client = AsyncMock()
    adapter.client.create_dataset = AsyncMock(side_effect=Exception("timeout"))
    adapter.client.list_datasets = AsyncMock(
        return_value=[SimpleNamespace(id="ds-recovered", name="nk:kb1:demo")]
    )
    monkeypatch.setattr(
        runtime_binding_service,
        "_find_dataset_id_by_prefix",
        AsyncMock(return_value="ds-recovered"),
    )
    from app.integrations.ragflow.exceptions import RagflowError

    adapter.client.create_dataset = AsyncMock(
        side_effect=RagflowError("timeout", message_key="errors.knowledge.ragflow_error")
    )
    dataset_id = await runtime_binding_service.create_dataset_idempotent(
        AsyncMock(),
        adapter,
        kb=kb,
        org_id="o1",
        embedding_model="bge-m3",
        chunk_method="naive",
        parser_config={},
        description=None,
    )
    assert dataset_id == "ds-recovered"


@pytest.mark.asyncio
async def test_compile_and_persist_desired_config(monkeypatch):
    kb = SimpleNamespace(
        id="kb1",
        org_id="o1",
        name="demo",
        embedding_model="bge-m3",
        chunk_method="naive",
        parser_config={},
        description="desc",
        knowledge_model_id=None,
    )
    binding = SimpleNamespace(
        desired_config=None,
        config_revision=0,
        capabilities={"supports_auto_questions": {"build_supported": True}},
    )
    profile = SimpleNamespace(index_types=["chunk", "question"])
    monkeypatch.setattr(
        "app.services.build_profile_service.resolve_profile_for_kb",
        AsyncMock(return_value=profile),
    )
    db = AsyncMock()
    db.flush = AsyncMock()
    desired = await runtime_binding_service.compile_and_persist_desired_config(db, kb, binding)
    assert desired["embedding_model"] == "bge-m3"
    assert desired["parser_config"].get("auto_questions") == 5
    assert binding.config_revision == 1


@pytest.mark.asyncio
async def test_reconcile_binding_config_in_sync(monkeypatch):
    from app.services import reconciliation_service

    kb = SimpleNamespace(id="kb1", org_id="o1", deleted_at=None)
    binding = SimpleNamespace(
        resource_id="ds1",
        capabilities={},
        desired_config=None,
        config_revision=0,
        observed_revision=0,
        drift_status="unknown",
        last_error=None,
        runtime_config=None,
        observed_config=None,
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=kb)
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    monkeypatch.setattr(reconciliation_service.advisory_lock, "kb_advisory_xact_lock", AsyncMock())
    monkeypatch.setattr(
        runtime_binding_service,
        "get_binding",
        AsyncMock(return_value=binding),
    )
    monkeypatch.setattr(
        runtime_binding_service,
        "compile_and_persist_desired_config",
        AsyncMock(
            return_value={
                "embedding_model": "bge-m3",
                "chunk_method": "naive",
                "parser_config": {},
                "name": "nk:kb1:demo",
            }
        ),
    )

    class FakeAdapter:
        async def get_dataset_runtime_config(self, _dataset_id):
            return {
                "embedding_model": "bge-m3",
                "chunk_method": "naive",
                "parser_config": {},
                "name": "nk:kb1:demo",
            }

        async def configure_index(self, *_args, **_kwargs):
            return None

        client = SimpleNamespace(update_dataset=AsyncMock())

    result = await reconciliation_service.reconcile_binding_config(db, "kb1", FakeAdapter())
    assert result["status"] == "success"
    assert result["drift_status"] == "in_sync"
