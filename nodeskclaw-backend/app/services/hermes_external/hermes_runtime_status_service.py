from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeStatusPair:
    gateway_runtime_status: str
    mcp_status: str


class HermesRuntimeStatusService:
    def compute(
        self,
        *,
        docker_status: str,
        gateway_status: str,
        gateway_port: int | None,
    ) -> RuntimeStatusPair:
        if not gateway_port:
            return RuntimeStatusPair("unconfigured", "unconfigured")

        if docker_status in {"exited", "missing", "paused", "created"}:
            return RuntimeStatusPair("unavailable", "unavailable")

        if docker_status != "running":
            return RuntimeStatusPair("unknown", "unknown")

        if gateway_status == "online":
            return RuntimeStatusPair("ready", "ready")

        if gateway_status == "unauthorized":
            return RuntimeStatusPair("degraded", "unauthorized")

        if gateway_status in {"offline", "timeout", "invalid_response"}:
            return RuntimeStatusPair("degraded", "unavailable")

        if gateway_status == "unconfigured":
            return RuntimeStatusPair("unconfigured", "unconfigured")

        return RuntimeStatusPair("unknown", "unknown")
