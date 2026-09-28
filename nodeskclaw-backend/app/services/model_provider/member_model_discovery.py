"""Discover models with the member data-plane key. Never sends the NEW-API admin token."""

from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.services.credential_crypto import MemberTokenError

logger = logging.getLogger(__name__)


def normalize_model_base(url: str | None) -> str:
    return (url or "").strip().rstrip("/")


def assert_auto_discovery_base(base_url: str) -> str:
    saved = normalize_model_base(base_url)
    expected = normalize_model_base(settings.NEW_API_MODEL_BASE_URL)
    if not saved or saved != expected:
        raise MemberTokenError(
            400,
            "errors.member_token.model_refresh_unsupported",
            "只能对当前配置的自动 NEW-API 模型地址刷新目录",
        )
    return saved


async def discover_model_ids(plaintext: str, base_url: str) -> list[str]:
    url = f"{base_url}/models"
    timeout = float(settings.NEW_API_TIMEOUT_SECONDS or 15)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {plaintext}", "Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        logger.warning("member model discovery transport failed: %s", type(exc).__name__)
        raise MemberTokenError(
            502,
            "errors.member_token.model_discovery_failed",
            "读取成员可见模型失败，请稍后重试",
        ) from exc
    if response.status_code in (401, 403):
        raise MemberTokenError(
            502,
            "errors.member_token.model_discovery_auth_failed",
            "成员模型目录鉴权失败，请检查这把 Key 是否仍然有效",
        )
    if response.status_code >= 400:
        logger.warning("member model discovery failed status %s", response.status_code)
        raise MemberTokenError(
            502,
            "errors.member_token.model_discovery_failed",
            "读取成员可见模型失败，请稍后重试",
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise MemberTokenError(
            502,
            "errors.member_token.model_discovery_response_invalid",
            "模型目录响应无法解析",
        ) from exc
    return _model_ids(body)


def _model_ids(body: object) -> list[str]:
    payload = body
    if isinstance(body, dict) and "data" in body:
        payload = body.get("data")
    if not isinstance(payload, list):
        raise MemberTokenError(
            502,
            "errors.member_token.model_discovery_response_invalid",
            "模型目录响应格式不正确",
        )
    if len(payload) > 1000:
        raise MemberTokenError(
            502,
            "errors.member_token.model_discovery_response_invalid",
            "模型目录超过 1000 条，无法保存",
        )
    ids: list[str] = []
    seen: set[str] = set()
    for item in payload:
        model_id = item.get("id") if isinstance(item, dict) else item
        if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 128:
            raise MemberTokenError(
                502,
                "errors.member_token.model_discovery_response_invalid",
                "模型目录包含无效的模型 ID",
            )
        if model_id in seen:
            raise MemberTokenError(
                502,
                "errors.member_token.model_discovery_response_invalid",
                "模型目录包含重复的模型 ID",
            )
        seen.add(model_id)
        ids.append(model_id)
    ids.sort()
    return ids
