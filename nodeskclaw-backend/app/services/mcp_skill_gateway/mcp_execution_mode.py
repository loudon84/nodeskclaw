from app.core.config import settings
from app.models.hermes_skill.skill import HermesSkill
from app.services.mcp_skill_gateway.auth import McpAuthContext

WAIT_MODE = "wait"
QUEUED_MODE = "queued"
ASYNC_EVENT_MODE = "async_event"

_VALID_MODES = {WAIT_MODE, QUEUED_MODE, ASYNC_EVENT_MODE}


def strip_mcp_control_args(arguments: dict | None) -> tuple[dict, bool | None]:
    raw = dict(arguments or {})
    wait_override = raw.pop("_wait", None)
    if wait_override is not None and not isinstance(wait_override, bool):
        wait_override = bool(wait_override)
    return raw, wait_override


def _normalized_default_mode() -> str:
    mode = (settings.MCP_TASK_DEFAULT_EXECUTION_MODE or ASYNC_EVENT_MODE).strip().lower()
    if mode not in _VALID_MODES:
        return ASYNC_EVENT_MODE
    return mode


def resolve_mcp_execution_mode(
    auth_ctx: McpAuthContext | None,
    skill: HermesSkill,
    output_policy: dict,
    *,
    wait_override: bool | None = None,
) -> str:
    is_runtime_skill = skill.source_type == "hermes_api_server"
    is_desktop_token = bool(auth_ctx and auth_ctx.auth_type == "mcp_client_token")

    if wait_override is True:
        return WAIT_MODE
    if wait_override is False:
        if is_runtime_skill and is_desktop_token:
            return ASYNC_EVENT_MODE
        return QUEUED_MODE

    if not is_runtime_skill:
        return QUEUED_MODE

    if not settings.MCP_TASK_SSE_ENABLED:
        return _resolve_without_sse(auth_ctx, output_policy)

    default_mode = _normalized_default_mode()
    if default_mode == ASYNC_EVENT_MODE:
        if auth_ctx and auth_ctx.auth_type == "mcp_client_token":
            return ASYNC_EVENT_MODE
        if auth_ctx and auth_ctx.auth_type == "user_jwt":
            return QUEUED_MODE
        return ASYNC_EVENT_MODE

    if default_mode == WAIT_MODE:
        if not settings.MCP_TASK_WAIT_ENABLED:
            return QUEUED_MODE
        return _resolve_legacy_wait(auth_ctx)

    if is_runtime_skill and is_desktop_token and settings.MCP_TASK_SSE_ENABLED:
        return ASYNC_EVENT_MODE

    return QUEUED_MODE


def _resolve_without_sse(auth_ctx: McpAuthContext | None, output_policy: dict) -> str:
    if not settings.MCP_TASK_WAIT_ENABLED:
        return QUEUED_MODE
    return _resolve_legacy_wait(auth_ctx)


def _resolve_legacy_wait(auth_ctx: McpAuthContext | None) -> str:
    default_mode = (settings.MCP_TASK_WAIT_DEFAULT_MODE or QUEUED_MODE).strip().lower()
    if default_mode not in (WAIT_MODE, QUEUED_MODE):
        default_mode = QUEUED_MODE

    if auth_ctx and auth_ctx.auth_type == "mcp_client_token":
        if settings.MCP_TASK_WAIT_FOR_MCP_CLIENT_TOKEN:
            return WAIT_MODE
        return QUEUED_MODE

    if auth_ctx and auth_ctx.auth_type == "user_jwt":
        if settings.MCP_TASK_WAIT_FOR_USER_JWT:
            return WAIT_MODE
        return QUEUED_MODE

    return default_mode if default_mode == WAIT_MODE else QUEUED_MODE
