from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.services import run_service
from app.services.agent_tool_gateway import (
    APPROVAL_EVENT,
    RESULT_EVENT,
    arguments_digest,
    decide_tool_call,
    find_argument_conflict,
    find_pending_approval,
    find_tool_result,
    public_tool_view,
)
from app.services.attempt_capability import stable_tool_call_id, verify_capability
from app.services.connector_router import execute_connector_run
from app.services.remote_agent_catalog_client import RemoteAgentCatalogClient
from app.services.secret_store import SecretStore

router = APIRouter(prefix="/internal/v1/agent-tools", tags=["agent-tools"])


def _event_dicts(events) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        payload = getattr(event, "payload", None)
        rows.append(
            {
                "event_type": getattr(event, "event_type", None),
                "payload": payload if isinstance(payload, dict) else {},
            }
        )
    return rows


@router.post("/mcp")
async def agent_tools_mcp(
    body: dict[str, Any],
    db: AsyncSession = Depends(get_db),
    capability: str | None = Header(default=None, alias="X-Agent-Tool-Capability"),
):
    claims, capability_error = verify_capability(
        capability,
        signing_key=settings.AGENT_TOOL_CAPABILITY_SIGNING_KEY,
    )
    if claims is None:
        raise HTTPException(status_code=401, detail=capability_error)
    run_id = str(claims.get("run_id") or "")
    org_id = str(claims.get("org_id") or "")
    attempt_id = str(claims.get("attempt_id") or "")
    token_generation = int(claims.get("generation") or 0)
    run = await run_service.get_run(db, run_id, org_id=org_id)
    if run is None or run.tool_name != "remote_agent" or run.status in run_service.TERMINAL or str(run.attempt_id or "") != attempt_id:
        raise HTTPException(status_code=401, detail="AGENT_TOOL_CAPABILITY_MISSING")
    generation = int(run.generation or 0)
    if generation != token_generation:
        raise HTTPException(status_code=401, detail="AGENT_TOOL_CAPABILITY_FENCED")
    method = str(body.get("method") or "")
    if method == "tools/list":
        tools = await _catalog_tools(run)
        return {"jsonrpc": "2.0", "id": body.get("id"), "result": {"tools": [public_tool_view(tool) for tool in tools]}}
    if method == "tools/call":
        if body.get("id") in (None, ""):
            raise HTTPException(status_code=400, detail="JSON-RPC id is required")
        result = await _call_tool(
            db,
            run,
            body.get("params") if isinstance(body.get("params"), dict) else {},
            generation,
            attempt_id=attempt_id,
            rpc_id=str(body.get("id")),
        )
        return {"jsonrpc": "2.0", "id": body.get("id"), "result": result}
    raise HTTPException(status_code=400, detail="unsupported mcp method")


async def _catalog_tools(run) -> list[dict[str, Any]]:
    snapshot = run.snapshot or {}
    binding_ids = list(snapshot.get("connector_binding_refs") or [])
    return await RemoteAgentCatalogClient().list_tools(
        org_id=run.org_id,
        binding_ids=binding_ids,
        account_ids=list(snapshot.get("integration_account_refs") or []),
        expert_id=str(snapshot.get("expert_id") or ""),
        user_id=getattr(run, "user_id", None),
    )


