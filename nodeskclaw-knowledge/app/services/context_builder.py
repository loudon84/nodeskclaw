"""Build LLM context from safe retrieval chunks."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.integrations.llm_proxy.models import ChatMessage as LlmChatMessage
from app.integrations.ragflow.models import RagflowChunk
from app.models.enums import AnswerMode


@dataclass
class SafeChunk:
    index: int
    chunk: RagflowChunk


ANSWER_MODE_PROMPTS = {
    AnswerMode.concise.value: (
        "请基于提供的参考资料简洁回答用户问题。优先给出直接结论，避免冗长铺垫。"
    ),
    AnswerMode.detailed.value: (
        "请基于提供的参考资料详细回答用户问题，解释关键依据与推理过程。"
    ),
    AnswerMode.structured.value: (
        "请基于提供的参考资料结构化回答，可使用标题、要点、步骤或表格组织内容。"
    ),
}


def build_safe_chunks(chunks: list[RagflowChunk]) -> list[SafeChunk]:
    return [SafeChunk(index=i + 1, chunk=chunk) for i, chunk in enumerate(chunks)]


def build_system_prompt(answer_mode: str) -> str:
    base = (
        "你是企业知识库问答助手。只能依据下方参考资料回答；"
        "若资料不足请明确说明无法从知识库中找到答案。"
        "引用资料时使用 [Source N] 格式，且 N 必须对应参考资料编号。"
    )
    mode_hint = ANSWER_MODE_PROMPTS.get(answer_mode, ANSWER_MODE_PROMPTS[AnswerMode.detailed.value])
    return f"{base}\n\n{mode_hint}"


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def trim_history_to_token_budget(
    history: list[LlmChatMessage],
    *,
    reserved_tokens: int,
    max_messages: int | None = None,
    max_tokens: int | None = None,
) -> list[LlmChatMessage]:
    max_messages = max_messages if max_messages is not None else settings.CHAT_HISTORY_MAX_MESSAGES
    max_tokens = max_tokens if max_tokens is not None else settings.CHAT_HISTORY_MAX_TOKENS
    budget = max(0, max_tokens - reserved_tokens)
    selected: list[LlmChatMessage] = []
    used = 0
    for message in reversed(history[-max_messages:]):
        cost = estimate_tokens(message.content or "")
        if selected and used + cost > budget:
            break
        selected.append(message)
        used += cost
    selected.reverse()
    return selected


def build_context_messages(
    safe_chunks: list[SafeChunk],
    *,
    answer_mode: str,
    history: list[LlmChatMessage] | None = None,
    user_message: str,
    max_messages: int | None = None,
    max_tokens: int | None = None,
) -> list[LlmChatMessage]:
    context_lines: list[str] = []
    for item in safe_chunks:
        content = (item.chunk.content or "").strip()
        context_lines.append(f"[Source {item.index}]\n{content}")

    context_block = "\n\n".join(context_lines) if context_lines else "（无可用参考资料）"
    system_prompt = build_system_prompt(answer_mode)
    knowledge_context = f"参考资料：\n{context_block}"

    reserved = (
        estimate_tokens(system_prompt)
        + estimate_tokens(knowledge_context)
        + estimate_tokens(user_message)
    )
    trimmed_history = trim_history_to_token_budget(
        history or [],
        reserved_tokens=reserved,
        max_messages=max_messages,
        max_tokens=max_tokens,
    )

    messages: list[LlmChatMessage] = [
        LlmChatMessage(role="system", content=system_prompt),
        LlmChatMessage(role="system", content=knowledge_context),
    ]
    messages.extend(trimmed_history)
    messages.append(LlmChatMessage(role="user", content=user_message))
    return messages


def context_contains_chunk_index(safe_chunks: list[SafeChunk], index: int) -> bool:
    return any(item.index == index for item in safe_chunks)
