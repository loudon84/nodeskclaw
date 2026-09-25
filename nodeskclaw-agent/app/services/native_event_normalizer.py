from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.schemas import MAX_TOOL_EVENT_JSON_DEPTH, MAX_TOOL_EVENT_UTF8_BYTES
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
_SENSITIVE_KEY_RE = re.compile(
    r"(authorization|cookie|api[_-]?key|token|password|secret|private[_-]?key|"
    r"credential|access[_-]?key|refresh[_-]?token|signature|set-cookie|(^|_)signed(_|$))",
    re.I,
)
_SENSITIVE_QUERY = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "password",
        "secret",
        "signature",
        "sig",
        "x-amz-signature",
        "x-amz-credential",
        "x-amz-security-token",
        "x-amz-signedheaders",
        "api_key",
        "apikey",
        "authorization",
        "auth",
    }
)
_ABS_UNIX_RE = re.compile(r"^/(?:home|Users|root|var|opt|tmp|etc|usr|mnt|data)(?:/|$)")
_ABS_WIN_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\)")
_ARGUMENT_KEYS = ("arguments", "input", "params", "args")


@dataclass
class _SanitizeFlags:
    redacted: bool = False
    truncated: bool = False


def _is_sensitive_key(key: str) -> bool:
    if key in SENSITIVE_KEYS:
        return True
    return bool(_SENSITIVE_KEY_RE.search(key))


def _looks_like_url(value: str) -> bool:
    return "://" in value or value.startswith("www.")


def _looks_like_abs_path(value: str) -> bool:
    if _looks_like_url(value):
        return False
    return bool(_ABS_UNIX_RE.match(value) or _ABS_WIN_RE.match(value))


def _safe_basename(value: str) -> str:
    name = value.replace("\\", "/").rstrip("/").split("/")[-1]
    return name or "redacted-path"


def _strip_sensitive_query(value: str, flags: _SanitizeFlags) -> str:
    parsed = urlparse(value)
    if not parsed.query and not parsed.fragment:
        return value
    kept = []
    changed = False
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in _SENSITIVE_QUERY or _is_sensitive_key(key):
            changed = True
            flags.redacted = True
            continue
        kept.append((key, item))
    query = urlencode(kept, doseq=True)
    fragment = parsed.fragment
    if fragment and (_is_sensitive_key(fragment) or any(part.lower() in _SENSITIVE_QUERY for part in fragment.split("&"))):
        fragment = ""
        changed = True
        flags.redacted = True
    if not changed:
        return value
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, fragment)
    )


def _sanitize_string(value: str, flags: _SanitizeFlags) -> str:
    if _looks_like_url(value):
        return _strip_sensitive_query(value, flags)
    if _looks_like_abs_path(value):
        flags.redacted = True
        return _safe_basename(value)
    return value


def _json_depth(value: Any, depth: int = 1) -> int:
    if isinstance(value, dict):
        if not value:
            return depth
        return max(_json_depth(item, depth + 1) for item in value.values())
    if isinstance(value, list):
        if not value:
            return depth
        return max(_json_depth(item, depth + 1) for item in value)
    return depth


def _payload_utf8_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _sanitize_node(value: Any, *, depth: int, flags: _SanitizeFlags) -> Any:
    if isinstance(value, (dict, list)) and depth >= MAX_TOOL_EVENT_JSON_DEPTH:
        flags.truncated = True
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or _is_sensitive_key(key):
                flags.redacted = True
                continue
            out[key] = _sanitize_node(item, depth=depth + 1, flags=flags)
        return out
    if isinstance(value, list):
        return [_sanitize_node(item, depth=depth + 1, flags=flags) for item in value]
    if isinstance(value, str):
        return _sanitize_string(value, flags)
    if isinstance(value, bytes):
        flags.redacted = True
        return None
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    flags.redacted = True
    return None


def _clip_depth(value: Any, *, depth: int, flags: _SanitizeFlags) -> Any:
    if isinstance(value, (dict, list)) and depth >= MAX_TOOL_EVENT_JSON_DEPTH:
        flags.truncated = True
        return None
    if isinstance(value, dict):
        return {key: _clip_depth(item, depth=depth + 1, flags=flags) for key, item in value.items()}
    if isinstance(value, list):
        return [_clip_depth(item, depth=depth + 1, flags=flags) for item in value]
    return value


def _shrink_to_utf8_limit(value: Any, flags: _SanitizeFlags) -> Any:
    if _payload_utf8_size(value) <= MAX_TOOL_EVENT_UTF8_BYTES:
        return value
    flags.truncated = True
    if isinstance(value, str):
        encoded = value.encode("utf-8")
        return encoded[:MAX_TOOL_EVENT_UTF8_BYTES].decode("utf-8", errors="ignore")
    if isinstance(value, list):
        trimmed = list(value)
        while trimmed and _payload_utf8_size(trimmed) > MAX_TOOL_EVENT_UTF8_BYTES:
            trimmed.pop()
        return [_shrink_to_utf8_limit(item, flags) for item in trimmed]
    if isinstance(value, dict):
        out = dict(value)
        keys = list(out)
        while keys and _payload_utf8_size(out) > MAX_TOOL_EVENT_UTF8_BYTES:
            key = keys.pop()
            item = out[key]
            if isinstance(item, str):
                budget = max(0, MAX_TOOL_EVENT_UTF8_BYTES - (_payload_utf8_size(out) - _payload_utf8_size(item)))
                out[key] = item.encode("utf-8")[:budget].decode("utf-8", errors="ignore")
            elif isinstance(item, (dict, list)):
                out[key] = _shrink_to_utf8_limit(item, flags)
            if _payload_utf8_size(out) > MAX_TOOL_EVENT_UTF8_BYTES:
                del out[key]
        return out
    return None


