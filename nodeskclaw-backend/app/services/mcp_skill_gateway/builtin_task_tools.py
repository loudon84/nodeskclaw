from typing import Any

from app.core.config import settings

BUILTIN_TASK_TOOL_NAMES = frozenset({
    "nodeskclaw_task_timeline",
    "nodeskclaw_task_result",
    "nodeskclaw_task_artifacts",
    "nodeskclaw_artifact_preview",
    "nodeskclaw_artifact_download_info",
    "nodeskclaw_task_wait",
})

_TASK_WAIT_TOOL = "nodeskclaw_task_wait"

_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "nodeskclaw_task_timeline",
        "description": "查询 NoDeskClaw Hermes 异步任务执行时间线，用于展示任务进度",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "NoDeskClaw HermesTask ID",
                },
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "nodeskclaw_task_result",
        "description": "查询 NoDeskClaw Hermes 异步任务最终结果和中心产物",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "include_timeline": {"type": "boolean", "default": True},
                "include_artifacts": {"type": "boolean", "default": True},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "nodeskclaw_task_artifacts",
        "description": "查询指定 NoDeskClaw Hermes 任务下的中心产物 server_artifacts",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "server_only": {"type": "boolean", "default": True},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "nodeskclaw_artifact_preview",
        "description": "通过 MCP 预览 NoDeskClaw 中心产物库中的 Artifact 内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "max_chars": {
                    "type": "integer",
                    "default": 12000,
                    "minimum": 1000,
                    "maximum": 50000,
                },
            },
            "required": ["artifact_id"],
        },
    },
    {
        "name": "nodeskclaw_artifact_download_info",
        "description": "获取 NoDeskClaw Artifact 下载信息（不含二进制内容）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact_id": {"type": "string"},
                "signed": {"type": "boolean", "default": False},
            },
            "required": ["artifact_id"],
        },
    },
    {
        "name": _TASK_WAIT_TOOL,
        "description": "等待 NoDeskClaw Hermes 异步任务完成（服务端短轮询，减少客户端反复查询）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string"},
                "timeout_seconds": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 5,
                    "maximum": 60,
                },
                "poll_interval_seconds": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["task_id"],
        },
    },
]


def is_builtin_task_tool(tool_name: str) -> bool:
    return tool_name in BUILTIN_TASK_TOOL_NAMES


def list_builtin_task_tool_descriptors() -> list[dict[str, Any]]:
    if not settings.MCP_TASK_TOOLS_ENABLED:
        return []
    tools: list[dict[str, Any]] = []
    for definition in _TOOL_DEFINITIONS:
        if definition["name"] == _TASK_WAIT_TOOL and not settings.MCP_TASK_WAIT_ENABLED:
            continue
        tools.append({
            "name": definition["name"],
            "description": definition["description"],
            "inputSchema": definition["inputSchema"],
        })
    return tools
