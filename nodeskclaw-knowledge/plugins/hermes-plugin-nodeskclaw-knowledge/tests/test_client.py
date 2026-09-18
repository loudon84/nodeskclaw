"""Tests for Knowledge retrieve HTTP client."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any

import pytest

from client import OPS_HINT, retrieve
from config import PluginSettings


class _FakeResponse:
    def __init__(self, body: dict[str, Any], status: int = 200) -> None:
        self._body = json.dumps(body).encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_retrieve_passthrough_success(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float = 60):  # noqa: ANN401
        captured["url"] = request.full_url
        captured["Authorization"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(
            {
                "code": 0,
                "error_code": None,
                "data": {"chunks": [{"content": "x"}], "evidence": []},
            }
        )

    monkeypatch.setattr("client.urllib.request.urlopen", fake_urlopen)
    settings = PluginSettings(url="http://kb.example.com:4530", token="jwt-1")
    result = retrieve(settings, knowledge_set_id="ks-1", query="hello", top_k=5)
    assert captured["url"] == "http://kb.example.com:4530/api/v2/agent/tools/knowledge.retrieve"
    assert captured["Authorization"] == "Bearer jwt-1"
    assert captured["body"] == {"knowledge_set_id": "ks-1", "query": "hello", "top_k": 5}
    assert result["data"]["chunks"][0]["content"] == "x"
    assert "plugin_ops_hint" not in result


def test_retrieve_401_adds_ops_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    def fake_urlopen(request: Any, timeout: float = 60):  # noqa: ANN401
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=BytesIO(
                json.dumps(
                    {
                        "code": 40100,
                        "error_code": 40100,
                        "message_key": "errors.auth.credentials_missing",
                        "message": "未提供认证信息",
                        "data": None,
                    }
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr("client.urllib.request.urlopen", fake_urlopen)
    settings = PluginSettings(url="http://kb.example.com:4530", token="bad")
    result = retrieve(settings, knowledge_set_id="ks-1", query="q")
    assert result["error_code"] == 40100
    assert result["message_key"] == "errors.auth.credentials_missing"
    assert result["plugin_ops_hint"] == OPS_HINT


def test_retrieve_403_no_ops_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    def fake_urlopen(request: Any, timeout: float = 60):  # noqa: ANN401
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=BytesIO(
                json.dumps(
                    {
                        "code": 40300,
                        "error_code": 40300,
                        "message_key": "errors.auth.forbidden",
                        "message": "无权限",
                        "data": None,
                    }
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr("client.urllib.request.urlopen", fake_urlopen)
    settings = PluginSettings(url="http://kb.example.com:4530", token="jwt")
    result = retrieve(settings, knowledge_set_id="ks-1", query="q")
    assert result["error_code"] == 40300
    assert "plugin_ops_hint" not in result
