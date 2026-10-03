from pathlib import Path

from app.agent import AcpV1Agent
from app.errors import AdapterError
from app.profile import Profile
from app.session_registry import SessionRegistry

import pytest


def test_initialize_rejects_v2():
    agent = AcpV1Agent(
        Profile({"profile_version": 1, "name": "n", "agent_ref": "e"}, "p.yaml"),
        SessionRegistry("e"),
        None,
        None,
        None,
        None,
    )
    with pytest.raises(AdapterError) as trans:
        agent.initialize_result({"protocolVersion": 2})
    assert trans.value.symbol == "ACP_PROTOCOL_VERSION_UNSUPPORTED"
    result = agent.initialize_result({"protocolVersion": 1})
    assert result["protocolVersion"] == 1
    assert result["agentCapabilities"]["loadSession"] is False


def test_session_new_rejects_mcp(tmp_path):
    cwd = str(tmp_path.resolve())
    agent = AcpV1Agent(
        Profile({"profile_version": 1, "name": "n", "agent_ref": "e"}, "p.yaml"),
        SessionRegistry("e"),
        None,
        None,
        None,
        None,
    )
    with pytest.raises(AdapterError) as trans:
        agent.session_new({"cwd": cwd, "mcpServers": [{"name": "x"}]})
    assert trans.value.symbol == "ACP_CLIENT_MCP_UNSUPPORTED"
    created = agent.session_new({"cwd": cwd, "mcpServers": []})
    assert created["sessionId"]
