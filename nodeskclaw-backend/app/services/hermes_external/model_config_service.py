"""External Docker Hermes model config service."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from typing import Any

import yaml

from app.core.exceptions import BadRequestError
from app.models.instance import Instance
from app.schemas.external_docker import (
    ExternalDockerModelConfigRawResponse,
    ExternalDockerModelConfigResponse,
    ExternalDockerModelConfigUpdateResponse,
    ExternalDockerModelConfigValidateResponse,
)
from app.services.hermes_external._common import _path_resolver, resolve_paths

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "secret_key",
    "access_token",
    "authorization",
    "password",
    "token",
    "max_tokens",
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


def _parse_yaml_content(content: str) -> dict[str, Any]:
    stripped = (content or "").strip()
    if not stripped:
        raise BadRequestError(
            message="config.yaml 内容不能为空",
            message_key="errors.external_docker.model_config_empty",
        )
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise BadRequestError(
            message=f"config.yaml 格式错误：{exc}",
            message_key="errors.external_docker.model_config_invalid_yaml",
        ) from exc
    if not isinstance(parsed, dict):
        raise BadRequestError(
            message="config.yaml 顶层必须是 YAML 对象",
            message_key="errors.external_docker.model_config_invalid_root",
        )
    return parsed


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


def get_model_config_raw(instance: Instance) -> ExternalDockerModelConfigRawResponse:
    ep = resolve_paths(instance)
    config_file = ep.config_file
    if not config_file.is_file():
        return ExternalDockerModelConfigRawResponse(
            config_file=str(config_file),
            exists=False,
            content="",
            message="Hermes config.yaml 未初始化",
        )
    return ExternalDockerModelConfigRawResponse(
        config_file=str(config_file),
        exists=True,
        content=config_file.read_text(encoding="utf-8"),
    )


def validate_model_config(content: str) -> ExternalDockerModelConfigValidateResponse:
    try:
        parsed = _parse_yaml_content(content)
    except BadRequestError as exc:
        return ExternalDockerModelConfigValidateResponse(
            valid=False,
            message=exc.message,
        )
    return ExternalDockerModelConfigValidateResponse(
        valid=True,
        message="YAML 格式正确",
        parsed_preview=parsed,
    )


def backup_config(instance: Instance) -> str | None:
    ep = resolve_paths(instance)
    config_file = ep.config_file
    if not config_file.is_file():
        return None
    backup_dir = ep.backups_dir / "config"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_file = backup_dir / f"config-{stamp}.yaml"
    shutil.copy2(config_file, backup_file)
    return str(backup_file)


async def update_model_config(
    instance: Instance,
    content: str,
    *,
    restart_after_save: bool = False,
) -> ExternalDockerModelConfigUpdateResponse:
    from app.services.hermes_external import lifecycle_service

    _parse_yaml_content(content)
    ep = resolve_paths(instance)
    _path_resolver.ensure_auto_create_dirs(ep)
    config_file = ep.config_file
    config_file.parent.mkdir(parents=True, exist_ok=True)

    backup_file = backup_config(instance)
    tmp = config_file.with_suffix(".yaml.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(config_file)

    restarted = False
    message = "配置已保存，重启 Hermes 实例后生效"
    if restart_after_save:
        await lifecycle_service.restart(instance)
        restarted = True
        message = "配置已保存，并已重启实例"

    return ExternalDockerModelConfigUpdateResponse(
        success=True,
        config_file=str(config_file),
        backup_file=backup_file,
        requires_restart=True,
        restarted=restarted,
        message=message,
    )
