"""MCP Skill Gateway tool registry with governance metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

PermissionLevel = Literal["read", "write", "admin"]
RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    category: str
    permission: PermissionLevel
    risk_level: RiskLevel
    requires_approval: bool
    enabled: bool


_ALL_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="hermes.instances.list",
        description="List bound Hermes Docker instances",
        input_schema={"type": "object", "properties": {}},
        category="hermes",
        permission="read",
        risk_level="low",
        requires_approval=False,
        enabled=True,
    ),
    ToolDefinition(
        name="hermes.instance.status",
        description="Get runtime status of a bound Hermes instance",
        input_schema={
            "type": "object",
            "properties": {"instance_ref": {"type": "string"}},
            "required": ["instance_ref"],
        },
        category="hermes",
        permission="read",
        risk_level="low",
        requires_approval=False,
        enabled=True,
    ),
    ToolDefinition(
        name="hermes.skills.list",
        description="List installed skills of a bound Hermes instance",
        input_schema={
            "type": "object",
            "properties": {"instance_ref": {"type": "string"}},
            "required": ["instance_ref"],
        },
        category="hermes",
        permission="read",
        risk_level="low",
        requires_approval=False,
        enabled=True,
    ),
    ToolDefinition(
        name="hermes.skills.install_builtin",
        description="Install built-in skill bundle to Hermes instance",
        input_schema={
            "type": "object",
            "properties": {
                "instance_ref": {"type": "string"},
                "skill_slug": {"type": "string"},
            },
            "required": ["instance_ref", "skill_slug"],
        },
        category="hermes",
        permission="write",
        risk_level="medium",
        requires_approval=True,
        enabled=True,
    ),
    ToolDefinition(
        name="hermes.skills.install_zip",
        description="Install skill from ZIP upload",
        input_schema={"type": "object", "properties": {}},
        category="hermes",
        permission="write",
        risk_level="medium",
        requires_approval=True,
        enabled=False,
    ),
    ToolDefinition(
        name="hermes.skills.install_git",
        description="Install skill from Git repository",
        input_schema={"type": "object", "properties": {}},
        category="hermes",
        permission="write",
        risk_level="medium",
        requires_approval=True,
        enabled=False,
    ),
    ToolDefinition(
        name="hermes.skills.uninstall",
        description="Uninstall skill from Hermes instance",
        input_schema={
            "type": "object",
            "properties": {
                "instance_ref": {"type": "string"},
                "skill_name": {"type": "string"},
            },
            "required": ["instance_ref", "skill_name"],
        },
        category="hermes",
        permission="write",
        risk_level="high",
        requires_approval=True,
        enabled=True,
    ),
    ToolDefinition(
        name="hermes.instance.restart",
        description="Restart Hermes Docker instance",
        input_schema={
            "type": "object",
            "properties": {
                "instance_ref": {"type": "string"},
            },
            "required": ["instance_ref"],
        },
        category="hermes",
        permission="admin",
        risk_level="high",
        requires_approval=True,
        enabled=True,
    ),
    ToolDefinition(
        name="hermes.instance.rebind",
        description="Rebind Hermes Docker instance",
        input_schema={"type": "object", "properties": {}},
        category="hermes",
        permission="admin",
        risk_level="high",
        requires_approval=True,
        enabled=False,
    ),
    ToolDefinition(
        name="genehub.skills.search",
        description="Search GeneHub skills visible to the current user for a Desktop Hermes profile",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "profile_id": {"type": "string"},
                "category": {"type": "string"},
                "tag": {"type": "string"},
            },
        },
        category="genehub",
        permission="read",
        risk_level="low",
        requires_approval=False,
        enabled=True,
    ),
    ToolDefinition(
        name="genehub.skill.detail",
        description="Get GeneHub skill detail with manifest preview",
        input_schema={
            "type": "object",
            "properties": {
                "gene_slug": {"type": "string"},
                "profile_id": {"type": "string"},
            },
            "required": ["gene_slug"],
        },
        category="genehub",
        permission="read",
        risk_level="low",
        requires_approval=False,
        enabled=True,
    ),
    ToolDefinition(
        name="genehub.skill.register_to_hermes",
        description="Create GeneHub skill registration job for Copilot Desktop local install",
        input_schema={
            "type": "object",
            "properties": {
                "gene_slug": {"type": "string"},
                "profile_id": {"type": "string"},
                "version": {"type": "string"},
                "action": {"type": "string", "enum": ["install", "update", "uninstall"]},
            },
            "required": ["gene_slug"],
        },
        category="genehub",
        permission="write",
        risk_level="medium",
        requires_approval=True,
        enabled=True,
    ),
    ToolDefinition(
        name="genehub.registration.status",
        description="Get GeneHub skill registration or install job status",
        input_schema={
            "type": "object",
            "properties": {
                "job_id": {"type": "string"},
                "gene_slug": {"type": "string"},
                "profile_id": {"type": "string"},
            },
        },
        category="genehub",
        permission="read",
        risk_level="low",
        requires_approval=False,
        enabled=True,
    ),
)

_TOOL_BY_NAME: dict[str, ToolDefinition] = {t.name: t for t in _ALL_TOOLS}


def get_tool(name: str) -> ToolDefinition | None:
    return _TOOL_BY_NAME.get(name)


def list_enabled_tools() -> list[ToolDefinition]:
    return [t for t in _ALL_TOOLS if t.enabled]


def count_tools_by_permission() -> dict[str, int]:
    counts = {"count": 0, "read": 0, "write": 0, "admin": 0}
    for tool in _ALL_TOOLS:
        if not tool.enabled:
            continue
        counts["count"] += 1
        counts[tool.permission] += 1
    return counts


def build_tool_descriptor(tool: ToolDefinition, auth_annotations: dict[str, Any] | None = None) -> dict[str, Any]:
    annotations: dict[str, Any] = {
        "category": tool.category,
        "permission": tool.permission,
        "riskLevel": tool.risk_level,
        "requiresApproval": tool.requires_approval,
        "enabled": tool.enabled,
    }
    if tool.requires_approval and tool.permission in ("write", "admin"):
        annotations["approvalMode"] = "server"
        annotations.update(auth_annotations or {
            "authorized": False,
            "grantStatus": "missing",
        })
    elif auth_annotations:
        annotations.update(auth_annotations)
    else:
        annotations["authorized"] = True
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.input_schema,
        "annotations": annotations,
    }


def list_enabled_tool_descriptors() -> list[dict[str, Any]]:
    return [build_tool_descriptor(t) for t in list_enabled_tools()]


def is_registry_tool(tool_name: str) -> bool:
    return tool_name in _TOOL_BY_NAME


def is_hermes_registry_tool(tool_name: str) -> bool:
    tool = _TOOL_BY_NAME.get(tool_name)
    return tool is not None and tool.category == "hermes"


def is_genehub_registry_tool(tool_name: str) -> bool:
    tool = _TOOL_BY_NAME.get(tool_name)
    return tool is not None and tool.category == "genehub"
