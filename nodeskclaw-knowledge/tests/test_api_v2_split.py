"""API v2 split — router wiring, health/ready, engineering and runtime admin."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v2 import applications, assets, engineering, retrieval, router, runtime_admin, translations
from app.core.config import settings
from app.core.exceptions import BadRequestError, ForbiddenError
from app.main import app
from app.runtime.ragflow import RuntimeHealth
from app.schemas.knowledge import KnowledgeSetV2Create
from app.schemas.principal import KnowledgePrincipal


def _member(**kwargs) -> KnowledgePrincipal:
    base = dict(
        user_id="u1",
        member_id="m1",
        org_id="o1",
        member_role="operator",
        is_super_admin=False,
    )
    base.update(kwargs)
    return KnowledgePrincipal(**base)


def _collect_v2_route_paths() -> set[str]:
    paths: set[str] = set()
    for included in router.router.routes:
        sub = getattr(included, "original_router", None)
        if sub is None:
            continue
        prefix = getattr(included, "include_context", None)
        prefix_path = getattr(prefix, "prefix", "") if prefix else ""
        for route in sub.routes:
            nested = getattr(route, "original_router", None)
            if nested is not None:
                for nested_route in nested.routes:
                    paths.add(prefix_path + nested_route.path)
            else:
                paths.add(prefix_path + route.path)
    return paths


def test_v2_router_includes_domain_subrouters():
    route_paths = _collect_v2_route_paths()
    assert "/knowledge-bases" in route_paths
    assert "/applications" in route_paths
    assert "/applications/{application_id}/retrieval" in route_paths
    assert "/retrieval/playground" in route_paths
    assert "/translations" in route_paths
    assert "/evidence/{evidence_id}" in route_paths
    assert "/knowledge-bases/{kb_id}/indexes" in route_paths
    assert "/builds" in route_paths
    assert "/runtime/health" in route_paths


def test_assets_module_has_no_application_routes():
    route_paths = {getattr(r, "path", "") for r in assets.router.routes}
    assert "/applications" not in route_paths
    assert "/knowledge-bases" in route_paths
    assert "/knowledge-sets" in route_paths


def test_applications_module_exports_application_routes():
    route_paths = {getattr(r, "path", "") for r in applications.router.routes}
    assert "/applications" in route_paths
    assert "/applications/{application_id}/publish" in route_paths


def test_retrieval_module_exports_retrieval_routes():
    route_paths = {getattr(r, "path", "") for r in retrieval.router.routes}
    assert "/applications/{application_id}/retrieval" in route_paths
    assert "/retrieval/playground" in route_paths


def test_translations_module_exports_translation_routes():
    route_paths = {getattr(r, "path", "") for r in translations.router.routes}
    assert "/translations" in route_paths
    assert "/translations/{document_id}" in route_paths


def test_engineering_module_exports_build_routes():
    route_paths = {getattr(r, "path", "") for r in engineering.router.routes}
    assert "/knowledge-bases/{kb_id}/indexes" in route_paths
    assert "/knowledge-bases/{kb_id}/build-profile" in route_paths
    assert "/builds/{build_id}/retry" in route_paths


def test_runtime_admin_module_exports_admin_routes():
    route_paths = {getattr(r, "path", "") for r in runtime_admin.router.routes}
    assert "/runtime/health" in route_paths
    assert "/runtime/capabilities" in route_paths
    assert "/runtime/capabilities/probe" in route_paths


def test_health_ready_returns_only_reachability_booleans():
    mock_health = RuntimeHealth(
        reachable=True,
        version="0.24.0",
        chunk_retrieval_ok=True,
        capabilities={"supports_chunk": {"build_supported": True}},
        degraded_reasons=[],
    )
    with (
        patch("app.main.async_session_factory") as session_factory,
        patch("app.runtime.ragflow.RagflowRuntimeAdapter") as adapter_cls,
        patch("app.main.NodeskclawBackendClient") as backend_cls,
    ):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session_factory.return_value = session

        adapter = AsyncMock()
        adapter.check_health = AsyncMock(return_value=mock_health)
        adapter.aclose = AsyncMock()
        adapter_cls.return_value = adapter

        backend = AsyncMock()
        backend.health_check = AsyncMock(return_value=True)
        backend.aclose = AsyncMock()
        backend_cls.return_value = backend

        with TestClient(app) as client:
            resp = client.get("/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"status", "checks"}
    assert set(body["checks"].keys()) == {"database", "ragflow", "backend"}
    assert all(isinstance(v, bool) for v in body["checks"].values())
    assert "details" not in body
    assert "ragflow_capabilities" not in str(body)


@pytest.mark.asyncio
async def test_runtime_admin_requires_super_admin(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    with pytest.raises(ForbiddenError):
        await runtime_admin.runtime_health(member=_member(is_super_admin=False))


@pytest.mark.asyncio
async def test_engineering_build_disabled(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    monkeypatch.setattr(settings, "KNOWLEDGE_V2_BUILD_ENABLED", False)
    with pytest.raises(BadRequestError) as exc:
        await engineering.list_builds(
            member=_member(),
            db=AsyncMock(),
        )
    assert exc.value.message_key == "errors.knowledge.build_disabled"


@pytest.mark.asyncio
async def test_create_set_v2_defaults_embedding(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_API_V2_ENABLED", True)
    created = SimpleNamespace(
        id="set1",
        org_id="o1",
        name="set-a",
        description=None,
        owner_member_id="m1",
        status="active",
        acl_version=1,
        visibility="private",
        retrieval_config=None,
        usage_count=0,
        last_used_at=None,
    )
    with (
        patch(
            "app.api.v2.assets.knowledge_set_service.create_knowledge_set",
            new=AsyncMock(return_value=created),
        ) as create,
        patch(
            "app.api.v2.assets.knowledge_set_service.list_set_items",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "app.api.v2.assets.retrieval_profile_service.get_active_profile",
            new=AsyncMock(return_value=None),
        ),
    ):
        result = await assets.create_knowledge_set_v2(
            KnowledgeSetV2Create(name="set-a"),
            member=_member(),
            db=AsyncMock(),
        )
    create.assert_awaited_once()
    assert create.await_args.kwargs["embedding_model"] == "bge-m3"
    assert result.data.name == "set-a"
