"""Tests for config dual-read (plugin config > env)."""

from __future__ import annotations

import pytest

from config import ConfigError, load_settings


def test_config_prefers_plugin_config_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMC_KB_API_URL", "http://env.example.com:4530")
    monkeypatch.setenv("SMC_KB_API_TOKEN", "env-token")
    settings = load_settings(
        {"url": "http://config.example.com:4530/", "token": "config-token"}
    )
    assert settings.url == "http://config.example.com:4530"
    assert settings.token == "config-token"


def test_config_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMC_KB_API_URL", "http://env.example.com:4530/")
    monkeypatch.setenv("SMC_KB_API_TOKEN", "env-token")
    settings = load_settings(None)
    assert settings.url == "http://env.example.com:4530"
    assert settings.token == "env-token"


def test_config_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMC_KB_API_URL", raising=False)
    monkeypatch.delenv("SMC_KB_API_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="Missing Knowledge plugin settings"):
        load_settings({})


def test_url_is_origin_stripped_of_trailing_slash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMC_KB_API_URL", raising=False)
    monkeypatch.delenv("SMC_KB_API_TOKEN", raising=False)
    settings = load_settings(
        {"url": "http://nodeskclaw-knowledge:4530/", "token": "jwt"}
    )
    assert settings.url == "http://nodeskclaw-knowledge:4530"
