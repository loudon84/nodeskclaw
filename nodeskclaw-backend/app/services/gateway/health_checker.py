import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.instance_mcp_server import InstanceMcpServer
from app.models.base import not_deleted
from app.services.gateway.types import UpstreamHealthState

logger = logging.getLogger(__name__)

gateway_health_checker: "GatewayHealthChecker | None" = None


class GatewayHealthChecker:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._task: asyncio.Task | None = None
        self._states: dict[str, UpstreamHealthState] = {}

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
        logger.info("Gateway 健康巡检已启动")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Gateway 健康巡检已停止")

    def is_available(self, mcp_server_id: str) -> bool:
        state = self._states.get(mcp_server_id)
        if state is None:
            return True
        return state.is_available

    def get_state(self, mcp_server_id: str) -> UpstreamHealthState | None:
        return self._states.get(mcp_server_id)

    def get_all_states(self) -> dict[str, UpstreamHealthState]:
        return dict(self._states)

    async def _loop(self) -> None:
        from app.core.config import settings
        interval = settings.GATEWAY_HEALTH_CHECK_INTERVAL
        timeout = settings.GATEWAY_HEALTH_CHECK_TIMEOUT
        failure_threshold = settings.GATEWAY_FAILURE_THRESHOLD
        recovery_threshold = settings.GATEWAY_RECOVERY_THRESHOLD

        while True:
            try:
                await self._check_all(timeout, failure_threshold, recovery_threshold)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Gateway 健康巡检异常")
            await asyncio.sleep(interval)

    async def _check_all(
        self,
        timeout: int,
        failure_threshold: int,
        recovery_threshold: int,
    ) -> None:
        async with self._session_factory() as db:
            result = await db.execute(
                select(InstanceMcpServer)
                .where(not_deleted(InstanceMcpServer), InstanceMcpServer.is_active.is_(True))
            )
            servers = result.scalars().all()

            for server in servers:
                await self._check_one(server, timeout, failure_threshold, recovery_threshold)

    async def _check_one(
        self,
        server: InstanceMcpServer,
        timeout: int,
        failure_threshold: int,
        recovery_threshold: int,
    ) -> None:
        if server.id not in self._states:
            self._states[server.id] = UpstreamHealthState(mcp_server_id=server.id)

        state = self._states[server.id]
        state.last_checked_at = datetime.now(timezone.utc)

        is_healthy = await self._probe(server, timeout)

        if is_healthy:
            state.consecutive_successes += 1
            state.consecutive_failures = 0
            if not state.is_available and state.consecutive_successes >= recovery_threshold:
                state.is_available = True
                logger.info("MCP Server %s 已恢复可用", server.name)
        else:
            state.consecutive_failures += 1
            state.consecutive_successes = 0
            if state.is_available and state.consecutive_failures >= failure_threshold:
                state.is_available = False
                logger.warning("MCP Server %s 已摘除（连续 %d 次失败）", server.name, failure_threshold)

    async def _probe(self, server: InstanceMcpServer, timeout: int) -> bool:
        if not server.url:
            return True

        health_url = server.health_url or (server.url.rstrip("/") + "/health")
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(health_url)
                return resp.status_code == 200
        except Exception:
            return False
