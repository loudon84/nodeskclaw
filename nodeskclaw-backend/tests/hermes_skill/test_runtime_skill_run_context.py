from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, ForbiddenError
from app.api.internal_edge import _revalidate_agent_run_session
from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService


def _request(**kwargs):
    base = dict(
        org_id="org-1",
        user_id="user-1",
        tool_name="writer_article_generate",
        runtime_skill_id="writer",
        agent_profile="writer",
        hermes_agent_instance_id="inst-1",
        agent_id="agent-1",
        arguments={"prompt": "hi"},
        client_context={},
        output_policy={"artifact_mode": "pull_only"},
        task_source="org_mcp",
        skill_id="skill-1",
        entrypoint="mcp_skill_gateway",
    )
    base.update(kwargs)
    return StartRuntimeSkillRunRequest(**base)


@pytest.mark.asyncio
async def test_build_context_prompt_first_has_no_workspace_descriptor():
    db = AsyncMock()
    service = RuntimeSkillRunService(db)
    with patch.object(
        RuntimeSkillRunService,
        "_resolve_member_id",
        new=AsyncMock(return_value="member-1"),
    ), patch.object(
        RuntimeSkillRunService,
        "_assert_workspace_proof",
        new=AsyncMock(),
    ) as proof:
        ctx = await service._build_authorized_execution_context(
            _request(workspace_id=None),
            {"knowledge_refs": [], "connector_binding_refs": []},
        )
    proof.assert_not_awaited()
    assert all(d.get("type") != "workspace" for d in ctx.get("descriptors") or [])


@pytest.mark.asyncio
async def test_assert_workspace_proof_rejects_cross_org():
    db = AsyncMock()
    service = RuntimeSkillRunService(db)
    user = MagicMock(is_active=True)
    workspace = MagicMock(org_id="org-other", id="ws-1")
    result = MagicMock()
    result.scalar_one_or_none.return_value = workspace
    db.get = AsyncMock(return_value=user)
    db.execute = AsyncMock(return_value=result)

    with patch(
        "app.services.workspace_member_service.check_workspace_access",
        new=AsyncMock(),
    ) as acl:
        with pytest.raises(ForbiddenError) as exc:
            await service._assert_workspace_proof("ws-1", "org-1", "user-1")
    assert exc.value.message_key == "errors.run.workspace_org_mismatch"
    acl.assert_not_awaited()


@pytest.mark.asyncio
async def test_assert_workspace_proof_rejects_missing_or_deleted():
    db = AsyncMock()
    service = RuntimeSkillRunService(db)
    user = MagicMock(is_active=True)
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.get = AsyncMock(return_value=user)
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(ForbiddenError) as exc:
        await service._assert_workspace_proof("ws-missing", "org-1", "user-1")
    assert exc.value.message_key == "errors.run.workspace_proof_denied"


@pytest.mark.asyncio
async def test_assert_workspace_proof_calls_acl_for_same_org():
    db = AsyncMock()
    service = RuntimeSkillRunService(db)
    user = MagicMock(is_active=True)
    workspace = MagicMock(org_id="org-1", id="ws-1")
    result = MagicMock()
    result.scalar_one_or_none.return_value = workspace
    db.get = AsyncMock(return_value=user)
    db.execute = AsyncMock(return_value=result)

    with patch(
        "app.services.workspace_member_service.check_workspace_access",
        new=AsyncMock(return_value=None),
    ) as acl:
        proof = await service._assert_workspace_proof("ws-1", "org-1", "user-1")
    acl.assert_awaited_once()
    assert proof["type"] == "workspace"
    assert proof["stable_id"] == "ws-1"


@pytest.mark.asyncio
async def test_start_rejects_client_context_injection():
    db = AsyncMock()
    service = RuntimeSkillRunService(db)
    with patch.object(
        RuntimeSkillRunService,
        "_resolve_release_meta",
        new=AsyncMock(return_value={"knowledge_refs": [], "connector_binding_refs": []}),
    ):
        with pytest.raises(BadRequestError):
            await service.start(
                _request(client_context={"download_url": "https://example.com/secret"})
            )


@pytest.mark.asyncio
async def test_start_rejects_expanded_knowledge_refs():
    db = AsyncMock()
    service = RuntimeSkillRunService(db)
    with patch.object(
        RuntimeSkillRunService,
        "_resolve_release_meta",
        new=AsyncMock(return_value={"knowledge_refs": ["ks-1"], "connector_binding_refs": []}),
    ):
        with pytest.raises(ForbiddenError):
            await service.start(
                _request(client_context={"knowledge_refs": ["ks-1", "ks-2"]})
            )


