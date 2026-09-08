from __future__ import annotations

import time
from collections.abc import Callable


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
class AssistantDeltaCoalescer:
    MAX_LATENCY_MS = 1000

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
        return []

    def flush(self) -> str | None:
        text = self.buffered_text()
        self._parts.clear()
        self._first_ms = None
        return text or None

    def flush_if_stale(self) -> str | None:
        if not self._parts:
            return None
        if self._latency_due():
            return self.flush()
        return None

    def _latency_due(self) -> bool:
        if self._first_ms is None:
            return False
        return (self._clock_ms() - self._first_ms) >= self.MAX_LATENCY_MS
