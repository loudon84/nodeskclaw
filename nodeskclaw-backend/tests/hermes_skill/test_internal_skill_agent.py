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

    req = MintCredentialRequest(instance_id="inst-1", scope="hermes:invoke")
    with patch("app.api.internal_skill_agent.create_access_token", return_value="jwt-test-token"):
        res = await mint_credential_lease(req, db=db, x_exec_org_id="org-1")

    assert res.token == "jwt-test-token"
    assert res.gateway_url == "http://gw:8642"
    assert res.expires_in == 900


@pytest.mark.asyncio
async def test_mint_credential_lease_missing_org_fails():
    db = AsyncMock()
    req = MintCredentialRequest(instance_id="inst-1")
    with pytest.raises(HTTPException) as exc_info:
        await mint_credential_lease(req, db=db, x_exec_org_id=None)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_verify_internal_token_fail_closed():
    with pytest.raises(HTTPException) as exc_info:
        _verify_internal_token("wrong-token")
    assert exc_info.value.status_code == 401
