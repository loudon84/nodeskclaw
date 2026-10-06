"""Minimal ACP JSON-RPC client over WebSocket for Provider Live tests."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import websockets


class RemoteAcpTestClient:
    def __init__(self, url: str, *, token: str, org_id: str, trace_id: str | None = None):
        self.url = url
        self.token = token
        self.org_id = org_id
        self.trace_id = trace_id or str(uuid.uuid4())
        self._ws = None
        self.session_id: str | None = None
        self.updates: list[dict[str, Any]] = []
        self.permissions: list[dict[str, Any]] = []
        self.last_seq = 0

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self.url,
            additional_headers={
                "Authorization": f"Bearer {self.token}",
                "X-Org-Id": self.org_id,
                "X-Trace-Id": self.trace_id,
            },
            subprotocols=["nodeskclaw.remote-acp.v1"],
            open_timeout=15,
        )

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send_rpc(self, method: str, params: dict[str, Any] | None = None, *, request_id: str | None = None) -> str:
        rid = request_id or str(uuid.uuid4())
        await self._ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": rid,
                    "method": method,
                    "params": params or {},
                }
            )
        )
        return rid

    async def wait_response(
        self,
        request_id: str,
        *,
        timeout: float = 30,
        auto_permission: bool = True,
        cancel_after: float | None = None,
        cancel_session_id: str | None = None,
    ) -> dict[str, Any]:
        deadline = asyncio.get_event_loop().time() + timeout
        cancel_task: asyncio.Task[None] | None = None
        if cancel_after is not None:
            async def _send_cancel() -> None:
                await asyncio.sleep(cancel_after)
                await self.send_rpc("session/cancel", {"sessionId": cancel_session_id or self.session_id})

            cancel_task = asyncio.create_task(_send_cancel())
        try:
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f"timed out waiting for {request_id}")
                raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
                frame = json.loads(raw)
                method = frame.get("method")
                if method == "session/update":
                    self.updates.append(frame)
                    seq = ((frame.get("params") or {}).get("seq") or (frame.get("params") or {}).get("event_seq") or 0)
                    try:
                        self.last_seq = max(self.last_seq, int(seq))
                    except (TypeError, ValueError):
                        pass
                    continue
                if method == "session/request_permission":
                    self.permissions.append(frame)
                    if auto_permission:
                        params = frame.get("params") or {}
                        meta = (params.get("_meta") or {}).get("nodeskclaw") or {}
                        await self._ws.send(
                            json.dumps(
                                {
                                    "jsonrpc": "2.0",
                                    "id": frame.get("id"),
                                    "result": {"outcome": "selected", "optionId": "allow_once"},
                                    "_meta": {"nodeskclaw": meta},
                                }
                            )
                        )
                    continue
                if frame.get("id") == request_id:
                    return frame
        finally:
            if cancel_task is not None:
                cancel_task.cancel()

    async def rpc(self, method: str, params: dict[str, Any] | None = None, *, request_id: str | None = None, timeout: float = 30) -> dict[str, Any]:
        rid = await self.send_rpc(method, params, request_id=request_id)
        return await self.wait_response(rid, timeout=timeout)

    async def initialize(self) -> dict[str, Any]:
        return await self.rpc("initialize", {"protocolVersion": 1})

    async def session_new(self) -> str:
        result = await self.rpc("session/new", {"cwd": "/", "mcpServers": []})
        if "error" in result:
            raise RuntimeError(result["error"])
        self.session_id = result["result"]["sessionId"]
        return self.session_id

    async def session_resume(self, session_id: str, after_seq: int = 0) -> dict[str, Any]:
        params: dict[str, Any] = {"sessionId": session_id}
        if after_seq:
            params["_meta"] = {"nodeskclaw": {"after_seq": after_seq}}
        result = await self.rpc("session/resume", params)
        if "error" not in result:
            self.session_id = session_id
        return result
