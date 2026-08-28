import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.api.internal_skill_agent import mint_credential_lease, MintCredentialRequest, _verify_internal_token
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance


@pytest.mark.asyncio
async def test_mint_credential_lease_success():
    db = AsyncMock()
    record = MagicMock(spec=HermesAgentInstance)
    record.id = "inst-1"
    record.gateway_url = "http://gw:8642"
    record.env_file = None
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    db.execute.return_value = mock_result

    req = MintCredentialRequest(
        run_id="run-123",
        attempt_id="att-456",
        instance_id="inst-1",
        scope="hermes:invoke",
        target="target-inst",
    )
    with patch("app.api.internal_skill_agent.create_access_token") as mock_token_func:
        mock_token_func.return_value = "jwt-test-token"
        res = await mint_credential_lease(req, db=db, x_exec_org_id="org-1")

    assert res.token == "jwt-test-token"
    assert res.gateway_url == "http://gw:8642"
    assert res.expires_in == 900
    mock_token_func.assert_called_once()
    extra_claims = mock_token_func.call_args[1]["extra_claims"]
    assert extra_claims["org_id"] == "org-1"
    assert extra_claims["run_id"] == "run-123"
    assert extra_claims["attempt_id"] == "att-456"
    assert extra_claims["instance_id"] == "inst-1"
    assert extra_claims["target"] == "target-inst"


@pytest.mark.asyncio
async def test_mint_credential_lease_missing_org_fails():
    db = AsyncMock()
    req = MintCredentialRequest(run_id="run-1", attempt_id="att-1", instance_id="inst-1")
    with pytest.raises(HTTPException) as exc_info:
        await mint_credential_lease(req, db=db, x_exec_org_id=None)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_mint_credential_lease_missing_run_or_attempt_fails():
    db = AsyncMock()
    # Missing run_id
    req1 = MintCredentialRequest(run_id="", attempt_id="att-1", instance_id="inst-1")
    with pytest.raises(HTTPException) as exc_info:
        await mint_credential_lease(req1, db=db, x_exec_org_id="org-1")
    assert exc_info.value.status_code == 400
    assert "missing run_id or attempt_id" in str(exc_info.value.detail)

    # Missing attempt_id
    req2 = MintCredentialRequest(run_id="run-1", attempt_id=" ", instance_id="inst-1")
    with pytest.raises(HTTPException) as exc_info:
        await mint_credential_lease(req2, db=db, x_exec_org_id="org-1")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_mint_credential_lease_nonexistent_or_other_org_instance_404():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result

    req = MintCredentialRequest(run_id="run-1", attempt_id="att-1", instance_id="inst-foreign")
    with pytest.raises(HTTPException) as exc_info:
        await mint_credential_lease(req, db=db, x_exec_org_id="org-1")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_verify_internal_token_fail_closed():
    with pytest.raises(HTTPException) as exc_info:
        _verify_internal_token("wrong-token")
    assert exc_info.value.status_code == 401
