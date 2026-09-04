import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.core.exceptions import BadRequestError, NotFoundError
from app.services.hermes_skill.skill_installer import (
    SkillInstaller,
    assert_installation_workspace_ref,
)


@pytest.mark.asyncio
async def test_build_target_path_requires_profile_root_for_hermes_agent():
    db = AsyncMock()
    installer = SkillInstaller(db)

    skill = MagicMock()
    skill.skill_id = "writer.article.generate"

    with patch.object(installer, "_get_profile_root_path", new_callable=AsyncMock, return_value=None), \
         patch.object(installer, "_resolve_agent_type", new_callable=AsyncMock, return_value="hermes_agent"):
        with pytest.raises(BadRequestError) as exc_info:
            await installer._build_target_path(skill, "agent-1", "profile-1", "copy", "hermes_agent")

    assert exc_info.value.message_key == "errors.skill.profile_root_path_missing"


@pytest.mark.asyncio
async def test_build_target_path_uses_profile_root():
    db = AsyncMock()
    installer = SkillInstaller(db)

    skill = MagicMock()
    skill.skill_id = "writer.article.generate"

    with patch.object(
        installer,
        "_get_profile_root_path",
        new_callable=AsyncMock,
        return_value="/data/hermes/profiles/writer",
    ):
        target = await installer._build_target_path(skill, "agent-1", "profile-1", "copy", "hermes_agent")

    assert target == Path("/data/hermes/profiles/writer/skills/writer-article-generate")


@pytest.mark.asyncio
async def test_assert_installation_workspace_ref_allows_empty():
    db = AsyncMock()
    await assert_installation_workspace_ref(db, None, "org-1")
    await assert_installation_workspace_ref(db, "", "org-1")
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_assert_installation_workspace_ref_rejects_missing():
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(NotFoundError) as exc_info:
        await assert_installation_workspace_ref(db, "ws-missing", "org-1")
    assert exc_info.value.message_key == "errors.workspace.not_found"


@pytest.mark.asyncio
async def test_assert_installation_workspace_ref_rejects_other_org():
    db = AsyncMock()
    workspace = MagicMock()
    workspace.org_id = "org-other"
    result = MagicMock()
    result.scalar_one_or_none.return_value = workspace
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(BadRequestError) as exc_info:
        await assert_installation_workspace_ref(db, "ws-1", "org-1")
    assert exc_info.value.message_key == "errors.skill.installation_workspace_invalid"


@pytest.mark.asyncio
async def test_install_rejects_deleted_or_missing_workspace_id():
    db = AsyncMock()
    installer = SkillInstaller(db)
    skill = MagicMock()
    skill.skill_id = "writer.article.generate"
    skill.agent_type = None
    skill.version = "1.0.0"
    skill.canonical_path = "/tmp/skill"
    skill.id = "skill-db-1"
    skill.is_mcp_exposed = False
    skill.runtime = "local"

    with patch.object(installer, "_get_active_skill", AsyncMock(return_value=skill)), patch(
        "app.services.hermes_skill.skill_installer.assert_installation_workspace_ref",
        AsyncMock(side_effect=NotFoundError("办公室不存在", "errors.workspace.not_found")),
    ):
        with pytest.raises(NotFoundError) as exc_info:
            await installer.install(
                skill_id="writer.article.generate",
                agent_id="agent-1",
                org_id="org-1",
                workspace_id="ws-deleted",
            )
    assert exc_info.value.message_key == "errors.workspace.not_found"
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_install_allows_empty_workspace_id():
    db = AsyncMock()
    installer = SkillInstaller(db)
    skill = MagicMock()
    skill.skill_id = "writer.article.generate"
    skill.agent_type = None
    skill.version = "1.0.0"
    skill.canonical_path = "/tmp/skill"
    skill.id = "skill-db-1"
    skill.is_mcp_exposed = False
    skill.runtime = "local"

    with patch.object(installer, "_get_active_skill", AsyncMock(return_value=skill)), patch(
        "app.services.hermes_skill.skill_installer.assert_installation_workspace_ref",
        AsyncMock(),
    ) as mock_assert, patch(
        "app.services.hermes_skill.skill_audit_logger.SkillAuditLogger",
    ) as mock_audit_cls:
        mock_audit_cls.return_value.log = AsyncMock()
        installation = await installer.install(
            skill_id="writer.article.generate",
            agent_id="agent-1",
            org_id="org-1",
            workspace_id=None,
        )

    mock_assert.assert_awaited_once_with(db, None, "org-1")
    assert installation.workspace_id is None
    db.add.assert_called_once()
