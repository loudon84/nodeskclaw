from typing import Any

MCP_AUTH_REQUIRED = "MCP_AUTH_REQUIRED"
MCP_AUTH_EXPIRED = "MCP_AUTH_EXPIRED"
MCP_ORG_FORBIDDEN = "MCP_ORG_FORBIDDEN"
MCP_TOOL_NOT_FOUND = "MCP_TOOL_NOT_FOUND"
MCP_TOOL_DISABLED = "MCP_TOOL_DISABLED"
MCP_TOOL_PERMISSION_DENIED = "MCP_TOOL_PERMISSION_DENIED"
MCP_TOOL_APPROVAL_REQUIRED = "MCP_TOOL_APPROVAL_REQUIRED"
MCP_TOOL_APPROVAL_PENDING = "MCP_TOOL_APPROVAL_PENDING"
MCP_TOOL_GRANT_NOT_FOUND = "MCP_TOOL_GRANT_NOT_FOUND"
MCP_TOOL_GRANT_REVOKED = "MCP_TOOL_GRANT_REVOKED"
MCP_TOOL_GRANT_EXPIRED = "MCP_TOOL_GRANT_EXPIRED"
MCP_TOOL_CONSTRAINT_VIOLATION = "MCP_TOOL_CONSTRAINT_VIOLATION"
MCP_TOOL_PROTECTED_RESOURCE = "MCP_TOOL_PROTECTED_RESOURCE"
MCP_TOOL_EXECUTION_FAILED = "MCP_TOOL_EXECUTION_FAILED"
MCP_INVALID_ARGUMENTS = "MCP_INVALID_ARGUMENTS"
HERMES_INSTANCE_NOT_FOUND = "HERMES_INSTANCE_NOT_FOUND"
HERMES_INSTANCE_AMBIGUOUS = "HERMES_INSTANCE_AMBIGUOUS"
HERMES_INSTANCE_FORBIDDEN = "HERMES_INSTANCE_FORBIDDEN"
HERMES_RUNTIME_UNAVAILABLE = "HERMES_RUNTIME_UNAVAILABLE"
HERMES_SKILLS_LIST_FAILED = "HERMES_SKILLS_LIST_FAILED"
MCP_INTERNAL_ERROR = "MCP_INTERNAL_ERROR"
MCP_METHOD_NOT_FOUND = "MCP_METHOD_NOT_FOUND"
MCP_TOOLS_LIST_FAILED = "MCP_TOOLS_LIST_FAILED"
MCP_NOT_IMPLEMENTED = "MCP_NOT_IMPLEMENTED"
GENEHUB_SKILL_NOT_FOUND = "GENEHUB_SKILL_NOT_FOUND"
GENEHUB_SKILL_FORBIDDEN = "GENEHUB_SKILL_FORBIDDEN"
GENEHUB_PROFILE_NOT_FOUND = "GENEHUB_PROFILE_NOT_FOUND"
GENEHUB_PROFILE_FORBIDDEN = "GENEHUB_PROFILE_FORBIDDEN"
GENEHUB_INSTALL_NOT_ALLOWED = "GENEHUB_INSTALL_NOT_ALLOWED"
GENEHUB_JOB_NOT_FOUND = "GENEHUB_JOB_NOT_FOUND"
GENEHUB_JOB_NOT_PENDING = "GENEHUB_JOB_NOT_PENDING"
GENEHUB_JOB_STATUS_UNAVAILABLE = "GENEHUB_JOB_STATUS_UNAVAILABLE"
GENEHUB_BUNDLE_PREVIEW_UNAVAILABLE = "GENEHUB_BUNDLE_PREVIEW_UNAVAILABLE"

