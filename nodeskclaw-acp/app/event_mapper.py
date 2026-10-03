from __future__ import annotations

from typing import Any

from app.errors import AdapterError

IGNORED_EVENTS = frozenset({"run.queued", "run.progress", "run.created"})


def join_text_blocks(blocks: list[Any]) -> str:
    texts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            raise AdapterError("ACP_PROMPT_UNSUPPORTED_CONTENT", "仅支持文本 Prompt")
        kind = str(block.get("type") or block.get("kind") or "")
        if kind and kind not in {"text", "Text"}:
            raise AdapterError("ACP_PROMPT_UNSUPPORTED_CONTENT", "仅支持文本 Prompt")
        text = block.get("text")
        if text is None:
            raise AdapterError("ACP_PROMPT_UNSUPPORTED_CONTENT", "仅支持文本 Prompt")
        texts.append(str(text))
    return "\n\n".join(texts).strip()


def reconcile_final(accumulated: str, final: str, delta_emitted: bool) -> str | None:
    if not delta_emitted:
        return final
    if final == accumulated:
        return None
    if final.startswith(accumulated):
        return final[len(accumulated):]
    raise AdapterError("ACP_STREAM_RECONCILIATION_MISMATCH", "流式文本与最终快照不一致")


def safe_artifact_text(payload: dict[str, Any]) -> str:
    name = str(payload.get("name") or payload.get("artifact_name") or "artifact")
    artifact_id = str(payload.get("artifact_id") or payload.get("id") or "")
    return f"Artifact generated: {name} artifact_id={artifact_id}"


def map_tool_result_status(outcome: str) -> str:
    if outcome == "success":
        return "completed"
    return "failed"
