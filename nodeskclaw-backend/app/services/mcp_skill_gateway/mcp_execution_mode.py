from typing import Any

from app.core.config import settings
from app.models.hermes_skill.skill import HermesSkill
from app.services.mcp_skill_gateway.auth import McpAuthContext

WAIT_MODE = "wait"
QUEUED_MODE = "queued"


def strip_mcp_control_args(arguments: dict | None) -> tuple[dict, bool | None]:
    raw = dict(arguments or {})
    wait_override = raw.pop("_wait", None)
    if wait_override is not None and not isinstance(wait_override, bool):
        wait_override = bool(wait_override)
    return raw, wait_override


def resolve_mcp_execution_mode(
    auth_ctx: McpAuthContext | None,
    skill: HermesSkill,
    output_policy: dict,
    *,
    wait_override: bool | None = None,
) -> str:
    if not settings.MCP_TASK_WAIT_ENABLED:
        return QUEUED_MODE

    if wait_override is True:
        return WAIT_MODE
    if wait_override is False:
        return QUEUED_MODE

    if skill.source_type != "hermes_api_server":
        return QUEUED_MODE

    default_mode = (settings.MCP_TASK_WAIT_DEFAULT_MODE or QUEUED_MODE).strip().lower()
    if default_mode not in (WAIT_MODE, QUEUED_MODE):
        default_mode = WAIT_MODE

    if auth_ctx and auth_ctx.auth_type == "mcp_client_token":
        if settings.MCP_TASK_WAIT_FOR_MCP_CLIENT_TOKEN:
            return WAIT_MODE
        return QUEUED_MODE

    if auth_ctx and auth_ctx.auth_type == "user_jwt":
        if settings.MCP_TASK_WAIT_FOR_USER_JWT:
            return WAIT_MODE
        return QUEUED_MODE

    if output_policy.get("artifact_mode") == "pull_only" and default_mode == WAIT_MODE:
        return WAIT_MODE

    return default_mode
