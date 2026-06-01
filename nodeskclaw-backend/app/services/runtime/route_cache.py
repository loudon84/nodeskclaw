"""RouteTable — in-memory topology cache with PG NOTIFY invalidation and version tracking."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.services.runtime.messaging.delivery_plan import DeliveryTarget

logger = logging.getLogger(__name__)

CACHE_TTL_S = 60


@dataclass
class VersionedRoutes:
    version: int
    targets: list[DeliveryTarget]
    created_at: float = field(default_factory=time.monotonic)


class RouteTable:
    def __init__(self, ttl_s: int = CACHE_TTL_S) -> None:
        self._cache: dict[tuple[str, str], VersionedRoutes] = {}
        self._versions: dict[str, int] = {}
        self._ttl_s = ttl_s

    def get(self, workspace_id: str, sender_id: str = "") -> list[DeliveryTarget] | None:
        key = (workspace_id, sender_id)
        entry = self._cache.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry.created_at > self._ttl_s:
            del self._cache[key]
            return None
        return entry.targets

    def get_version(self, workspace_id: str) -> int:
        return self._versions.get(workspace_id, 0)

    def put(self, workspace_id: str, targets: list[DeliveryTarget], sender_id: str = "") -> int:
        seen: set[str] = set()
        unique: list[DeliveryTarget] = []
        for t in targets:
            if t.node_id not in seen:
                seen.add(t.node_id)
                unique.append(t)

        version = self._versions.get(workspace_id, 0) + 1
        self._versions[workspace_id] = version
        self._cache[(workspace_id, sender_id)] = VersionedRoutes(
            version=version, targets=unique,
        )
        return version

    def is_stale(self, workspace_id: str, plan_version: int) -> bool:
        current = self._versions.get(workspace_id, 0)
        return plan_version < current

    def invalidate(self, workspace_id: str) -> None:
        keys_to_remove = [k for k in self._cache if k[0] == workspace_id]
        for k in keys_to_remove:
            del self._cache[k]
        self._versions[workspace_id] = self._versions.get(workspace_id, 0) + 1
        logger.debug("RouteTable: invalidated cache for workspace %s (v=%d)", workspace_id, self._versions[workspace_id])

    def invalidate_all(self) -> None:
        for ws_id in list(self._versions.keys()):
            self._versions[ws_id] = self._versions.get(ws_id, 0) + 1
        self._cache.clear()
        logger.debug("RouteTable: invalidated all cached routes")

    @property
    def size(self) -> int:
        return len(self._cache)


route_table = RouteTable()
