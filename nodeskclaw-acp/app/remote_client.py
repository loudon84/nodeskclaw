from __future__ import annotations

from typing import Any, AsyncIterator

import httpx

from app.config import Settings
from app.constants import AUTH_REFRESH_MAX
from app.credentials import CredentialStore
from app.errors import AdapterError, auth_refresh_failed


class RemoteAgentHttpClient:
    def __init__(self, settings: Settings, store: CredentialStore):
        self.settings = settings
        self.store = store
        self._client = httpx.AsyncClient(timeout=60.0)

    def _base(self) -> str:
        return self.settings.NODESKCLAW_BASE_URL.rstrip("/")

    async def close(self) -> None:
        await self._client.aclose()

    async def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        token = await self.store.resolve_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if extra:
            headers.update(extra)
        return headers

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = f"{self._base()}{path}"
        extra_headers = kwargs.pop("headers", None)
        retries = 0
        while True:
            headers = await self._headers(extra_headers)
            response = await self._client.request(method, url, headers=headers, **kwargs)
            if response.status_code != 401 or retries >= AUTH_REFRESH_MAX:
                return response
            if not self.store.current_refresh():
                raise auth_refresh_failed()
            await self.store.refresh_once()
            retries += 1

    async def login(self, account: str, password: str) -> dict[str, Any]:
        url = f"{self._base()}/api/v1/auth/account-login"
        response = await self._client.post(url, json={"account": account, "password": password})
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else payload
        return data if isinstance(data, dict) else {}

    async def refresh_tokens(self, refresh_token: str) -> dict[str, Any]:
        url = f"{self._base()}/api/v1/auth/refresh"
        response = await self._client.post(url, json={"refresh_token": refresh_token})
        if response.status_code >= 400:
            raise auth_refresh_failed()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else payload
        return data if isinstance(data, dict) else {}

    async def doctor_me(self) -> dict[str, Any]:
        response = await self._request("GET", "/api/v1/auth/me")
        if response.status_code >= 400:
            raise AdapterError("ACP_AUTH_REQUIRED", "无法读取当前用户")
        payload = response.json()
        return payload.get("data") if isinstance(payload, dict) else {}

    async def create_run(self, body: dict[str, Any]) -> dict[str, Any]:
        response = await self._request("POST", "/api/v1/remote-agent/runs", json=body)
        return self._parse(response, create=True)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        response = await self._request("GET", f"/api/v1/remote-agent/runs/{run_id}")
        return self._parse(response)

    async def cancel_run(self, run_id: str) -> dict[str, Any]:
        response = await self._request("POST", f"/api/v1/remote-agent/runs/{run_id}/cancel")
        return self._parse(response)

    async def decide_approval(self, run_id: str, approval_id: str, decision: str, idempotency_key: str) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"/api/v1/remote-agent/runs/{run_id}/approvals/{approval_id}/decision",
            json={"decision": decision},
            headers={"X-Idempotency-Key": idempotency_key},
        )
        return self._parse(response)

    async def stream_events(self, run_id: str, last_event_id: str | None = None) -> AsyncIterator[dict[str, Any]]:
        headers = await self._headers({"Accept": "text/event-stream", "Cache-Control": "no-store"})
        if last_event_id:
            headers["Last-Event-ID"] = last_event_id
        url = f"{self._base()}/api/v1/remote-agent/runs/{run_id}/events"
        async with self._client.stream("GET", url, headers=headers) as response:
            if response.status_code == 401:
                await self.store.refresh_once()
                headers = await self._headers({"Accept": "text/event-stream", "Cache-Control": "no-store"})
                if last_event_id:
                    headers["Last-Event-ID"] = last_event_id
                async with self._client.stream("GET", url, headers=headers) as retry:
                    async for item in self._iter_sse(retry):
                        yield item
                return
            async for item in self._iter_sse(response):
                yield item

    async def _iter_sse(self, response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
        event_id = ""
        event_type = ""
        data_lines: list[str] = []
        async for line in response.aiter_lines():
            if line.startswith("id:"):
                event_id = line[3:].strip()
            elif line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line == "":
                if event_type or data_lines:
                    raw = "\n".join(data_lines)
                    payload: dict[str, Any] = {}
                    if raw:
                        import json

                        try:
                            parsed = json.loads(raw)
                            if isinstance(parsed, dict):
                                payload = parsed
                        except json.JSONDecodeError:
                            payload = {"text": raw}
                    yield {"event_id": event_id, "event_type": event_type or payload.get("event_type"), "data": payload}
                event_id = ""
                event_type = ""
                data_lines = []

    def _parse(self, response: httpx.Response, *, create: bool = False) -> dict[str, Any]:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if response.status_code >= 400:
            symbol = str(payload.get("error_code") or "REMOTE_ERROR")
            mapped = self._map_remote_symbol(symbol, create=create)
            raise AdapterError(
                mapped,
                str(payload.get("message") or "远程请求失败"),
                remote_error_code=symbol,
            )
        if isinstance(payload, dict) and "data" in payload and isinstance(payload.get("data"), dict):
            return payload["data"]
        return payload if isinstance(payload, dict) else {}

    def _map_remote_symbol(self, symbol: str, *, create: bool) -> str:
        if symbol in {"REMOTE_AGENT_TARGET_NOT_FOUND", "REMOTE_AGENT_RUNTIME_UNAVAILABLE"}:
            return "ACP_EXPERT_UNAVAILABLE"
        if symbol == "REMOTE_AGENT_SESSION_BUSY":
            return "ACP_SESSION_BUSY"
        if symbol in {
            "REMOTE_AGENT_SESSION_NOT_FOUND",
            "REMOTE_AGENT_SESSION_AMBIGUOUS",
            "REMOTE_AGENT_SESSION_SEQ_AMBIGUOUS",
        }:
            return "ACP_SESSION_RESUME_FORBIDDEN"
        if symbol == "REMOTE_AGENT_SESSION_AGENT_MISMATCH":
            return "ACP_SESSION_AGENT_MISMATCH"
        if create or symbol.endswith("_NOT_FOUND") or "DENIED" in symbol or "REJECTED" in symbol:
            return "ACP_REMOTE_CREATE_FAILED"
        return "ACP_REMOTE_RUN_FAILED"

    async def get_session_proof(self, session_ref: str, profile) -> dict[str, Any]:
        params = {
            "expect_agent_ref": profile.agent_ref,
            "expect_knowledge_ref": list(profile.knowledge_refs),
            "expect_connector_binding_ref": list(profile.connector_binding_refs),
            "expect_integration_account_ref": list(profile.integration_account_refs),
        }
        response = await self._request(
            "GET",
            f"/api/v1/remote-agent/sessions/{session_ref}",
            params=params,
        )
        try:
            return self._parse(response)
        except AdapterError as exc:
            if response.status_code == 404 or exc.remote_error_code in {
                "REMOTE_AGENT_SESSION_NOT_FOUND",
                "REMOTE_AGENT_SESSION_AMBIGUOUS",
                "REMOTE_AGENT_SESSION_SEQ_AMBIGUOUS",
            }:
                raise AdapterError("ACP_SESSION_RESUME_FORBIDDEN", exc.message, remote_error_code=exc.remote_error_code)
            if exc.remote_error_code == "REMOTE_AGENT_SESSION_AGENT_MISMATCH":
                raise AdapterError("ACP_SESSION_AGENT_MISMATCH", exc.message, remote_error_code=exc.remote_error_code)
            raise

    async def get_session_proof_raw(self, session_ref: str) -> tuple[int, dict[str, Any]]:
        response = await self._request("GET", f"/api/v1/remote-agent/sessions/{session_ref}")
        try:
            payload = response.json()
        except Exception:
            payload = {}
        return response.status_code, payload if isinstance(payload, dict) else {}
