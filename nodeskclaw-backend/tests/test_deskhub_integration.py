"""Tests for DeskHub adapter, bootstrap config, and registry aggregation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.services.deskhub_client import DeskHubAdapter, _extract_paginated
from app.services.registry_adapter import (
    RegistrySearchResult,
    RegistrySkillDetail,
    RegistrySkillItem,
)


class _MockResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._body


class _MockHTTP:
    def __init__(self, responses: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]] = []
        self.is_closed = False

    async def get(self, url: str, params: dict[str, Any] | None = None) -> _MockResponse:
        path = url.removeprefix("https://skills.deskclaw.me")
        self.calls.append(("GET", path, params, None))
        return _MockResponse(self.responses[("GET", path)])

    async def post(self, url: str, json: dict[str, Any] | None = None) -> _MockResponse:
        path = url.removeprefix("https://skills.deskclaw.me")
        self.calls.append(("POST", path, None, json))
        return _MockResponse(self.responses[("POST", path)])

    async def aclose(self) -> None:
        self.is_closed = True


def _make_deskhub_adapter(mock_http: _MockHTTP) -> DeskHubAdapter:
    adapter = DeskHubAdapter(
        registry_id="deskhub",
        registry_name="DeskHub",
        base_url="https://skills.deskclaw.me",
        api_key="dhb_test",
    )
    adapter._http = mock_http
    return adapter


class TestDeskHubAdapter:
    def test_extract_paginated_supports_object_and_array(self) -> None:
        items, total = _extract_paginated({"data": {"items": [{"slug": "a"}], "total": 42}})
        assert items == [{"slug": "a"}]
        assert total == 42

        items, total = _extract_paginated({"data": [{"slug": "b"}]})
        assert items == [{"slug": "b"}]
        assert total == 1

    @pytest.mark.asyncio
    async def test_search_maps_deskhub_items(self) -> None:
        mock_http = _MockHTTP({
            ("GET", "/api/v1/genes"): {
                "code": 0,
                "data": {
                    "items": [{
                        "slug": "skill-a",
                        "name": "Skill A",
                        "short_description": "short",
                        "version": "1.0.0",
                        "tags": ["tool"],
                        "install_count": 9,
                    }],
                    "total": 1,
                },
            },
        })
        adapter = _make_deskhub_adapter(mock_http)

        result = await adapter.search_skills(
            keyword="skill",
            tag="tool",
            category="efficiency",
            sort="popularity",
            page=2,
            page_size=10,
        )

        assert result is not None
        assert result.total == 1
        assert result.items[0].slug == "skill-a"
        assert result.items[0].source_registry == "deskhub"
        assert result.items[0].source_registry_name == "DeskHub"
        assert mock_http.calls[0] == (
            "GET",
            "/api/v1/genes",
            {
                "page": 2,
                "page_size": 10,
                "q": "skill",
                "tags": "tool",
                "category": "efficiency",
                "sort": "popular",
            },
            None,
        )
        await adapter.close()
        assert mock_http.is_closed is True

    @pytest.mark.asyncio
    async def test_protocol_methods_use_deskhub_endpoints(self) -> None:
        mock_http = _MockHTTP({
            ("GET", "/api/v1/genes/skill-a"): {
                "code": 0,
                "data": {"slug": "skill-a", "name": "Skill A"},
            },
            ("GET", "/api/v1/genes/skill-a/manifest"): {
                "code": 0,
                "data": {"skill": {"name": "skill-a"}},
            },
            ("GET", "/api/v1/genes/featured"): {
                "code": 0,
                "data": [{"slug": "skill-a", "name": "Skill A"}],
            },
            ("GET", "/api/v1/genes/tags"): {
                "code": 0,
                "data": [{"tag": "tool", "count": 3}],
            },
            ("GET", "/api/v1/genes/skill-a/synergies"): {
                "code": 0,
                "data": [{"slug": "skill-b"}],
            },
            ("POST", "/api/v1/genes"): {
                "code": 0,
                "data": {"slug": "skill-a"},
            },
            ("POST", "/api/v1/genes/skill-a/installed"): {
                "code": 0,
                "data": {},
            },
            ("POST", "/api/v1/genes/skill-a/effectiveness"): {
                "code": 0,
                "data": {},
            },
        })
        adapter = _make_deskhub_adapter(mock_http)

        detail = await adapter.get_skill("skill-a")
        manifest = await adapter.get_manifest("skill-a", version="1.0.0")
        featured = await adapter.get_featured(limit=5)
        tags = await adapter.get_tags()
        synergies = await adapter.get_synergies("skill-a")
        published = await adapter.publish_skill({"slug": "skill-a"})
        reported_install = await adapter.report_install("skill-a")
        reported_effectiveness = await adapter.report_effectiveness("skill-a", "success", 1.0)

        assert detail is not None
        assert detail.source_registry == "deskhub"
        assert manifest == {"skill": {"name": "skill-a"}}
        assert featured and featured[0].source_registry_name == "DeskHub"
        assert tags == [{"tag": "tool", "count": 3}]
        assert synergies == [{"slug": "skill-b"}]
        assert published == {"slug": "skill-a"}
        assert reported_install is True
        assert reported_effectiveness is True
        assert ("POST", "/api/v1/genes", None, {"manifest": {"slug": "skill-a"}}) in mock_http.calls


class TestRegistryBootstrap:
    def test_no_deskhub_config_registers_only_local(self) -> None:
        from app.services.registry_bootstrap import build_registry_adapters

        adapters = build_registry_adapters(
            session_factory=lambda: None,
            skill_registries_raw="",
            deskhub_registry_url="",
            deskhub_api_key="",
        )

        assert [adapter.registry_id for adapter in adapters] == ["local"]

    @pytest.mark.asyncio
    async def test_deskhub_url_auto_registers_deskhub(self) -> None:
        from app.services.registry_bootstrap import build_registry_adapters

        adapters = build_registry_adapters(
            session_factory=lambda: None,
            skill_registries_raw="",
            deskhub_registry_url="https://skills.deskclaw.me",
            deskhub_api_key="dhb_test",
        )

        assert [adapter.registry_id for adapter in adapters] == ["local", "deskhub"]
        assert adapters[1].registry_name == "DeskHub"
        assert adapters[1].base_url == "https://skills.deskclaw.me"
        await adapters[1].close()

    @pytest.mark.asyncio
    async def test_skill_registries_overrides_default_deskhub_config(self) -> None:
        from app.services.registry_bootstrap import build_registry_adapters

        adapters = build_registry_adapters(
            session_factory=lambda: None,
            skill_registries_raw=(
                '[{"type":"deskhub","id":"official","url":"https://skills.deskclaw.me",'
                '"api_key":"dhb_test","name":"DeskHub"}]'
            ),
            deskhub_registry_url="https://ignored.example.com",
            deskhub_api_key="ignored",
        )

        assert [adapter.registry_id for adapter in adapters] == ["local", "official"]
        assert adapters[1].registry_name == "DeskHub"
        await adapters[1].close()

    def test_old_registry_env_names_are_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GENEHUB_REGISTRY_URL", "https://old.example.com")
        monkeypatch.delenv("DESKHUB_REGISTRY_URL", raising=False)

        settings = Settings(DEBUG=True, _env_file=None)

        assert settings.DESKHUB_REGISTRY_URL == ""


def test_source_registry_migration_rewrites_only_legacy_value(monkeypatch: pytest.MonkeyPatch) -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "c355da7aa436_normalize_gene_source_registry.py"
    )
    spec = importlib.util.spec_from_file_location("source_registry_migration", migration_path)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)

    migration.upgrade()

    assert statements == [
        "UPDATE genes SET source_registry = 'local' WHERE source_registry = 'genehub'"
    ]


def test_local_adapter_preserves_stored_deskhub_source() -> None:
    from app.services.local_adapter import _gene_to_item

    gene = SimpleNamespace(
        id="local-id",
        slug="skill-a",
        name="Skill A",
        description=None,
        short_description=None,
        version="1.0.0",
        tags="[]",
        category=None,
        source="official",
        source_ref=None,
        icon=None,
        install_count=0,
        avg_rating=0,
        effectiveness_score=0,
        is_featured=False,
        review_status="approved",
        is_published=True,
        manifest="{}",
        dependencies="[]",
        synergies="[]",
        parent_gene_id=None,
        created_by_instance_id=None,
        created_by=None,
        org_id=None,
        visibility="public",
        created_at=None,
        updated_at=None,
        source_registry="deskhub",
    )

    item = _gene_to_item(gene)

    assert item.source_registry == "deskhub"
    assert item.source_registry_name == "DeskHub"


class _MockAdapter:
    def __init__(self, registry_id: str, items: list[RegistrySkillItem]):
        self.registry_id = registry_id
        self.registry_name = registry_id
        self.base_url = None
        self._items = items

    async def search_skills(self, **kwargs) -> RegistrySearchResult:
        return RegistrySearchResult(items=self._items, total=len(self._items))

    async def get_skill(self, slug: str) -> RegistrySkillDetail | None:
        for item in self._items:
            if item.slug == slug:
                return RegistrySkillDetail(**item.model_dump())
        return None

    async def get_manifest(self, slug: str, version=None) -> dict | None:
        for item in self._items:
            if item.slug == slug:
                return item.manifest
        return None

    async def get_featured(self, limit: int = 10) -> list[RegistrySkillItem]:
        return self._items[:limit]

    async def get_tags(self) -> list[dict]:
        return [{"tag": "mock", "count": 1}]

    async def get_synergies(self, slug: str) -> list[dict] | None:
        return None

    async def publish_skill(self, manifest: dict) -> dict | None:
        return None

    async def report_install(self, slug: str) -> bool:
        return True

    async def report_effectiveness(self, slug: str, metric_type: str, value: float) -> bool:
        return True

    async def close(self) -> None:
        pass


def _make_item(slug: str, registry_id: str, install_count: int = 0) -> RegistrySkillItem:
    return RegistrySkillItem(
        slug=slug,
        name=slug,
        source_registry=registry_id,
        source_registry_name=registry_id,
        install_count=install_count,
    )


class TestRegistryAggregator:
    @pytest.mark.asyncio
    async def test_search_merges_by_local_deskhub_clawhub_priority(self):
        from app.services.registry_aggregator import RegistryAggregator

        local = _MockAdapter("local", [_make_item("skill-a", "local"), _make_item("skill-b", "local")])
        deskhub = _MockAdapter("deskhub", [_make_item("skill-b", "deskhub"), _make_item("skill-c", "deskhub")])
        clawhub = _MockAdapter("clawhub", [_make_item("skill-b", "clawhub"), _make_item("skill-d", "clawhub")])
        aggregator = RegistryAggregator([clawhub, deskhub, local])

        result = await aggregator.search()

        assert {item.slug for item in result.items} == {"skill-a", "skill-b", "skill-c", "skill-d"}
        skill_b = next(item for item in result.items if item.slug == "skill-b")
        assert skill_b.source_registry == "local"

    @pytest.mark.asyncio
    async def test_get_skill_uses_local_before_deskhub(self):
        from app.services.registry_aggregator import RegistryAggregator

        local = _MockAdapter("local", [_make_item("skill-x", "local")])
        deskhub = _MockAdapter("deskhub", [_make_item("skill-x", "deskhub")])
        aggregator = RegistryAggregator([deskhub, local])

        detail = await aggregator.get_skill("skill-x")

        assert detail is not None
        assert detail.source_registry == "local"

    @pytest.mark.asyncio
    async def test_search_handles_adapter_failure(self):
        from app.services.registry_aggregator import RegistryAggregator

        class FailingAdapter(_MockAdapter):
            async def search_skills(self, **kwargs):
                raise RuntimeError("network error")

        local = _MockAdapter("local", [_make_item("skill-a", "local")])
        failing = FailingAdapter("deskhub", [])
        aggregator = RegistryAggregator([local, failing])

        result = await aggregator.search()

        assert len(result.items) == 1
        assert result.items[0].slug == "skill-a"

    @pytest.mark.asyncio
    async def test_get_featured_dedupes_and_sorts(self):
        from app.services.registry_aggregator import RegistryAggregator

        local = _MockAdapter("local", [_make_item("skill-a", "local", install_count=5)])
        deskhub = _MockAdapter("deskhub", [_make_item("skill-b", "deskhub", install_count=10)])
        aggregator = RegistryAggregator([local, deskhub])

        featured = await aggregator.get_featured(limit=10)

        assert len(featured) == 2
        assert featured[0].slug == "skill-b"

    @pytest.mark.asyncio
    async def test_publish_and_report_routes_to_selected_adapter(self):
        from app.services.registry_aggregator import RegistryAggregator

        local = _MockAdapter("local", [])
        deskhub = _MockAdapter("deskhub", [])
        aggregator = RegistryAggregator([local, deskhub])

        assert await aggregator.publish_to("deskhub", {"slug": "test"}) is None
        assert await aggregator.report_install_to("deskhub", "test") is True
        assert await aggregator.report_effectiveness_to("deskhub", "test", "success", 1.0) is True
        assert await aggregator.publish_to("unknown", {"slug": "test"}) is None

    @pytest.mark.asyncio
    async def test_module_level_api(self):
        from app.services import registry_aggregator

        local = _MockAdapter("local", [_make_item("skill-a", "local")])
        registry_aggregator.init([local])

        aggregator = registry_aggregator.get_aggregator()
        result = await aggregator.search()
        assert len(result.items) == 1

        await registry_aggregator.close()

        with pytest.raises(RuntimeError):
            registry_aggregator.get_aggregator()