_ERROR_CODES: dict[str, int] = {
    MCP_AUTH_REQUIRED: -32010,
    MCP_AUTH_EXPIRED: -32011,
    MCP_ORG_FORBIDDEN: -32012,
    MCP_TOOL_NOT_FOUND: -32020,
    MCP_TOOL_DISABLED: -32021,
    MCP_TOOL_PERMISSION_DENIED: -32022,
    MCP_TOOL_APPROVAL_REQUIRED: -32023,
    MCP_TOOL_GRANT_REVOKED: -32024,
    MCP_TOOL_APPROVAL_PENDING: -32025,
    MCP_TOOL_GRANT_NOT_FOUND: -32026,
    MCP_TOOL_GRANT_EXPIRED: -32027,
    MCP_TOOL_CONSTRAINT_VIOLATION: -32028,
    MCP_TOOL_PROTECTED_RESOURCE: -32029,
    MCP_TOOL_EXECUTION_FAILED: -32031,
    MCP_INVALID_ARGUMENTS: -32030,
    HERMES_INSTANCE_NOT_FOUND: -32040,
    HERMES_INSTANCE_AMBIGUOUS: -32041,
    HERMES_INSTANCE_FORBIDDEN: -32042,
    HERMES_RUNTIME_UNAVAILABLE: -32050,
    HERMES_SKILLS_LIST_FAILED: -32051,
    MCP_INTERNAL_ERROR: -32060,
    MCP_METHOD_NOT_FOUND: -32601,
    MCP_TOOLS_LIST_FAILED: -32053,
    MCP_NOT_IMPLEMENTED: -32021,
    GENEHUB_SKILL_NOT_FOUND: -32070,
    GENEHUB_SKILL_FORBIDDEN: -32071,
    GENEHUB_PROFILE_NOT_FOUND: -32072,
    GENEHUB_PROFILE_FORBIDDEN: -32073,
    GENEHUB_INSTALL_NOT_ALLOWED: -32074,
    GENEHUB_JOB_NOT_FOUND: -32075,
    GENEHUB_JOB_NOT_PENDING: -32077,
    GENEHUB_JOB_STATUS_UNAVAILABLE: -32076,
    GENEHUB_BUNDLE_PREVIEW_UNAVAILABLE: -32078,
}

_DEFAULT_MESSAGES: dict[str, str] = {
    MCP_AUTH_REQUIRED: "Authentication required",
    MCP_AUTH_EXPIRED: "Authentication expired",
    MCP_ORG_FORBIDDEN: "Organization access forbidden",
    MCP_TOOL_NOT_FOUND: "Tool not found",
    MCP_TOOL_DISABLED: "Tool is disabled",
    MCP_TOOL_PERMISSION_DENIED: "Tool permission denied",
    MCP_TOOL_APPROVAL_REQUIRED: "Tool approval required",
    MCP_TOOL_APPROVAL_PENDING: "Tool approval pending",
    MCP_TOOL_GRANT_NOT_FOUND: "Tool grant not found",
    MCP_TOOL_GRANT_REVOKED: "Tool grant revoked",
    MCP_TOOL_GRANT_EXPIRED: "Tool grant expired",
    MCP_TOOL_CONSTRAINT_VIOLATION: "Tool constraint violation",
    MCP_TOOL_PROTECTED_RESOURCE: "Protected resource",
    MCP_TOOL_EXECUTION_FAILED: "Tool execution failed",
    MCP_INVALID_ARGUMENTS: "Invalid arguments",
    HERMES_INSTANCE_NOT_FOUND: "Instance not found",
    HERMES_INSTANCE_AMBIGUOUS: "Instance reference is ambiguous",
    HERMES_INSTANCE_FORBIDDEN: "Instance access forbidden",
    HERMES_RUNTIME_UNAVAILABLE: "Hermes runtime unavailable",
    HERMES_SKILLS_LIST_FAILED: "Failed to list skills",
    MCP_INTERNAL_ERROR: "Internal error",
    MCP_METHOD_NOT_FOUND: "Method not found",
    MCP_TOOLS_LIST_FAILED: "Failed to list tools",
    MCP_NOT_IMPLEMENTED: "Not implemented",
    GENEHUB_SKILL_NOT_FOUND: "GeneHub skill not found",
    GENEHUB_SKILL_FORBIDDEN: "GeneHub skill access forbidden",
    GENEHUB_PROFILE_NOT_FOUND: "Desktop Hermes profile not found",
    GENEHUB_PROFILE_FORBIDDEN: "Desktop Hermes profile access forbidden",
    GENEHUB_INSTALL_NOT_ALLOWED: "GeneHub skill install not allowed",
    GENEHUB_JOB_NOT_FOUND: "GeneHub install job not found",
    GENEHUB_JOB_NOT_PENDING: "GeneHub install job is not pending",
    GENEHUB_JOB_STATUS_UNAVAILABLE: "GeneHub registration status unavailable",
    GENEHUB_BUNDLE_PREVIEW_UNAVAILABLE: "GeneHub bundle preview unavailable",
}

