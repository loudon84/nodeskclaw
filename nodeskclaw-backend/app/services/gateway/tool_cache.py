import asyncio
import logging
import time
from typing import Any, Callable, Awaitable

from app.core.config import settings

logger = logging.getLogger(__name__)


class ToolCache:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_or_fetch(
        self,
        key: str,
        fetcher: Callable[[], Awaitable[Any]],
    ) -> Any:
        ttl = getattr(settings, "GATEWAY_TOOL_CACHE_TTL", 60)
        now = time.time()
        async with self._lock:
            if key in self._cache:
                cached_at, cached_val = self._cache[key]
                if now - cached_at < ttl:
                    return cached_val

        result = await fetcher()

        async with self._lock:
            self._cache[key] = (now, result)

        return result

    async def invalidate(self, key: str | None = None) -> None:
        async with self._lock:
            if key is None:
                self._cache.clear()
            else:
                self._cache.pop(key, None)
