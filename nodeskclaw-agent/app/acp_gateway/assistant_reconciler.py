from __future__ import annotations

from app.acp_gateway.errors import AcpGatewayError


class AssistantReconciler:
    def __init__(self) -> None:
        self._accumulated: dict[str, str] = {}

    def apply_delta(self, message_id: str, delta: str) -> str:
        mid = str(message_id or "").strip() or "_default"
        text = delta or ""
        self._accumulated[mid] = self._accumulated.get(mid, "") + text
        return text

    def apply_snapshot(self, message_id: str, snapshot: str) -> str:
        mid = str(message_id or "").strip() or "_default"
        snap = snapshot or ""
        acc = self._accumulated.get(mid, "")
        if not snap.startswith(acc):
            raise AcpGatewayError(
                "ACP_STREAM_RECONCILIATION_MISMATCH",
                "assistant snapshot is not prefix-compatible with emitted deltas",
            )
        suffix = snap[len(acc) :]
        self._accumulated[mid] = snap
        return suffix

    def silent_apply_delta(self, message_id: str, delta: str) -> None:
        self.apply_delta(message_id, delta)

    def silent_apply_snapshot(self, message_id: str, snapshot: str) -> None:
        mid = str(message_id or "").strip() or "_default"
        snap = snapshot or ""
        acc = self._accumulated.get(mid, "")
        if snap.startswith(acc):
            self._accumulated[mid] = snap
            return
        if acc.startswith(snap):
            return
        self._accumulated[mid] = snap
