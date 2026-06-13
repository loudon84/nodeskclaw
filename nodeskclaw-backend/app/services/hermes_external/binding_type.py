"""Derive instance binding type from advanced_config."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.models.instance import Instance

BindingType = Literal["platform_managed", "external_docker"]

BINDING_TYPE_LABELS: dict[str, str] = {
    "platform_managed": "平台部署",
    "external_docker": "外部绑定",
}


def get_instance_binding_type(instance: Instance) -> BindingType:
    raw = instance.advanced_config
    if not raw:
        return "platform_managed"

    try:
        cfg = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return "platform_managed"

    if cfg.get("attach_mode") == "external":
        return "external_docker"

    lifecycle_mode = cfg.get("lifecycle_mode")
    paths = cfg.get("paths") or {}
    if lifecycle_mode in ("managed_compose", "managed_container") and paths.get("host_data_dir"):
        return "external_docker"

    if cfg.get("external_container_name"):
        return "external_docker"

    return "platform_managed"


def get_binding_type_label(binding_type: BindingType) -> str:
    return BINDING_TYPE_LABELS.get(binding_type, "")
