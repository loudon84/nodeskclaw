"""Tests for knowledge.retrieve tool handler."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools.knowledge import knowledge_retrieve, set_plugin_config, set_session_store


def test_handler_uses_tool_arg_and_returns_json(monkeypatch: pytest.MonkeyPatch) -> None:
    set_plugin_config({"url": "http://kb.example.com:4530", "token": "jwt"})
    set_session_store({})

    def fake_retrieve(settings: Any, **kwargs: Any) -> dict[str, Any]:
        assert settings.token == "jwt"
        assert kwargs["knowledge_set_id"] == "ks-tool"
        assert kwargs["query"] == "hello"
        assert kwargs["top_k"] == 3
        return {
            "code": 0,
            "error_code": None,
            "data": {"chunks": [{"file_name": "a.pdf", "similarity": 0.9}], "evidence": []},
        }

    monkeypatch.setattr("tools.knowledge.retrieve", fake_retrieve)
    raw = knowledge_retrieve(
        {"knowledge_set_id": "ks-tool", "query": "hello", "top_k": 3},
        knowledge_set_id="ks-session",
    )
    payload = json.loads(raw)
    assert payload["code"] == 0
    assert payload["data"]["chunks"][0]["file_name"] == "a.pdf"


def test_handler_falls_back_to_session(monkeypatch: pytest.MonkeyPatch) -> None:
    set_plugin_config({"url": "http://kb.example.com:4530", "token": "jwt"})
    set_session_store({"s1": "ks-store"})

    def fake_retrieve(settings: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["knowledge_set_id"] == "ks-store"
        return {"code": 0, "data": {"chunks": [], "evidence": []}}

    monkeypatch.setattr("tools.knowledge.retrieve", fake_retrieve)
    raw = knowledge_retrieve({"query": "q"}, session_id="s1")
    assert json.loads(raw)["code"] == 0


def test_handler_missing_scope_returns_error() -> None:
    set_plugin_config({"url": "http://kb.example.com:4530", "token": "jwt"})
    set_session_store({})
    raw = knowledge_retrieve({"query": "q"})
    payload = json.loads(raw)
    assert payload["error_code"] == 40000
    assert "knowledge_set_id" in payload["message"]
