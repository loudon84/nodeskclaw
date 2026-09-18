"""Resolve knowledge_set_id: tool args override session scope."""

from __future__ import annotations

from typing import Any


class ScopeError(ValueError):
    """Raised when no KnowledgeSet id is available from args or session."""


def resolve_knowledge_set_id(
    args: dict[str, Any],
    kwargs: dict[str, Any],
    session_store: dict[str, str] | None = None,
) -> str:
    from_args = args.get("knowledge_set_id")
    if from_args is not None and str(from_args).strip():
        return str(from_args).strip()

    from_kwargs = kwargs.get("knowledge_set_id")
    if from_kwargs is not None and str(from_kwargs).strip():
        return str(from_kwargs).strip()

    context = kwargs.get("knowledge_context")
    if isinstance(context, dict):
        from_ctx = context.get("knowledge_set_id")
        if from_ctx is not None and str(from_ctx).strip():
            return str(from_ctx).strip()

    if session_store:
        session_id = kwargs.get("session_id")
        if session_id is not None and str(session_id).strip():
            stored = session_store.get(str(session_id).strip())
            if stored is not None and str(stored).strip():
                return str(stored).strip()

    raise ScopeError(
        "knowledge_set_id is required: pass it as a tool argument or "
        "ensure the application set session knowledge_context.knowledge_set_id."
    )
