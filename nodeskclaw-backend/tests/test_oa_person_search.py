from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import AppException, BadRequestError
from app.services import org_service


@pytest.mark.asyncio
async def test_search_oa_persons_empty_query_returns_empty(monkeypatch):
    monkeypatch.setattr(org_service.settings, "OA_PERSON_API_URL", "http://example.com/oa/person")
    result = await org_service.search_oa_persons("  ")
    assert result == []


@pytest.mark.asyncio
async def test_search_oa_persons_not_configured(monkeypatch):
    monkeypatch.setattr(org_service.settings, "OA_PERSON_API_URL", "")
    with pytest.raises(BadRequestError) as exc:
        await org_service.search_oa_persons("王冬辉")
    assert exc.value.message_key == "errors.org.oa_person_not_configured"


@pytest.mark.asyncio
async def test_search_oa_persons_maps_fields(monkeypatch):
    monkeypatch.setattr(org_service.settings, "OA_PERSON_API_URL", "http://example.com/oa/person")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "code": 1,
        "msg": "success",
        "data": [
            {
                "fd_no": "SMC-SZ-HR21007",
                "fd_name": "王冬辉",
                "fd_email": "wangdonghui@example.com",
                "fd_mobile_no": "13392860050",
                "fd_department": "IT部",
                "fd_staff": "开发经理",
            }
        ],
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.services.org_service.httpx.AsyncClient", return_value=mock_client):
        result = await org_service.search_oa_persons("王冬辉")

    mock_client.get.assert_awaited_once()
    call_kwargs = mock_client.get.await_args
    assert call_kwargs.args[0] == "http://example.com/oa/person"
    assert call_kwargs.kwargs["params"] == {"fd_name": "王冬辉"}
    assert len(result) == 1
    person = result[0]
    assert person.fd_no == "SMC-SZ-HR21007"
    assert person.fd_name == "王冬辉"
    assert person.fd_email == "wangdonghui@example.com"
    assert person.fd_department == "IT部"
    assert person.fd_staff == "开发经理"
    assert not hasattr(person, "fd_mobile_no") or getattr(person, "fd_mobile_no", None) is None


@pytest.mark.asyncio
async def test_search_oa_persons_upstream_code_failure(monkeypatch):
    monkeypatch.setattr(org_service.settings, "OA_PERSON_API_URL", "http://example.com/oa/person")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"code": 0, "msg": "fail", "data": []}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("app.services.org_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AppException) as exc:
            await org_service.search_oa_persons("王冬辉")
    assert exc.value.message_key == "errors.org.oa_person_search_failed"


@pytest.mark.asyncio
async def test_search_oa_persons_upstream_timeout(monkeypatch):
    monkeypatch.setattr(org_service.settings, "OA_PERSON_API_URL", "http://example.com/oa/person")

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with patch("app.services.org_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(AppException) as exc:
            await org_service.search_oa_persons("王冬辉")
    assert exc.value.message_key == "errors.org.oa_person_search_failed"
