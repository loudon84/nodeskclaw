"""Chat history trim and knowledge-context retention (PRD §71)."""

from app.integrations.llm_proxy.models import ChatMessage as LlmChatMessage
from app.integrations.ragflow.models import RagflowChunk
from app.services.context_builder import (
    build_context_messages,
    build_safe_chunks,
    estimate_tokens,
    trim_history_to_token_budget,
)


def test_trim_history_drops_oldest_messages():
    history = [
        LlmChatMessage(role="user", content="old-1 " + ("x" * 40)),
        LlmChatMessage(role="assistant", content="old-2 " + ("y" * 40)),
        LlmChatMessage(role="user", content="recent-1"),
        LlmChatMessage(role="assistant", content="recent-2"),
    ]
    trimmed = trim_history_to_token_budget(
        history,
        reserved_tokens=10,
        max_messages=10,
        max_tokens=30,
    )
    joined = " ".join(m.content for m in trimmed)
    assert "recent-1" in joined or "recent-2" in joined
    assert "old-1" not in joined


def test_build_context_keeps_knowledge_before_history():
    chunk = RagflowChunk(
        id="c1",
        content="knowledge-priority-payload",
        document_id="d1",
        document_metadata={"nk_source_file_id": "sf1"},
    )
    history = [
        LlmChatMessage(role="user", content="h" * 200),
        LlmChatMessage(role="assistant", content="a" * 200),
        LlmChatMessage(role="user", content="keep-me"),
    ]
    messages = build_context_messages(
        build_safe_chunks([chunk]),
        answer_mode="detailed",
        history=history,
        user_message="question",
        max_messages=20,
        max_tokens=80,
    )
    assert messages[0].role == "system"
    assert messages[1].role == "system"
    assert "knowledge-priority-payload" in messages[1].content
    assert messages[-1].role == "user"
    assert messages[-1].content == "question"
    history_msgs = messages[2:-1]
    history_text = " ".join(m.content for m in history_msgs)
    assert "knowledge-priority-payload" not in history_text
    reserved = (
        estimate_tokens(messages[0].content)
        + estimate_tokens(messages[1].content)
        + estimate_tokens("question")
    )
    used = sum(estimate_tokens(m.content or "") for m in history_msgs)
    assert reserved + used <= 80 or not history_msgs
