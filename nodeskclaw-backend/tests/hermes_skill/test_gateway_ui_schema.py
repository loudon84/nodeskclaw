import pytest

from app.services.hermes_skill.manifest_parser import ManifestParser
from app.services.hermes_skill.skill_scanner import SkillScanner


def test_gateway_yaml_parses_ui_schema_and_examples():
    content = """
expose_as_mcp: true
tool_name: writer_article_generate
input_schema:
  type: object
  properties:
    requirement:
      type: string
ui_schema:
  requirement:
    widget: textarea
    label: 写作需求
examples:
  - title: 内部文章
    arguments:
      requirement: 写一篇关于企业引入 AI Agent 的内部文章
primary_artifact_policy:
  artifact_type: markdown
  prefer_file_name: article.md
"""
    gateway = ManifestParser.parse_gateway_yaml(content)
    assert gateway.ui_schema["requirement"]["widget"] == "textarea"
    assert gateway.examples[0]["title"] == "内部文章"
    assert gateway.primary_artifact_policy["prefer_file_name"] == "article.md"


def test_skill_scanner_build_extra_metadata():
    from app.services.hermes_skill.manifest_parser import ParsedManifest, ParsedGatewayConfig, ParsedSkillMeta

    manifest = ParsedManifest(
        meta=ParsedSkillMeta(skill_id="writer.article", name="Writer"),
        gateway=ParsedGatewayConfig(
            ui_schema={"requirement": {"widget": "textarea"}},
            examples=[{"title": "demo"}],
            primary_artifact_policy={"artifact_type": "markdown"},
        ),
    )
    extra = SkillScanner._build_extra_metadata(manifest)
    assert extra["ui_schema"]["requirement"]["widget"] == "textarea"
    assert extra["examples"][0]["title"] == "demo"
    assert extra["primary_artifact_policy"]["artifact_type"] == "markdown"


def test_build_mcp_descriptor():
    from app.services.mcp_skill_gateway.constants import build_mcp_descriptor

    descriptor = build_mcp_descriptor()
    assert descriptor["name"] == "Hermes MCP Gateway"
    assert descriptor["healthEndpoint"] == "/api/v1/hermes/mcp/health"
    assert descriptor["approvalCenterPath"] == "/hermes/skill-authorizations"
