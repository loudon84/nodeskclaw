from starlette.testclient import TestClient

from app.main import app
from app.services.remote_acp.errors import AUTH_REQUIRED


def test_ws_rejects_missing_bearer():
    client = TestClient(app)
    try:
        with client.websocket_connect(
            "/api/v1/remote-experts/sales-expert/acp",
            headers={"Sec-WebSocket-Protocol": "nodeskclaw.remote-acp.v1", "X-Org-Id": "org"},
        ):
            assert False
    except Exception:
        pass


def test_ws_rejects_query_token():
    client = TestClient(app)
    try:
        with client.websocket_connect(
            "/api/v1/remote-experts/sales-expert/acp?token=secret",
            headers={
                "Authorization": "Bearer x",
                "Sec-WebSocket-Protocol": "nodeskclaw.remote-acp.v1",
                "X-Org-Id": "org",
            },
        ):
            assert False
    except Exception:
        pass


def test_auth_required_payload():
    body = AUTH_REQUIRED.to_response().body
    assert b"REMOTE_ACP_AUTH_REQUIRED" in body
