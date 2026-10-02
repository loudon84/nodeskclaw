from app.services.attempt_capability import mint_capability, stable_tool_call_id, verify_capability


def test_capability_round_trip_and_rejects_tamper():
    token = mint_capability(
        org_id="org",
        run_id="run",
        attempt_id="att",
        generation=3,
        signing_key="test-key",
        ttl_seconds=900,
        now=1_000,
    )
    claims, error = verify_capability(token, signing_key="test-key", now=1_100)
    assert error == ""
    assert claims["run_id"] == "run"
    assert claims["generation"] == 3
    body, signature = token.split(".")
    tampered = f"{body[:-1]}{'A' if body[-1] != 'A' else 'B'}.{signature}"
    assert verify_capability(tampered, signing_key="test-key", now=1_100)[0] is None


def test_capability_expiry_and_missing_key():
    token = mint_capability(
        org_id="org",
        run_id="run",
        attempt_id="att",
        generation=1,
        signing_key="test-key",
        ttl_seconds=900,
        now=1_000,
    )
    assert verify_capability(token, signing_key="test-key", now=1_900)[1] == "AGENT_TOOL_CAPABILITY_EXPIRED"
    assert mint_capability(
        org_id="org",
        run_id="run",
        attempt_id="att",
        generation=1,
        signing_key="",
        ttl_seconds=900,
    ) is None
    assert verify_capability(token, signing_key="", now=1_100)[1] == "AGENT_TOOL_CAPABILITY_MISSING"


def test_tool_call_id_stays_stable_for_the_same_rpc_id():
    first = stable_tool_call_id(attempt_id="att", generation=2, rpc_id="7")
    assert first == stable_tool_call_id(attempt_id="att", generation=2, rpc_id="7")
    assert first != stable_tool_call_id(attempt_id="att", generation=2, rpc_id="8")
