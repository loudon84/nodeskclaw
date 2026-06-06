import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.core.exceptions import AppException


class ManifestParseError(AppException):
    def __init__(
        self,
        message: str,
        message_key: str = "errors.skill.manifest_parse_error",
        error_code: int = 50202,
    ):
        super().__init__(
            code=error_code,
            message=message,
            status_code=400,
            message_key=message_key,
            error_code=error_code,
        )


def _validate_json_schema(schema: dict, path: str, label: str) -> None:
    try:
        import jsonschema
        jsonschema.Draft7Validator.check_schema(schema)
    except ImportError:
        pass
    except jsonschema.SchemaError as exc:
        raise ManifestParseError(
            message=f"{label} JSON Schema 不合法: {exc.message} ({path})",
            message_key="errors.skill.json_schema_invalid",
            error_code=50204,
        ) from exc


@dataclass
class ParsedSkillMeta:
    skill_id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    agent_type: str = ""
    runtime: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class ParsedGatewayConfig:
    expose_as_mcp: bool = False
    skill_id: str = ""
    tool_name: str = ""
    title: str = ""
    description: str = ""
    version: str = "1.0.0"
    category: str = ""
    input_schema: dict = field(default_factory=dict)
    output_schema: dict = field(default_factory=dict)
    gateway_runtime: dict = field(default_factory=dict)
    permissions: dict = field(default_factory=dict)
    install_config: dict = field(default_factory=dict)
    allowed_modes: list[str] = field(default_factory=lambda: ["copy"])


@dataclass
class ParsedManifest:
    meta: ParsedSkillMeta = field(default_factory=ParsedSkillMeta)
    gateway: ParsedGatewayConfig = field(default_factory=ParsedGatewayConfig)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)

_SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_VALID_ALLOWED_MODES = {"copy", "symlink", "docker_mount", "registry_bind", "api_deploy"}


class ManifestParser:

    @staticmethod
    def parse_skill_md(content: str, path: str = "") -> ParsedSkillMeta:
        match = _FRONTMATTER_RE.match(content)
        if not match:
            raise ManifestParseError(
                message=f"SKILL.md 缺少 YAML frontmatter: {path}",
                message_key="errors.skill.frontmatter_missing",
                error_code=50202,
            )
        try:
            data = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            raise ManifestParseError(
                message=f"SKILL.md YAML 解析失败: {exc}",
                message_key="errors.skill.yaml_parse_error",
                error_code=50203,
            ) from exc

        if not isinstance(data, dict):
            raise ManifestParseError(
                message=f"SKILL.md frontmatter 不是 YAML 映射: {path}",
                message_key="errors.skill.frontmatter_invalid",
                error_code=50202,
            )

        if not data.get("id"):
            raise ManifestParseError(
                message=f"SKILL.md 缺少必填字段 id: {path}",
                message_key="errors.skill.frontmatter_missing_id",
                error_code=50202,
            )
        if not data.get("name"):
            raise ManifestParseError(
                message=f"SKILL.md 缺少必填字段 name: {path}",
                message_key="errors.skill.frontmatter_missing_name",
                error_code=50202,
            )

        if not _SKILL_ID_RE.match(str(data["id"])):
            raise ManifestParseError(
                message=f"SKILL.md id 格式不合法，需匹配 ^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$ : {path}",
                message_key="errors.skill.skill_id_format_invalid",
                error_code=50202,
            )

        return ParsedSkillMeta(
            skill_id=str(data["id"]),
            name=str(data["name"]),
            description=str(data.get("description", "")),
            version=str(data.get("version", "1.0.0")),
            agent_type=str(data.get("agent_type", "")),
            runtime=str(data.get("runtime", "")),
            tags=data.get("tags", []) or [],
        )

    @staticmethod
    def parse_gateway_yaml(content: str, path: str = "") -> ParsedGatewayConfig:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ManifestParseError(
                message=f"gateway.yaml YAML 解析失败: {exc}",
                message_key="errors.skill.yaml_parse_error",
                error_code=50203,
            ) from exc

        if not isinstance(data, dict):
            data = {}

        allowed_modes = data.get("install", {}).get("allowed_modes", ["copy"])
        invalid_modes = set(allowed_modes) - _VALID_ALLOWED_MODES
        if invalid_modes:
            raise ManifestParseError(
                message=f"gateway.yaml 含非法 allowed_modes: {invalid_modes}",
                message_key="errors.skill.gateway_invalid_mode",
                error_code=50203,
            )

        expose_as_mcp = bool(data.get("expose_as_mcp", False))
        tool_name = str(data.get("tool_name", ""))
        input_schema = data.get("input_schema", {}) or {}

        if expose_as_mcp and not tool_name:
            raise ManifestParseError(
                message=f"gateway.yaml expose_as_mcp=true 但缺少 tool_name: {path}",
                message_key="errors.skill.gateway_mcp_no_tool_name",
                error_code=50203,
            )
        if expose_as_mcp and not input_schema:
            raise ManifestParseError(
                message=f"gateway.yaml expose_as_mcp=true 但缺少 input_schema: {path}",
                message_key="errors.skill.gateway_mcp_no_input_schema",
                error_code=50203,
            )
        if tool_name and not _TOOL_NAME_RE.match(tool_name):
            raise ManifestParseError(
                message=f"gateway.yaml tool_name 格式不合法，需匹配 ^[a-z][a-z0-9_]*$ : {path}",
                message_key="errors.skill.tool_name_format_invalid",
                error_code=50203,
            )

        input_schema_val = data.get("input_schema", {}) or {}
        output_schema_val = data.get("output_schema", {}) or {}
        if input_schema_val:
            _validate_json_schema(input_schema_val, path, "input_schema")
        if output_schema_val:
            _validate_json_schema(output_schema_val, path, "output_schema")

        return ParsedGatewayConfig(
            expose_as_mcp=expose_as_mcp,
            skill_id=str(data.get("skill_id", "")),
            tool_name=str(data.get("tool_name", "")),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            version=str(data.get("version", "1.0.0")),
            category=str(data.get("category", "")),
            input_schema=input_schema_val,
            output_schema=output_schema_val,
            gateway_runtime=data.get("runtime", {}) or {},
            permissions=data.get("permissions", {}) or {},
            install_config=data.get("install", {}) or {},
            allowed_modes=allowed_modes,
        )

    @staticmethod
    def parse_skill_package(skill_dir: Path) -> ParsedManifest:
        skill_md_path = skill_dir / "SKILL.md"
        gateway_yaml_path = skill_dir / "gateway.yaml"

        if not skill_md_path.is_file():
            raise ManifestParseError(
                message=f"目录缺少 SKILL.md: {skill_dir}",
                message_key="errors.skill.skill_md_not_found",
                error_code=50202,
            )

        meta = ManifestParser.parse_skill_md(
            skill_md_path.read_text(encoding="utf-8"),
            path=str(skill_md_path),
        )

        gateway = ParsedGatewayConfig()
        if gateway_yaml_path.is_file():
            gateway = ManifestParser.parse_gateway_yaml(
                gateway_yaml_path.read_text(encoding="utf-8"),
                path=str(gateway_yaml_path),
            )

        if gateway.skill_id and gateway.skill_id != meta.skill_id:
            raise ManifestParseError(
                message=f"gateway.yaml skill_id={gateway.skill_id} 与 SKILL.md id={meta.skill_id} 不一致",
                message_key="errors.skill.skill_id_mismatch",
                error_code=50205,
            )

        return ParsedManifest(meta=meta, gateway=gateway)
