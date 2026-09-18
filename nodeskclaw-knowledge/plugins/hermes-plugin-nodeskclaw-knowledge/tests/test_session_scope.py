"""Tests for knowledge_set_id resolution."""

from __future__ import annotations

import pytest

from session_scope import ScopeError, resolve_knowledge_set_id


def test_tool_arg_overrides_session() -> None:
    ks = resolve_knowledge_set_id(
        {"knowledge_set_id": "ks-tool"},
        {"knowledge_set_id": "ks-session", "session_id": "s1"},
        {"s1": "ks-store"},
    )
    assert ks == "ks-tool"


def test_falls_back_to_kwargs_knowledge_set_id() -> None:
    ks = resolve_knowledge_set_id(
        {"query": "q"},
        {"knowledge_set_id": "ks-kwargs"},
        None,
    )
    assert ks == "ks-kwargs"


def test_falls_back_to_knowledge_context() -> None:
    ks = resolve_knowledge_set_id(
        {},
        {"knowledge_context": {"knowledge_set_id": "ks-ctx"}},
        None,
    )
    assert ks == "ks-ctx"


def test_falls_back_to_session_store() -> None:
    ks = resolve_knowledge_set_id(
        {},
        {"session_id": "abc"},
        {"abc": "ks-store"},
    )
    assert ks == "ks-store"


def test_missing_raises() -> None:
    with pytest.raises(ScopeError, match="knowledge_set_id is required"):
        resolve_knowledge_set_id({"query": "q"}, {}, None)
