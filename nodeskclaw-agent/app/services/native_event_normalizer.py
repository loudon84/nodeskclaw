from __future__ import annotations

import logging
from typing import Any

from app.services.assistant_delta_coalescer import AssistantDeltaCoalescer

logger = logging.getLogger(__name__)

PHASE_STAGE = {
    "PREPARING": "preparing",
    "RUNTIME_STARTING": "runtime_starting",
    "RUNTIME_RUNNING": "runtime_running",
    "WAITING_APPROVAL": "waiting_approval",
    "STOPPING": "stopping",
    "RECONCILING": "reconciling",
}

DELTA_TYPES = frozenset(
    {
        "message.delta",
        "assistant.delta",
        "token.delta",
        "response.output_text.delta",
    }
)
INTERNAL_TYPES = frozenset(
    {
        "reasoning.available",
        "subagent.start",
        "subagent.started",
        "subagent.complete",
        "subagent.completed",
        "approval.responded",
        "run.steered",
    }
)
RUNTIME_TERMINAL_TYPES = frozenset(
    {
        "run.completed",
        "run.failed",
        "run.cancelled",
        "run.canceled",
        "run.interrupted",
    }
)
SENSITIVE_KEYS = frozenset(
    {
        "output_tail",
        "child_session_id",
        "cost",
        "cost_usd",
        "runtime_run_id",
        "files_read",
        "files_written",
        "preview",
    }
)


def progress_payload(phase: str, message: str) -> dict[str, str]:
    canonical = phase.upper()
    stage = PHASE_STAGE.get(canonical, canonical.lower())
    return {"phase": canonical, "stage": stage, "message": message}


def _event_type(data: dict[str, Any]) -> str:
    return str(data.get("type") or data.get("event_type") or data.get("event") or "").strip()


def _payload(data: dict[str, Any]) -> dict[str, Any]:
    nested = data.get("payload")
    return nested if isinstance(nested, dict) else data