async def _call_tool(
    db: AsyncSession,
    run,
    params: dict[str, Any],
    generation: int,
    *,
    attempt_id: str,
    rpc_id: str,
) -> dict[str, Any]:
    tool_name = str(params.get("name") or "")
    arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
    tool_call_id = stable_tool_call_id(attempt_id=attempt_id, generation=generation, rpc_id=rpc_id)
    digest = arguments_digest(arguments)
    events = _event_dicts(await run_service.list_events(db, run.run_id))
    if find_argument_conflict(events, tool_call_id=tool_call_id, digest=digest):
        return {"isError": True, "content": [{"type": "text", "text": "TOOL_CALL_IDEMPOTENCY_CONFLICT"}]}
    stored = find_tool_result(events, tool_call_id=tool_call_id, digest=digest)
    tools = await _catalog_tools(run)
    listed = any(tool.get("tool_name") == tool_name for tool in tools)
    pending = find_pending_approval(events)
    decision = decide_tool_call(
        generation_matches=generation == int(run.generation or 0),
        tool_listed=listed,
        run_waiting=run.status == "WAITING_APPROVAL",
        pending_other=pending is not None,
        stored_result=stored,
    )
    if decision == "replay" and stored is not None:
        return stored.get("result") or {"isError": False, "content": stored.get("content")}
    if decision == "fail_run":
        await run_service.set_status(db, run.run_id, "FAILED", org_id=run.org_id)
        await run_service.append_event(
            db,
            run.run_id,
            RESULT_EVENT,
            {"tool_call_id": tool_call_id, "arguments_digest": digest, "outcome": "STALE_ATTEMPT"},
            org_id=run.org_id,
        )
        return {"isError": True, "content": [{"type": "text", "text": "STALE_ATTEMPT"}]}
    if decision == "deny_unknown":
        return {"isError": True, "content": [{"type": "text", "text": "CONNECTOR_TOOL_NOT_ALLOWED"}]}
    if decision == "tool_error":
        return {"isError": True, "content": [{"type": "text", "text": "CONNECTOR_APPROVAL_PENDING"}]}
    approval_id = str(uuid.uuid4())
    await run_service.set_status(
        db,
        run.run_id,
        "WAITING_APPROVAL",
        org_id=run.org_id,
        expected_status=[run.status],
    )
    await run_service.append_event(
        db,
        run.run_id,
        APPROVAL_EVENT,
        {
            "approval_id": approval_id,
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "arguments_digest": digest,
            "arguments": arguments,
        },
        org_id=run.org_id,
    )
    return {
        "isError": True,
        "content": [{"type": "text", "text": "REQUIRE_APPROVAL"}],
        "approval_id": approval_id,
    }


async def complete_connector_approval(
    db: AsyncSession,
    *,
    run,
    approval_id: str,
    choice: str,
) -> bool:
    events = _event_dicts(await run_service.list_events(db, run.run_id))
    pending = find_pending_approval(events)
    if pending is None or str(pending.get("approval_id")) != approval_id:
        return False
    tool_name = str(pending.get("tool_name") or "")
    digest = str(pending.get("arguments_digest") or "")
    tool_call_id = str(pending.get("tool_call_id") or "")
    arguments = pending.get("arguments") if isinstance(pending.get("arguments"), dict) else {}
    if choice == "deny":
        await run_service.set_status(db, run.run_id, "RUNNING", org_id=run.org_id, expected_status=["WAITING_APPROVAL"])
        await run_service.append_event(
            db,
            run.run_id,
            RESULT_EVENT,
            {
                "approval_id": approval_id,
                "tool_call_id": tool_call_id,
                "arguments_digest": digest,
                "outcome": "TOOL_EXECUTION_DENIED",
                "result": {"isError": True, "content": [{"type": "text", "text": "TOOL_EXECUTION_DENIED"}]},
            },
            org_id=run.org_id,
        )
        return True
    tools = await _catalog_tools(run)
    selected = next((tool for tool in tools if tool.get("tool_name") == tool_name), None)
    listed = selected is not None
    if not listed:
        await run_service.set_status(db, run.run_id, "FAILED", org_id=run.org_id, expected_status=["WAITING_APPROVAL"])
        await run_service.append_event(
            db,
            run.run_id,
            RESULT_EVENT,
            {"approval_id": approval_id, "tool_call_id": tool_call_id, "arguments_digest": digest, "outcome": "CONNECTOR_CONTEXT_STALE"},
            org_id=run.org_id,
        )
        return True
    if selected and selected.get("source") == "external":
        return await _complete_external_approval(
            db,
            run=run,
            approval_id=approval_id,
            tool_call_id=tool_call_id,
            digest=digest,
            tool_name=tool_name,
            arguments=arguments,
        )
    snapshot = run.snapshot or {}
    route = await RemoteAgentCatalogClient().resolve_route(
        org_id=run.org_id,
        binding_ids=list(snapshot.get("connector_binding_refs") or []),
        tool_name=tool_name,
    )
    if route is None:
        await run_service.set_status(db, run.run_id, "FAILED", org_id=run.org_id, expected_status=["WAITING_APPROVAL"])
        return True
    secret_ref = str(route.get("connector_secret_ref_id") or "").strip()
    if secret_ref:
        try:
            SecretStore().resolve(secret_ref, fail_closed=True)
        except Exception:
            await run_service.set_status(db, run.run_id, "FAILED", org_id=run.org_id, expected_status=["WAITING_APPROVAL"])
            await run_service.append_event(
                db,
                run.run_id,
                RESULT_EVENT,
                {"approval_id": approval_id, "tool_call_id": tool_call_id, "arguments_digest": digest, "outcome": "CONNECTOR_CREDENTIAL_UNAVAILABLE"},
                org_id=run.org_id,
            )
            return True
    try:
        events_out = []
        async for event in execute_connector_run(
            tool_name=tool_name,
            arguments=arguments,
            route_snapshot={
                "connector_kind": route.get("connector_kind"),
                "connector_config": route.get("connector_config") or {},
                "connector_secret_ref_id": route.get("connector_secret_ref_id"),
            },
            org_id=run.org_id,
        ):
            events_out.append(event)
        await run_service.set_status(db, run.run_id, "RUNNING", org_id=run.org_id, expected_status=["WAITING_APPROVAL"])
        await run_service.append_event(
            db,
            run.run_id,
            RESULT_EVENT,
            {
                "approval_id": approval_id,
                "tool_call_id": tool_call_id,
                "arguments_digest": digest,
                "outcome": "ok",
                "result": {"isError": False, "content": events_out},
            },
            org_id=run.org_id,
        )
    except Exception as exc:
        from app.services.agent_tool_gateway import classify_connector_exception

        kind = classify_connector_exception(exc)
        outcome = "CONNECTOR_ACTION_OUTCOME_UNKNOWN" if kind == "outcome_unknown" else "CONNECTOR_TOOL_ERROR"
        next_status = "FAILED" if kind == "fail_run" else "RUNNING"
        await run_service.set_status(db, run.run_id, next_status, org_id=run.org_id, expected_status=["WAITING_APPROVAL"])
        await run_service.append_event(
            db,
            run.run_id,
            RESULT_EVENT,
            {"approval_id": approval_id, "tool_call_id": tool_call_id, "arguments_digest": digest, "outcome": outcome},
            org_id=run.org_id,
        )
    return True


