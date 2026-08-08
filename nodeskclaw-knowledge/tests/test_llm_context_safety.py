"""LLM context must not include denied chunks."""

from app.integrations.llm_proxy.models import ChatMessage as LlmChatMessage
from app.integrations.ragflow.models import RagflowChunk
from app.services.context_builder import build_context_messages, build_safe_chunks


def test_denied_chunk_not_in_built_context():
    allowed = RagflowChunk(
        id="c1",
        content="allowed content",
        document_id="d1",
        document_metadata={"nk_source_file_id": "sf_ok"},
    )
    denied = RagflowChunk(
        id="c2",
        content="secret content",
        document_id="d2",
        document_metadata={"nk_source_file_id": "sf_deny"},
    )
    safe_chunks = build_safe_chunks([allowed])
    messages = build_context_messages(
        safe_chunks,
        answer_mode="detailed",
        history=[LlmChatMessage(role="user", content="hello")],
        user_message="question",
    )
    context_message = messages[1].content
    assert "allowed content" in context_message
    assert "secret content" not in context_message
    assert "[Source 1]" in context_message
    assert denied.content not in context_message
