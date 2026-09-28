"""Validate the member token models JSON document."""

from __future__ import annotations

from app.services.credential_crypto import MemberTokenError

_CAPABILITIES = {
    "chat",
    "reasoning",
    "tools",
    "vision",
    "audio",
    "embedding",
    "image_generation",
}
_TOP_KEYS = {"schema_version", "default_model", "items"}
_ITEM_KEYS = {
    "id",
    "display_name",
    "context_window",
    "max_output_tokens",
    "enabled",
    "capabilities",
    "settings",
}
_SETTING_KEYS = {
    "temperature",
    "top_p",
    "max_tokens",
    "reasoning_effort",
    "timeout_seconds",
    "extra",
}

EMPTY_MODELS = {"schema_version": "1.0", "default_model": None, "items": []}


def normalize_models_document(payload: dict | None) -> dict:
    if payload is None:
        return dict(EMPTY_MODELS)
    if not isinstance(payload, dict) or set(payload) - _TOP_KEYS:
        raise _invalid()
    if payload.get("schema_version") != "1.0":
        raise _invalid()
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise _invalid()
    default_model = payload.get("default_model")
    if default_model is not None and not isinstance(default_model, str):
        raise _invalid()
    seen: set[str] = set()
    cleaned = []
    for item in items:
        cleaned.append(_item(item, seen))
    enabled_ids = {item["id"] for item in cleaned if item["enabled"]}
    if default_model is not None and default_model not in enabled_ids:
        raise _invalid()
    return {
        "schema_version": "1.0",
        "default_model": default_model,
        "items": cleaned,
    }


def _item(item: object, seen: set[str]) -> dict:
    if not isinstance(item, dict) or set(item) - _ITEM_KEYS:
        raise _invalid()
    model_id = item.get("id")
    display_name = item.get("display_name")
    if not _bounded(model_id) or not _bounded(display_name):
        raise _invalid()
    if model_id in seen:
        raise _invalid()
    seen.add(model_id)
    context_window = _positive_int(item.get("context_window"))
    max_output = _positive_int(item.get("max_output_tokens"))
    enabled = item.get("enabled", True)
    if not isinstance(enabled, bool):
        raise _invalid()
    capabilities = item.get("capabilities")
    if (
        not isinstance(capabilities, list)
        or len(capabilities) != len(set(capabilities))
        or any(cap not in _CAPABILITIES for cap in capabilities)
    ):
        raise _invalid()
    result = {
        "id": model_id,
        "display_name": display_name,
        "context_window": context_window,
        "max_output_tokens": max_output,
        "enabled": enabled,
        "capabilities": capabilities,
    }
    if "settings" in item:
        result["settings"] = _settings(item["settings"])
    return result


def _settings(value: object) -> dict:
    if not isinstance(value, dict) or set(value) - _SETTING_KEYS:
        raise _invalid()
    extra = value.get("extra", {})
    if not isinstance(extra, dict):
        raise _invalid()
    cleaned = {"extra": extra}
    for key in ("temperature", "top_p", "max_tokens", "reasoning_effort", "timeout_seconds"):
        if key in value:
            cleaned[key] = value[key]
    return cleaned


def _positive_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _invalid()
    return value


def _bounded(value: object) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= 128


def build_runtime_models_document(
    *,
    selected_ids: list[str],
    default_model: str,
    discovered_ids: set[str],
    existing_items: list,
) -> dict:
    if not selected_ids or len(selected_ids) != len(set(selected_ids)):
        raise MemberTokenError(400, "errors.member_token.default_model_required", "请至少选择一个模型并指定默认模型")
    if default_model not in selected_ids:
        raise MemberTokenError(
            400,
            "errors.member_token.default_model_not_selected",
            "默认模型必须是已勾选的模型",
        )
    if any(model_id not in discovered_ids for model_id in selected_ids):
        raise MemberTokenError(
            400,
            "errors.member_token.runtime_model_not_available",
            "所选模型不在该成员当前可见目录中，请刷新后重试",
        )
    previous = {}
    for item in existing_items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            previous[item["id"]] = item
    items = []
    for model_id in selected_ids:
        source = previous.get(model_id) or {}
        capabilities = source.get("capabilities")
        if not isinstance(capabilities, list):
            capabilities = []
        items.append(
            {
                "id": model_id,
                "display_name": source.get("display_name") if isinstance(source.get("display_name"), str) else model_id,
                "context_window": source.get("context_window") if isinstance(source.get("context_window"), int) else None,
                "max_output_tokens": source.get("max_output_tokens") if isinstance(source.get("max_output_tokens"), int) else None,
                "enabled": True,
                "capabilities": capabilities,
            }
        )
    return normalize_models_document(
        {"schema_version": "1.0", "default_model": default_model, "items": items}
    )


def _invalid() -> MemberTokenError:
    return MemberTokenError(
        400,
        "errors.member_token.models_invalid",
        "模型清单格式不正确",
    )
