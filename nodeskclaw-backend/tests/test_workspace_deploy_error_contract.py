from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.deps import get_current_org, get_db
from app.main import app


def _make_db_override(fake_db):
    async def override_db():
        yield fake_db

    return override_db


@pytest.mark.asyncio
async def test_get_workspace_deploy_not_found_returns_unified_error(client):
    fake_db = AsyncMock()
    fake_db.execute.return_value = SimpleNamespace(first=lambda: None)
    app.dependency_overrides[get_current_org] = lambda: (
        SimpleNamespace(id="user-1"), SimpleNamespace(id="org-1"),
    )
    app.dependency_overrides[get_db] = _make_db_override(fake_db)
    try:
        response = await client.get("/api/v1/workspaces/deploys/deploy-missing")
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json() == {
        "code": 40461,
        "error_code": 40461,
        "message_key": "errors.workspace_deploy.not_found",
        "message": "部署记录不存在",
        "data": None,
    }


@pytest.mark.asyncio
async def test_workspace_deploy_progress_not_found_returns_unified_error(client):
    fake_db = AsyncMock()
    fake_db.execute.return_value = SimpleNamespace(scalar_one_or_none=lambda: None)
    app.dependency_overrides[get_current_org] = lambda: (
        SimpleNamespace(id="user-1"), SimpleNamespace(id="org-1"),
    )
    app.dependency_overrides[get_db] = _make_db_override(fake_db)
    try:
        response = await client.get("/api/v1/workspaces/deploys/deploy-missing/progress")
    finally:
        app.dependency_overrides.pop(get_current_org, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404
    assert response.json() == {
        "code": 40461,
        "error_code": 40461,
        "message_key": "errors.workspace_deploy.not_found",
        "message": "部署记录不存在",
        "data": None,
    }
