from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import AppException, ConflictError, ForbiddenError
from app.services.hermes_external import profile_skill_inventory_service as inventory_service
from app.services.hermes_external.hermes_api_server_client import HermesApiResponse
from app.services.hermes_skill.hermes_skill_authorization_service import HermesSkillAuthorizationService
from app.services.hermes_skill.permission_checker import PermissionChecker


def _prepare_host_data_dir(tmp_path: Path) -> Path:
    host_data_dir = tmp_path / "data" / "hermes"
    host_data_dir.mkdir(parents=True)
    (host_data_dir / ".env").write_text(
        "API_SERVER_ENABLED=true\nAPI_SERVER_KEY=test-key\n",
        encoding="utf-8",
    )
    (host_data_dir / "config.yaml").write_text("models: {}\n", encoding="utf-8")
    (host_data_dir / "SOUL.md").write_text("You are a helpful assistant.\n", encoding="utf-8")
    return host_data_dir


def _api_server_skills_payload() -> dict:
    return {
        "skills": [
            {"name": "arxiv", "category": "research", "description": "Search arxiv papers"},
            {"name": "web-search", "category": "web", "description": "Search the web"},
        ]
    }


@pytest.mark.asyncio
async def test_list_skill_tree_from_api_server(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_dir = host_data_dir / "profiles" / "researcher"
    profile_dir.mkdir(parents=True)
    (profile_dir / ".env").write_text("X=1\n", encoding="utf-8")

    async def fake_list_skills(self):
        return HermesApiResponse(status_code=200, ok=True, data=_api_server_skills_payload())

    with patch(
        "app.services.hermes_external.profile_skill_inventory_service.HermesApiServerClient.list_skills",
        fake_list_skills,
    ):
        result = await inventory_service.list_full_skill_inventory(
            "common-writer",
            "researcher",
            host_data_dir,
            "http://127.0.0.1:18789",
            str(host_data_dir / ".env"),
        )

    assert result.source_mode == "api_server_inventory"
    assert result.total == 2
    slugs = {item.slug for group in result.groups for item in group.items}
    assert slugs == {"arxiv", "web-search"}
    arxiv = next(item for group in result.groups for item in group.items if item.slug == "arxiv")
    assert arxiv.source == "api_server"
    assert arxiv.manageable is False
    assert arxiv.can_authorize is True
    assert arxiv.category == "research"


@pytest.mark.asyncio
async def test_list_skill_tree_api_server_not_configured(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_dir = host_data_dir / "profiles" / "researcher"
    profile_dir.mkdir(parents=True)
    (profile_dir / ".env").write_text("X=1\n", encoding="utf-8")

    with pytest.raises(ConflictError) as exc_info:
        await inventory_service.list_full_skill_inventory(
            "common-writer",
            "researcher",
            host_data_dir,
            None,
            str(host_data_dir / ".env"),
        )
    assert exc_info.value.message_key == "errors.hermes.api_server_not_configured"


@pytest.mark.asyncio
async def test_list_skill_tree_api_server_offline(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_dir = host_data_dir / "profiles" / "researcher"
    profile_dir.mkdir(parents=True)
    (profile_dir / ".env").write_text("X=1\n", encoding="utf-8")

    async def fake_list_skills(self):
        return HermesApiResponse(status_code=None, ok=False, data=None, error="offline")

    with patch(
        "app.services.hermes_external.profile_skill_inventory_service.HermesApiServerClient.list_skills",
        fake_list_skills,
    ):
        with pytest.raises(AppException) as exc_info:
            await inventory_service.list_full_skill_inventory(
                "common-writer",
                "researcher",
                host_data_dir,
                "http://127.0.0.1:18789",
                str(host_data_dir / ".env"),
            )
    assert exc_info.value.status_code == 503
    assert exc_info.value.message_key == "errors.hermes.api_server_offline"


@pytest.mark.asyncio
async def test_list_skill_tree_api_server_unauthorized(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_dir = host_data_dir / "profiles" / "researcher"
    profile_dir.mkdir(parents=True)
    (profile_dir / ".env").write_text("X=1\n", encoding="utf-8")

    async def fake_list_skills(self):
        return HermesApiResponse(status_code=401, ok=False, data=None, error="unauthorized")

    with patch(
        "app.services.hermes_external.profile_skill_inventory_service.HermesApiServerClient.list_skills",
        fake_list_skills,
    ):
        with pytest.raises(ForbiddenError) as exc_info:
            await inventory_service.list_full_skill_inventory(
                "common-writer",
                "researcher",
                host_data_dir,
                "http://127.0.0.1:18789",
                str(host_data_dir / ".env"),
            )
    assert exc_info.value.message_key == "errors.hermes.api_server_unauthorized"


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
