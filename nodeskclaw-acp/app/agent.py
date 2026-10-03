from __future__ import annotations

from pathlib import Path
from typing import Any

from app.constants import ACP_PROTOCOL_VERSION, ACP_SDK_PIN, CONFORMANCE_LABEL
from app.errors import AdapterError, client_mcp_unsupported, protocol_unsupported, session_not_found
from app.permission_bridge import PermissionBridge
from app.profile import Profile
from app.prompt_turn import PromptTurnController
from app.remote_client import RemoteAgentHttpClient
from app.session_registry import SessionRegistry


class AcpV1Agent:
    def __init__(
        self,
        profile: Profile,
        registry: SessionRegistry,
        client: RemoteAgentHttpClient,
        turns: PromptTurnController,
        permissions: PermissionBridge,
        writer,
    ):
        self.profile = profile
        self.registry = registry
        self.client = client
        self.turns = turns
        self.permissions = permissions
        self.writer = writer
        self._initialized = False

    def initialize_result(self, params: dict[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        if requested not in (None, 1, "1"):
            raise protocol_unsupported()
        self._initialized = True
        return {
            "protocolVersion": ACP_PROTOCOL_VERSION,
            "agentCapabilities": {
                "loadSession": False,
                "promptCapabilities": {"image": False, "audio": False, "embeddedContext": False},
                "mcpCapabilities": {"http": False, "sse": False},
                "sessionCapabilities": {"resume": {}, "close": {}},
            },
            "implementation": {
                "name": "nodeskclaw-acp",
                "title": "NodeSkClaw Remote Expert ACP Adapter",
                "version": "1.6.1",
                "sdk": ACP_SDK_PIN,
                "conformance": CONFORMANCE_LABEL,
            },
            "authMethods": [
                {
                    "id": "nodeskclaw-acp-login",
                    "name": "nodeskclaw-acp login",
                    "description": "Interactive NodeSkClaw account login into OS keyring",
                }
            ],
        }

    def session_new(self, params: dict[str, Any]) -> dict[str, str]:
        cwd = str(params.get("cwd") or "")
        if not cwd or not Path(cwd).is_absolute():
            raise AdapterError("ACP_PROFILE_INVALID", "cwd 必须是绝对路径")
        mcp = params.get("mcpServers")
        if mcp is None:
            mcp = []
        if mcp:
            raise client_mcp_unsupported()
        state = self.registry.create(cwd)
        return {"sessionId": state.session_id}

    async def session_resume(self, params: dict[str, Any]) -> dict[str, Any]:
        cwd = str(params.get("cwd") or "")
        if not cwd or not Path(cwd).is_absolute() or not Path(cwd).exists():
            raise AdapterError("ACP_PROFILE_INVALID", "cwd 必须是存在的绝对路径")
        mcp = params.get("mcpServers")
        if mcp is None:
            mcp = []
        if mcp:
            raise client_mcp_unsupported()
        session_id = str(params.get("sessionId") or "")
        if not session_id:
            raise session_not_found()
        proof = await self.client.get_session_proof(session_id, self.profile)
        next_seq = int(proof.get("next_turn_seq") or 1)
        busy = str(proof.get("status") or "") == "busy"
        self.registry.adopt(session_id, cwd, next_turn_seq=next_seq, remote_busy=busy)
        return {}

    async def session_close(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id = str(params.get("sessionId") or "")
        if not session_id:
            raise session_not_found()
        status, payload = await self.client.get_session_proof_raw(session_id)
        run_ids: list[str] = []
        if status == 200:
            last_run_id = payload.get("last_run_id")
            if payload.get("status") == "busy" and last_run_id:
                run_ids.append(str(last_run_id))
        elif status == 409:
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            extra = data.get("non_terminal_run_ids") or []
            run_ids.extend(str(item) for item in extra)
        for run_id in run_ids:
            try:
                await self.client.cancel_run(run_id)
            except AdapterError:
                pass
        self.registry.drop(session_id)
        return {}

    async def session_prompt(self, params: dict[str, Any], request_id: Any) -> dict[str, Any]:
        session_id = str(params.get("sessionId") or "")
        prompt = params.get("prompt")
        if not isinstance(prompt, list):
            raise AdapterError("ACP_PROMPT_UNSUPPORTED_CONTENT", "prompt 必须是 ContentBlock 数组")
        return await self.turns.run_prompt(session_id, str(request_id), prompt)

    async def session_cancel(self, params: dict[str, Any]) -> None:
        session_id = str(params.get("sessionId") or "")
        if not session_id:
            raise session_not_found()
        await self.turns.cancel(session_id)
