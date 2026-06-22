from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AppException, BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.schemas.hermes_instance_skill import HermesInstanceSkillItem, HermesInstanceSkillListResponse
from app.services.hermes_external import hermes_agent_mcp_gateway_service as mcp_gateway_service
from app.services.hermes_external import hermes_instance_skill_service as instance_skill_service
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


def _instance_skill_list(agent_profile: str = "common-writer") -> HermesInstanceSkillListResponse:
    return HermesInstanceSkillListResponse(
        agent_profile=agent_profile,
        gateway_url="http://127.0.0.1:18789",
        source_mode="api_server_default",
        total=2,
        skills=[
            HermesInstanceSkillItem(name="arxiv", category="research", description="Search arxiv papers"),
            HermesInstanceSkillItem(name="web-search", category="web", description="Search the web"),
        ],
        warnings=[],
        last_refreshed_at=datetime.now(timezone.utc),
    )


def _binding_record(tmp_path: Path, profile: str = "common-writer"):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    record = MagicMock()
    record.id = "rec-1"
    record.instance_id = "inst-1"
    record.profile_name = profile
    record.gateway_url = "http://127.0.0.1:18789"
    record.env_file = str(host_data_dir / ".env")
    return record


@pytest.mark.asyncio
async def test_list_skill_tree_from_api_server(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_dir = host_data_dir / "profiles" / "researcher"
    profile_dir.mkdir(parents=True)
    (profile_dir / ".env").write_text("X=1\n", encoding="utf-8")
    db = AsyncMock()

    with patch.object(
        instance_skill_service,
        "list_instance_skills",
        AsyncMock(return_value=_instance_skill_list()),
    ):
        result = await inventory_service.list_full_skill_inventory(
            db,
            "org-1",
            "common-writer",
            "researcher",
            host_data_dir,
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
    db = AsyncMock()

    with patch.object(
        instance_skill_service,
        "list_instance_skills",
        AsyncMock(side_effect=ConflictError(
            message="not configured",
            message_key="errors.hermes.api_server_not_configured",
        )),
    ):
        with pytest.raises(ConflictError) as exc_info:
            await inventory_service.list_full_skill_inventory(
                db,
                "org-1",
                "common-writer",
                "researcher",
                host_data_dir,
            )
    assert exc_info.value.message_key == "errors.hermes.api_server_not_configured"


@pytest.mark.asyncio
async def test_list_skill_tree_api_server_offline(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_dir = host_data_dir / "profiles" / "researcher"
    profile_dir.mkdir(parents=True)
    (profile_dir / ".env").write_text("X=1\n", encoding="utf-8")
    db = AsyncMock()

    with patch.object(
        instance_skill_service,
        "list_instance_skills",
        AsyncMock(side_effect=AppException(
            code=50301,
            error_code=50301,
            message="offline",
            message_key="errors.hermes.api_server_offline",
            status_code=503,
        )),
    ):
        with pytest.raises(AppException) as exc_info:
            await inventory_service.list_full_skill_inventory(
                db,
                "org-1",
                "common-writer",
                "researcher",
                host_data_dir,
            )
    assert exc_info.value.status_code == 503
    assert exc_info.value.message_key == "errors.hermes.api_server_offline"


@pytest.mark.asyncio
async def test_list_skill_tree_api_server_unauthorized(tmp_path: Path):
    host_data_dir = _prepare_host_data_dir(tmp_path)
    profile_dir = host_data_dir / "profiles" / "researcher"
    profile_dir.mkdir(parents=True)
    (profile_dir / ".env").write_text("X=1\n", encoding="utf-8")
    db = AsyncMock()

    with patch.object(
        instance_skill_service,
        "list_instance_skills",
        AsyncMock(side_effect=ForbiddenError(
            message="unauthorized",
            message_key="errors.hermes.api_server_unauthorized",
        )),
    ):
        with pytest.raises(ForbiddenError) as exc_info:
            await inventory_service.list_full_skill_inventory(
                db,
                "org-1",
                "common-writer",
                "researcher",
                host_data_dir,
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
