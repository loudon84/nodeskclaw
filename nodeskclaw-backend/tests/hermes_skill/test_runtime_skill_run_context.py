from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import BadRequestError, ForbiddenError
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
