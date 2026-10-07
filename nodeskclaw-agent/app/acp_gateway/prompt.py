from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.acp_gateway import PROMPT_IDEMPOTENCY_PREFIX, REMOTE_AGENT_TOOL_NAME
from app.acp_gateway.errors import AcpGatewayError
from app.acp_gateway.resources import canonical_prompt_digest, parse_prompt_attachments
from app.acp_gateway.run_context_client import fetch_run_context
from app.config import settings
from app.schemas import CreateRunRequest
from app.services import run_service

SCHEMA = settings.SKILL_AGENT_SCHEMA


def prompt_idempotency_key(session_id: str, request_id: str) -> str:
    material = f"{PROMPT_IDEMPOTENCY_PREFIX}\x00{session_id}\x00{request_id}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def require_uuid_request_id(request_id: Any) -> str:
    if not isinstance(request_id, str):
        raise AcpGatewayError("ACP_PROTOCOL_ERROR", "mutating request id must be uuid")
    try:
        uuid.UUID(request_id)
    except ValueError as exc:
        raise AcpGatewayError("ACP_PROTOCOL_ERROR", "mutating request id must be uuid") from exc
    return request_id


async def find_run_by_idempotency(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    idempotency_key: str,
) -> dict[str, Any] | None:
    row = (
        await db.execute(
            text(
                f"""
                SELECT id, status, arguments, command_digest
                FROM "{SCHEMA}".runs
                WHERE org_id = :org_id AND user_id = :user_id
                  AND tool_name = :tool_name AND idempotency_key = :idempotency_key
                LIMIT 1
                """
            ),
            {
                "org_id": org_id,
                "user_id": user_id,
                "tool_name": REMOTE_AGENT_TOOL_NAME,
                "idempotency_key": idempotency_key,
            },
        )
    ).mappings().first()
    return dict(row) if row else None


async def create_or_replay_prompt_run(
    db: AsyncSession,
    *,
    session_id: str,
    request_id: str,
    prompt: Any,
    capability_token: str,
    claims: dict[str, Any],
    fetch_context=fetch_run_context,
) -> dict[str, Any]:
    request_id = require_uuid_request_id(request_id)
    digest = canonical_prompt_digest(prompt)
    key = prompt_idempotency_key(session_id, request_id)
    existing = await find_run_by_idempotency(
        db,
        org_id=str(claims["org_id"]),
        user_id=str(claims["user_id"]),
        idempotency_key=key,
    )
    if existing:
        stored = ((existing.get("arguments") or {}).get("acp_prompt_digest"))
        if stored and stored != digest:
            raise AcpGatewayError("ACP_IDEMPOTENCY_CONFLICT", "prompt digest mismatch")
        return {"run_id": existing["id"], "status": existing["status"], "replay": True}

    attachment_refs = parse_prompt_attachments(prompt)
    context = await fetch_context(
        capability=capability_token,
        body={
            "org_id": claims["org_id"],
            "user_id": claims["user_id"],
            "agent_ref": claims["agent_ref"],
            "session_id": session_id,
            "attachment_refs": attachment_refs,
            "prompt_digest": digest,
        },
        trace_id=str(claims.get("trace_id") or ""),
    )
    route_snapshot = dict(context.get("route_snapshot") or {})
    route_snapshot.setdefault("expert_slug", claims["agent_ref"])
    route_snapshot["session_continuity_required"] = True
    run_id = str(uuid.uuid4())
    request = CreateRunRequest(
        run_id=run_id,
        tool_name=REMOTE_AGENT_TOOL_NAME,
        org_id=str(claims["org_id"]),
        user_id=str(claims["user_id"]),
        arguments={"prompt": prompt, "acp_prompt_digest": digest},
        route_snapshot=route_snapshot,
        execution_context=context.get("execution_context") or {},
        context_version=int(context.get("context_version") or claims.get("context_version") or 1),
        knowledge_refs=list(context.get("knowledge_refs") or []),
        placement={"role": "central", "engine": "hermes"},
        idempotency_key=key,
        run_session_id=session_id,
        request_trace_id=str(claims.get("trace_id") or ""),
        dispatch_id=f"acp_{run_id}",
    )
    try:
        created = await run_service.create_run(
            db,
            request,
            org_id=str(claims["org_id"]),
            user_id=str(claims["user_id"]),
        )
    except ValueError as exc:
        text = str(exc)
        if "ACP_RUNTIME_SESSION_CONTINUITY_LOST" in text:
            raise AcpGatewayError(
                "ACP_RUNTIME_SESSION_CONTINUITY_LOST",
                "prior runtime session binding missing",
            ) from exc
        if "BUSY" in text:
            raise AcpGatewayError("ACP_SESSION_BUSY", "session has an active run") from exc
        if "mismatch" in text or "cross-org" in text:
            raise AcpGatewayError("ACP_SESSION_FORBIDDEN", text) from exc
        raise AcpGatewayError("ACP_RUNTIME_UNAVAILABLE", text) from exc
    except RuntimeError as exc:
        if "idempotency conflict" in str(exc):
            raise AcpGatewayError("ACP_IDEMPOTENCY_CONFLICT", "prompt digest mismatch") from exc
        raise
    return {"run_id": created.run_id, "status": created.status, "replay": False}
