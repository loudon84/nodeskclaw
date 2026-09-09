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
    assert flushed == ["".join(deltas)]


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_coalescer_does_not_flush_on_size_or_paragraph():
    clock = {"ms": 0}
    coalescer = AssistantDeltaCoalescer(clock_ms=lambda: clock["ms"])
    long_text = "字" * 200
    assert coalescer.push(long_text) == []
    assert coalescer.push("para\n\nmore") == []
    clock["ms"] = 120
    assert coalescer.flush_if_stale() is None
    clock["ms"] = 999
    assert coalescer.flush_if_stale() is None
    clock["ms"] = 1000
    assert coalescer.flush_if_stale() == long_text + "para\n\nmore"


def test_coalescer_splits_utf8_safe_when_buffer_exceeds_max_delta():
    from app.services.assistant_delta_coalescer import MAX_DELTA_UTF8_BYTES, split_utf8_by_bytes

    coalescer = AssistantDeltaCoalescer(clock_ms=lambda: 0)
    glyph = "字"
    count = (MAX_DELTA_UTF8_BYTES // len(glyph.encode("utf-8"))) + 4
    text = glyph * count
    immediate = coalescer.push(text)
    assert immediate
    assert all(len(part.encode("utf-8")) <= MAX_DELTA_UTF8_BYTES for part in immediate)
    remainder = coalescer.buffered_text()
    joined = "".join(immediate) + remainder
    assert joined == text
    assert split_utf8_by_bytes(text, MAX_DELTA_UTF8_BYTES)[0] == immediate[0]


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Runtime Semantic Event Fidelity]]
def test_coalescer_keeps_tiny_paragraph_in_buffer():
    coalescer = AssistantDeltaCoalescer(clock_ms=lambda: 0)
    assert coalescer.push("。\n\n") == []
    assert coalescer.buffered_text() == "。\n\n"
    assert coalescer.push("后文") == []
    assert coalescer.flush() == "。\n\n后文"