@pytest.mark.asyncio
async def test_start_fails_closed_when_knowledge_proof_denied():
    db = AsyncMock()
    db.add = MagicMock()
    task = MagicMock()
    task.id = "run-abc"
    task.output_policy = {}

    with patch("app.services.hermes_skill.runtime_skill_run_service.settings") as mock_settings, \
         patch("app.services.hermes_skill.runtime_skill_run_service.TaskService") as task_cls, \
         patch.object(
             RuntimeSkillRunService,
             "_resolve_release_meta",
             new=AsyncMock(return_value={"knowledge_refs": ["ks-1"], "connector_binding_refs": []}),
         ), \
         patch.object(
             RuntimeSkillRunService,
             "_resolve_member_id",
             new=AsyncMock(return_value="member-1"),
         ), \
         patch.object(
             RuntimeSkillRunService,
             "_fetch_knowledge_proofs",
             new=AsyncMock(return_value={"ks-1": {"set_id": "ks-1", "allowed": False, "auth_version": ""}}),
         ):
        mock_settings.KNOWLEDGE_SERVICE_BASE_URL = "http://knowledge.test"
        mock_settings.KNOWLEDGE_SERVICE_TOKEN = "token"
        mock_settings.SKILL_AGENT_ENABLED = True
        task_cls.return_value.create_task = AsyncMock(return_value=task)

        with pytest.raises(ForbiddenError):
            await RuntimeSkillRunService(db).start(_request())

    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_revalidate_rejects_workspace_authorization_version_change():
    service = RuntimeSkillRunService(AsyncMock())
    with patch.object(RuntimeSkillRunService, "_resolve_member_id", new=AsyncMock(return_value="member-1")), \
         patch.object(
             RuntimeSkillRunService,
             "_assert_workspace_proof",
             new=AsyncMock(return_value={"stable_id": "ws-1", "auth_version": "new"}),
         ):
        with pytest.raises(ForbiddenError, match="Workspace 授权版本不一致"):
            await service.revalidate_execution_context(
                org_id="org-1",
                user_id="user-1",
                context_version=2,
                execution_context={
                    "context_version": 2,
                    "descriptors": [{"type": "workspace", "stable_id": "ws-1", "auth_version": "old"}],
                },
            )


@pytest.mark.asyncio
async def test_revalidate_rejects_attachment_authorization_version_change():
    service = RuntimeSkillRunService(AsyncMock())
    with patch.object(RuntimeSkillRunService, "_resolve_member_id", new=AsyncMock(return_value="member-1")), \
         patch.object(
             RuntimeSkillRunService,
             "_assert_workspace_proof",
             new=AsyncMock(return_value={"stable_id": "ws-1", "auth_version": "ws"}),
         ), \
         patch.object(
             RuntimeSkillRunService,
             "_assert_attachment_proofs",
             new=AsyncMock(return_value=[{"stable_id": "chat:file-1", "auth_version": "new"}]),
         ):
        with pytest.raises(ForbiddenError, match="附件授权版本不一致"):
            await service.revalidate_execution_context(
                org_id="org-1",
                user_id="user-1",
                context_version=2,
                execution_context={
                    "context_version": 2,
                    "descriptors": [
                        {"type": "workspace", "stable_id": "ws-1", "auth_version": "ws"},
                        {"type": "attachment", "stable_id": "chat:file-1", "auth_version": "old"},
                    ],
                },
            )


@pytest.mark.asyncio
async def test_revalidate_rejects_inactive_or_missing_subject():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(ForbiddenError, match="组织成员不存在"):
        await RuntimeSkillRunService(db).revalidate_execution_context(
            org_id="org-1",
            user_id="user-1",
            context_version=2,
            execution_context={"context_version": 2, "descriptors": []},
        )


@pytest.mark.asyncio
async def test_edge_session_revalidation_proxies_to_agent_runtime(monkeypatch):
    response = MagicMock(status_code=200)
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.post = AsyncMock(return_value=response)
    monkeypatch.setattr("app.api.internal_edge.settings.SKILL_AGENT_ENABLED", True)
    monkeypatch.setattr("app.api.internal_edge.settings.SKILL_AGENT_BASE_URL", "http://agent.test:4580")

    with patch("app.api.internal_edge.httpx.AsyncClient", return_value=client):
        await _revalidate_agent_run_session(
            run_id="run-1",
            org_id="org-1",
            user_id="user-1",
            context_version=8,
        )

    assert client.post.await_args.args[0] == "http://agent.test:4580/internal/v1/runs/run-1/session/revalidate"
    assert client.post.await_args.kwargs["json"] == {"context_version": 8}
