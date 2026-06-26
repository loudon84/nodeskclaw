import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.skill_routing_service import RoutingResult, ROUTING_REASON_EXPLICIT_AGENT
from app.models.hermes_skill.hermes_task import TaskStatus


@pytest.mark.asyncio
async def test_call_tool_with_agent_alias_routing():
    db = AsyncMock()
    mapper = McpToolMapper(db)
    skill = MagicMock(skill_id="writer.article", id="skill-db-1", input_schema=None)
    skill.source_type = "hub"
    installation = MagicMock(
        id="inst-1",
        agent_id="agent-1",
        profile_id="writer",
        workspace_id="ws-1",
    )
    routing_result = RoutingResult(
        matched=True,
        installation=installation,
        skill=skill,
        reason=ROUTING_REASON_EXPLICIT_AGENT,
        installation_id="inst-1",
        skill_id="writer.article",
        agent_id="agent-1",
        profile_id="writer",
        workspace_id="ws-1",
    )
    task = MagicMock(
        id="task-1",
        task_no="TASK-0001",
        status=TaskStatus.QUEUED,
        event_url="/api/v1/hermes/tasks/task-1/events",
        artifact_url="/api/v1/hermes/tasks/task-1/artifacts",
    )
    resolution = MagicMock(agent_alias="common-writer")

    with patch.object(mapper, "_skill_to_tool_dict", AsyncMock()):
        with patch("app.services.hermes_skill.mcp_tool_mapper.PermissionChecker") as perm:
            perm.require_permission = AsyncMock()
            with patch("app.services.hermes_skill.mcp_tool_mapper.SkillRoutingService") as routing_cls:
                routing_cls.extract_routing.return_value = ({"requirement": "test"}, {"agent_alias": "common-writer"})
                routing_cls.return_value.get_exposed_skill = AsyncMock(return_value=skill)
                routing_cls.return_value.resolve_by_tool_name = AsyncMock(return_value=routing_result)
                with patch("app.services.hermes_skill.mcp_tool_mapper.AgentAliasResolver") as alias_cls:
                    alias = alias_cls.return_value
                    alias.enrich_routing = AsyncMock(return_value={
                        "agent_alias": "common-writer",
                        "agent_id": "agent-1",
                    })
                    alias.resolve = AsyncMock(return_value=resolution)
                    with patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService") as authz_cls:
                        authz_cls.return_value.can_invoke = AsyncMock(return_value=True)
                        with patch("app.services.hermes_skill.mcp_tool_mapper.TaskService") as task_cls:
                            task_cls.return_value.create_task = AsyncMock(return_value=task)
                            with patch("app.services.hermes_skill.skill_audit_logger.SkillAuditLogger") as audit_cls:
                                audit_cls.return_value.log = AsyncMock()
                                result = await mapper.call_tool(
                                    "writer_article_generate",
                                    {"requirement": "test", "_routing": {"agent_alias": "common-writer"}},
                                    "org-1",
                                    user_id="user-1",
                                    client_context={"client": "copilot-desktop"},
                                )
    assert result["agent_alias"] == "common-writer"
    assert result["event_token_url"] == "/api/v1/hermes/tasks/task-1/events-token"
    assert result["result_url"] == "/api/v1/hermes/tasks/task-1/result"
    task_cls.return_value.create_task.assert_awaited_once()
    create_kwargs = task_cls.return_value.create_task.await_args.kwargs
    assert create_kwargs["client_context"]["client"] == "copilot-desktop"
    assert create_kwargs["routing_metadata"]["agent_alias"] == "common-writer"
