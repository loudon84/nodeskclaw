import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, settings
from app.db import get_db

migration_path = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "0001_initial_agent_schema.py"
spec = importlib.util.spec_from_file_location("migration_0001", migration_path)
migration_0001 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration_0001)


def _test_client(monkeypatch, mock_db=None):
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", False)
    import app.main as main_module

    if mock_db is None:
        mock_db = AsyncMock()
        mock_res = MagicMock()
        mock_res.first.return_value = ("0001_initial_agent_schema",)
        mock_db.execute.return_value = mock_res

    async def _override_db():
        yield mock_db

    main_module.app.dependency_overrides[get_db] = _override_db
    client = TestClient(main_module.app)
    try:
        yield client
    finally:
        main_module.app.dependency_overrides.clear()


def test_schema_configuration_and_migration_alignment():
    default_settings = Settings()
    assert default_settings.SKILL_AGENT_SCHEMA == "agent"
    assert migration_0001.SCHEMA == "agent"


def test_health_ready_fails_on_insecure_defaults_in_production(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", False)
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "change-me-skill-agent-token")
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", "/tmp/artifacts")

    for client in _test_client(monkeypatch):
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"
        assert "insecure default internal token in production" in data["reasons"]
        assert "ephemeral artifact directory configured in production" in data["reasons"]


def test_health_ready_fails_on_edge_insecure_config(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", False)
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "valid-secure-token-123")
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", "./var/artifacts")
    monkeypatch.setattr(settings, "SKILL_AGENT_ROLE", "edge")
    monkeypatch.setattr(settings, "SKILL_AGENT_EDGE_TOKEN", "")
    monkeypatch.setattr(settings, "SKILL_AGENT_EDGE_NODE_ID", "")
    monkeypatch.setattr(settings, "SKILL_AGENT_CENTRAL_BASE_URL", "http://central:4510")

    for client in _test_client(monkeypatch):
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert "missing edge token" in data["reasons"]
        assert "missing edge node id" in data["reasons"]
        assert "insecure edge central base url (must be https://)" in data["reasons"]


def test_health_ready_succeeds_in_insecure_dev_mode(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "change-me-skill-agent-token")
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", "./var/artifacts")

    for client in _test_client(monkeypatch):
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


def test_readiness_fails_on_db_down(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    mock_db = AsyncMock()
    mock_db.execute.side_effect = Exception("DB connection refused")

    for client in _test_client(monkeypatch, mock_db=mock_db):
        resp = client.get("/healthz/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["database"] == "disconnected"
        assert data["checks"]["database"] is False


def test_readiness_fails_on_schema_drift(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    mock_db = AsyncMock()
    # SELECT 1 succeeds, but alembic_version returns empty/error
    mock_res_db = MagicMock()
    mock_res_db.first.return_value = None
    mock_db.execute.side_effect = [MagicMock(), mock_res_db]

    for client in _test_client(monkeypatch, mock_db=mock_db):
        resp = client.get("/healthz/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["checks"]["migration"] is False


def test_readiness_fails_on_illegal_storage_path(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", False)
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secure-token-123456")
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", "/tmp/forbidden_artifacts")

    for client in _test_client(monkeypatch):
        resp = client.get("/healthz/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["checks"]["config_security"] is False
        assert "ephemeral artifact directory configured in production" in data["reasons"]


def test_insecure_mode_allows_ephemeral_storage_with_audit_warning(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", "./tmp_ephemeral_dev")

    for client in _test_client(monkeypatch):
        resp = client.get("/healthz/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
