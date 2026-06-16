import pytest
from unittest.mock import AsyncMock, patch

from app.services.hermes_skill.hermes_client_service import HermesClientService


@pytest.mark.asyncio
async def test_list_client_tools_delegates_to_mapper():
    db = AsyncMock()
    svc = HermesClientService(db)
    with patch.object(svc.alias_resolver, "resolve", AsyncMock(return_value=None)):
        with patch("app.services.hermes_skill.hermes_client_service.McpToolMapper") as mapper_cls:
            mapper = mapper_cls.return_value
            mapper.list_tools = AsyncMock(return_value=[{"name": "writer_article_generate"}])
            with patch.object(svc.audit, "log", AsyncMock()):
                data = await svc.list_client_tools(
                    "org-1", "user-1", agent_alias="common-writer", category="writer",
                )
    assert data["total"] == 1
    assert data["items"][0]["name"] == "writer_article_generate"
    mapper.list_tools.assert_awaited_once()
