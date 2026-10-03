from __future__ import annotations

from app.core.config import settings
from app.services.remote_acp.errors import EXPERT_UNAVAILABLE, RUNTIME_UNAVAILABLE


def assert_runtime_ready(item: dict, *, skill_agent_enabled: bool | None = None) -> None:
    enabled = settings.SKILL_AGENT_ENABLED if skill_agent_enabled is None else skill_agent_enabled
    if not enabled or not settings.SKILL_AGENT_BASE_URL:
        raise RUNTIME_UNAVAILABLE
    if item.get("status") != "ready":
        raise EXPERT_UNAVAILABLE
    acp = (item.get("capabilities") or {}).get("acp") or {}
    if acp.get("remote_transport") is False:
        raise EXPERT_UNAVAILABLE


def agent_ws_url() -> str:
    base = settings.SKILL_AGENT_BASE_URL.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :] + "/internal/v1/acp"
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :] + "/internal/v1/acp"
    return base + "/internal/v1/acp"
