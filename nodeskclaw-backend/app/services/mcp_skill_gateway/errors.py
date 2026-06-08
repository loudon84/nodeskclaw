from typing import Any

MCP_UNAUTHORIZED = "MCP_UNAUTHORIZED"
MCP_FORBIDDEN = "MCP_FORBIDDEN"
MCP_INITIALIZE_REQUIRED = "MCP_INITIALIZE_REQUIRED"
MCP_TOOLS_LIST_FAILED = "MCP_TOOLS_LIST_FAILED"
MCP_GATEWAY_REQUEST_FAILED = "MCP_GATEWAY_REQUEST_FAILED"
MCP_METHOD_NOT_FOUND = "MCP_METHOD_NOT_FOUND"
MCP_INVALID_REQUEST = "MCP_INVALID_REQUEST"
MCP_INTERNAL_ERROR = "MCP_INTERNAL_ERROR"

_ERROR_CODES: dict[str, int] = {
    MCP_UNAUTHORIZED: -32001,
    MCP_FORBIDDEN: -32003,
    MCP_INITIALIZE_REQUIRED: -32010,
    MCP_TOOLS_LIST_FAILED: -32011,
    MCP_GATEWAY_REQUEST_FAILED: -32012,
    MCP_METHOD_NOT_FOUND: -32601,
    MCP_INVALID_REQUEST: -32600,
    MCP_INTERNAL_ERROR: -32603,
}

_SKILL_ERROR_MAP: dict[str, tuple[str, int]] = {
    "errors.skill.tool_not_found": (MCP_GATEWAY_REQUEST_FAILED, -32011),
    "errors.skill.tool_not_installed": (MCP_GATEWAY_REQUEST_FAILED, -32011),
    "errors.skill.permission_denied": (MCP_FORBIDDEN, -32003),
    "errors.skill.input_schema_validation_failed": (MCP_INVALID_REQUEST, -32600),
    "errors.member.skill_not_granted": (MCP_FORBIDDEN, -32003),
}


def mcp_jsonrpc_code(error_code: str) -> int:
    return _ERROR_CODES.get(error_code, -32603)


def mcp_error(
    jsonrpc_id: Any,
    error_code: str,
    reason: str,
    *,
    jsonrpc_code: int | None = None,
) -> dict:
    code = jsonrpc_code if jsonrpc_code is not None else mcp_jsonrpc_code(error_code)
    return {
        "jsonrpc": "2.0",
        "id": jsonrpc_id,
        "error": {
            "code": code,
            "message": error_code,
            "data": {
                "errorCode": error_code,
                "reason": reason,
            },
        },
    }


def mcp_success(jsonrpc_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": jsonrpc_id, "result": result}


def map_skill_error(jsonrpc_id: Any, message_key: str | None, message: str) -> dict:
    error_code, code = _SKILL_ERROR_MAP.get(
        message_key or "",
        (MCP_INTERNAL_ERROR, -32603),
    )
    return mcp_error(jsonrpc_id, error_code, message, jsonrpc_code=code)