async def _complete_external_approval(
    db: AsyncSession,
    *,
    run,
    approval_id: str,
    tool_call_id: str,
    digest: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> bool:
    outcome_body = await RemoteAgentCatalogClient().execute_external(
        run_id=run.run_id,
        tool_name=tool_name,
        arguments=arguments,
        tool_call_id=tool_call_id,
        attempt_id=str(run.attempt_id or ""),
        generation=int(run.generation or 0),
        approval_id=approval_id,
        arguments_digest=digest,
    )
    outcome = str((outcome_body or {}).get("outcome") or "fail_run")
    if outcome == "fail_run":
        await run_service.set_status(db, run.run_id, "FAILED", org_id=run.org_id, expected_status=["WAITING_APPROVAL"])
        await run_service.append_event(
            db,
            run.run_id,
            RESULT_EVENT,
            {"approval_id": approval_id, "tool_call_id": tool_call_id, "arguments_digest": digest, "outcome": "EXTERNAL_ACTION_CONTEXT_STALE"},
            org_id=run.org_id,
        )
        return True
    if outcome == "outcome_unknown":
        recorded = "EXTERNAL_ACTION_OUTCOME_UNKNOWN"
        next_status = "RUNNING"
        result = {"isError": True, "content": [{"type": "text", "text": recorded}]}
    elif outcome == "ok":
        recorded = "ok"
        next_status = "RUNNING"
        result = outcome_body.get("result") or {"isError": False, "content": []}
    elif outcome == "conflict":
        recorded = "TOOL_CALL_IDEMPOTENCY_CONFLICT"
        next_status = "RUNNING"
        result = {"isError": True, "content": [{"type": "text", "text": recorded}]}
    else:
        recorded = "EXTERNAL_TOOL_ERROR"
        next_status = "RUNNING"
        result = {"isError": True, "content": [{"type": "text", "text": recorded}]}
    await run_service.set_status(db, run.run_id, next_status, org_id=run.org_id, expected_status=["WAITING_APPROVAL"])
    await run_service.append_event(
        db,
        run.run_id,
        RESULT_EVENT,
        {
            "approval_id": approval_id,
            "tool_call_id": tool_call_id,
            "arguments_digest": digest,
            "outcome": recorded,
            "result": result,
        },
        org_id=run.org_id,
    )
    return True
