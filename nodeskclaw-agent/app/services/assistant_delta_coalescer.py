from __future__ import annotations

import time
from collections.abc import Callable

from app.services.execution_observability import record_metric

MAX_DELTA_UTF8_BYTES = 64 * 1024
MAX_SNAPSHOT_UTF8_BYTES = 1 * 1024 * 1024


def split_utf8_by_bytes(text: str, max_bytes: int) -> list[str]:
    if not text:
        return []
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return [text]
    chunks: list[str] = []
    start = 0
    length = len(encoded)
    while start < length:
        end = min(start + max_bytes, length)
        while end > start:
            try:
                piece = encoded[start:end].decode("utf-8")
            except UnicodeDecodeError:
                end -= 1
                continue
            chunks.append(piece)
            start = end
            break
        else:
            raise ValueError("unable to split utf-8 on character boundary")
    return chunks


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
class AssistantDeltaCoalescer:
    MAX_LATENCY_MS = 1000
    MAX_DELTA_UTF8_BYTES = MAX_DELTA_UTF8_BYTES

    def __init__(self, *, clock_ms: Callable[[], int] | None = None) -> None:
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._parts: list[str] = []
        self._first_ms: int | None = None

    def buffered_text(self) -> str:
        return "".join(self._parts)

    def push(self, text: str) -> list[str]:
        if not text:
            return []
        if self._first_ms is None:
            self._first_ms = self._clock_ms()
        self._parts.append(text)
        return self._drain_oversize()

    def flush(self) -> str | None:
        text = self.buffered_text()
        self._parts.clear()
        self._first_ms = None
        if text:
            record_metric("runtime_assistant_coalesced_total", labels={"engine": "hermes"})
            return text
        return None

    def flush_chunks(self) -> list[str]:
        text = self.flush()
        if not text:
            return []
        return split_utf8_by_bytes(text, self.MAX_DELTA_UTF8_BYTES)

    def flush_if_stale(self) -> str | None:
        if not self._parts:
            return None
        if self._latency_due():
            return self.flush()
        return None

    def flush_if_stale_chunks(self) -> list[str]:
        text = self.flush_if_stale()
        if not text:
            return []
        return split_utf8_by_bytes(text, self.MAX_DELTA_UTF8_BYTES)

    def _drain_oversize(self) -> list[str]:
        out: list[str] = []
        while True:
            buf = self.buffered_text()
            encoded_len = len(buf.encode("utf-8"))
            if encoded_len <= self.MAX_DELTA_UTF8_BYTES:
                break
            chunks = split_utf8_by_bytes(buf, self.MAX_DELTA_UTF8_BYTES)
            head, *rest = chunks
            out.append(head)
            record_metric("runtime_assistant_coalesced_total", labels={"engine": "hermes"})
            remainder = "".join(rest)
            self._parts = [remainder] if remainder else []
            if not self._parts:
                self._first_ms = None
            elif self._first_ms is None:
                self._first_ms = self._clock_ms()
        return out

    def _latency_due(self) -> bool:
        if self._first_ms is None:
            return False
        return (self._clock_ms() - self._first_ms) >= self.MAX_LATENCY_MS
