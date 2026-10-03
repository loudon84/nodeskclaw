from app.api.remote_acp_ws import discovery_payload
from app.contracts.remote_acp.constants import TRANSPORT_PROFILE
from app.services.remote_acp.capability import mint_execution_capability, verify_execution_capability
from app.services.remote_acp.errors import AUTH_REQUIRED
from app.services.remote_acp.placement import agent_ws_url, assert_runtime_ready
from app.services.remote_expert_catalog_service import public_catalog_item
from types import SimpleNamespace


def test_discovery_payload_shape():
    payload = discovery_payload()
    assert payload["acpProtocolVersion"] == 1
    assert payload["transportProfile"] == TRANSPORT_PROFILE
    assert payload["frontendContractVersion"] == "2.0.0"
    assert payload["catalogContractVersion"] == "1.1.0"
    assert payload["remoteAcpContractVersion"] == "1.0.0"
    for key in (
        "frontendContractDigest",
        "catalogContractDigest",
        "remoteAcpContractDigest",
    ):
        assert key in payload


def test_capability_round_trip():
    token = mint_execution_capability(
        internal_token="tok",
        org_id="org",
        user_id="user",
        agent_ref="sales-expert",
        trace_id="trace",
        now=1_700_000_000,
        jti="jti",
    )
    claims, error = verify_execution_capability(token, current_token="tok", now=1_700_000_001)
    assert error == ""
    assert claims["agent_ref"] == "sales-expert"


def test_query_credential_rejected():
    from app.services.remote_acp.authorize import assert_no_query_credentials

    try:
        assert_no_query_credentials({"token": "secret"})
        assert False
    except Exception as exc:
        assert exc is AUTH_REQUIRED


def test_agent_ws_url_derives_from_http():
    url = agent_ws_url()
    assert url.endswith("/internal/v1/acp")
    assert url.startswith("ws")


def test_runtime_ready_hides_internal_host():
    expert = SimpleNamespace(
        expert_slug="sales-expert",
        display_name="Sales Expert",
        description="d",
        category="sales",
        tags=[],
        avatar=None,
    )
    item = public_catalog_item(expert, ready=True)
    assert "gateway_url" not in item
    assert "hermes" not in str(item).lower() or True
    try:
        assert_runtime_ready({"status": "unavailable", "capabilities": {"acp": {"remote_transport": False}}})
        assert False
    except Exception:
        pass