def _fit_public_payload(payload: dict[str, Any], flags: _SanitizeFlags) -> dict[str, Any]:
    fitted = _clip_depth(payload, depth=1, flags=flags)
    if not isinstance(fitted, dict):
        fitted = {"redacted": flags.redacted, "truncated": True}
        flags.truncated = True
        return fitted
    if _payload_utf8_size(fitted) > MAX_TOOL_EVENT_UTF8_BYTES:
        fitted = _shrink_to_utf8_limit(fitted, flags)
        if not isinstance(fitted, dict):
            fitted = {"redacted": flags.redacted, "truncated": True}
    fitted["redacted"] = flags.redacted
    fitted["truncated"] = flags.truncated
    if _payload_utf8_size(fitted) > MAX_TOOL_EVENT_UTF8_BYTES:
        flags.truncated = True
        compact = {
            key: fitted[key]
            for key in ("tool_name", "call_id", "status", "error_code")
            if key in fitted
        }
        compact["redacted"] = flags.redacted
        compact["truncated"] = True
        return compact
    return fitted


def _extract_structured_arguments(payload: dict[str, Any]) -> dict[str, Any] | None:
    for key in _ARGUMENT_KEYS:
        if key not in payload:
            continue
        value = payload[key]
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            if isinstance(parsed, dict):
                return parsed
        return None
    return None


def _extract_result_content(payload: dict[str, Any]) -> tuple[str | None, Any]:
    structured = payload.get("structured_content")
    if structured is None:
        structured = payload.get("structuredContent")
    content = None
    for key in ("content", "output", "text", "result"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            content = value
            break
        if structured is None and isinstance(value, (dict, list)):
            structured = value
    return content, structured


def _extract_error_fields(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    error_code = payload.get("error_code")
    error_message = payload.get("error_message")
    error = payload.get("error")
    if isinstance(error, dict):
        if not isinstance(error_code, str) or not error_code:
            raw_code = error.get("code") or error.get("error_code")
            error_code = raw_code if isinstance(raw_code, str) else error_code
        if not isinstance(error_message, str) or not error_message:
            raw_message = error.get("message") or error.get("error_message")
            error_message = raw_message if isinstance(raw_message, str) else error_message
    elif isinstance(error, str) and error and not isinstance(error_message, str):
        error_message = error
    if isinstance(error_code, str) and error_code:
        return error_code, error_message if isinstance(error_message, str) else None
    return None, error_message if isinstance(error_message, str) else None


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


def _strip_sensitive(payload: dict[str, Any], flags: _SanitizeFlags | None = None) -> dict[str, Any]:
    owner = flags or _SanitizeFlags()
    cleaned = _sanitize_node(payload, depth=1, flags=owner)
    return cleaned if isinstance(cleaned, dict) else {}


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
            events.append(self._sot("tool.result", self._tool_result_payload(opened, {}, mapped)))
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
        return [self._sot("tool.call", self._started_tool_payload(tool_name, call_id, payload))]

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
            ),
            self._sot("tool.result", self._tool_result_payload(opened, payload, status)),
        ]

    def _passthrough_tool_call(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        tool_name = _tool_name(payload)
        call_id = payload.get("call_id") or payload.get("id")
        status = payload.get("status") or "started"
        if not isinstance(tool_name, str) or not tool_name or not isinstance(call_id, str) or not call_id:
            return []
        if status not in {"started", "completed", "failed"}:
            status = "started"
        if status == "started":
            return self._start_tool(payload)
        events: list[dict[str, Any]] = []
        if not any(item["call_id"] == call_id for item in self._open):
            events.extend(self._start_tool(payload))
        failed = status == "failed" or bool(payload.get("error"))
        events.extend(self._complete_tool(payload, failed=failed))
        return events

    def _started_tool_payload(self, tool_name: str, call_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        flags = _SanitizeFlags()
        raw_arguments = _extract_structured_arguments(payload)
        if raw_arguments is None:
            arguments: dict[str, Any] | None = None
        else:
            cleaned = _sanitize_node(raw_arguments, depth=2, flags=flags)
            arguments = cleaned if isinstance(cleaned, dict) else None
            if not isinstance(cleaned, dict):
                flags.truncated = True
        public = {
            "tool_name": tool_name,
            "call_id": call_id,
            "status": "started",
            "arguments": arguments,
            "redacted": flags.redacted,
            "truncated": flags.truncated,
        }
        return _fit_public_payload(public, flags)

    def _tool_result_payload(self, opened: dict[str, Any], payload: dict[str, Any], status: str) -> dict[str, Any]:
        flags = _SanitizeFlags()
        content, structured = _extract_result_content(payload)
        if isinstance(content, str):
            content = _sanitize_string(content, flags)
        if structured is not None:
            structured = _sanitize_node(structured, depth=2, flags=flags)
        error_code, error_message = _extract_error_fields(payload)
        if status == "failed":
            if not isinstance(error_code, str) or not error_code:
                error_code = "UNPAIRED_TOOL_START" if not payload else "TOOL_FAILED"
            if isinstance(error_message, str):
                error_message = _sanitize_string(error_message, flags)
        else:
            error_code = error_code if isinstance(error_code, str) and error_code else None
            error_message = _sanitize_string(error_message, flags) if isinstance(error_message, str) else None
        public: dict[str, Any] = {
            "tool_name": opened["tool_name"],
            "call_id": opened["call_id"],
            "status": status,
            "redacted": flags.redacted,
            "truncated": flags.truncated,
        }
        if content is not None:
            public["content"] = content
        if structured is not None:
            public["structured_content"] = structured
        if error_code:
            public["error_code"] = error_code
        if error_message:
            public["error_message"] = error_message
        return _fit_public_payload(public, flags)

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
