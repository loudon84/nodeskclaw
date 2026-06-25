from app.services.hermes_agents.router_skill_template_service import (
    FORBIDDEN_CONTENT_FRAGMENTS,
    render_router_skill_md,
    tool_display_title,
)


def test_tool_display_title_override():
    assert tool_display_title("hermes_common_researcher__customer-profiling") == "客户画像与销售机会分析"


def test_render_router_skill_md_contains_tools():
    tools = [
        {
            "name": "hermes_common_researcher__customer-profiling",
            "description": "分析客户画像",
            "inputSchema": {"type": "object"},
        },
    ]
    content = render_router_skill_md("common-skills", tools)
    assert "nodeskclaw-skill-router" in content
    assert "hermes_common_researcher__customer-profiling" in content
    assert "common-skills" in content
    for fragment in FORBIDDEN_CONTENT_FRAGMENTS:
        assert fragment not in content


def test_render_router_skill_md_no_token_leak():
    tools = [{"name": "skill-a", "description": "desc", "inputSchema": {}}]
    content = render_router_skill_md("nodeskclaw-skills", tools)
    assert "ndsk_mcp_" not in content
    assert "Bearer" not in content
