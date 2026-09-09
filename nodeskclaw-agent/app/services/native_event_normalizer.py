from __future__ import annotations

import logging
from typing import Any

from app.services.assistant_delta_coalescer import (
    MAX_SNAPSHOT_UTF8_BYTES,
    AssistantDeltaCoalescer,
    split_utf8_by_bytes,
)
from app.services.execution_observability import record_metric, update_trace_attrs

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
        self._message_counter = 0
        self._segment_seq = 0
        self._open: list[dict[str, Any]] = []
        self._message_id: str | None = None
        self._delta_seq = 0
        self._segment_text = ""
        self._closed_assistant_text = ""
        self._delta_fingerprints: dict[tuple[str, int], str] = {}
        self.payload_rejections: list[dict[str, Any]] = []
        self.internal_traces: list[dict[str, Any]] = []
        self.observability_gaps: list[dict[str, Any]] = []
        self._drained_trace_count = 0

    @property
    def _emitted_assistant(self) -> str:
        return self._closed_assistant_text + self._segment_text

    def ingest(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        if "choices" in data or (
            isinstance(data.get("delta"), dict) and "content" in (data.get("delta") or {}) and not _event_type(data)
        ):
            return []
        event_type = _event_type(data)
        payload = _payload(data)
        if event_type in DELTA_TYPES:
            record_metric("runtime_message_delta_total", labels={"engine": "hermes"})
            return self._emit_delta_chunks(self.coalescer.push(_delta_text(payload)))
        if event_type in INTERNAL_TYPES or event_type.startswith("subagent."):
            self._trace(event_type, payload)
            return []
        if event_type in RUNTIME_TERMINAL_TYPES:
            status = "completed" if event_type == "run.completed" else "failed"
            if event_type in {"run.cancelled", "run.canceled"}:
                status = "failed"
            events = self.close(terminal_status=status)
            output = payload.get("output") or payload.get("final_response")
            if status == "completed" and isinstance(output, str) and output.strip() and not self._emitted_assistant:
                events = self.emit_assistant_snapshot(output.strip()) + events
            return events
        if event_type in {"tool.started", "tool.start"}:
            events = self._close_message_segment()
            events.extend(self._start_tool(payload))
            return events
        if event_type in {"tool.completed", "tool.complete", "tool.failed"}:
            events = self._close_message_segment()
            failed = event_type == "tool.failed" or bool(payload.get("error"))
            events.extend(self._complete_tool(payload, failed=failed))
            return events
        if event_type in {"approval.request", "approval.requested"}:
            events = self._close_message_segment()
            events.extend(self._approval(payload))
            return events
        if event_type in {"assistant.message", "message", "agent.message"}:
            text = payload.get("text") or payload.get("content") or payload.get("message")
            if isinstance(text, str) and text:
                return self._ingest_assistant_text(text)
            return []
        if event_type == "reasoning.summary":
            summary = payload.get("reasoning_summary") or payload.get("summary")
            if isinstance(summary, str) and summary:
                return [self._sot("reasoning.summary", {"summary": summary})]
            return []
        if event_type in {"tool.call", "tool_call"}:
            events = self._close_message_segment()
            events.extend(self._passthrough_tool_call(payload))
            return events
        if event_type in {"clarify.requested", "clarify"}:
            question = payload.get("question")
            if isinstance(question, str) and question:
                clarify: dict[str, Any] = {"question": question}
                if isinstance(payload.get("options"), list):
                    clarify["options"] = payload["options"]
                return [self._sot("clarify.requested", clarify)]
            return []
        return []

    # @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
    def drain_internal_traces(self) -> list[dict[str, Any]]:
        pending = self.internal_traces[self._drained_trace_count :]
        self._drained_trace_count = len(self.internal_traces)
        events: list[dict[str, Any]] = []
        for trace in pending:
            event_type = str(trace.get("event_type") or "")
            if not event_type.startswith("subagent."):
                continue
            events.append(
                self._sot(
                    "internal.runtime.trace",
                    {"runtime_event_type": event_type, "category": "subagent"},
                )
            )
        return events

    def flush_due_to_latency(self) -> list[dict[str, Any]]:
        return self._emit_delta_chunks(self.coalescer.flush_if_stale_chunks())

    def emit_assistant_snapshot(self, text: str) -> list[dict[str, Any]]:
        if not isinstance(text, str) or not text:
            return []
        if self._is_duplicate_assistant(text):
            return []
        current = self._segment_text + self.coalescer.buffered_text()
        if current and text.startswith(current):
            extension = text[len(current) :]
            if extension:
                events = self._emit_delta_chunks(self.coalescer.push(extension))
                events.extend(self._close_message_segment())
                return events
            return self._close_message_segment()
        if current:
            self._reject("assistant_snapshot_conflict", {"existing": current, "incoming": text})
            return self._close_message_segment()
        return self._emit_direct_snapshot(text)

    def close(self, *, terminal_status: str = "failed") -> list[dict[str, Any]]:
        events = self._close_message_segment()
        mapped = "completed" if terminal_status in {"completed", "succeeded", "success"} else "failed"
        while self._open:
            opened = self._open.pop(0)
            events.append(
                self._sot(
                    "tool.call",
                    {"tool_name": opened["tool_name"], "call_id": opened["call_id"], "status": mapped},
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
            record_metric("runtime_tool_unpaired_total", labels={"outcome": mapped})
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
        update_trace_attrs(tool_call_id=call_id, correlation_confidence=confidence)
        record_metric("runtime_tool_start_total", labels={"outcome": "started"})
        return [
            self._sot(
                "tool.call",
                {"tool_name": tool_name, "call_id": call_id, "status": "started"},
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
        record_metric("runtime_tool_complete_total", labels={"outcome": status})
        return [
            self._sot(
                "tool.call",
                {"tool_name": opened["tool_name"], "call_id": opened["call_id"], "status": status},
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
        return [self._sot("tool.call", public)]

    def _approval(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        approval_id = payload.get("approval_id") or payload.get("id")
        summary = payload.get("summary") or payload.get("text") or payload.get("message")
        if not isinstance(approval_id, str) or not approval_id:
            approval_id = f"{self.attempt_id}:approval:{self._next_id('approval')}"
        if not isinstance(summary, str) or not summary:
            summary = "approval requested"
        return [self._sot("approval.requested", {"approval_id": approval_id, "summary": summary})]

    def _ingest_assistant_text(self, text: str) -> list[dict[str, Any]]:
        emitted = self._emitted_assistant
        pending = self.coalescer.buffered_text()
        current = emitted + pending
        if text == emitted or text == current:
            return []
        if current and text.startswith(current):
            text = text[len(current) :]
            if not text:
                return []
        return self._emit_delta_chunks(self.coalescer.push(text))

    def _is_duplicate_assistant(self, text: str) -> bool:
        emitted = self._emitted_assistant
        pending = self.coalescer.buffered_text()
        return text == emitted or text == emitted + pending

    def _emit_delta_chunks(self, texts: list[str]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for text in texts:
            if not isinstance(text, str) or not text:
                continue
            for chunk in split_utf8_by_bytes(text, self.coalescer.MAX_DELTA_UTF8_BYTES):
                event = self._append_delta(chunk)
                if event is not None:
                    events.append(event)
        return events

    def _append_delta(self, chunk: str) -> dict[str, Any] | None:
        if not chunk:
            return None
        self._ensure_message_segment()
        assert self._message_id is not None
        next_seq = self._delta_seq + 1
        key = (self._message_id, next_seq)
        prior = self._delta_fingerprints.get(key)
        if prior is not None and prior != chunk:
            self._reject(
                "delta_seq_conflict",
                {"message_id": self._message_id, "delta_seq": next_seq, "existing": prior, "incoming": chunk},
            )
            return None
        candidate = self._segment_text + chunk
        if len(candidate.encode("utf-8")) > MAX_SNAPSHOT_UTF8_BYTES:
            self._reject(
                "snapshot_too_large",
                {"message_id": self._message_id, "size": len(candidate.encode("utf-8"))},
            )
            return None
        self._delta_seq = next_seq
        self._delta_fingerprints[key] = chunk
        self._segment_text = candidate
        return self._sot(
            "assistant.delta",
            {"message_id": self._message_id, "delta_seq": self._delta_seq, "delta": chunk},
        )

    def _close_message_segment(self) -> list[dict[str, Any]]:
        events = self._emit_delta_chunks(self.coalescer.flush_chunks())
        if self._message_id is None:
            return events
        if not self._segment_text:
            self._reset_message_segment()
            return events
        if len(self._segment_text.encode("utf-8")) > MAX_SNAPSHOT_UTF8_BYTES:
            self._reject(
                "snapshot_too_large",
                {"message_id": self._message_id, "size": len(self._segment_text.encode("utf-8"))},
            )
            self._reset_message_segment()
            return events
        events.append(
            self._sot(
                "assistant.message",
                {"message_id": self._message_id, "text": self._segment_text},
            )
        )
        self._closed_assistant_text += self._segment_text
        self._reset_message_segment()
        return events

    def _emit_direct_snapshot(self, text: str) -> list[dict[str, Any]]:
        if len(text.encode("utf-8")) > MAX_SNAPSHOT_UTF8_BYTES:
            self._reject("snapshot_too_large", {"size": len(text.encode("utf-8"))})
            return []
        self._ensure_message_segment()
        assert self._message_id is not None
        message_id = self._message_id
        self._segment_text = text
        self._closed_assistant_text += text
        self._reset_message_segment()
        return [self._sot("assistant.message", {"message_id": message_id, "text": text})]

    def _ensure_message_segment(self) -> None:
        if self._message_id is None:
            self._message_counter += 1
            self._message_id = f"msg_{self.attempt_id}_{self._message_counter}"
            self._delta_seq = 0
            self._segment_text = ""

    def _reset_message_segment(self) -> None:
        self._message_id = None
        self._delta_seq = 0
        self._segment_text = ""

    def _reject(self, reason: str, details: dict[str, Any]) -> None:
        record = {"reason": reason, "details": details}
        self.payload_rejections.append(record)
        logger.warning(
            "native normalizer rejection attempt=%s reason=%s details=%s",
            self.attempt_id,
            reason,
            details,
        )

    def _sot(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_type": event_type,
            "payload": payload,
            "source": "agent",
            "source_event_id": f"{self.source_prefix}:{self._next_counter()}",
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
