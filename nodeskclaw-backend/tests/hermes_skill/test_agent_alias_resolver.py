import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.agent_alias_resolver import (
    AgentAliasResolver,
    REASON_MATCHED_BY_ALIAS,
    REASON_MATCHED_BY_AGENT_ID,
    REASON_MATCHED_BY_NAME,
)
from app.models.instance import Instance


def _instance(
    instance_id: str = "inst-1",
    name: str = "Writer Agent",
    slug: str = "writer-agent",
    advanced_config: str | None = None,
):
    inst = MagicMock(spec=Instance)
    inst.id = instance_id
    inst.name = name
    inst.slug = slug
    inst.advanced_config = advanced_config
    inst.deleted_at = None
    return inst


@pytest.mark.asyncio
async def test_resolve_by_agent_alias_in_advanced_config():
    db = AsyncMock()
    inst = _instance(advanced_config=json.dumps({"agent_alias": "common-writer"}))
    svc = AgentAliasResolver(db)
    build_mock = AsyncMock(return_value=MagicMock(agent_alias="common-writer"))
    with patch.object(svc, "_list_org_instances", AsyncMock(return_value=[inst])):
        with patch.object(svc, "_build_resolution", build_mock):
            result = await svc.resolve("org-1", "common-writer")
    assert result is not None
    build_mock.assert_awaited_once()
    assert build_mock.await_args.args[3] == REASON_MATCHED_BY_ALIAS


@pytest.mark.asyncio
async def test_resolve_by_name():
    db = AsyncMock()
    inst = _instance(name="common-writer")
    svc = AgentAliasResolver(db)
    build_mock = AsyncMock(return_value=MagicMock(agent_alias="common-writer"))
    with patch.object(svc, "_list_org_instances", AsyncMock(return_value=[inst])):
        with patch.object(svc, "_build_resolution", build_mock):
            result = await svc.resolve("org-1", "common-writer")
    assert result is not None
    assert build_mock.await_args.args[3] == REASON_MATCHED_BY_NAME


@pytest.mark.asyncio
async def test_resolve_by_agent_id_fallback():
    db = AsyncMock()
    inst = _instance(instance_id="agent-uuid-1")
    svc = AgentAliasResolver(db)
    build_mock = AsyncMock(return_value=MagicMock(agent_id="agent-uuid-1"))
    with patch.object(svc, "_list_org_instances", AsyncMock(return_value=[inst])):
        with patch.object(svc, "_build_resolution", build_mock):
            result = await svc.resolve("org-1", "agent-uuid-1")
    assert result is not None
    assert build_mock.await_args.args[3] == REASON_MATCHED_BY_AGENT_ID


@pytest.mark.asyncio
async def test_resolve_not_found():
    db = AsyncMock()
    svc = AgentAliasResolver(db)
    with patch.object(svc, "_list_org_instances", AsyncMock(return_value=[])):
        result = await svc.resolve("org-1", "missing-alias")
    assert result is None


@pytest.mark.asyncio
async def test_list_available_agents_filters_non_routable():
    db = AsyncMock()
    inst = _instance(advanced_config=json.dumps({"agent_alias": "common-writer"}))
    svc = AgentAliasResolver(db)
    with patch.object(svc, "_list_org_instances", AsyncMock(return_value=[inst])):
        with patch.object(svc.runtime_svc, "is_agent_routable", AsyncMock(return_value=False)):
            items = await svc.list_available_agents("org-1")
    assert items == []
