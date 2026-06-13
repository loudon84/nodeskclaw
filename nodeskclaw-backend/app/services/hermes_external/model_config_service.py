"""External Docker Hermes model config service."""

from __future__ import annotations

import re
from typing import Any

import yaml

from app.models.instance import Instance
from app.schemas.external_docker import ExternalDockerModelConfigResponse
from app.services.hermes_external._common import resolve_paths

_SENSITIVE_KEYS = {
    "api_key",
    "secret_key",
    "access_token",
    "authorization",
    "password",
    "token",
}


def _mask_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(v) for v in value]
    if isinstance(value, str) and value:
        return "******"
    return value


def _mask_sensitive(obj: Any) -> Any:
    if isinstance(obj, dict):
        masked: dict[str, Any] = {}
        for key, value in obj.items():
            key_lower = str(key).lower()
            if key_lower in _SENSITIVE_KEYS or any(k in key_lower for k in _SENSITIVE_KEYS):
                masked[key] = "******" if value else value
            else:
                masked[key] = _mask_sensitive(value)
        return masked
    if isinstance(obj, list):
        return [_mask_sensitive(v) for v in obj]
    return obj


def _extract_providers(config: dict[str, Any]) -> list[dict[str, Any]]:
    providers: list[dict[str, Any]] = []
    models = config.get("models") or config.get("model") or {}
    if isinstance(models, dict):
        provider_list = models.get("providers") or models.get("provider") or []
        if isinstance(provider_list, list):
            providers.extend(_mask_sensitive(item) for item in provider_list if isinstance(item, dict))
        elif isinstance(provider_list, dict):
            for name, item in provider_list.items():
                if isinstance(item, dict):
                    entry = _mask_sensitive(dict(item))
                    entry.setdefault("name", name)
                    providers.append(entry)
    llm = config.get("llm") or {}
    if isinstance(llm, dict) and llm:
        providers.append(_mask_sensitive(dict(llm)))
    if not providers and config:
        summary = {
            "default_model": config.get("default_model") or config.get("model"),
            "planner_model": config.get("planner_model"),
            "executor_model": config.get("executor_model"),
            "compression_model": config.get("compression_model") or config.get("compress_model"),
            "embedding_model": config.get("embedding_model"),
            "enabled": config.get("enabled"),
        }
        providers.append(_mask_sensitive({k: v for k, v in summary.items() if v is not None}))
    return providers


def get_model_config(instance: Instance) -> ExternalDockerModelConfigResponse:
    ep = resolve_paths(instance)
    config_file = ep.config_file
    if not config_file.is_file():
        return ExternalDockerModelConfigResponse(
            config_file=str(config_file),
            exists=False,
            providers=[],
            masked=True,
            message="Hermes config.yaml 未初始化。请先通过 Hermes WebUI 或配置模板初始化。",
        )

    raw_text = config_file.read_text(encoding="utf-8")
    try:
        config = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError:
        return ExternalDockerModelConfigResponse(
            config_file=str(config_file),
            exists=True,
            providers=[],
            masked=True,
            message="config.yaml 解析失败，请检查文件格式。",
        )

    if not isinstance(config, dict):
        config = {}

    return ExternalDockerModelConfigResponse(
        config_file=str(config_file),
        exists=True,
        providers=_extract_providers(config),
        masked=True,
    )
