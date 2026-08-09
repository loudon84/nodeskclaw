"""HTTP Manifest connector with pagination, download and auth modes."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.connectors.base import ConnectorCapabilities
from app.connectors.models import DiscoveryPage, FetchedSource, SourceDescriptor
from app.connectors.registry import register
from app.core.exceptions import BadRequestError, ValidationError
from app.services.http_egress_guard import SafeRedirectGuard, resolve_and_validate_url

# @lat: [[knowledge-objects#Connector Domain]]


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _with_cursor(url: str, cursor: str | None) -> str:
    if not cursor:
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["cursor"] = cursor
    return urlunparse(parsed._replace(query=urlencode(query)))


@register("http_manifest")
class HttpManifestConnector:
    capabilities = ConnectorCapabilities(
        incremental_cursor=True,
        stable_external_id=True,
        delete_events=True,
        folders=False,
        source_metadata=True,
        authentication=True,
    )

    def __init__(
        self,
        config: dict[str, Any],
        *,
        credentials: dict[str, Any] | None = None,
        client: httpx.AsyncClient | None = None,
        **_kwargs: Any,
    ) -> None:
        self.config = dict(config or {})
        self.credentials = dict(credentials or {})
        self.manifest_url = str(self.config.get("manifest_url") or "")
        if not self.manifest_url:
            raise BadRequestError(
                message="http_manifest 需要 manifest_url",
                message_key="errors.knowledge.connector_config_invalid",
            )
        allow = set(self.config.get("allow_private_networks") or [])
        self.allow_private = {str(x) for x in allow}
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=float(self.config.get("timeout_seconds") or 30), follow_redirects=False)

    def _auth_headers(self) -> dict[str, str]:
        mode = str(self.config.get("auth_mode") or self.credentials.get("auth_mode") or "none").lower()
        headers: dict[str, str] = {}
        if mode in {"", "none"}:
            return headers
        if mode == "bearer":
            token = self.credentials.get("token") or self.credentials.get("access_token")
            if not token:
                raise BadRequestError(message="缺少 bearer token", message_key="errors.knowledge.connector_credential_invalid")
            headers["Authorization"] = f"Bearer {token}"
            return headers
        if mode == "api_key_header":
            header_name = str(self.credentials.get("header_name") or self.config.get("api_key_header") or "X-API-Key")
            api_key = self.credentials.get("api_key") or self.credentials.get("token")
            if not api_key:
                raise BadRequestError(message="缺少 api_key", message_key="errors.knowledge.connector_credential_invalid")
            headers[header_name] = str(api_key)
            return headers
        if mode == "basic":
            username = str(self.credentials.get("username") or "")
            password = str(self.credentials.get("password") or "")
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
            return headers
        raise BadRequestError(message="不支持的 auth_mode", message_key="errors.knowledge.connector_config_invalid")

    async def _request(self, method: str, url: str) -> httpx.Response:
        resolve_and_validate_url(url, allow_private_networks=self.allow_private)
        guard = SafeRedirectGuard(allow_private_networks=self.allow_private)
        current = url
        headers = self._auth_headers()
        for _ in range(guard.max_redirects + 1):
            response = await self._client.request(method, current, headers=headers)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValidationError(
                        message="重定向缺少 Location",
                        message_key="errors.knowledge.http_url_blocked",
                    )
                # Resolve relative redirects against current URL
                current = str(response.url.join(location))
                guard.on_redirect(current)
                continue
            response.raise_for_status()
            return response
        raise ValidationError(message="HTTP 重定向次数过多", message_key="errors.knowledge.http_url_blocked")

    async def test_connection(self) -> dict[str, Any]:
        page = await self.discover(cursor=None)
        return {"ok": True, "sample_count": len(page.objects)}

    async def discover(self, *, cursor: dict[str, Any] | None = None) -> DiscoveryPage:
        cursor_token = None
        if cursor:
            cursor_token = cursor.get("cursor") or cursor.get("next_cursor")
        url = _with_cursor(self.manifest_url, str(cursor_token) if cursor_token else None)
        response = await self._request("GET", url)
        payload = response.json()
        if not isinstance(payload, dict):
            raise BadRequestError(message="Manifest 必须是对象", message_key="errors.knowledge.connector_manifest_invalid")
        items = payload.get("items") or payload.get("objects") or []
        if not isinstance(items, list):
            raise BadRequestError(message="Manifest items 必须是数组", message_key="errors.knowledge.connector_manifest_invalid")
        objects: list[SourceDescriptor] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get("id") or item.get("external_object_id") or "")
            if not external_id:
                continue
            objects.append(
                SourceDescriptor(
                    external_object_id=external_id,
                    name=str(item.get("name") or external_id),
                    path=item.get("path"),
                    canonical_uri=item.get("download_url") or item.get("canonical_uri"),
                    mime_type=item.get("mime_type"),
                    size=item.get("size"),
                    external_revision=str(item.get("revision") or item.get("external_revision") or "") or None,
                    etag=item.get("etag"),
                    modified_at=_parse_dt(item.get("modified_at")),
                    source_metadata=dict(item.get("metadata") or {}),
                    is_deleted=bool(item.get("is_deleted") or False),
                )
            )
        next_cursor_val = payload.get("next_cursor")
        has_more = bool(next_cursor_val)
        return DiscoveryPage(
            objects=objects,
            next_cursor={"cursor": next_cursor_val} if has_more else None,
            has_more=has_more,
        )

    async def fetch(self, descriptor: SourceDescriptor) -> FetchedSource:
        url = descriptor.canonical_uri
        if not url:
            raise BadRequestError(message="缺少 download_url", message_key="errors.knowledge.connector_fetch_failed")
        response = await self._request("GET", url)
        data = response.content
        digest = hashlib.sha256(data).hexdigest()
        return FetchedSource(
            file_name=descriptor.name,
            mime_type=descriptor.mime_type or response.headers.get("content-type"),
            stream=data,
            size=len(data),
            sha256=digest,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
