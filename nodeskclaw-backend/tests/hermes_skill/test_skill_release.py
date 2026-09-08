"""SkillRelease service unit tests (no DB required for digest helpers)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, ConflictError
from app.models.hermes_skill.skill_release import SkillReleaseStatus
from app.services.hermes_skill.skill_release_service import (
    SkillReleaseService,
    build_bundle_zip_bytes,
    bundle_descriptor_from_release,
    bundle_zip_path,
    compute_skill_content_digest,
    snapshot_hash,
)


def _skill(**overrides):
    base = {
        "id": "skill-db-1",
        "org_id": "org-1",
        "skill_id": "foo",
        "tool_name": "foo",
        "name": "foo",
        "title": "Foo",
        "description": "desc",
        "version": "1.0.0",
        "category": "ops",
        "input_schema": {"type": "object"},
        "output_schema": None,
        "output_policy": None,
        "extra_metadata": {"requires_approval": True},
        "tags": ["a"],
        "source_type": "hermes_api_server",
        "source_ref": "hermes://x",
        "canonical_path": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_compute_skill_content_digest_stable():
    skill = _skill()
    d1 = compute_skill_content_digest(skill)
    d2 = compute_skill_content_digest(skill)
    assert d1 == d2
    assert len(d1) == 64


def test_snapshot_hash_changes_with_digest():
    h1 = snapshot_hash(skill_release_id="r1", digest="aaa", route_snapshot={"route_type": "hermes_api_server"})
    h2 = snapshot_hash(skill_release_id="r1", digest="bbb", route_snapshot={"route_type": "hermes_api_server"})
    assert h1 != h2


@pytest.mark.asyncio
async def test_create_draft_rejects_duplicate_version():
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill = _skill()
    service.get_skill = AsyncMock(return_value=skill)

    existing_release = SimpleNamespace(id="rel-1", version="1.0.0")
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing_release
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ConflictError):
        await service.create_draft_from_skill(
            org_id="org-1",
            skill_id="foo",
            operator_user_id="user-1",
            version="1.0.0",
        )


@pytest.mark.asyncio
async def test_create_draft_stores_connector_and_knowledge_requirements():
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill = _skill()
    service.get_skill = AsyncMock(return_value=skill)

    no_existing = MagicMock()
    no_existing.scalar_one_or_none.return_value = None
    instance_row = MagicMock()
    instance = SimpleNamespace(id="inst-1", org_id="org-1")
    instance_row.scalar_one_or_none.return_value = instance
    db.execute = AsyncMock(side_effect=[no_existing, instance_row])
    db.add = MagicMock()
    db.flush = AsyncMock()

    release = await service.create_draft_from_skill(
        org_id="org-1",
        skill_id="foo",
        operator_user_id="user-1",
        connector_instance_ids=["inst-1"],
        knowledge_refs=["kb://doc-1", " "],
    )

    assert release.requirements["knowledge_refs"] == ["kb://doc-1"]
    assert len(release.requirements["connector_binding_ids"]) == 1


@pytest.mark.asyncio
async def test_deprecate_rejects_non_published():
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill = _skill()
    service.get_skill = AsyncMock(return_value=skill)
    draft = SimpleNamespace(
        id="rel-1",
        status=SkillReleaseStatus.DRAFT.value,
        skill_db_id=skill.id,
    )
    service._get_release = AsyncMock(return_value=draft)

    with pytest.raises(BadRequestError):
        await service.deprecate(org_id="org-1", skill_id="foo", release_id="rel-1")


@pytest.mark.asyncio
async def test_publish_chat_mode_success(tmp_path: Path, monkeypatch):
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill_dir = tmp_path / "skill-copy"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("hello bundle", encoding="utf-8")
    skill = _skill(canonical_path=str(skill_dir))
    service.get_skill = AsyncMock(return_value=skill)
    service.get_published_by_skill_db_id = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.hermes_skill.skill_release_service.settings.HERMES_SKILL_HUB_ROOT",
        str(tmp_path / "hub"),
    )

    draft = SimpleNamespace(
        id="rel-1",
        status=SkillReleaseStatus.DRAFT.value,
        skill_db_id=skill.id,
        version="1.0.0",
        digest=compute_skill_content_digest(skill),
        bundle_ref=None,
        bundle_sha256=None,
        bundle_size_bytes=None,
        input_schema={"type": "object", "properties": {"user_prompt": {"type": "string"}}},
        extra_metadata={"interactionMode": "chat", "promptField": "user_prompt"},
        published_at=None,
        published_by=None,
        deprecated_at=None,
    )
    service._get_release = AsyncMock(return_value=draft)

    published = await service.publish(org_id="org-1", skill_id="foo", release_id="rel-1", operator_user_id="user-1")
    assert published.status == SkillReleaseStatus.PUBLISHED.value
    assert published.bundle_ref
    assert published.bundle_sha256
    assert published.bundle_sha256 != published.digest
    assert published.bundle_size_bytes == len(build_bundle_zip_bytes(skill_dir))
    assert bundle_zip_path(published.bundle_ref).is_file()
    descriptor = bundle_descriptor_from_release(published)
    assert descriptor
    assert "releases/" not in str(descriptor)
    assert published.extra_metadata["supportsAttachments"] is False
    assert "annotations" in published.extra_metadata
    assert published.extra_metadata["annotations"]["riskLevel"] == "low"
    assert published.extra_metadata["annotations"]["requiresApproval"] is False
    assert published.extra_metadata["annotations"]["approvalMode"] == "none"


@pytest.mark.asyncio
async def test_publish_freezes_bundle_against_working_copy_changes(tmp_path: Path, monkeypatch):
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill_dir = tmp_path / "skill-copy"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("v1", encoding="utf-8")
    skill = _skill(canonical_path=str(skill_dir))
    service.get_skill = AsyncMock(return_value=skill)
    service.get_published_by_skill_db_id = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "app.services.hermes_skill.skill_release_service.settings.HERMES_SKILL_HUB_ROOT",
        str(tmp_path / "hub"),
    )

    draft = SimpleNamespace(
        id="rel-1",
        status=SkillReleaseStatus.DRAFT.value,
        skill_db_id=skill.id,
        version="1.0.0",
        digest=compute_skill_content_digest(skill),
        bundle_ref=None,
        bundle_sha256=None,
        bundle_size_bytes=None,
        input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}},
        extra_metadata={},
        published_at=None,
        published_by=None,
        deprecated_at=None,
    )
    service._get_release = AsyncMock(return_value=draft)
    published = await service.publish(org_id="org-1", skill_id="foo", release_id="rel-1", operator_user_id="user-1")
    frozen_sha = published.bundle_sha256

    (skill_dir / "SKILL.md").write_text("v2 changed", encoding="utf-8")
    republished = await service.publish(org_id="org-1", skill_id="foo", release_id="rel-1", operator_user_id="user-1")
    assert republished.bundle_sha256 == frozen_sha


@pytest.mark.asyncio
async def test_publish_rejects_missing_canonical_path():
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill = _skill(canonical_path=None)
    service.get_skill = AsyncMock(return_value=skill)
    draft = SimpleNamespace(
        id="rel-1",
        status=SkillReleaseStatus.DRAFT.value,
        skill_db_id=skill.id,
        version="1.0.0",
        digest=compute_skill_content_digest(skill),
        bundle_ref=None,
        bundle_sha256=None,
        bundle_size_bytes=None,
        input_schema={"type": "object", "properties": {"prompt": {"type": "string"}}},
        extra_metadata={},
    )
    service._get_release = AsyncMock(return_value=draft)

    with pytest.raises(BadRequestError, match="canonical_path"):
        await service.publish(org_id="org-1", skill_id="foo", release_id="rel-1", operator_user_id="user-1")


def test_bundle_zip_path_rejects_non_opaque_reference():
    with pytest.raises(BadRequestError, match="Bundle reference"):
        bundle_zip_path("../outside")


def test_build_bundle_rejects_symlink(tmp_path: Path):
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    skill_dir = tmp_path / "skill-copy"
    skill_dir.mkdir()
    try:
        (skill_dir / "linked-secret.txt").symlink_to(outside)
    except OSError:
        pytest.skip("当前平台不允许创建测试符号链接")

    with pytest.raises(BadRequestError, match="符号链接"):
        build_bundle_zip_bytes(skill_dir)


@pytest.mark.asyncio
async def test_publish_chat_mode_missing_prompt_field():
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill = _skill()
    service.get_skill = AsyncMock(return_value=skill)

    draft = SimpleNamespace(
        id="rel-1",
        status=SkillReleaseStatus.DRAFT.value,
        skill_db_id=skill.id,
        input_schema={"type": "object", "properties": {"user_prompt": {"type": "string"}}},
        extra_metadata={"interactionMode": "chat"},
    )
    service._get_release = AsyncMock(return_value=draft)

    with pytest.raises(BadRequestError) as exc_info:
        await service.publish(org_id="org-1", skill_id="foo", release_id="rel-1", operator_user_id="user-1")
    assert exc_info.value.message_key == "errors.skill.catalog.invalid_interaction_contract"


@pytest.mark.asyncio
async def test_publish_chat_mode_forbidden_routing_key():
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill = _skill()
    service.get_skill = AsyncMock(return_value=skill)

    draft = SimpleNamespace(
        id="rel-1",
        status=SkillReleaseStatus.DRAFT.value,
        skill_db_id=skill.id,
        input_schema={"type": "object", "properties": {"_routing": {"type": "string"}}},
        extra_metadata={"interactionMode": "chat", "promptField": "_routing"},
    )
    service._get_release = AsyncMock(return_value=draft)

    with pytest.raises(BadRequestError) as exc_info:
        await service.publish(org_id="org-1", skill_id="foo", release_id="rel-1", operator_user_id="user-1")
    assert exc_info.value.message_key == "errors.skill.catalog.invalid_interaction_contract"


@pytest.mark.asyncio
async def test_publish_chat_mode_non_string_field():
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill = _skill()
    service.get_skill = AsyncMock(return_value=skill)

    draft = SimpleNamespace(
        id="rel-1",
        status=SkillReleaseStatus.DRAFT.value,
        skill_db_id=skill.id,
        input_schema={"type": "object", "properties": {"prompt": {"type": "number"}}},
        extra_metadata={"interactionMode": "chat", "promptField": "prompt"},
    )
    service._get_release = AsyncMock(return_value=draft)

    with pytest.raises(BadRequestError) as exc_info:
        await service.publish(org_id="org-1", skill_id="foo", release_id="rel-1", operator_user_id="user-1")
    assert exc_info.value.message_key == "errors.skill.catalog.invalid_interaction_contract"


@pytest.mark.asyncio
async def test_publish_chat_mode_non_object_schema():
    db = AsyncMock()
    service = SkillReleaseService(db)
    skill = _skill()
    service.get_skill = AsyncMock(return_value=skill)

    draft = SimpleNamespace(
        id="rel-1",
        status=SkillReleaseStatus.DRAFT.value,
        skill_db_id=skill.id,
        input_schema={"type": "array"},
        extra_metadata={"interactionMode": "chat", "promptField": "prompt"},
    )
    service._get_release = AsyncMock(return_value=draft)

    with pytest.raises(BadRequestError) as exc_info:
        await service.publish(org_id="org-1", skill_id="foo", release_id="rel-1", operator_user_id="user-1")
    assert exc_info.value.message_key == "errors.skill.catalog.invalid_interaction_contract"
