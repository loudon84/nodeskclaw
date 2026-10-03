import json
from pathlib import Path

from app.acp_gateway.capability import mint_execution_capability, verify_execution_capability

VECTOR = json.loads(
    Path("contracts/acp-runtime-gateway/v1.0.0/golden/capability-vector.json").read_text(encoding="utf-8")
)


def test_golden_capability_vector_round_trip():
    claims, error = verify_execution_capability(
        VECTOR["token"],
        current_token=VECTOR["internalToken"],
        now=VECTOR["now"] + 1,
    )
    assert error == ""
    assert claims["agent_ref"] == "sales-expert"
    assert claims["org_id"] == "org-1"


def test_capability_tamper_rejected():
    token = VECTOR["token"]
    body, sig = token.split(".")
    tampered = f"{body[:-1]}{'A' if body[-1] != 'A' else 'B'}.{sig}"
    claims, error = verify_execution_capability(
        tampered,
        current_token=VECTOR["internalToken"],
        now=VECTOR["now"] + 1,
    )
    assert claims is None
    assert error == "ACP_CAPABILITY_INVALID"


def test_capability_expiry_and_previous_key():
    token = mint_execution_capability(
        internal_token="previous-token",
        org_id="org-1",
        user_id="user-1",
        agent_ref="sales-expert",
        issued_at=VECTOR["now"],
        expires_at=VECTOR["now"] + 60,
        trace_id="trace",
        jti="jti-1",
    )
    claims, error = verify_execution_capability(
        token,
        current_token="current-token",
        previous_token="previous-token",
        now=VECTOR["now"] + 1,
    )
    assert error == ""
    assert claims["jti"] == "jti-1"
    _, expired = verify_execution_capability(
        token,
        current_token="current-token",
        previous_token="previous-token",
        now=VECTOR["now"] + 61,
    )
    assert expired == "ACP_CAPABILITY_EXPIRED"
