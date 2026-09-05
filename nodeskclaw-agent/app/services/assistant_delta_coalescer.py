from __future__ import annotations

import time
from collections.abc import Callable


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
class AssistantDeltaCoalescer:
    MAX_BUFFERED_CHARS = 80
    MAX_LATENCY_MS = 100

    def __init__(self, *, clock_ms: Callable[[], int] | None = None) -> None:
        self._clock_ms = clock_ms or (lambda: int(time.monotonic() * 1000))
        self._parts: list[str] = []
        self._first_ms: int | None = None

    def buffered_text(self) -> str:
        return "".join(self._parts)

    def push(self, text: str) -> list[str]:
        if not text:
            return []
        flushed: list[str] = []
        if self._first_ms is None:
            self._first_ms = self._clock_ms()
        remaining = text
        while remaining:
            split_at = remaining.find("\n\n")
            if split_at >= 0:
                self._parts.append(remaining[: split_at + 2])
                remaining = remaining[split_at + 2 :]
                chunk = self.flush()
                if chunk:
                    flushed.append(chunk)
                continue
            self._parts.append(remaining)
            remaining = ""
            if len(self.buffered_text()) >= self.MAX_BUFFERED_CHARS:
                chunk = self.flush()
                if chunk:
                    flushed.append(chunk)
            elif self._latency_due():
                chunk = self.flush()
                if chunk:
                    flushed.append(chunk)
        return flushed

    def flush(self) -> str | None:
        text = self.buffered_text()
        self._parts.clear()
        self._first_ms = None
        return text or None

    def flush_if_stale(self) -> str | None:
        if not self._parts:
            return None
        if self._latency_due() or len(self.buffered_text()) >= self.MAX_BUFFERED_CHARS:
            return self.flush()
        return None

    def _latency_due(self) -> bool:
        if self._first_ms is None:
            return False
        return (self._clock_ms() - self._first_ms) >= self.MAX_LATENCY_MS
