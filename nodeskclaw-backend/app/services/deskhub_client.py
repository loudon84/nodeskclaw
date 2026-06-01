"""DeskHub Registry adapter for the shared ``/api/v1/genes`` protocol."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.services.registry_adapter import (
    RegistryAdapter,
    RegistrySearchResult,
    RegistrySkillDetail,
    RegistrySkillItem,
)

logger = logging.getLogger(__name__)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


def _extract_paginated(body: dict[str, Any]) -> tuple[list[dict], int]:
    data = body.get("data", {})
    if isinstance(data, dict):
        return data.get("items", []), data.get("total", 0)
    if isinstance(data, list):
        return data, len(data)
    return [], 0


class DeskHubAdapter(RegistryAdapter):
    """Adapter for registries that speak the DeskHub ``/api/v1/genes/*`` protocol.

    Reusable for DeskHub and any future registry that aligns with the same API.
    """

    _TIMEOUT = 5.0
    _SORT_MAP = {"popularity": "popular", "rating": "rating", "newest": "newest"}

    def __init__(
        self,
        *,
        registry_id: str,
        registry_name: str,
        base_url: str,
        api_key: str = "",
    ) -> None:
        super().__init__(
            registry_id=registry_id,
            registry_name=registry_name,
            base_url=base_url,
        )
        self._api_key = api_key
        headers: dict[str, str] = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(timeout=self._TIMEOUT, headers=headers)

    def _url(self, path: str) -> str:
        assert self.base_url is not None
        return f"{self.base_url.rstrip('/')}{path}"

    def _gene_to_item(self, gene: dict[str, Any]) -> RegistrySkillItem:
        return RegistrySkillItem(
            slug=gene.get("slug", ""),
            name=gene.get("name", ""),
            description=gene.get("description"),
            short_description=gene.get("short_description"),
            version=gene.get("version"),
            tags=gene.get("tags") or [],
            category=gene.get("category"),
            source=gene.get("source", "official"),
            source_ref=gene.get("source_ref"),
            icon=gene.get("icon"),
            install_count=gene.get("install_count", 0),
            avg_rating=gene.get("avg_rating", 0),
            effectiveness_score=gene.get("effectiveness_score", 0),
            is_featured=gene.get("is_featured", gene.get("install_count", 0) > 0),
            review_status=gene.get("review_status", "approved"),
            is_published=gene.get("is_published", True),
            manifest=gene.get("manifest"),
            dependencies=gene.get("dependencies") or [],
            synergies=gene.get("synergies") or [],
            parent_gene_id=gene.get("parent_gene_id"),
            created_by_instance_id=gene.get("created_by_instance_id"),
            created_by=gene.get("created_by"),
            org_id=gene.get("org_id"),
            visibility=gene.get("visibility", "public"),
            created_at=_parse_dt(gene.get("created_at")),
            updated_at=_parse_dt(gene.get("updated_at")),
            source_registry=self.registry_id,
            source_registry_name=self.registry_name,
        )

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict | None:
        try:
            resp = await self._http.get(self._url(path), params=params)
            resp.raise_for_status()
            body = resp.json()
            if body.get("code") != 0:
                logger.warning(
                    "%s API error: GET %s -> %s",
                    self.registry_name, path, body.get("message"),
                )
                return None
            return body
        except Exception as e:
            self._log_error("GET", path, e)
            return None

    async def _post(self, path: str, json_body: dict | None = None) -> dict | None:
        try:
            resp = await self._http.post(self._url(path), json=json_body or {})
            resp.raise_for_status()
            body = resp.json()
            if body.get("code") != 0:
                logger.warning(
                    "%s API error: POST %s -> %s",
                    self.registry_name, path, body.get("message"),
                )
                return None
            return body
        except Exception as e:
            self._log_error("POST", path, e)
            return None

    def _log_error(self, method: str, path: str, exc: Exception) -> None:
        if isinstance(exc, httpx.TimeoutException):
            logger.warning("%s timeout: %s %s", self.registry_name, method, path)
        elif isinstance(exc, httpx.HTTPStatusError):
            logger.warning(
                "%s HTTP %d: %s %s",
                self.registry_name, exc.response.status_code, method, path,
            )
        elif isinstance(exc, httpx.RequestError):
            logger.warning(
                "%s connection error: %s %s -> %s",
                self.registry_name, method, path, exc,
            )
        else:
            logger.warning(
                "%s unexpected error: %s %s -> %s",
                self.registry_name, method, path, exc,
            )

    # ── RegistryAdapter interface ──

    async def search_skills(
        self,
        *,
        keyword: str | None = None,
        tag: str | None = None,
        category: str | None = None,
        source: str | None = None,
        visibility: str | None = None,
        org_id: str | None = None,
        sort: str = "popularity",
        page: int = 1,
        page_size: int = 20,
    ) -> RegistrySearchResult | None:
        params: dict[str, Any] = {"page": page, "page_size": page_size}
        if keyword:
            params["q"] = keyword
        if tag:
            params["tags"] = tag
        if category:
            params["category"] = category
        params["sort"] = self._SORT_MAP.get(sort, sort)

        body = await self._get("/api/v1/genes", params)
        if body is None:
            return None

        raw_items, total = _extract_paginated(body)
        items = [self._gene_to_item(g) for g in raw_items]
        return RegistrySearchResult(items=items, total=total)

    async def get_skill(self, slug: str) -> RegistrySkillDetail | None:
        body = await self._get(f"/api/v1/genes/{slug}")
        data = body.get("data") if body else None
        if not data:
            return None
        item = self._gene_to_item(data)
        return RegistrySkillDetail(**item.model_dump())

    async def get_manifest(self, slug: str, version: str | None = None) -> dict | None:
        params = {"version": version} if version else None
        body = await self._get(f"/api/v1/genes/{slug}/manifest", params)
        return body.get("data") if body else None

    async def get_featured(self, limit: int = 10) -> list[RegistrySkillItem] | None:
        body = await self._get("/api/v1/genes/featured", {"limit": limit})
        data = body.get("data") if body else None
        if not data or not isinstance(data, list):
            return None
        return [self._gene_to_item(g) for g in data]

    async def get_tags(self) -> list[dict] | None:
        body = await self._get("/api/v1/genes/tags")
        return body.get("data") if body else None

    async def get_synergies(self, slug: str) -> list[dict] | None:
        body = await self._get(f"/api/v1/genes/{slug}/synergies")
        return body.get("data") if body else None

    async def publish_skill(self, manifest: dict) -> dict | None:
        body = await self._post("/api/v1/genes", {"manifest": manifest})
        return body.get("data") if body else None

    async def report_install(self, slug: str) -> bool:
        result = await self._post(f"/api/v1/genes/{slug}/installed")
        return result is not None

    async def report_effectiveness(
        self, slug: str, metric_type: str, value: float
    ) -> bool:
        result = await self._post(
            f"/api/v1/genes/{slug}/effectiveness",
            {"metric_type": metric_type, "value": value},
        )
        return result is not None

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
