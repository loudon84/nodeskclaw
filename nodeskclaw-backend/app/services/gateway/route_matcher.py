import fnmatch
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gateway.gateway_route import McpGatewayRoute
from app.models.base import not_deleted
from app.services.gateway.types import UpstreamTarget

logger = logging.getLogger(__name__)


class RouteMatcher:
    def __init__(self) -> None:
        self._routes: list[McpGatewayRoute] = []
        self._loaded = False

    async def refresh(self, db: AsyncSession) -> None:
        result = await db.execute(
            select(McpGatewayRoute)
            .where(not_deleted(McpGatewayRoute), McpGatewayRoute.is_active.is_(True))
            .order_by(McpGatewayRoute.priority.desc())
        )
        self._routes = list(result.scalars().all())
        self._loaded = True
        logger.info("Gateway 路由规则已刷新，共 %d 条活跃规则", len(self._routes))

    def match(
        self,
        instance_id: str,
        tool_name: str | None = None,
        org_id: str | None = None,
    ) -> list[UpstreamTarget]:
        for route in self._routes:
            if route.instance_id != instance_id:
                continue
            if org_id and route.org_id != org_id:
                continue
            if not route.match_tools:
                return self._build_targets(route)
            if tool_name and self._tool_matches(route.match_tools, tool_name):
                return self._build_targets(route)
        return []

    def _tool_matches(self, patterns: list, tool_name: str) -> bool:
        for pattern in patterns:
            if fnmatch.fnmatch(tool_name, pattern):
                return True
        return False

    def _build_targets(self, route: McpGatewayRoute) -> list[UpstreamTarget]:
        targets = []
        for server_id in route.mcp_server_ids:
            targets.append(
                UpstreamTarget(
                    mcp_server_id=server_id,
                    mcp_server_name="",
                    transport="",
                    url=None,
                    command=None,
                    instance_id=route.instance_id,
                )
            )
        return targets
