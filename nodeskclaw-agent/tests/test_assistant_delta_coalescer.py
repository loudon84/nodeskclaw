from __future__ import annotations

from app.services.assistant_delta_coalescer import AssistantDeltaCoalescer


def test_coalescer_chinese_chars_are_batched_not_per_glyph():
    clock = {"ms": 0}

    def now() -> int:
        return clock["ms"]

    coalescer = AssistantDeltaCoalescer(clock_ms=now)
    deltas = list("中文输出需要合并避免逐字落库" * 8)
    flushed: list[str] = []
    for ch in deltas:
        flushed.extend(coalescer.push(ch))
    tail = coalescer.flush()
    if tail:
        flushed.append(tail)
    joined = "".join(flushed)
    assert joined == "".join(deltas)
    assert len(flushed) < len(deltas)
    assert all(len(item) >= 2 or "\n\n" in item for item in flushed[:-1] or flushed)


def test_coalescer_flushes_on_latency_and_paragraph():
    clock = {"ms": 0}
    coalescer = AssistantDeltaCoalescer(clock_ms=lambda: clock["ms"])
    assert coalescer.push("ab") == []
    clock["ms"] = 120
    assert coalescer.push("c") == ["abc"]
    assert coalescer.push("para\n\nmore") == ["para\n\n"]
    assert coalescer.flush() == "more"
