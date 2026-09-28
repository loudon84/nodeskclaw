"""Runtime provider bootstrap tests. These never call NEW-API."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.runtime_model_bootstrap import router
from app.core.deps import get_current_org, get_db
from app.services import runtime_model_bootstrap_service
from app.services.credential_crypto import encrypt_member_token
from app.services.member_token_models import EMPTY_MODELS
from app.services.runtime_model_bootstrap_service import _evaluate, build_runtime_bootstrap
from tests.test_member_token import KEY
from app.core.config import settings


@pytest.fixture(autouse=True)
def _crypto_key(monkeypatch):
    monkeypatch.setattr(settings, "MODEL_TOKEN_ENCRYPTION_KEY", KEY)


def _ready_row():
    return SimpleNamespace(
        id="t1",
        member_id="m1",
        provider="new-api",
        source="auto",
        base_url="http://new-api.example/v1",
        token=encrypt_member_token("bootstrap-key-12345678", token_id="t1", member_id="m1", provider="new-api"),
        token_fingerprint="fp",
        provider_group="vip",
        is_active=True,
        sync_status="synced",
        updated_at=datetime(2026, 9, 26, tzinfo=timezone.utc),
        models={
            "schema_version": "1.0",
            "default_model": "alpha",
            "items": [{
                "id": "alpha",
                "display_name": "Alpha",
                "context_window": None,
                "max_output_tokens": None,
                "enabled": True,
                "capabilities": ["chat"],
            }],
        },
    )


def test_bootstrap_states_hide_key_until_ready():
    missing = _evaluate(None)
    assert missing == {"ready": False, "state": "MODEL_NOT_CONFIGURED", "revision": None}
    assert "api_key" not in missing
    closing = _evaluate(SimpleNamespace(
        sync_status="revoke_pending",
        is_active=False,
        provider="new-api",
    ))
    assert closing["state"] == "MODEL_CREDENTIAL_CLOSING"
    assert "api_key" not in closing
    empty = _ready_row()
    empty.models = dict(EMPTY_MODELS)
    assert _evaluate(empty)["state"] == "MODEL_LIST_EMPTY"
    ready = _evaluate(_ready_row())
    assert ready["state"] == "READY"
    assert ready["api_key"] == "bootstrap-key-12345678"
    assert ready["base_url"] == "http://new-api.example/v1"
    assert "bootstrap-key" not in ready["revision"]


@pytest.mark.asyncio
async def test_bootstrap_route_requires_login_and_does_not_store_the_key():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        denied = await client.post("/api/v1/runtime/model-bootstrap", json={"consumer": "desktop", "runtime": "hermes"})
    assert denied.status_code in (401, 403)

    async def _no_token(*_args, **_kwargs):
        return {"ready": False, "state": "MODEL_NOT_CONFIGURED", "revision": None}

    app.dependency_overrides[get_current_org] = lambda: (SimpleNamespace(id="u1"), SimpleNamespace(id="org-1"))
    with patch.object(runtime_model_bootstrap_service, "build_runtime_bootstrap", new=_no_token):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/runtime/model-bootstrap",
                json={"consumer": "desktop", "runtime": "hermes", "org_id": "other"},
            )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ready_bootstrap_response_has_no_store_header():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_org] = lambda: (SimpleNamespace(id="u1"), SimpleNamespace(id="org-1"))

    async def _ready(*_args, **_kwargs):
        return _evaluate(_ready_row())

    with patch.object(runtime_model_bootstrap_service, "build_runtime_bootstrap", new=_ready):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/runtime/model-bootstrap",
                json={"consumer": "desktop", "runtime": "hermes"},
            )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["base_url"] == "http://new-api.example/v1"
    assert body["api_key"] == "bootstrap-key-12345678"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert "bootstrap-key" not in str({k: v for k, v in body.items() if k != "api_key"})


@pytest.mark.asyncio
async def test_bootstrap_uses_current_org_default_only():
    user = SimpleNamespace(id="u1")
    db = AsyncMock()
    with (
        patch.object(runtime_model_bootstrap_service, "_membership", new=AsyncMock(return_value=None)),
        patch.object(runtime_model_bootstrap_service, "hooks") as hooks,
    ):
        hooks.emit = AsyncMock()
        data = await build_runtime_bootstrap(db, user=user, org_id="org-1", consumer="desktop", runtime="hermes")
    assert data["state"] == "MODEL_NOT_CONFIGURED"
    assert "api_key" not in data
    details = hooks.emit.await_args.kwargs["details"]
    assert "api_key" not in details