_MESSAGE_KEY_MAP: dict[str, str] = {
    "errors.auth.user_not_found": MCP_ORG_FORBIDDEN,
    "errors.skill.tool_not_found": MCP_TOOL_NOT_FOUND,
    "errors.skill.tool_not_installed": MCP_TOOL_NOT_FOUND,
    "errors.skill.installation_not_found": MCP_TOOL_NOT_FOUND,
    "errors.skill.installation_ambiguous": MCP_TOOL_EXECUTION_FAILED,
    "errors.skill.routing_agent_not_allowed": MCP_TOOL_PERMISSION_DENIED,
    "errors.skill.routing_workspace_not_allowed": MCP_TOOL_PERMISSION_DENIED,
    "errors.skill.routing_profile_not_allowed": MCP_TOOL_PERMISSION_DENIED,
    "errors.skill.permission_denied": MCP_TOOL_PERMISSION_DENIED,
    "errors.skill.input_schema_validation_failed": MCP_INVALID_ARGUMENTS,
    "errors.member.skill_not_granted": MCP_TOOL_PERMISSION_DENIED,
    "errors.external_docker.instance_not_found": HERMES_INSTANCE_NOT_FOUND,
    "errors.external_docker.instance_ref_required": MCP_INVALID_ARGUMENTS,
    "errors.external_docker.instance_ambiguous": HERMES_INSTANCE_AMBIGUOUS,
    "errors.external_docker.instance_forbidden": HERMES_INSTANCE_FORBIDDEN,
    "errors.external_docker.skills_list_failed": HERMES_SKILLS_LIST_FAILED,
    "errors.external_docker.runtime_unavailable": HERMES_RUNTIME_UNAVAILABLE,
    "errors.genehub.skill_not_found": GENEHUB_SKILL_NOT_FOUND,
    "errors.genehub.install_job_permission_denied": GENEHUB_INSTALL_NOT_ALLOWED,
    "errors.genehub.install_job_not_found": GENEHUB_JOB_NOT_FOUND,
    "errors.genehub.install_job_invalid_status": GENEHUB_JOB_STATUS_UNAVAILABLE,
    "errors.genehub.bundle_preview_unavailable": GENEHUB_BUNDLE_PREVIEW_UNAVAILABLE,
    "errors.desktop.profile_not_found": GENEHUB_PROFILE_NOT_FOUND,
    "errors.desktop.profile_forbidden": GENEHUB_PROFILE_FORBIDDEN,
    MCP_AUTH_REQUIRED: MCP_AUTH_REQUIRED,
    MCP_AUTH_EXPIRED: MCP_AUTH_EXPIRED,
    MCP_ORG_FORBIDDEN: MCP_ORG_FORBIDDEN,
    MCP_TOOL_NOT_FOUND: MCP_TOOL_NOT_FOUND,
    MCP_TOOL_DISABLED: MCP_TOOL_DISABLED,
    MCP_TOOL_PERMISSION_DENIED: MCP_TOOL_PERMISSION_DENIED,
    MCP_INVALID_ARGUMENTS: MCP_INVALID_ARGUMENTS,
    HERMES_INSTANCE_NOT_FOUND: HERMES_INSTANCE_NOT_FOUND,
    HERMES_INSTANCE_AMBIGUOUS: HERMES_INSTANCE_AMBIGUOUS,
    HERMES_INSTANCE_FORBIDDEN: HERMES_INSTANCE_FORBIDDEN,
    HERMES_RUNTIME_UNAVAILABLE: HERMES_RUNTIME_UNAVAILABLE,
    HERMES_SKILLS_LIST_FAILED: HERMES_SKILLS_LIST_FAILED,
    MCP_INTERNAL_ERROR: MCP_INTERNAL_ERROR,
    MCP_NOT_IMPLEMENTED: MCP_TOOL_DISABLED,
}


def mcp_jsonrpc_code(error_code: str) -> int:
    return _ERROR_CODES.get(error_code, -32060)


def mcp_error_v2(
    jsonrpc_id: Any,
    error_code: str,
    message: str | None = None,
    *,
    data: dict[str, Any] | None = None,
) -> dict:
    payload = dict(data or {})
    payload.setdefault("errorCode", error_code)
    return {
        "jsonrpc": "2.0",
        "id": jsonrpc_id,
        "error": {
            "code": mcp_jsonrpc_code(error_code),
            "message": message or _DEFAULT_MESSAGES.get(error_code, error_code),
            "data": payload,
        },
    }


def mcp_success(jsonrpc_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": jsonrpc_id, "result": result}


def map_app_error(
    jsonrpc_id: Any,
    message_key: str | None,
    message: str,
    *,
    extra_data: dict[str, Any] | None = None,
) -> dict:
    error_code = _MESSAGE_KEY_MAP.get(message_key or "", MCP_INTERNAL_ERROR)
    data = dict(extra_data or {})
    return mcp_error_v2(jsonrpc_id, error_code, message, data=data)


def map_skill_error(
    jsonrpc_id: Any,
    message_key: str | None,
    message: str,
    *,
    extra_data: dict[str, Any] | None = None,
) -> dict:
    return map_app_error(jsonrpc_id, message_key, message, extra_data=extra_data)
