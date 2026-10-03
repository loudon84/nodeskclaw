from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.base import not_deleted
from app.models.expert import Expert
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService

CATALOG_CAPABILITIES = {
    "acp_protocol_version": 1,
    "attachments": "resource_link",
    "approvals": True,
    "artifacts": "resource_link",
    "session_resume": True,
    "session_close": True,
    "knowledge_context": True,
    "connector_context": True,
    "integration_account_context": True,
}


def public_catalog_item(expert: Expert, *, ready: bool) -> dict[str, Any]:
    return {
        "agent_ref": expert.expert_slug,
        "display_name": expert.display_name,
        "description": expert.description,
        "category": expert.category,
        "tags": list(expert.tags or []),
        "avatar": expert.avatar,
        "status": "ready" if ready else "unavailable",
        "capabilities": dict(CATALOG_CAPABILITIES),
    }


class RemoteExpertCatalogService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._catalog = ExpertCatalogService(db)

    async def list_items(self, org_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(Expert)
            .where(
                Expert.org_id == org_id,
                Expert.published.is_(True),
                Expert.enabled.is_(True),
                not_deleted(Expert),
            )
            .order_by(Expert.sort_order.asc(), Expert.expert_slug.asc())
        )
        experts = list((await self.db.execute(stmt)).scalars().all())
        return [await self._item(org_id, expert) for expert in experts]

    async def get_item(self, org_id: str, agent_ref: str) -> dict[str, Any]:
        expert = await self._catalog.get_by_slug(org_id, agent_ref)
        if expert is None or not expert.published or not expert.enabled:
            raise NotFoundError("远程专家不存在", "errors.remote_expert.not_found")
        return await self._item(org_id, expert)

    async def _item(self, org_id: str, expert: Expert) -> dict[str, Any]:
        try:
            ready = await self._catalog.runtime_ready(org_id, expert)
        except NotFoundError:
            ready = False
        return public_catalog_item(expert, ready=ready)
