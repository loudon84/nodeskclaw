from app.services.hermes_agents.mcp_tools_list_client import filter_tools, is_business_skill_tool


def test_is_business_skill_tool_excludes_registry():
    assert is_business_skill_tool("hermes_common_researcher__customer-profiling") is True
    assert is_business_skill_tool("hermes.instances.list") is False
    assert is_business_skill_tool("hermes.instance.get") is False
    assert is_business_skill_tool("hermes.skills.install") is False
    assert is_business_skill_tool("genehub.search") is False


def test_filter_tools_skill_only_default():
    tools = [
        {"name": "hermes_common_researcher__customer-profiling", "description": "a"},
        {"name": "hermes.instances.list", "description": "b"},
        {"name": "genehub.search", "description": "c"},
    ]
    filtered = filter_tools(tools, tool_filter="skill_only", include_registry_tools=False)
    assert len(filtered) == 1
    assert filtered[0]["name"] == "hermes_common_researcher__customer-profiling"


def test_filter_tools_include_registry():
    tools = [
        {"name": "hermes_common_researcher__customer-profiling", "description": "a"},
        {"name": "hermes.instances.list", "description": "b"},
    ]
    filtered = filter_tools(tools, tool_filter="skill_only", include_registry_tools=True)
    assert len(filtered) == 2
