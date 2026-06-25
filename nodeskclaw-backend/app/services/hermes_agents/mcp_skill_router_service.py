import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.hermes_skill.hermes_mcp_router_sync_log import HermesMcpRouterSyncLog
from app.models.instance import Instance
from app.models.user import User
from app.services.hermes_agents.env_file_service import read_env, resolve_env_path
from app.services.hermes_agents.mcp_tools_list_client import (
    fetch_mcp_tools_list,
    filter_tools,
    sanitize_tool_snapshot,
)
from app.services.hermes_agents.router_skill_template_service import (
    ROUTER_SKILL_NAME,
    render_router_skill_md,
)
from app.services.hermes_agents.skill_file_service import atomic_write_text_file, remove_directory
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_external.path_resolver import HermesExternalPathResolver
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

logger = logging.getLogger(__name__)

McpRouterUiStatus = Literal["none", "mcp_unauthorized", "synced", "failed"]


def resolve_router_skill_path(
    record: HermesAgentInstance,
    profile: str,
    instance: Instance | None = None,
) -> Path:
    skill_name = record.mcp_router_skill_name or ROUTER_SKILL_NAME
    resolver = HermesExternalPathResolver()

    if instance is not None:
        profile_paths = resolver.resolve_profile(instance, profile)
        return profile_paths.skills_dir / skill_name / "SKILL.md"

    if record.data_dir:
        base = Path(record.data_dir)
        profile_paths = resolver.resolve_profile_from_host_data_dir(base, profile)
        return profile_paths.skills_dir / skill_name / "SKILL.md"

    if record.env_file or record.instance_dir:
        env_path = resolve_env_path(record.env_file, record.instance_dir)
        if env_path.is_file():
            env_data = parse_env_file(env_path, require_gateway_port=False)
            data_dir = env_data.data_dir
            if data_dir:
                host_data_dir = Path(data_dir)
                profile_paths = resolver.resolve_profile_from_host_data_dir(host_data_dir, profile)
                return profile_paths.skills_dir / skill_name / "SKILL.md"

    if record.instance_dir:
        base = Path(record.instance_dir) / "data" / "hermes"
        profile_paths = resolver.resolve_profile_from_host_data_dir(base, profile)
        return profile_paths.skills_dir / skill_name / "SKILL.md"

    raise BadRequestError(
        "无法解析 Router Skill 路径，请检查实例目录配置",
        "errors.mcp_router.skill_path_missing",
    )


def router_skill_dir(skill_path: Path) -> Path:
    return skill_path.parent


