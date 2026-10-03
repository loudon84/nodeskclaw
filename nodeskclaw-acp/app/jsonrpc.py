from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, TextIO

from app.errors import AdapterError


class JsonRpcServer:
    def __init__(self, agent, stdin: TextIO | None = None, stdout: TextIO | None = None):
        self.agent = agent
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self._pending_permissions: dict[str, asyncio.Future] = {}
        self._permission_seq = 0

    def _write(self, payload: dict[str, Any]) -> None:
        self.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.stdout.flush()

    async def notify(self, session_id: str, update: dict[str, Any]) -> None:
        self._write(
            {
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {"sessionId": session_id, **update},
            }
        )

    async def request_permission(self, params: dict[str, Any]) -> str:
        self._permission_seq += 1
        req_id = f"perm-{self._permission_seq}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_permissions[req_id] = future
        self._write({"jsonrpc": "2.0", "id": req_id, "method": "session/request_permission", "params": params})
        try:
            result = await future
        finally:
            self._pending_permissions.pop(req_id, None)
        if isinstance(result, dict):
            outcome = result.get("outcome") if isinstance(result.get("outcome"), dict) else result
            return str(outcome.get("optionId") or outcome.get("selected") or "cancelled")
        return "cancelled"

    async def serve(self) -> None:
        while True:
            line = await asyncio.to_thread(self.stdin.readline)
            if line == "":
                return
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            await self._dispatch(message)

    async def _dispatch(self, message: dict[str, Any]) -> None:
        if "method" not in message and "id" in message:
            future = self._pending_permissions.get(str(message.get("id")))
            if future and not future.done():
                if "error" in message:
                    future.set_result({"optionId": "cancelled"})
                else:
                    future.set_result(message.get("result") or {})
            return
        method = str(message.get("method") or "")
        req_id = message.get("id")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        session_id = str(params.get("sessionId") or "")
        try:
            if method == "initialize":
                result = self.agent.initialize_result(params)
            elif method == "session/new":
                result = self.agent.session_new(params)
            elif method == "session/prompt":
                async def _notify(update: dict[str, Any]) -> None:
                    await self.notify(session_id, update)

                self.agent.turns.notify = _notify
                self.agent.turns.request_permission = self.request_permission
                result = await self.agent.session_prompt(params, req_id)
            elif method in {"session/cancel", "$/cancel_request"}:
                await self.agent.session_cancel(params)
                if req_id is None:
                    return
                result = {}
            elif method == "authenticate":
                result = {}
            else:
                raise AdapterError("ACP_PROFILE_INVALID", f"不支持的方法 {method}")
        except AdapterError as exc:
            if req_id is not None:
                self._write(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32000, "message": exc.message, "data": exc.to_data()},
                    }
                )
            return
        if req_id is not None:
            self._write({"jsonrpc": "2.0", "id": req_id, "result": result})
