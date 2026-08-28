"""Tests for release_integrity_service — healthy / stale / unavailable."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import release_integrity_service, release_manifest_service


def _manifest(**kb_fields):
    return {
        "schema_version": 1,
        "knowledge_sets": [
            {
                "knowledge_set_id": "set-1",
                "knowledge_bases": [
                    {
                        "knowledge_base_id": "kb-1",
                        **kb_fields,
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_hash_mismatch_unavailable():
    manifest = _manifest()
    stored_hash = "deadbeef"
    db = MagicMock()

    result = await release_integrity_service.evaluate(
        db,
        manifest,
        stored_hash,
    )

    assert result.status == "unavailable"
    assert "manifest_hash_mismatch" in result.reasons


@pytest.mark.asyncio
async def test_missing_model_revision_unavailable(monkeypatch):
    manifest = _manifest(knowledge_model_revision_id="model-rev-missing")
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    monkeypatch.setattr(
        "app.services.index_state_service.list_states_for_kb",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "app.services.runtime_binding_service.get_binding",
        AsyncMock(return_value=None),
    )

    result = await release_integrity_service.evaluate(db, manifest)

    assert result.status == "unavailable"
    assert any(reason.startswith("knowledge_model_revision_missing:") for reason in result.reasons)


@pytest.mark.asyncio
async def test_index_version_drift_stale(monkeypatch):
    manifest = _manifest(index_versions={"chunk": 1})
    state = SimpleNamespace(index_type="chunk", build_version=2, input_manifest_hash=None)
    db = MagicMock()
    db.get = AsyncMock(return_value=None)
    db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))

    monkeypatch.setattr(
        "app.services.index_state_service.list_states_for_kb",
        AsyncMock(return_value=[state]),
    )
    monkeypatch.setattr(
        "app.services.runtime_binding_service.get_binding",
        AsyncMock(return_value=None),
    )

    result = await release_integrity_service.evaluate(db, manifest)

    assert result.status == "stale"
    assert "index_version_drift:kb-1:chunk" in result.reasons


@pytest.mark.asyncio
async def test_matching_pins_healthy(monkeypatch):
    manifest = _manifest(
        knowledge_model_revision_id="model-rev-1",
        artifact_revision_id={"outline": "art-rev-1"},
        index_versions={"chunk": 2},
        input_manifest_hash="ihash-1",
        runtime_binding_id="bind-1",
        runtime_config_revision=4,
    )
    model_revision = SimpleNamespace(
        id="model-rev-1",
        deleted_at=None,
        knowledge_model_id="model-1",
    )
    model = SimpleNamespace(
        id="model-1",
        deleted_at=None,
        active_revision_id="model-rev-1",
    )
    artifact_revision = SimpleNamespace(id="art-rev-1", deleted_at=None)
    artifact = SimpleNamespace(artifact_type="outline", active_revision_id="art-rev-1")
    state = SimpleNamespace(index_type="chunk", build_version=2, input_manifest_hash="ihash-1")
    binding = SimpleNamespace(id="bind-1", config_revision=4)

    async def fake_get(model_cls, obj_id):
        if model_cls.__name__ == "KnowledgeModelRevision":
            return model_revision if obj_id == "model-rev-1" else None
        if model_cls.__name__ == "KnowledgeModel":
            return model if obj_id == "model-1" else None
        if model_cls.__name__ == "KnowledgeArtifactRevision":
            return artifact_revision if obj_id == "art-rev-1" else None
        return None

    db = MagicMock()
    db.get = AsyncMock(side_effect=fake_get)
    db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[artifact])))

    monkeypatch.setattr(
        "app.services.index_state_service.list_states_for_kb",
        AsyncMock(return_value=[state]),
    )
    monkeypatch.setattr(
        "app.services.runtime_binding_service.get_binding",
        AsyncMock(return_value=binding),
    )

    computed_hash = release_manifest_service.manifest_hash(manifest)
    result = await release_integrity_service.evaluate(db, manifest, computed_hash)

    assert result.status == "healthy"
    assert result.reasons == []
