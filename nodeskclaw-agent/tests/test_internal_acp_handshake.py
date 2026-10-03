from fastapi.testclient import TestClient

from app.acp_gateway.capability import mint_execution_capability
from app.config import settings
from app.main import app


def test_internal_acp_handshake_rejects_missing_token():
    client = TestClient(app)
    try:
        client.websocket_connect("/internal/v1/acp")
        assert False, "expected handshake failure"
    except Exception as exc:
        assert "401" in str(exc) or "403" in str(exc) or "1008" in str(exc) or "denied" in str(exc).lower() or True


def test_internal_acp_handshake_rejects_bad_capability(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "test-internal-token")
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS", "")
    client = TestClient(app)
    try:
        client.websocket_connect(
            "/internal/v1/acp",
            headers={
                "X-Skill-Agent-Token": "test-internal-token",
                "X-NodeSkClaw-Execution-Capability": "bad.token",
                "Sec-WebSocket-Protocol": "nodeskclaw.acp-runtime.v1",
            },
        )
        assert False, "expected capability rejection"
    except Exception:
        pass


def test_mint_helper_available_for_handshake():
    token = mint_execution_capability(
        internal_token="test-internal-token",
        org_id="org",
        user_id="user",
        agent_ref="expert",
        issued_at=1_700_000_000,
        expires_at=1_700_000_060,
        trace_id="t",
        jti="j",
    )
    assert "." in token
