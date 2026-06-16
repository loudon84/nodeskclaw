import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.hermes_client_service import HermesClientService, DesktopContext


@pytest.mark.asyncio
async def test_readiness_check_all_pass():
    db = AsyncMock()
    svc = HermesClientService(db)
    resolution = MagicMock(
        agent_alias="common-writer",
        agent_id="agent-1",
        profile_id="writer",
        workspace_id="workspace-writer",
        runtime_status="enabled",
        health="ok",
        reason="matched_by_agent_alias",
    )
    skill = MagicMock(
        id="skill-db-1",
        skill_id="writer.article",
        tool_name="writer_article_generate",
        name="Writer",
        title="文章生成",
        is_active=True,
        is_mcp_exposed=True,
        input_schema={"type": "object"},
        extra_metadata={"ui_schema": {"requirement": {"widget": "textarea"}}},
    )
    installation = MagicMock(
        id="inst-1",
        agent_id="agent-1",
        profile_id="writer",
        workspace_id="workspace-writer",
    )
    mock_skill_result = MagicMock()
    mock_skill_result.scalar_one_or_none.return_value = skill
    mock_inst_result = MagicMock()
    mock_inst_result.scalar_one_or_none.return_value = installation
    db.execute = AsyncMock(side_effect=[mock_skill_result, mock_inst_result])

    with patch.object(svc.alias_resolver, "resolve", AsyncMock(return_value=resolution)):
        with patch.object(svc.runtime_svc, "get_runtime_state", AsyncMock(return_value={
            "profile_root_path_exists": True,
            "workspace_root_path_exists": True,
        })):
            with patch("app.services.hermes_skill.hermes_client_service.HermesSkillAuthorizationService") as authz_cls:
                authz = authz_cls.return_value
                authz.can_list = AsyncMock(return_value=True)
                authz.can_invoke = AsyncMock(return_value=True)
                with patch("app.services.hermes_skill.hermes_client_service.HermesQueuePolicyService") as queue_cls:
                    queue_cls.return_value.can_enqueue = AsyncMock(return_value=(True, None))
                    with patch.object(svc.audit, "log", AsyncMock()):
                        result = await svc.run_readiness_check(
                            "org-1",
                            "user-1",
                            agent_alias="common-writer",
                            tool_name="writer_article_generate",
                            desktop_ctx=DesktopContext(device_id="d1"),
                        )
    assert result["ready"] is True
    assert result["checks"]["agent_exists"] is True
    assert result["checks"]["skill_exists"] is True
    assert result["routing"]["agent_alias"] == "common-writer"


@pytest.mark.asyncio
async def test_readiness_check_agent_missing():
    db = AsyncMock()
    svc = HermesClientService(db)
    with patch.object(svc.alias_resolver, "resolve", AsyncMock(return_value=None)):
        with patch.object(svc.audit, "log", AsyncMock()):
            result = await svc.run_readiness_check(
                "org-1", "user-1", agent_alias="missing-agent",
            )
    assert result["ready"] is False
    assert result["checks"]["agent_exists"] is False
    assert len(result["errors"]) == 1
