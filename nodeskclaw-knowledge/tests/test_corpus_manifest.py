"""Corpus manifest tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import build_input_manifest_service


@pytest.mark.asyncio
async def test_compute_manifest_hash_changes_when_any_active_version_changes():
    sf_a = SimpleNamespace(id="sf_a", metadata_revision=1)
    version_a = SimpleNamespace(id="v1", ragflow_document_id="doc_a", deleted_at=None)
    sf_b = SimpleNamespace(id="sf_b", metadata_revision=2)
    version_b = SimpleNamespace(id="v8", ragflow_document_id="doc_b", deleted_at=None)
    kb = SimpleNamespace(id="kb1", org_id="o1")

    result1 = MagicMock()
    result1.all.return_value = [(sf_a, version_a), (sf_b, version_b)]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result1)

    hash1, items1, _ = await build_input_manifest_service.compute_manifest(db, kb)
    assert len(items1) == 2

    version_b2 = SimpleNamespace(id="v9", ragflow_document_id="doc_b2", deleted_at=None)
    result2 = MagicMock()
    result2.all.return_value = [(sf_a, version_a), (sf_b, version_b2)]
    db.execute = AsyncMock(return_value=result2)

    hash2, _items2, _ = await build_input_manifest_service.compute_manifest(db, kb)
    assert hash1 != hash2


def test_build_delta_detects_added_changed_removed():
    prev = [
        build_input_manifest_service.ManifestItem("sf1", "v1", 1, "d1"),
        build_input_manifest_service.ManifestItem("sf2", "v2", 1, "d2"),
    ]
    curr = [
        build_input_manifest_service.ManifestItem("sf1", "v1", 1, "d1"),
        build_input_manifest_service.ManifestItem("sf2", "v3", 2, "d3"),
        build_input_manifest_service.ManifestItem("sf3", "v4", 1, "d4"),
    ]
    delta = build_input_manifest_service.compute_build_delta(prev, curr)
    assert {i.source_file_id for i in delta.added} == {"sf3"}
    assert {i.source_file_id for i in delta.changed} == {"sf2"}
    assert delta.unchanged[0].source_file_id == "sf1"
