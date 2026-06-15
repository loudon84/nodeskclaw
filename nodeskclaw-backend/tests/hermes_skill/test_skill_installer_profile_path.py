import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.core.exceptions import BadRequestError
from app.services.hermes_skill.skill_installer import SkillInstaller


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