class McpSkillRouterService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.binding = HermesDockerBindingService(db)
        self.audit = SkillAuditLogger(db)

    async def get_agent(self, org_id: str, agent_id: str) -> HermesAgentInstance:
        result = await self.db.execute(
            select(HermesAgentInstance).where(
                not_deleted(HermesAgentInstance),
                HermesAgentInstance.id == agent_id,
                HermesAgentInstance.org_id == org_id,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            raise NotFoundError("Hermes Agent 实例不存在", "errors.hermes.agent_instance_not_found")
        return record

    def _read_mcp_env(self, record: HermesAgentInstance) -> tuple[str, str, str]:
        env_path = resolve_env_path(record.env_file, record.instance_dir)
        env = read_env(env_path)
        enabled = (env.get("NODESKCLAW_MCP_ENABLED") or "").lower() == "true"
        token = env.get("NODESKCLAW_MCP_TOKEN") or ""
        url = env.get("NODESKCLAW_MCP_URL") or ""
        mcp_name = env.get("NODESKCLAW_MCP_NAME") or "nodeskclaw-skills"
        if not enabled or not token or not url:
            raise BadRequestError(
                "请先授权 MCP Skill Gateway",
                "errors.mcp_router.mcp_not_authorized",
            )
        return url, token, mcp_name

    def compute_ui_status(self, record: HermesAgentInstance) -> McpRouterUiStatus:
        if not record.mcp_gateway_env_synced and not record.mcp_gateway_enabled:
            if record.mcp_router_last_error:
                return "failed"
            return "mcp_unauthorized"
        if not record.mcp_gateway_env_synced:
            return "mcp_unauthorized"
        if record.mcp_router_last_error and not record.mcp_router_enabled:
            return "failed"
        if record.mcp_router_enabled:
            return "synced"
        if record.mcp_router_last_error:
            return "failed"
        return "none"

    async def sync(
        self,
        org_id: str,
        agent_id: str,
        user: User,
        *,
        profile: str = "default",
        force: bool = True,
        tool_filter: str = "skill_only",
        include_registry_tools: bool = False,
    ) -> dict[str, Any]:
        record = await self.get_agent(org_id, agent_id)
        instance = await self.binding.get_linked_instance(record)
        instance_name = record.profile_name

        await self._audit(
            "mcp_router.sync.started",
            org_id,
            user.id,
            agent_id,
            instance_name,
            {"profile": profile},
        )

        try:
            mcp_url, mcp_token, mcp_name = self._read_mcp_env(record)
            skill_path = resolve_router_skill_path(record, profile, instance)

            if skill_path.is_file() and not force:
                raise ConflictError(
                    "Router Skill 已存在，请设置 force=true 覆盖",
                    "errors.mcp_router.skill_exists",
                )

            raw_tools = await fetch_mcp_tools_list(mcp_url, mcp_token, params={})
            tools = filter_tools(
                raw_tools,
                tool_filter=tool_filter,
                include_registry_tools=include_registry_tools,
            )
            if not tools:
                raise BadRequestError(
                    "MCP tools/list 返回空列表，请检查授权范围",
                    "errors.mcp_router.tools_empty",
                )

            content = render_router_skill_md(mcp_name, tools)
            atomic_write_text_file(skill_path, content, mode=0o644, backup=True)

            now = datetime.now(timezone.utc)
            record.mcp_router_enabled = True
            record.mcp_router_skill_name = ROUTER_SKILL_NAME
            record.mcp_router_skill_path = str(skill_path)
            record.mcp_router_tool_count = len(tools)
            record.mcp_router_last_synced_at = now
            record.mcp_router_last_error = None

            sync_log = HermesMcpRouterSyncLog(
                id=str(uuid.uuid4()),
                org_id=org_id,
                agent_id=agent_id,
                instance_name=instance_name,
                profile=profile,
                mcp_name=mcp_name,
                router_skill_name=ROUTER_SKILL_NAME,
                router_skill_path=str(skill_path),
                tool_count=len(tools),
                tool_snapshot=sanitize_tool_snapshot(tools),
                status="completed",
                created_by=user.id,
            )
            self.db.add(sync_log)
            await self.db.flush()

            tool_names = [t["name"] for t in tools]
            await self._audit(
                "mcp_router.skill_file.written",
                org_id,
                user.id,
                agent_id,
                instance_name,
                {"path": str(skill_path), "tool_count": len(tools)},
            )
            await self._audit(
                "mcp_router.sync.completed",
                org_id,
                user.id,
                agent_id,
                instance_name,
                {"tool_count": len(tools), "path": str(skill_path)},
            )

            return {
                "ok": True,
                "agent_id": agent_id,
                "instance_name": instance_name,
                "profile": profile,
                "mcp_name": mcp_name,
                "router_skill_name": ROUTER_SKILL_NAME,
                "router_skill_path": str(skill_path),
                "tool_count": len(tools),
                "tool_names": tool_names,
                "synced_at": now.isoformat(),
            }

        except Exception as exc:
            record.mcp_router_last_error = str(exc)
            if not isinstance(exc, (BadRequestError, ConflictError)):
                record.mcp_router_enabled = False
            await self.db.flush()

            sync_log = HermesMcpRouterSyncLog(
                id=str(uuid.uuid4()),
                org_id=org_id,
                agent_id=agent_id,
                instance_name=instance_name,
                profile=profile,
                router_skill_name=ROUTER_SKILL_NAME,
                tool_count=0,
                status="failed",
                error_message=str(exc),
                created_by=user.id,
            )
            self.db.add(sync_log)
            await self.db.flush()

            await self._audit(
                "mcp_router.sync.failed",
                org_id,
                user.id,
                agent_id,
                instance_name,
                {"error": str(exc)},
            )
            if isinstance(exc, (BadRequestError, ConflictError)):
                raise
            raise BadRequestError(str(exc), "errors.mcp_router.sync_failed") from exc

    async def get_status(
        self,
        org_id: str,
        agent_id: str,
        *,
        profile: str = "default",
    ) -> dict[str, Any]:
        record = await self.get_agent(org_id, agent_id)
        instance = await self.binding.get_linked_instance(record)
        skill_path = resolve_router_skill_path(record, profile, instance)
        exists = skill_path.is_file()
        return {
            "status": self.compute_ui_status(record),
            "enabled": record.mcp_router_enabled,
            "router_skill_name": record.mcp_router_skill_name,
            "router_skill_path": str(skill_path),
            "exists": exists,
            "tool_count": record.mcp_router_tool_count,
            "last_synced_at": (
                record.mcp_router_last_synced_at.isoformat()
                if record.mcp_router_last_synced_at
                else None
            ),
            "last_error": record.mcp_router_last_error,
        }

    async def delete(
        self,
        org_id: str,
        agent_id: str,
        user: User,
        *,
        profile: str = "default",
    ) -> dict[str, Any]:
        record = await self.get_agent(org_id, agent_id)
        instance = await self.binding.get_linked_instance(record)
        skill_path = resolve_router_skill_path(record, profile, instance)
        skill_dir = router_skill_dir(skill_path)

        try:
            remove_directory(skill_dir)
        except BadRequestError:
            pass

        record.mcp_router_enabled = False
        record.mcp_router_skill_path = None
        record.mcp_router_tool_count = 0
        record.mcp_router_last_synced_at = None
        record.mcp_router_last_error = None
        await self.db.flush()

        await self._audit(
            "mcp_router.skill_file.deleted",
            org_id,
            user.id,
            agent_id,
            record.profile_name,
            {"path": str(skill_dir)},
        )

        return {
            "ok": True,
            "agent_id": agent_id,
            "deleted": True,
            "router_skill_path": str(skill_path),
        }

    async def enrich_agent_summary(
        self,
        record: HermesAgentInstance,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        ui_status = self.compute_ui_status(record)
        summary["mcp_router_status"] = ui_status
        summary["mcp_router_tool_count"] = record.mcp_router_tool_count
        summary["mcp_router_skill_path"] = record.mcp_router_skill_path
        summary["mcp_router_last_synced_at"] = (
            record.mcp_router_last_synced_at.isoformat()
            if record.mcp_router_last_synced_at
            else None
        )
        summary["mcp_router_last_error"] = record.mcp_router_last_error
        return summary

    async def _audit(
        self,
        action: str,
        org_id: str,
        actor_id: str,
        agent_id: str,
        instance_name: str,
        details: dict[str, Any],
    ) -> None:
        await self.audit.log(
            action=action,
            target_id=agent_id,
            org_id=org_id,
            actor_id=actor_id,
            details={"instance_name": instance_name, **details},
        )
