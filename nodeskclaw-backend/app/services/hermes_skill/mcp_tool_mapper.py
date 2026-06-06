import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation

logger = logging.getLogger(__name__)


class McpToolMapper:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_tools(self, org_id: str) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.org_id == org_id,
                HermesSkill.is_active.is_(True),
                HermesSkill.is_mcp_exposed.is_(True),
            )
        )
        tools = []
        for skill in result.scalars().all():
            tools.append({
                "name": skill.tool_name or skill.skill_id.replace(".", "_"),
                "title": skill.title or skill.name,
                "description": skill.description or "",
                "inputSchema": skill.input_schema or {},
                "version": skill.version,
            })
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict,
        org_id: str,
    ) -> dict[str, Any]:
        result = await self.db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.org_id == org_id,
                HermesSkill.tool_name == tool_name,
                HermesSkill.is_mcp_exposed.is_(True),
            )
        )
        skill = result.scalar_one_or_none()
        if not skill:
            raise NotFoundError(f"MCP Tool {tool_name} 不存在", "errors.skill.tool_not_found")

        install_result = await self.db.execute(
            select(HermesSkillInstallation).where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.skill_id == skill.skill_id,
                HermesSkillInstallation.status == "installed",
            )
        )
        installation = install_result.scalar_one_or_none()
        if not installation:
            raise NotFoundError(
                f"Skill {tool_name} 未安装到任何 Agent",
                "errors.skill.tool_not_installed",
            )

        return {
            "tool_name": tool_name,
            "agent_id": installation.agent_id,
            "status": "dispatched",
            "task_id": None,
        }
