"""Registry adapter bootstrap helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.registry_adapter import RegistryAdapter

logger = logging.getLogger(__name__)


def _load_registry_configs(
    *,
    skill_registries_raw: str,
    deskhub_registry_url: str,
    deskhub_api_key: str,
) -> list[dict[str, Any]]:
    external_registry_configs: list[dict[str, Any]] = []
    raw = skill_registries_raw.strip()
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                external_registry_configs = parsed
            else:
                logger.warning("SKILL_REGISTRIES 不是 JSON 数组，已忽略")
        except json.JSONDecodeError as exc:
            logger.warning("SKILL_REGISTRIES JSON 解析失败: %s", exc)

    if not external_registry_configs and deskhub_registry_url:
        external_registry_configs.append({
            "type": "deskhub",
            "id": "deskhub",
            "url": deskhub_registry_url,
            "api_key": deskhub_api_key,
            "name": "DeskHub",
        })

    return external_registry_configs


def build_registry_adapters(
    *,
    session_factory: Any,
    skill_registries_raw: str,
    deskhub_registry_url: str,
    deskhub_api_key: str,
) -> list[RegistryAdapter]:
    from app.services.clawhub_adapter import ClawHubAdapter
    from app.services.deskhub_client import DeskHubAdapter
    from app.services.local_adapter import LocalAdapter

    adapters: list[RegistryAdapter] = [
        LocalAdapter(session_factory=session_factory),
    ]
    registry_configs = _load_registry_configs(
        skill_registries_raw=skill_registries_raw,
        deskhub_registry_url=deskhub_registry_url,
        deskhub_api_key=deskhub_api_key,
    )

    for config in registry_configs:
        registry_type = config.get("type", "")
        registry_id = config.get("id", registry_type)
        registry_url = config.get("url", "")
        registry_name = config.get("name", registry_id)
        registry_key = config.get("api_key", "")

        if registry_type == "deskhub" and registry_url:
            adapters.append(
                DeskHubAdapter(
                    registry_id=registry_id,
                    registry_name=registry_name,
                    base_url=registry_url,
                    api_key=registry_key,
                )
            )
            logger.info("已注册 DeskHubAdapter: %s (%s)", registry_id, registry_url)
        elif registry_type == "clawhub" and registry_url:
            adapters.append(
                ClawHubAdapter(
                    registry_id=registry_id,
                    registry_name=registry_name,
                    base_url=registry_url,
                    api_key=registry_key,
                )
            )
            logger.info("已注册 ClawHubAdapter (stub): %s (%s)", registry_id, registry_url)
        else:
            logger.warning("未知 registry type=%s, id=%s, 已跳过", registry_type, registry_id)

    return adapters
