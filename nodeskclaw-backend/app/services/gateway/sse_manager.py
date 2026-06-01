import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from app.services.gateway.types import SSEProxyConnection

logger = logging.getLogger(__name__)


class SSEManager:
    def __init__(self) -> None:
        self._connections: dict[str, SSEProxyConnection] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    def start_cleanup(self) -> None:
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("SSE 连接清理任务已启动")

    async def stop_cleanup(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            self._connections.clear()
        logger.info("SSE 连接管理器已停止")

    async def register_connection(
        self,
        client_id: str,
        upstream_server_id: str,
        instance_id: str,
    ) -> str:
        connection_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        conn = SSEProxyConnection(
            connection_id=connection_id,
            client_id=client_id,
            upstream_server_id=upstream_server_id,
            instance_id=instance_id,
            created_at=now,
            last_activity_at=now,
        )
        async with self._lock:
            self._connections[connection_id] = conn
        return connection_id

    async def touch(self, connection_id: str) -> None:
        async with self._lock:
            conn = self._connections.get(connection_id)
            if conn:
                conn.last_activity_at = datetime.now(timezone.utc)

    async def remove_connection(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.pop(connection_id, None)

    def get_active_connection_count(self, instance_id: str | None = None) -> int:
        if instance_id is None:
            return len(self._connections)
        return sum(1 for c in self._connections.values() if c.instance_id == instance_id)

    async def _cleanup_loop(self) -> None:
        idle_timeout = 300
        while True:
            try:
                await self._cleanup_idle(idle_timeout)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("SSE 连接清理异常")
            await asyncio.sleep(60)

    async def _cleanup_idle(self, idle_timeout: int) -> None:
        now = datetime.now(timezone.utc)
        to_remove: list[str] = []
        async with self._lock:
            for cid, conn in self._connections.items():
                elapsed = (now - conn.last_activity_at).total_seconds()
                if elapsed > idle_timeout:
                    to_remove.append(cid)
            for cid in to_remove:
                del self._connections[cid]
        if to_remove:
            logger.info("SSE 清理 %d 个空闲连接", len(to_remove))
