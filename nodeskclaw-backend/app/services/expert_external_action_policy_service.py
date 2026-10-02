from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.expert import Expert
from app.models.integration.account import IntegrationAccount
from app.models.integration.external_action_policy import ExpertExternalActionPolicy
from app.services.external_action.naming import META_TOOL_KEYS, surface_name
from app.services.integration_account_service import account_scope_denied

_MODES = frozenset({"REQUIRE_APPROVAL", "DENY"})


def public_policy(row: ExpertExternalActionPolicy) -> dict[str, Any]:
    return {
        "id": row.id,
        "provider": row.provider,
        "toolkit_slug": row.toolkit_slug,
        "provider_tool_key": row.provider_tool_key,
        "mode": row.mode,
        "policy_version": row.policy_version,
        "enabled": row.enabled,
        "input_schema": row.input_schema,
        "description": row.description or "",
    }


class ExpertExternalActionPolicyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_policies(self, *, org_id: str, expert_id: str) -> list[dict[str, Any]]:
        await self._expert(org_id, expert_id)
        rows = await self._rows(org_id, expert_id)
        return [public_policy(row) for row in rows]

    async def replace_policies(self, *, org_id: str, expert_id: str, policies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        await self._expert(org_id, expert_id)
        existing = {self._identity(row): row for row in await self._rows(org_id, expert_id)}
        seen: set[tuple[str, str, str, str]] = set()
        for item in policies:
            parsed = self._parse_item(item)
            seen.add(parsed["identity"])
            current = existing.get(parsed["identity"])
            if current is None:
                self.db.add(
                    ExpertExternalActionPolicy(
                        id=str(uuid.uuid4()),
                        org_id=org_id,
                        expert_id=expert_id,
                        provider=parsed["provider"],
                        toolkit_slug=parsed["toolkit_slug"],
                        provider_tool_key=parsed["provider_tool_key"],
                        mode=parsed["mode"],
                        policy_version=1,
                        enabled=parsed["enabled"],
                        input_schema=parsed["input_schema"],
                        description=parsed["description"],
                    )
                )
                continue
            changed = (
                current.mode != parsed["mode"]
                or current.enabled != parsed["enabled"]
                or (current.description or "") != (parsed["description"] or "")
                or (current.input_schema or None) != parsed["input_schema"]
            )
            current.mode = parsed["mode"]
            current.enabled = parsed["enabled"]
            current.description = parsed["description"]
            current.input_schema = parsed["input_schema"]
            if changed:
                current.policy_version = int(current.policy_version or 1) + 1
        for identity, row in existing.items():
            if identity not in seen:
                row.soft_delete()
        await self.db.commit()
        return await self.list_policies(org_id=org_id, expert_id=expert_id)

    async def _expert(self, org_id: str, expert_id: str) -> Expert:
        expert = await self.db.get(Expert, expert_id)
        if expert is None or expert.deleted_at is not None or expert.org_id != org_id:
            raise NotFoundError("专家不存在", "errors.expert.not_found")
        return expert

    async def _rows(self, org_id: str, expert_id: str) -> list[ExpertExternalActionPolicy]:
        result = await self.db.execute(
            select(ExpertExternalActionPolicy).where(
                not_deleted(ExpertExternalActionPolicy),
                ExpertExternalActionPolicy.org_id == org_id,
                ExpertExternalActionPolicy.expert_id == expert_id,
            )
        )
        return list(result.scalars().all())

    def _parse_item(self, item: dict[str, Any]) -> dict[str, Any]:
        provider = str(item.get("provider") or "").strip()
        toolkit = str(item.get("toolkit_slug") or "").strip()
        tool_key = str(item.get("provider_tool_key") or "").strip()
        mode = str(item.get("mode") or "DENY").strip()
        if provider != "composio" or not toolkit or not tool_key or mode not in _MODES or tool_key in META_TOOL_KEYS:
            raise BadRequestError("外部工具策略无效", "errors.integration.policy_invalid")
        enabled = bool(item.get("enabled", mode == "REQUIRE_APPROVAL"))
        if mode == "DENY":
            enabled = False
        schema = item.get("input_schema")
        if schema is not None and not isinstance(schema, dict):
            raise BadRequestError("外部工具策略无效", "errors.integration.policy_invalid")
        description = item.get("description")
        if description is not None and not isinstance(description, str):
            raise BadRequestError("外部工具策略无效", "errors.integration.policy_invalid")
        return {
            "identity": (provider, toolkit, tool_key, "composio"),
            "provider": provider,
            "toolkit_slug": toolkit,
            "provider_tool_key": tool_key,
            "mode": mode,
            "enabled": enabled,
            "input_schema": schema,
            "description": description,
        }

    @staticmethod
    def _identity(row: ExpertExternalActionPolicy) -> tuple[str, str, str, str]:
        return (row.provider, row.toolkit_slug, row.provider_tool_key, "composio")


async def enabled_approval_policies(
    db: AsyncSession,
    *,
    org_id: str,
    expert_id: str,
) -> list[ExpertExternalActionPolicy]:
    result = await db.execute(
        select(ExpertExternalActionPolicy).where(
            not_deleted(ExpertExternalActionPolicy),
            ExpertExternalActionPolicy.org_id == org_id,
            ExpertExternalActionPolicy.expert_id == expert_id,
            ExpertExternalActionPolicy.enabled.is_(True),
            ExpertExternalActionPolicy.mode == "REQUIRE_APPROVAL",
        )
    )
    return [row for row in result.scalars().all() if row.provider_tool_key not in META_TOOL_KEYS]


def require_toolkit_coverage(accounts: list[IntegrationAccount], policies: list[ExpertExternalActionPolicy]) -> None:
    if not policies:
        raise account_scope_denied()
    for account in accounts:
        covered = any(
            policy.provider == account.provider and policy.toolkit_slug == account.toolkit_slug
            for policy in policies
        )
        if not covered:
            raise account_scope_denied()


def list_external_tools(
    accounts: list[IntegrationAccount],
    policies: list[ExpertExternalActionPolicy],
) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    seen: set[str] = set()
    for account in accounts:
        for policy in policies:
            if policy.provider != account.provider or policy.toolkit_slug != account.toolkit_slug:
                continue
            name = surface_name(policy.provider, policy.toolkit_slug, policy.provider_tool_key)
            if name in seen:
                continue
            seen.add(name)
            tools.append(
                {
                    "tool_name": name,
                    "description": policy.description or "",
                    "input_schema": policy.input_schema or {"type": "object"},
                    "mode": "REQUIRE_APPROVAL",
                    "source": "external",
                    "provider_tool_key": policy.provider_tool_key,
                    "toolkit_slug": policy.toolkit_slug,
                    "provider": policy.provider,
                }
            )
    return tools
