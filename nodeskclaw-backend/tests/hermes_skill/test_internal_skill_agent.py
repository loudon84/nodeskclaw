import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from app.api.internal_skill_agent import mint_credential_lease, MintCredentialRequest, _verify_internal_token
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance


def _instance(*, env_file="/data/hermes/.env"):
    record = MagicMock(spec=HermesAgentInstance)
    record.id = "inst-1"
    record.gateway_url = "http://gw:8642"
    record.env_file = env_file
    return record


def _mint_request():
    return MintCredentialRequest(
        run_id="run-123",
        attempt_id="att-456",
        instance_id="inst-1",
        scope="hermes:invoke",
        target="target-inst",
    )


@pytest.mark.asyncio
# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Credential Lease API Server Key]]
async def test_mint_credential_lease_returns_api_server_key():
    db = AsyncMock()
    record = _instance()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    db.execute.return_value = mock_result

    env = MagicMock()
    env.api_server_model_name = "marketing"
    env.raw = {"API_SERVER_KEY": "hermes-api-server-key"}

    with patch("app.api.internal_skill_agent.parse_env_file", return_value=env), patch(
        "app.core.security.create_access_token",
    ) as mock_token_func:
        res = await mint_credential_lease(_mint_request(), db=db, x_exec_org_id="org-1")

    assert res.token == "hermes-api-server-key"
    assert res.gateway_url == "http://gw:8642"
    assert res.model == "marketing"
    assert res.expires_in == 900
    mock_token_func.assert_not_called()
    from app.api import internal_skill_agent as mint_mod
    assert not hasattr(mint_mod, "create_access_token")


@pytest.mark.asyncio
async def test_mint_credential_lease_missing_api_server_key_fail_closed():
    db = AsyncMock()
    record = _instance()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    db.execute.return_value = mock_result

    env = MagicMock()
    env.api_server_model_name = "marketing"
    env.raw = {}

    with patch("app.api.internal_skill_agent.parse_env_file", return_value=env), patch(
        "app.core.security.create_access_token",
    ) as mock_token_func:
        with pytest.raises(HTTPException) as exc_info:
            await mint_credential_lease(_mint_request(), db=db, x_exec_org_id="org-1")

    assert exc_info.value.status_code == 503
    mock_token_func.assert_not_called()


@pytest.mark.asyncio
async def test_mint_credential_lease_missing_env_file_fail_closed():
    db = AsyncMock()
    record = _instance(env_file=None)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = record
    db.execute.return_value = mock_result

    with patch("app.core.security.create_access_token") as mock_token_func:
        with pytest.raises(HTTPException) as exc_info:
            await mint_credential_lease(_mint_request(), db=db, x_exec_org_id="org-1")

    assert exc_info.value.status_code == 503
    mock_token_func.assert_not_called()


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
    req1 = MintCredentialRequest(run_id="", attempt_id="att-1", instance_id="inst-1")
    with pytest.raises(HTTPException) as exc_info:
        await mint_credential_lease(req1, db=db, x_exec_org_id="org-1")
    assert exc_info.value.status_code == 400
    assert "missing run_id or attempt_id" in str(exc_info.value.detail)

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
