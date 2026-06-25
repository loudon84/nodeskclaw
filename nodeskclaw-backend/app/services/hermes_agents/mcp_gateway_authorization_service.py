import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.mcp_client_token import McpClientToken
from app.models.user import User
from app.services.deploy_service import _rewrite_docker_callback_url
from app.services.hermes_agents.env_file_service import (
    MCP_ENV_KEYS,
    remove_env_keys,
    resolve_env_path,
    write_mcp_env_values,
)
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.mcp_skill_gateway.constants import MCP_ENDPOINT
from app.services.mcp_skill_gateway.mcp_client_token_service import McpClientTokenService

logger = logging.getLogger(__name__)

McpGatewayUiStatus = Literal["none", "authorized", "env_synced", "expired", "revoked", "env_failed"]


def build_mcp_gateway_url() -> str:
    base = (settings.AGENT_API_BASE_URL or "").rstrip("/")
    if not base:
        raise BadRequestError("AGENT_API_BASE_URL 未配置", "errors.mcp_gateway.api_base_url_missing")
    rewritten = _rewrite_docker_callback_url(base)
    if rewritten.endswith("/api/v1"):
        return f"{rewritten}{MCP_ENDPOINT.removeprefix('/api/v1')}"
    if MCP_ENDPOINT.startswith("/"):
        return f"{rewritten.rstrip('/')}{MCP_ENDPOINT}"
    return f"{rewritten}/{MCP_ENDPOINT}"


class McpGatewayAuthorizationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.token_service = McpClientTokenService(db)
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

    async def _resolve_allowed_skills(
        self,
        org_id: str,
        user_id: str,
        requested: list[str] | None,
    ) -> list[str] | None:
        if requested:
            return requested
        mapper = McpToolMapper(self.db)
        tools = await mapper.list_tools(org_id, user_id=user_id)
        skill_ids: list[str] = []
        for tool in tools:
            tool_name = tool.get("name")
            if not tool_name:
                continue
            skill_ids.append(tool_name)
        return skill_ids or None

    def compute_ui_status(
        self,
        record: HermesAgentInstance,
        token: McpClientToken | None,
    ) -> McpGatewayUiStatus:
        if token is None:
            if record.mcp_gateway_enabled and record.mcp_gateway_last_error:
                return "env_failed"
            return "none"
        if self.token_service.is_revoked(token):
            return "revoked"
        if self.token_service.is_expired(token):
            return "expired"
        if record.mcp_gateway_last_error or not record.mcp_gateway_env_synced:
            if record.mcp_gateway_enabled:
                return "env_failed"
        if record.mcp_gateway_enabled and record.mcp_gateway_env_synced:
            return "env_synced"
        if record.mcp_gateway_enabled:
            return "authorized"
        return "none"

    async def get_status(self, org_id: str, agent_id: str) -> dict[str, Any]:
        record = await self.get_agent(org_id, agent_id)
        token: McpClientToken | None = None
        if record.mcp_gateway_token_id:
            token = await self.token_service.get_token_by_id(record.mcp_gateway_token_id)
        if token is None:
            token = await self.token_service.get_active_token(agent_id)

        ui_status = self.compute_ui_status(record, token)
        enabled = record.mcp_gateway_enabled and ui_status not in ("none", "revoked", "expired")

        return {
            "status": ui_status,
            "enabled": enabled,
            "token_prefix": record.mcp_gateway_token_prefix or (token.token_prefix if token else None),
            "mcp_url": record.mcp_gateway_url,
            "env_synced": record.mcp_gateway_env_synced,
            "expires_at": token.expires_at.isoformat() if token and token.expires_at else None,
            "revoked_at": token.revoked_at.isoformat() if token and token.revoked_at else None,
            "last_error": record.mcp_gateway_last_error,
        }

    async def authorize(
        self,
        org_id: str,
        agent_id: str,
        user: User,
        *,
        profile: str = "default",
        workspace_id: str = "default",
        expires_days: int = 180,
        allowed_skills: list[str] | None = None,
        write_env: bool = True,
        force_rotate: bool = False,
    ) -> dict[str, Any]:
        record = await self.get_agent(org_id, agent_id)
        mcp_url = build_mcp_gateway_url()
        instance_name = record.profile_name

        old_token = await self.token_service.get_active_token(agent_id)
        if (
            old_token
            and not self.token_service.is_expired(old_token)
            and not force_rotate
            and not write_env
        ):
            return await self._build_authorize_result(record, old_token, mcp_url, env_updated=False)

        if old_token:
            await self.token_service.revoke_token(old_token.id)
            await self._audit(
                "mcp_gateway.token.revoked",
                org_id,
                user.id,
                agent_id,
                instance_name,
                {"token_prefix": old_token.token_prefix, "reason": "rotate"},
            )

        resolved_skills = await self._resolve_allowed_skills(org_id, user.id, allowed_skills)
        plain, token_record = await self.token_service.create_token(
            org_id=org_id,
            hermes_agent_id=agent_id,
            instance_name=instance_name,
            created_by=user.id,
            profile=profile,
            workspace_id=workspace_id,
            allowed_skills=resolved_skills,
            expires_days=expires_days,
        )

        await self._audit(
            "mcp_gateway.token.created",
            org_id,
            user.id,
            agent_id,
            instance_name,
            {"token_prefix": token_record.token_prefix},
        )

        env_path: Path | None = None
        env_updated = False
        try:
            if write_env:
                env_path = resolve_env_path(record.env_file, record.instance_dir)
                write_mcp_env_values(
                    env_path,
                    {
                        "NODESKCLAW_MCP_URL": mcp_url,
                        "NODESKCLAW_MCP_TOKEN": plain,
                        "NODESKCLAW_MCP_ENABLED": "true",
                        "NODESKCLAW_MCP_NAME": "nodeskclaw-skills",
                    },
                )
                env_updated = True
                await self._audit(
                    "mcp_gateway.env.updated",
                    org_id,
                    user.id,
                    agent_id,
                    instance_name,
                    {"env_path": str(env_path), "token_prefix": token_record.token_prefix},
                )

            record.mcp_gateway_enabled = True
            record.mcp_gateway_token_id = token_record.id
            record.mcp_gateway_token_prefix = token_record.token_prefix
            record.mcp_gateway_url = mcp_url
            record.mcp_gateway_env_synced = env_updated
            record.mcp_gateway_last_authorized_at = datetime.now(timezone.utc)
            record.mcp_gateway_last_error = None
            await self.db.flush()

            await self._audit(
                "mcp_gateway.authorize.completed",
                org_id,
                user.id,
                agent_id,
                instance_name,
                {"token_prefix": token_record.token_prefix, "env_path": str(env_path) if env_path else None},
            )

            return await self._build_authorize_result(
                record, token_record, mcp_url, env_updated=env_updated, env_path=env_path,
            )

        except Exception as exc:
            await self.token_service.revoke_token(token_record.id)
            record.mcp_gateway_enabled = False
            record.mcp_gateway_token_id = None
            record.mcp_gateway_token_prefix = token_record.token_prefix
            record.mcp_gateway_url = mcp_url
            record.mcp_gateway_env_synced = False
            record.mcp_gateway_last_error = str(exc)
            await self.db.flush()
            await self._audit(
                "mcp_gateway.env.update_failed",
                org_id,
                user.id,
                agent_id,
                instance_name,
                {"error": str(exc), "token_prefix": token_record.token_prefix},
            )
            await self._audit(
                "mcp_gateway.authorize.failed",
                org_id,
                user.id,
                agent_id,
                instance_name,
                {"error": str(exc)},
            )
            if isinstance(exc, BadRequestError):
                raise
            raise BadRequestError(str(exc), "errors.mcp_gateway.authorize_failed") from exc

    async def revoke(
        self,
        org_id: str,
        agent_id: str,
        user: User,
        *,
        remove_env_keys_flag: bool = True,
    ) -> dict[str, Any]:
        record = await self.get_agent(org_id, agent_id)
        token = await self.token_service.get_active_token(agent_id)
        if token is None and record.mcp_gateway_token_id:
            token = await self.token_service.get_token_by_id(record.mcp_gateway_token_id)

        prefix = record.mcp_gateway_token_prefix
        if token:
            await self.token_service.revoke_token(token.id)
            prefix = token.token_prefix
            await self._audit(
                "mcp_gateway.token.revoked",
                org_id,
                user.id,
                agent_id,
                record.profile_name,
                {"token_prefix": token.token_prefix},
            )

        if remove_env_keys_flag:
            try:
                env_path = resolve_env_path(record.env_file, record.instance_dir)
                remove_env_keys(env_path, MCP_ENV_KEYS)
            except BadRequestError:
                pass

        record.mcp_gateway_enabled = False
        record.mcp_gateway_token_id = None
        record.mcp_gateway_env_synced = False
        record.mcp_gateway_last_error = None
        await self.db.flush()

        return {
            "ok": True,
            "agent_id": agent_id,
            "token_prefix": prefix,
            "revoked": True,
        }

    async def enrich_agent_summary(self, record: HermesAgentInstance, summary: dict[str, Any]) -> dict[str, Any]:
        token: McpClientToken | None = None
        if record.mcp_gateway_token_id:
            token = await self.token_service.get_token_by_id(record.mcp_gateway_token_id)
        if token is None and record.mcp_gateway_enabled:
            token = await self.token_service.get_active_token(record.id)

        ui_status = self.compute_ui_status(record, token)
        summary["mcp_gateway_status"] = ui_status
        summary["mcp_gateway_token_prefix"] = record.mcp_gateway_token_prefix
        summary["mcp_gateway_url"] = record.mcp_gateway_url
        summary["mcp_gateway_env_synced"] = record.mcp_gateway_env_synced
        summary["mcp_gateway_expires_at"] = (
            token.expires_at.isoformat() if token and token.expires_at else None
        )
        summary["mcp_gateway_last_error"] = record.mcp_gateway_last_error
        return summary

    async def _build_authorize_result(
        self,
        record: HermesAgentInstance,
        token: McpClientToken,
        mcp_url: str,
        *,
        env_updated: bool,
        env_path: Path | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "agent_id": record.id,
            "instance_name": record.profile_name,
            "mcp_url": mcp_url,
            "token_prefix": token.token_prefix,
            "env_path": str(env_path) if env_path else (record.env_file or None),
            "env_updated": env_updated,
            "mcp_gateway_enabled": record.mcp_gateway_enabled,
            "expires_at": token.expires_at.isoformat() if token.expires_at else None,
        }

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
