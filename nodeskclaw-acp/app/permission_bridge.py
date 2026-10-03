from __future__ import annotations

from app.errors import AdapterError
from app.remote_client import RemoteAgentHttpClient


class PermissionBridge:
    def __init__(self, client: RemoteAgentHttpClient):
        self.client = client

    def options(self) -> list[dict[str, str]]:
        return [
            {"optionId": "allow_once", "name": "Allow once", "kind": "allow_once"},
            {"optionId": "reject_once", "name": "Reject once", "kind": "reject_once"},
        ]

    async def apply(
        self,
        *,
        session_id: str,
        run_id: str,
        approval_id: str,
        option_id: str,
    ) -> str:
        if option_id == "allow_once":
            key = f"acp:{session_id}:{run_id}:{approval_id}:approve"
            await self.client.decide_approval(run_id, approval_id, "approve", key)
            return "approved"
        if option_id == "reject_once":
            key = f"acp:{session_id}:{run_id}:{approval_id}:deny"
            await self.client.decide_approval(run_id, approval_id, "deny", key)
            return "denied"
        if option_id in {"cancelled", "cancel"}:
            await self.client.cancel_run(run_id)
            return "cancelled"
        raise AdapterError("ACP_REMOTE_PERMISSION_FAILED", "不支持的 permission 选项")
