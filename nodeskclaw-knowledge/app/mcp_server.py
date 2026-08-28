"""MCP transport — protocol adapter only; reuses agent_tools service paths.

Mounted under `/api/v2/mcp` when Knowledge API v2 is enabled. Can also be imported
as a standalone FastAPI router for MCP-only deployments.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.agent_tools import (
    knowledge_get_document,
    knowledge_get_evidence,
    knowledge_get_structure,
    knowledge_get_table,
    knowledge_search_or_retrieve,
)
from app.core.deps import get_db, get_member_context, get_runtime_adapter
from app.core.exceptions import BadRequestError
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal

router = APIRouter(prefix="/mcp", tags=["mcp"])

MCP_TOOL_NAMES = (
    "knowledge.search",
    "knowledge.retrieve",
    "knowledge.get_document",
    "knowledge.get_evidence",
    "knowledge.get_structure",
    "knowledge.get_table",
)


class McpToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(serialization_alias="inputSchema")


class McpToolsListResponse(BaseModel):
    tools: list[McpToolDefinition]


class McpToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class McpToolCallResponse(BaseModel):
    content: list[dict[str, Any]]
    is_error: bool = Field(False, serialization_alias="isError")


MCP_TOOLS: list[McpToolDefinition] = [
    McpToolDefinition(
        name="knowledge.search",
        description="按 KnowledgeApplication 或 KnowledgeSet 检索知识片段。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "application_id": {"type": "string"},
                "knowledge_set_id": {"type": "string"},
                "top_k": {"type": "integer"},
                "channel": {"type": "string"},
                "release_id": {"type": "string"},
            },
            "required": ["query"],
        },
    ),
    McpToolDefinition(
        name="knowledge.retrieve",
        description="按 KnowledgeApplication 或 KnowledgeSet 检索知识片段（与 knowledge.search 语义一致）。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "application_id": {"type": "string"},
                "knowledge_set_id": {"type": "string"},
                "top_k": {"type": "integer"},
                "channel": {"type": "string"},
                "release_id": {"type": "string"},
            },
            "required": ["query"],
        },
    ),
    McpToolDefinition(
        name="knowledge.get_document",
        description="获取 SourceFile 元数据（不含 runtime document id）。",
        input_schema={
            "type": "object",
            "properties": {"source_file_id": {"type": "string"}},
            "required": ["source_file_id"],
        },
    ),
    McpToolDefinition(
        name="knowledge.get_evidence",
        description="解析持久化 evidence_id，返回可引用证据内容。",
        input_schema={
            "type": "object",
            "properties": {"evidence_id": {"type": "string"}},
            "required": ["evidence_id"],
        },
    ),
    McpToolDefinition(
        name="knowledge.get_structure",
        description="通过 ACL 链获取 Outline/PageIndex 结构节点。",
        input_schema={
            "type": "object",
            "properties": {
                "knowledge_base_id": {"type": "string"},
                "query": {"type": "string"},
                "source_file_id": {"type": "string"},
            },
            "required": ["knowledge_base_id"],
        },
    ),
    McpToolDefinition(
        name="knowledge.get_table",
        description="通过 ACL 链获取 Table 行证据。",
        input_schema={
            "type": "object",
            "properties": {
                "knowledge_base_id": {"type": "string"},
                "query": {"type": "string"},
                "source_file_id": {"type": "string"},
            },
            "required": ["knowledge_base_id"],
        },
    ),
]


def list_tools() -> list[McpToolDefinition]:
    return list(MCP_TOOLS)


async def call_tool(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    *,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if name in ("knowledge.search", "knowledge.retrieve"):
        query = arguments.get("query")
        if not query or not str(query).strip():
            raise BadRequestError(
                message="缺少 query",
                message_key="errors.common.bad_request",
            )
        return await knowledge_search_or_retrieve(
            db,
            member,
            ragflow,
            query=str(query),
            application_id=arguments.get("application_id"),
            knowledge_set_id=arguments.get("knowledge_set_id"),
            top_k=arguments.get("top_k"),
            channel=str(arguments.get("channel") or "stable"),
            release_id=arguments.get("release_id"),
        )

    if name == "knowledge.get_document":
        return await knowledge_get_document(
            db,
            member,
            source_file_id=arguments.get("source_file_id"),
        )

    if name == "knowledge.get_evidence":
        evidence_id = arguments.get("evidence_id")
        if not evidence_id:
            raise BadRequestError(
                message="缺少 evidence_id",
                message_key="errors.common.bad_request",
            )
        return await knowledge_get_evidence(db, member, evidence_id=str(evidence_id))

    if name == "knowledge.get_structure":
        kb_id = arguments.get("knowledge_base_id")
        if not kb_id:
            raise BadRequestError(
                message="缺少 knowledge_base_id",
                message_key="errors.common.bad_request",
            )
        return await knowledge_get_structure(
            db,
            member,
            ragflow,
            knowledge_base_id=str(kb_id),
            query=arguments.get("query"),
            source_file_id=arguments.get("source_file_id"),
        )

    if name == "knowledge.get_table":
        kb_id = arguments.get("knowledge_base_id")
        if not kb_id:
            raise BadRequestError(
                message="缺少 knowledge_base_id",
                message_key="errors.common.bad_request",
            )
        return await knowledge_get_table(
            db,
            member,
            ragflow,
            knowledge_base_id=str(kb_id),
            query=arguments.get("query"),
            source_file_id=arguments.get("source_file_id"),
        )

    raise BadRequestError(
        message=f"未知 MCP 工具: {name}",
        message_key="errors.knowledge.mcp_tool_not_found",
    )


@router.post("/tools/list", response_model=ApiResponse[McpToolsListResponse])
async def mcp_list_tools(
    member: KnowledgePrincipal = Depends(get_member_context),
):
    return ApiResponse(data=McpToolsListResponse(tools=list_tools()))


@router.post("/tools/call", response_model=ApiResponse[McpToolCallResponse])
async def mcp_call_tool(
    body: McpToolCallRequest,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    result = await call_tool(
        db,
        member,
        ragflow,
        name=body.name,
        arguments=body.arguments,
    )
    return ApiResponse(
        data=McpToolCallResponse(
            content=[{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
            is_error=False,
        )
    )
