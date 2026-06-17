import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.hermes_skill.agents_bind_router import (
    get_hermes_agent,
    list_hermes_agents,
    scan_existing_agents,
)
from app.core.exceptions import NotFoundError
from app.schemas.hermes_skill.hermes_agent_instance import ScanExistingAgentsRequest
from app.services.hermes_external.hermes_docker_binding_service import (
    BindScanItem,
    BindScanResult,
    HermesDockerBindingService,
)


def _user_org():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    return user, org


@pytest.mark.asyncio
async def test_list_hermes_agents_returns_summaries():
    user, org = _user_org()
    db = AsyncMock()
    record = MagicMock()
    record.id = "rec-1"
    record.profile_name = "common-writer"
    record.container_name = "hermes-common-writer"
    record.container_id = "cid"
    record.image = "hermes:latest"
    record.docker_status = "running"
    record.docker_health = "healthy"
    record.host_ip = "127.0.0.1"
    record.webui_port = 8900
    record.webui_url = "http://127.0.0.1:8900"
    record.gateway_port = 18900
    record.gateway_url = "http://127.0.0.1:18900"
    record.gateway_status = "online"
    record.gateway_runtime_status = "ready"
    record.mcp_status = "ready"
    record.instance_dir = "/data/instances/common-writer"
    record.data_dir = "/data/instances/common-writer/data/hermes"
    record.env_file = "/data/instances/common-writer/.env"
    record.compose_file = None
    record.compose_project = "hermes-common-writer"
    record.managed_mode = "external_docker"
    record.instance_id = None
    record.last_probe_at = None
    record.last_seen_at = None
    record.last_error = None

    with patch("app.api.hermes_skill.agents_bind_router.PermissionChecker.require_permission", AsyncMock()):
        with patch.object(
            HermesDockerBindingService,
            "list_instances_for_api",
            AsyncMock(return_value=[(record, None)]),
        ):
            response = await list_hermes_agents(
                include_unavailable=True,
                include_unbound=False,
                managed_mode=None,
                refresh=False,
                user_org=(user, org),
                db=db,
            )

    assert response["code"] == 0
    assert response["data"]["items"][0]["profile_name"] == "common-writer"
    assert response["data"]["items"][0]["runtime_status"] == "ready"


@pytest.mark.asyncio
async def test_scan_existing_agents_commits_and_returns_counts():
    user, org = _user_org()
    db = AsyncMock()
    scan_result = BindScanResult(
        scanned=1,
        bound=1,
        failed=0,
        items=[
            BindScanItem(
                id="rec-1",
                profile_name="common-writer",
                container_name="hermes-common-writer",
                docker_status="running",
                docker_health="healthy",
                webui_url="http://127.0.0.1:8900",
                gateway_url="http://127.0.0.1:18900",
                api_server_enabled=True,
                api_server_model_name="gpt-4",
                has_api_server_key=True,
                api_server_status="online",
                agent_call_status="callable",
                runtime_status="ready",
                mcp_status="ready",
                last_error=None,
            ),
        ],
    )

    with patch("app.api.hermes_skill.agents_bind_router.PermissionChecker.require_permission", AsyncMock()):
        with patch("app.api.hermes_skill.agents_bind_router.HermesDockerBindingService") as svc_cls:
            svc = svc_cls.return_value
            svc.scan_existing = AsyncMock(return_value=scan_result)
            with patch("app.api.hermes_skill.agents_bind_router.SkillAuditLogger") as audit_cls:
                audit_cls.return_value.log = AsyncMock()
                response = await scan_existing_agents(
                    ScanExistingAgentsRequest(),
                    user_org=(user, org),
                    db=db,
                )

    assert response["code"] == 0
    assert response["data"]["scanned"] == 1
    assert response["data"]["bound"] == 1
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_hermes_agent_not_found():
    user, org = _user_org()
    db = AsyncMock()

    with patch("app.api.hermes_skill.agents_bind_router.PermissionChecker.require_permission", AsyncMock()):
        with patch("app.api.hermes_skill.agents_bind_router.HermesDockerBindingService") as svc_cls:
            svc = svc_cls.return_value
            svc.get_by_profile = AsyncMock(return_value=None)
            with pytest.raises(NotFoundError):
                await get_hermes_agent("missing-profile", user_org=(user, org), db=db)
