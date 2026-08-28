"""Tests for release_manifest_service — V1 schema / hash / parse."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestError
from app.services import release_manifest_service


def test_manifest_hash_stable():
    a = {"schema_version": 1, "b": 2, "a": 1}
    b = {"a": 1, "b": 2, "schema_version": 1}
    assert release_manifest_service.manifest_hash(a) == release_manifest_service.manifest_hash(b)


def test_parse_rejects_knowledge_set_ids():
    with pytest.raises(BadRequestError):
        release_manifest_service.parse(
            {
                "schema_version": 1,
                "knowledge_set_ids": ["s1"],
                "knowledge_sets": [{"knowledge_set_id": "s1", "knowledge_bases": []}],
            }
        )


def test_parse_rejects_top_level_knowledge_bases_without_sets():
    with pytest.raises(BadRequestError):
        release_manifest_service.parse(
            {
                "schema_version": 1,
                "knowledge_bases": [{"knowledge_base_id": "kb1"}],
            }
        )


def test_parse_accepts_v1_knowledge_sets():
    parsed = release_manifest_service.parse(
        {
            "schema_version": 1,
            "knowledge_sets": [
                {
                    "knowledge_set_id": "s1",
                    "knowledge_bases": [
                        {
                            "knowledge_base_id": "kb1",
                            "weight": 2.0,
                            "artifact_revision_id": {"outline": "rev-1"},
                        }
                    ],
                }
            ],
        }
    )
    assert parsed["knowledge_sets"][0]["knowledge_set_id"] == "s1"


@pytest.mark.asyncio
async def test_build_pins_artifact_revision_and_per_kb_weight(monkeypatch):
    member = SimpleNamespace(org_id="org-1", member_id="m1")
    app = SimpleNamespace(id="app-1", answer_model="gpt-4")
    kb = SimpleNamespace(
        id="kb-1",
        knowledge_model_id=None,
        active_build_profile_id="bp-1",
    )
    set_item = SimpleNamespace(knowledge_base_id="kb-1", weight=3.5)
    artifact = SimpleNamespace(
        artifact_type="outline",
        active_revision_id="art-rev-1",
        version=9,
    )
    state = SimpleNamespace(index_type="chunk", build_version=2, input_manifest_hash="ihash")

    db = MagicMock()
    db.scalars = AsyncMock(
        side_effect=[
            MagicMock(all=MagicMock(return_value=[set_item])),
            MagicMock(all=MagicMock(return_value=[artifact])),
        ]
    )
    db.get = AsyncMock(return_value=None)

    monkeypatch.setattr(
        "app.services.knowledge_application_service.list_bound_set_ids",
        AsyncMock(return_value=["set-1"]),
    )
    monkeypatch.setattr(
        "app.services.knowledge_set_service.list_bound_knowledge_bases",
        AsyncMock(return_value=[kb]),
    )
    monkeypatch.setattr(
        "app.services.runtime_binding_service.get_binding",
        AsyncMock(return_value=SimpleNamespace(id="bind-1", config_revision=4)),
    )
    monkeypatch.setattr(
        "app.services.index_state_service.list_states_for_kb",
        AsyncMock(return_value=[state]),
    )

    manifest = await release_manifest_service.build(
        db,
        member,
        app,
        release_version=1,
        retrieval_policy_revision_id="pol-1",
    )
    assert manifest["schema_version"] == 1
    kb_payload = manifest["knowledge_sets"][0]["knowledge_bases"][0]
    assert kb_payload["weight"] == 3.5
    assert kb_payload["artifact_revision_id"] == {"outline": "art-rev-1"}
    assert "artifact_versions" not in kb_payload
    assert "knowledge_set_ids" not in manifest
