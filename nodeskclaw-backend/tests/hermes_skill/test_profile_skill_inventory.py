from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.profile_extended import ProfileSkillItem
from app.services.hermes_external import profile_skill_inventory_service as inventory_service
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.hermes_skill.permission_checker import PermissionChecker


def _prepare_host_data_dir(tmp_path: Path) -> Path:
    host_data_dir = tmp_path / "data" / "hermes"
    host_data_dir.mkdir(parents=True)
    (host_data_dir / ".env").write_text("API_SERVER_ENABLED=true\n", encoding="utf-8")
    (host_data_dir / "config.yaml").write_text("models: {}\n", encoding="utf-8")
    (host_data_dir / "SOUL.md").write_text("You are a helpful assistant.\n", encoding="utf-8")
    return host_data_dir


def _runtime_json() -> str:
    return """
    [
      {"name": "arxiv", "category": "research", "source": "builtin", "trust": "builtin", "status": "enabled"},
      {"name": "writer-outline", "category": "", "source": "local", "trust": "local", "status": "enabled"}
    ]
    """


@pytest.mark.asyncio
async def test_list_skill_tree_from_runtime(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    writer_skills = host_data_dir / "profiles" / "researcher" / "skills" / "writer-outline"
    writer_skills.mkdir(parents=True)
    (writer_skills / "SKILL.md").write_text("# writer\n", encoding="utf-8")
    (host_data_dir / "profiles" / "researcher" / ".env").write_text("X=1\n", encoding="utf-8")

    async def fake_exec(container_name: str, profile: str, *, use_json: bool):
        assert container_name == "hermes-common-writer"
        assert profile == "researcher"
        if use_json:
            return 0, _runtime_json(), ""
        return 1, "", "table fallback failed"

    with patch.object(inventory_service, "_ensure_container_running", AsyncMock()), \
         patch.object(inventory_service, "_exec_runtime_command", side_effect=fake_exec):
        result = await inventory_service.list_full_skill_inventory(
            "common-writer",
            "researcher",
            host_data_dir,
            "hermes-common-writer",
        )

    assert result.source_mode == "runtime_inventory"
    slugs = {item.slug for group in result.groups for item in group.items}
    assert "arxiv" in slugs
    assert "writer-outline" in slugs
    writer = next(item for group in result.groups for item in group.items if item.slug == "writer-outline")
    assert writer.manageable is True
    assert writer.path is not None


@pytest.mark.asyncio
async def test_list_skill_tree_fallback_to_profile_dir(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    local_skill = host_data_dir / "profiles" / "researcher" / "skills" / "local-only"
    local_skill.mkdir(parents=True)
    (local_skill / "SKILL.md").write_text("# local\n", encoding="utf-8")
    (host_data_dir / "profiles" / "researcher" / ".env").write_text("X=1\n", encoding="utf-8")

    async def fake_exec(container_name: str, profile: str, *, use_json: bool):
        return 1, "", "hermes skills list failed: timeout"

    with patch.object(inventory_service, "_ensure_container_running", AsyncMock()), \
         patch.object(inventory_service, "_exec_runtime_command", side_effect=fake_exec):
        result = await inventory_service.list_full_skill_inventory(
            "common-writer",
            "researcher",
            host_data_dir,
            "hermes-common-writer",
        )

    assert result.source_mode == "profile_only_fallback"
    assert result.warnings
    slugs = {item.slug for group in result.groups for item in group.items}
    assert slugs == {"local-only"}


def test_merge_runtime_and_profile_local_skill():
    runtime_items = [
        inventory_service._runtime_item_from_fields(
            name="writer-outline",
            category="uncategorized",
            source_raw="local",
            trust_raw="local",
            status_raw="enabled",
        )
    ]
    local_items = [
        ProfileSkillItem(
            slug="writer-outline",
            name="Writer Outline",
            path="/data/hermes/profiles/researcher/skills/writer-outline",
            enabled=True,
            has_skill_md=True,
            source="profile",
        )
    ]
    merged = inventory_service._merge_runtime_and_local(runtime_items, local_items)
    assert len(merged) == 1
    item = merged[0]
    assert item.source == "local"
    assert item.manageable is True
    assert item.path == "/data/hermes/profiles/researcher/skills/writer-outline"
    assert item.has_skill_md is True


@pytest.mark.asyncio
async def test_user_subject_grant_can_invoke():
    db = AsyncMock()
    svc = HermesSkillAuthorizationService(db)
    with patch.object(PermissionChecker, "get_user_role", AsyncMock(return_value="member")), \
         patch.object(svc, "_user_grant_allows", AsyncMock(return_value=False)), \
         patch.object(svc, "_subject_grant_allows", AsyncMock(return_value=True)):
        assert await svc.can_invoke("org-1", "user-1", "skill-db", "arxiv") is True


@pytest.mark.asyncio
async def test_role_subject_grant_can_invoke():
    db = AsyncMock()
    svc = HermesSkillAuthorizationService(db)
    with patch.object(PermissionChecker, "get_user_role", AsyncMock(return_value="manager")), \
         patch.object(svc, "_user_grant_allows", AsyncMock(return_value=False)), \
         patch.object(svc, "_subject_grant_allows", AsyncMock(side_effect=lambda org, stype, sid, skill, perm, now: stype == "role")):
        assert await svc.can_invoke("org-1", "user-1", "skill-db", "arxiv") is True


@pytest.mark.asyncio
async def test_org_subject_grant_can_invoke():
    db = AsyncMock()
    svc = HermesSkillAuthorizationService(db)
    with patch.object(PermissionChecker, "get_user_role", AsyncMock(return_value="member")), \
         patch.object(svc, "_user_grant_allows", AsyncMock(return_value=False)), \
         patch.object(svc, "_subject_grant_allows", AsyncMock(side_effect=lambda org, stype, sid, skill, perm, now: stype == "org")):
        assert await svc.can_invoke("org-1", "user-1", "skill-db", "arxiv") is True


@pytest.mark.asyncio
async def test_permission_denied_without_grant():
    db = AsyncMock()
    svc = HermesSkillAuthorizationService(db)
    with patch.object(PermissionChecker, "get_user_role", AsyncMock(return_value="member")), \
         patch.object(svc, "_user_grant_allows", AsyncMock(return_value=False)), \
         patch.object(svc, "_subject_grant_allows", AsyncMock(return_value=False)):
        assert await svc.can_invoke("org-1", "user-1", "skill-db", "arxiv") is False
