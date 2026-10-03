from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.acp_gateway import ACP_PROTOCOL_VERSION
from app.acp_gateway.errors import AcpGatewayError
from app.acp_gateway.event_pump import pump_run_events
from app.acp_gateway.jsonrpc import error_frame, parse_frame, result_frame
from app.acp_gateway.permission import apply_permission
from app.acp_gateway.prompt import create_or_replay_prompt_run
from app.acp_gateway.session import (
    assert_session_scope,
    close_session,
    create_session,
    latest_run_for_session,
    load_session,
    session_has_nonterminal_run,
)
from app.services import run_service


class AcpConnection:
    def __init__(self, websocket: WebSocket, db: AsyncSession, claims: dict[str, Any], capability_token: str):
        self.websocket = websocket
        self.db = db
        self.claims = claims
        self.capability_token = capability_token
        self.initialized = False
        self.active_prompt: asyncio.Task[Any] | None = None
        self.cancel_event = asyncio.Event()
        self.after_seq = 0
        self._db_lock = asyncio.Lock()

    async def _persist(self) -> None:
        await self.db.commit()

    async def send(self, payload: dict[str, Any]) -> None:
        await self.websocket.send_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    async def serve(self) -> None:
        while True:
            raw = await self.websocket.receive_text()
            try:
                frame = parse_frame(raw)
            except AcpGatewayError as exc:
                await self.send(exc.to_jsonrpc(None))
                continue
            method = frame.get("method")
            request_id = frame.get("id")
            params = frame.get("params") or {}
            try:
                if method == "initialize":
                    await self.send(result_frame(request_id, self._initialize(params)))
                elif method == "session/new":
                    await self.send(result_frame(request_id, await self._session_new(params)))
                elif method == "session/resume":
                    await self.send(result_frame(request_id, await self._session_resume(params)))
                elif method == "session/close":
                    await self._session_close(params)
                    await self.send(result_frame(request_id, {}))
                elif method == "session/prompt":
                    if self.active_prompt and not self.active_prompt.done():
                        raise AcpGatewayError("ACP_SESSION_BUSY", "prompt already running")
                    self.active_prompt = asyncio.create_task(self._run_prompt_and_reply(request_id, params))
                elif method == "session/cancel":
                    await self._session_cancel(params)
                    await self.send(result_frame(request_id, {}))
                elif method == "session/request_permission":
                    await self.send(error_frame(request_id, "ACP_PROTOCOL_ERROR", "server method"))
                else:
                    if request_id is not None and "result" in frame:
                        await self.handle_permission_result(frame)
                        continue
                    await self.send(error_frame(request_id, "ACP_PROTOCOL_ERROR", f"unknown method {method}"))
            except AcpGatewayError as exc:
                await self.send(exc.to_jsonrpc(request_id))

    async def _run_prompt_and_reply(self, request_id: Any, params: dict[str, Any]) -> None:
        try:
            result = await self._session_prompt(request_id, params)
            await self.send(result_frame(request_id, result))
        except AcpGatewayError as exc:
            await self.send(exc.to_jsonrpc(request_id))

    def _initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        if requested not in (None, 1, "1"):
            raise AcpGatewayError("ACP_PROTOCOL_ERROR", "unsupported protocol")
        self.initialized = True
        return {
            "protocolVersion": ACP_PROTOCOL_VERSION,
            "agentCapabilities": {
                "loadSession": False,
                "promptCapabilities": {"image": False, "audio": False, "embeddedContext": False},
                "mcpCapabilities": {"http": False, "sse": False},
                "sessionCapabilities": {"resume": {}, "close": {}},
            },
            "implementation": {
                "name": "nodeskclaw-agent",
                "title": "NodeSkClaw ACP Runtime Gateway",
                "version": "2.0.0",
            },
            "authMethods": [],
        }

    async def _require_session(self, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        session_id = str(params.get("sessionId") or "")
        if not session_id:
            raise AcpGatewayError("ACP_SESSION_NOT_FOUND", "sessionId required")
        row = await load_session(self.db, session_id)
        if not row:
            raise AcpGatewayError("ACP_SESSION_NOT_FOUND", "session not found")
        assert_session_scope(
            row,
            org_id=str(self.claims["org_id"]),
            user_id=str(self.claims["user_id"]),
            agent_ref=str(self.claims["agent_ref"]),
        )
        return session_id, row

    async def _session_new(self, params: dict[str, Any]) -> dict[str, str]:
        if not self.initialized:
            raise AcpGatewayError("ACP_PROTOCOL_ERROR", "initialize required")
        mcp = params.get("mcpServers") or []
        if mcp:
            raise AcpGatewayError("ACP_PROTOCOL_ERROR", "client mcp unsupported")
        session_id = await create_session(
            self.db,
            org_id=str(self.claims["org_id"]),
            user_id=str(self.claims["user_id"]),
            agent_ref=str(self.claims["agent_ref"]),
            cwd=str(params.get("cwd") or "") or None,
        )
        await self._persist()
        return {"sessionId": session_id}

    async def _session_resume(self, params: dict[str, Any]) -> dict[str, Any]:
        if not self.initialized:
            raise AcpGatewayError("ACP_PROTOCOL_ERROR", "initialize required")
        session_id, _row = await self._require_session(params)
        meta = params.get("_meta") or {}
        nodeskclaw = meta.get("nodeskclaw") if isinstance(meta, dict) else {}
        if isinstance(nodeskclaw, dict) and nodeskclaw.get("after_seq") is not None:
            self.after_seq = int(nodeskclaw["after_seq"])
        else:
            self.after_seq = 0
        return {"sessionId": session_id}

    async def _session_close(self, params: dict[str, Any]) -> None:
        session_id, _row = await self._require_session(params)
        if await session_has_nonterminal_run(self.db, session_id):
            raise AcpGatewayError("ACP_SESSION_BUSY", "session has active run")
        await close_session(self.db, session_id)
        await self._persist()

    async def _session_prompt(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        session_id, _row = await self._require_session(params)
        self.cancel_event = asyncio.Event()
        created = await create_or_replay_prompt_run(
            self.db,
            session_id=session_id,
            request_id=str(request_id),
            prompt=params.get("prompt") or params.get("blocks") or [],
            capability_token=self.capability_token,
            claims=self.claims,
        )
        await self._persist()
        stop_reason = await pump_run_events(
            self.db,
            run_id=created["run_id"],
            session_id=session_id,
            agent_ref=str(self.claims["agent_ref"]),
            org_id=str(self.claims["org_id"]),
            after_seq=self.after_seq,
            send=self.send,
            cancel_event=self.cancel_event,
        )
        return {"stopReason": stop_reason}

    async def _session_cancel(self, params: dict[str, Any]) -> None:
        session_id, _row = await self._require_session(params)
        self.cancel_event.set()
        latest = await latest_run_for_session(self.db, session_id)
        if not latest:
            return
        try:
            await run_service.cancel_run(self.db, latest["id"], org_id=str(self.claims["org_id"]))
            await self._persist()
        except Exception as exc:
            raise AcpGatewayError("ACP_CANCEL_FAILED", str(exc)) from exc

    async def handle_permission_result(self, frame: dict[str, Any]) -> None:
        result = frame.get("result") or {}
        meta = (frame.get("_meta") or {}).get("nodeskclaw") or {}
        run_id = str(meta.get("run_id") or "")
        approval_id = str(meta.get("approval_id") or "")
        if not run_id or not approval_id:
            return
        await apply_permission(
            self.db,
            run_id=run_id,
            org_id=str(self.claims["org_id"]),
            approval_id=approval_id,
            outcome=result,
            expected_attempt_id=str(meta.get("attempt_id") or "") or None,
            expected_generation=int(meta["generation"]) if meta.get("generation") is not None else None,
        )


def now_unix() -> int:
    return int(time.time())
