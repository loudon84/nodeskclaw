import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.config import (
    ALEMBIC_VERSION_NUM_LENGTH,
    Settings,
    alembic_context_version_options,
    alembic_version_relation,
    settings,
)
from app.db import get_db
from app.services.readiness import expected_alembic_heads

migration_path = Path(__file__).resolve().parent.parent / "alembic" / "versions" / "0001_initial_agent_schema.py"
spec = importlib.util.spec_from_file_location("migration_0001", migration_path)
migration_0001 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration_0001)

DEFAULT_HEAD = next(iter(expected_alembic_heads()))


def _mock_session_local(monkeypatch, mock_db: AsyncMock) -> None:
    import app.main as main_module

    class _SessionCtx:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(main_module, "SessionLocal", lambda: _SessionCtx())


def _default_mock_db() -> AsyncMock:
    mock_db = AsyncMock()
    mock_ok = MagicMock()
    mock_version = MagicMock()
    mock_version.fetchall.return_value = [(DEFAULT_HEAD,)]
    mock_db.execute.side_effect = [mock_ok, mock_version]
    return mock_db


def _test_client(monkeypatch, mock_db=None):
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", False)
    import app.main as main_module

    if mock_db is None:
        mock_db = _default_mock_db()

    _mock_session_local(monkeypatch, mock_db)

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
    assert alembic_context_version_options() == {
        "version_table": "alembic_version",
        "version_table_schema": "agent",
    }
    assert alembic_version_relation() == '"agent".alembic_version'


def test_agent_revision_ids_fit_version_column():
    versions_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    for path in sorted(versions_dir.glob("*.py")):
        revision = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("revision") and "=" in line:
                revision = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
        assert revision, f"missing revision in {path.name}"
        assert len(revision) <= ALEMBIC_VERSION_NUM_LENGTH, (
            f"{path.name} revision {revision!r} exceeds VARCHAR({ALEMBIC_VERSION_NUM_LENGTH})"
        )


def test_health_ready_queries_schema_qualified_alembic_version(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    mock_db = _default_mock_db()

    for client in _test_client(monkeypatch, mock_db=mock_db):
        resp = client.get("/health/ready")
        assert resp.status_code == 200

    version_sqls = [str(call.args[0]) for call in mock_db.execute.call_args_list if call.args]
    assert any('"agent".alembic_version' in sql for sql in version_sqls)
    assert not any("FROM alembic_version" in sql.replace('"agent".alembic_version', "") for sql in version_sqls)


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
    mock_res_db = MagicMock()
    mock_res_db.fetchall.return_value = []
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


def test_health_ready_worker_freshness_check(monkeypatch, tmp_path):
    import app.main as main_module
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_ROLE", "central")
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", str(tmp_path))

    mock_worker = MagicMock()
    mock_worker.last_successful_loop_at = datetime.now(timezone.utc) - timedelta(seconds=300)
    main_module.app.state.worker = mock_worker

    for client in _test_client(monkeypatch):
        monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", True)
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["checks"]["worker"] is False
        assert "worker.loop.stale" in data["codes"]

    mock_worker.last_successful_loop_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    for client in _test_client(monkeypatch):
        monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", True)
        resp = client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["checks"]["worker"] is True
        assert data["status"] == "ok"


def test_health_ready_worker_missing_successful_loop(monkeypatch, tmp_path):
    import app.main as main_module

    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_ROLE", "central")
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", str(tmp_path))

    mock_worker = MagicMock()
    mock_worker.last_successful_loop_at = None
    main_module.app.state.worker = mock_worker

    for client in _test_client(monkeypatch):
        monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", True)
        resp = client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert "worker.loop.missing" in data["codes"]


def test_edge_readiness_requires_heartbeat_when_worker_is_disabled(monkeypatch, tmp_path):
    import app.main as main_module

    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", False)
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", False)
    monkeypatch.setattr(settings, "SKILL_AGENT_ROLE", "edge")
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secure-internal-token")
    monkeypatch.setattr(settings, "SKILL_AGENT_EDGE_TOKEN", "secure-edge-token")
    monkeypatch.setattr(settings, "SKILL_AGENT_EDGE_NODE_ID", "edge-1")
    monkeypatch.setattr(settings, "SKILL_AGENT_CENTRAL_BASE_URL", "https://backend.test")
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", str(tmp_path))
    main_module.app.state.worker = None

    for client in _test_client(monkeypatch):
        resp = client.get("/health/ready")

    assert resp.status_code == 503
    assert "edge.heartbeat.missing" in resp.json()["codes"]


def test_edge_readiness_does_not_require_database_or_migration(monkeypatch, tmp_path):
    import app.main as main_module
    from datetime import datetime, timezone

    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_ROLE", "edge")
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", str(tmp_path))
    mock_db = AsyncMock()
    mock_db.execute.side_effect = RuntimeError("database unavailable")
    edge_worker = MagicMock()
    edge_worker.last_heartbeat_at = datetime.now(timezone.utc)
    main_module.app.state.worker = edge_worker

    for client in _test_client(monkeypatch, mock_db=mock_db):
        monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", True)
        resp = client.get("/health/ready")

    assert resp.status_code == 200
    assert "database" not in resp.json()["checks"]


def test_central_readiness_closes_storage_driver(monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", False)
    monkeypatch.setattr(settings, "SKILL_AGENT_ROLE", "central")
    storage_driver = MagicMock()
    storage_driver.probe_isolation = AsyncMock(return_value={"ok": True, "cleanup_failed": False})
    storage_driver.close = AsyncMock()
    monkeypatch.setattr(main_module, "get_storage_driver", lambda: storage_driver)

    for client in _test_client(monkeypatch):
        resp = client.get("/health/ready")

    assert resp.status_code == 200
    storage_driver.close.assert_awaited_once()
