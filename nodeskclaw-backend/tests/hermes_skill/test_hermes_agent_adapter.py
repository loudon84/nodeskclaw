import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.instance import Instance
from app.services.hermes_skill.hermes_agent_adapter import HermesAgentAdapter, _parse_advanced_config


def test_parse_advanced_config_from_json_string():
    instance = MagicMock(spec=Instance)
    instance.advanced_config = '{"hermes_base_url": "https://agent.example.com"}'
    assert _parse_advanced_config(instance)["hermes_base_url"] == "https://agent.example.com"


def test_get_base_url_priority():
    instance = MagicMock(spec=Instance)
    instance.advanced_config = {
        "hermes_base_url": "https://hermes.example.com",
        "gateway_url": "https://gateway.example.com",
        "endpoint_url": "https://endpoint.example.com",
    }
    instance.ingress_domain = "ingress.example.com"
    assert HermesAgentAdapter._get_base_url(instance) == "https://hermes.example.com"


def test_get_base_url_endpoint_fallback():
    instance = MagicMock(spec=Instance)
    instance.advanced_config = {"endpoint_url": "https://endpoint.example.com"}
    instance.ingress_domain = None
    assert HermesAgentAdapter._get_base_url(instance) == "https://endpoint.example.com"


def test_get_base_url_ingress_fallback():
    instance = MagicMock(spec=Instance)
    instance.advanced_config = {}
    instance.ingress_domain = "ingress.example.com"
    assert HermesAgentAdapter._get_base_url(instance) == "https://ingress.example.com"


@pytest.mark.asyncio
async def test_get_run_status_supports_nested_status():
    db = AsyncMock()
    adapter = HermesAgentAdapter(db)
    task = MagicMock()
    task.hermes_run_id = "run-1"
    task.agent_id = "agent-1"
    task.org_id = "org-1"

    with patch.object(adapter, "get_run", new_callable=AsyncMock) as mock_get_run:
        mock_get_run.return_value = {"data": {"status": "completed"}}
        result = await adapter.get_run_status(task)

    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_cancel_run_fallback_to_post():
    db = AsyncMock()
    adapter = HermesAgentAdapter(db)
    task = MagicMock()
    task.hermes_run_id = "run-1"
    task.agent_id = "agent-1"
    task.org_id = "org-1"

    instance = MagicMock()
    instance.advanced_config = {"hermes_base_url": "https://agent.example.com"}
    instance.org_id = "org-1"

    with patch.object(adapter, "_get_instance", new_callable=AsyncMock, return_value=instance):
        with patch("app.services.hermes_skill.hermes_agent_adapter.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            delete_resp = MagicMock()
            delete_resp.status_code = 405
            mock_client.delete = AsyncMock(return_value=delete_resp)
            mock_client.post = AsyncMock(return_value=MagicMock(status_code=200))
            mock_client_cls.return_value = mock_client

            await adapter.cancel_run(task)

    mock_client.delete.assert_awaited_once()
    mock_client.post.assert_awaited_once()
