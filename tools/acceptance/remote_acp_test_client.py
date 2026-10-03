"""Minimal ACP JSON-RPC client over WebSocket for Provider Live tests."""

from __future__ import annotations

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

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self.url,
            additional_headers={
                "Authorization": f"Bearer {self.token}",
                "X-Org-Id": self.org_id,
                "X-Trace-Id": self.trace_id,
            },
            subprotocols=["nodeskclaw.remote-acp.v1"],
            open_timeout=10,
        )

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()

    async def rpc(self, method: str, params: dict[str, Any] | None = None, *, request_id: str | None = None) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id or str(uuid.uuid4()),
            "method": method,
            "params": params or {},
        }
        await self._ws.send(json.dumps(payload))
        while True:
            raw = await self._ws.recv()
            frame = json.loads(raw)
            if frame.get("id") == payload["id"] or (frame.get("method") and method == "session/prompt"):
                if frame.get("id") == payload["id"]:
                    return frame
            if method != "session/prompt":
                return frame

    async def initialize(self) -> dict[str, Any]:
        return await self.rpc("initialize", {"protocolVersion": 1})

    async def session_new(self) -> str:
        result = await self.rpc("session/new", {"cwd": "/", "mcpServers": []})
        self.session_id = result["result"]["sessionId"]
        return self.session_id