def _delta_text(payload: dict[str, Any]) -> str:
    delta = payload.get("delta")
    if isinstance(delta, str) and delta:
        return delta
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str) and content:
            return content
    for key in ("text", "content", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _tool_name(payload: dict[str, Any]) -> str:
    for key in ("tool_name", "tool", "name", "function_name"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _strip_sensitive(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in SENSITIVE_KEYS}


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def normalize_native_event(
    data: dict[str, Any],
    *,
    attempt_id: str,
    source_prefix: str,
    normalizer: NativeEventNormalizer | None = None,
) -> list[dict[str, Any]]:
    owner = normalizer or NativeEventNormalizer(attempt_id=attempt_id, source_prefix=source_prefix)
    return owner.ingest(data)


class NativeEventNormalizer:
    def __init__(
        self,
        *,
        attempt_id: str,
        source_prefix: str,
        coalescer: AssistantDeltaCoalescer | None = None,
    ) -> None:
        self.attempt_id = attempt_id
        self.source_prefix = source_prefix
        self.coalescer = coalescer or AssistantDeltaCoalescer()
        self._counter = 0
        self._segment_seq = 0
        self._open: list[dict[str, Any]] = []
        self.internal_traces: list[dict[str, Any]] = []
        self.observability_gaps: list[dict[str, Any]] = []

    def ingest(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        if "choices" in data or (
            isinstance(data.get("delta"), dict) and "content" in (data.get("delta") or {}) and not _event_type(data)
        ):
            return []
        event_type = _event_type(data)
        payload = _payload(data)
        if event_type in DELTA_TYPES:
            return self._from_texts(self.coalescer.push(_delta_text(payload)))
        if event_type in INTERNAL_TYPES or event_type.startswith("subagent."):
            self._trace(event_type, payload)
            return []
        if event_type in RUNTIME_TERMINAL_TYPES:
            status = "completed" if event_type == "run.completed" else "failed"
            if event_type in {"run.cancelled", "run.canceled"}:
                status = "failed"
            return self.close(terminal_status=status)
        if event_type in {"tool.started", "tool.start"}:
            events = self._from_texts([self.coalescer.flush()] if self.coalescer.buffered_text() else [])
            events.extend(self._start_tool(payload))
            return events
        if event_type in {"tool.completed", "tool.complete", "tool.failed"}:
            events = self._from_texts([self.coalescer.flush()] if self.coalescer.buffered_text() else [])
            failed = event_type == "tool.failed" or bool(payload.get("error"))
            events.extend(self._complete_tool(payload, failed=failed))
            return events
        if event_type in {"approval.request", "approval.requested"}:
            events = self._from_texts([self.coalescer.flush()] if self.coalescer.buffered_text() else [])
            events.extend(self._approval(payload))
            return events
        if event_type in {"assistant.message", "message", "agent.message"}:
            events = self._from_texts([self.coalescer.flush()] if self.coalescer.buffered_text() else [])
            text = payload.get("text") or payload.get("content") or payload.get("message")
            if isinstance(text, str) and text:
                events.append(self._sot("assistant.message", {"text": text}, "assistant"))
            return events
        if event_type == "reasoning.summary":
            summary = payload.get("reasoning_summary") or payload.get("summary")
            if isinstance(summary, str) and summary:
                return [self._sot("reasoning.summary", {"summary": summary}, "reasoning")]
            return []
        if event_type in {"tool.call", "tool_call"}:
            events = self._from_texts([self.coalescer.flush()] if self.coalescer.buffered_text() else [])
            events.extend(self._passthrough_tool_call(payload))
            return events
        if event_type in {"clarify.requested", "clarify"}:
            question = payload.get("question")
            if isinstance(question, str) and question:
                clarify: dict[str, Any] = {"question": question}
                if isinstance(payload.get("options"), list):
                    clarify["options"] = payload["options"]
                return [self._sot("clarify.requested", clarify, "clarify")]
            return []
        return []

    def flush_due_to_latency(self) -> list[dict[str, Any]]:
        text = self.coalescer.flush_if_stale()
        return self._from_texts([text] if text else [])

    def close(self, *, terminal_status: str = "failed") -> list[dict[str, Any]]:
        events = self._from_texts([self.coalescer.flush()] if self.coalescer.buffered_text() else [])
        mapped = "completed" if terminal_status in {"completed", "succeeded", "success"} else "failed"
        while self._open:
            opened = self._open.pop(0)
            events.append(
                self._sot(
                    "tool.call",
                    {"tool_name": opened["tool_name"], "call_id": opened["call_id"], "status": mapped},
                    f"tool:{opened['call_id']}",
                )
            )
            self.observability_gaps.append(
                {
                    "kind": "unpaired_tool_start",
                    "tool_name": opened["tool_name"],
                    "call_id": opened["call_id"],
                    "closed_as": mapped,
                }
            )
            logger.info(
                "native normalizer unpaired tool start closed attempt=%s tool=%s call_id=%s as=%s",
                self.attempt_id,
                opened["tool_name"],
                opened["call_id"],
                mapped,
            )
        return events

    def _start_tool(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        tool_name = _tool_name(payload)
        if not tool_name:
            return []
        upstream = payload.get("tool_call_id") or payload.get("call_id") or payload.get("id")
        self._segment_seq += 1
        if isinstance(upstream, str) and upstream:
            call_id = upstream
            confidence = "high"
        else:
            call_id = f"{self.attempt_id}:{tool_name}:{self._segment_seq}"
            confidence = "low" if any(item["tool_name"] == tool_name for item in self._open) else "high"
        if confidence == "low":
            for item in self._open:
                if item["tool_name"] == tool_name:
                    item["correlation_confidence"] = "low"
        opened = {
            "tool_name": tool_name,
            "call_id": call_id,
            "segment_seq": self._segment_seq,
            "correlation_confidence": confidence,
        }
        self._open.append(opened)
        self._trace(
            "tool.correlation",
            {"tool_name": tool_name, "call_id": call_id, "correlation_confidence": confidence},
        )
        return [
            self._sot(
                "tool.call",
                {"tool_name": tool_name, "call_id": call_id, "status": "started"},
                f"tool:{call_id}",
            )
        ]

    def _complete_tool(self, payload: dict[str, Any], *, failed: bool) -> list[dict[str, Any]]:
        tool_name = _tool_name(payload)
        upstream = payload.get("tool_call_id") or payload.get("call_id") or payload.get("id")
        match_index = None
        if isinstance(upstream, str) and upstream:
            for index, item in enumerate(self._open):
                if item["call_id"] == upstream:
                    match_index = index
                    break
        if match_index is None and tool_name:
            for index, item in enumerate(self._open):
                if item["tool_name"] == tool_name:
                    match_index = index
                    break
        if match_index is None:
            return []
        opened = self._open.pop(match_index)
        status = "failed" if failed else "completed"
        return [
            self._sot(
                "tool.call",
                {"tool_name": opened["tool_name"], "call_id": opened["call_id"], "status": status},
                f"tool:{opened['call_id']}",
            )
        ]

    def _passthrough_tool_call(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        tool_name = _tool_name(payload)
        call_id = payload.get("call_id") or payload.get("id")
        status = payload.get("status") or "started"
        if not isinstance(tool_name, str) or not tool_name or not isinstance(call_id, str) or not call_id:
            return []
        if status not in {"started", "completed", "failed"}:
            status = "started"
        public = {"tool_name": tool_name, "call_id": call_id, "status": status}
        return [self._sot("tool.call", public, f"tool:{call_id}")]

    def _approval(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        approval_id = payload.get("approval_id") or payload.get("id")
        summary = payload.get("summary") or payload.get("text") or payload.get("message")
        if not isinstance(approval_id, str) or not approval_id:
            approval_id = f"{self.attempt_id}:approval:{self._next_id('approval')}"
        if not isinstance(summary, str) or not summary:
            summary = "approval requested"
        return [self._sot("approval.requested", {"approval_id": approval_id, "summary": summary}, "approval")]

    def _from_texts(self, texts: list[str | None]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for text in texts:
            if isinstance(text, str) and text:
                events.append(self._sot("assistant.message", {"text": text}, "assistant"))
        return events

    def _sot(self, event_type: str, payload: dict[str, Any], kind: str) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "payload": payload,
            "source": "agent",
            "source_event_id": f"{self.source_prefix}:{kind}:{self._next_counter()}",
        }

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter

    def _next_id(self, kind: str) -> str:
        return f"{kind}:{self._next_counter()}"

    def _trace(self, event_type: str, payload: dict[str, Any]) -> None:
        trace = {"event_type": event_type, "payload": _strip_sensitive(payload)}
        self.internal_traces.append(trace)
        logger.info("native internal trace attempt=%s type=%s", self.attempt_id, event_type)
