"""Generate and check knowledge-frontend-contract v1.0.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from frontend_contract_spec import (  # noqa: E402
    FIXTURE_SCHEMA,
    MATRIX,
    NEGATIVE_FIXTURES,
    PROVIDER_RUNTIME_ID_KEYS,
    SCHEMAS,
    STABILITY_VALUES,
)

# @lat: [[decisions/knowledge-frontend-contract#Check Gate]]

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = KNOWLEDGE_ROOT / "contracts" / "frontend" / "v1.0.0"
EXCLUDED_FROM_SUMS = frozenset({"SHA256SUMS", "consumer-lock.json"})
SUGGESTED_TAG = "knowledge-frontend-contract-v1.0.0"
SCHEMA_FILE_TO_TITLE = {name: schema["title"] for name, schema in SCHEMAS.items()}
URN_TO_TITLE = {
    f"urn:nodeskclaw:knowledge:frontend:v1:{name}": schema["title"] for name, schema in SCHEMAS.items()
}


def _normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_normalize_lf(text).encode("utf-8"))


def _write_json_lf(path: Path, payload: Any) -> None:
    _write_text_lf(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=KNOWLEDGE_ROOT.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _bundle_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in EXCLUDED_FROM_SUMS
    }


def _rewrite_refs(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str) and item in URN_TO_TITLE:
                out[key] = f"#/components/schemas/{URN_TO_TITLE[item]}"
            else:
                out[key] = _rewrite_refs(item)
        return out
    if isinstance(value, list):
        return [_rewrite_refs(item) for item in value]
    return value


def _component_schema(schema: dict) -> dict:
    body = {key: value for key, value in schema.items() if key not in {"$schema", "$id"}}
    return _rewrite_refs(body)


def _dump_yaml(value: Any, indent: int = 0) -> str:
    prefix = "  " * indent
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if value == "" or any(ch in value for ch in ":#{}[],&*!|>%@`'\"\n") or value in {"true", "false", "null"}:
            return json.dumps(value, ensure_ascii=False)
        return value
    if isinstance(value, list):
        if not value:
            return "[]"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                dumped = _dump_yaml(item, indent + 1)
                if dumped.startswith("\n"):
                    lines.append(f"{prefix}-" + dumped)
                else:
                    first, *rest = dumped.splitlines()
                    lines.append(f"{prefix}- {first}")
                    lines.extend(rest)
            else:
                lines.append(f"{prefix}- {_dump_yaml(item)}")
        return "\n" + "\n".join(lines) if indent else "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = []
        for key, item in value.items():
            dumped = _dump_yaml(item, indent + 1)
            key_text = json.dumps(key) if any(ch in str(key) for ch in ":{}[],&*!#") else str(key)
            if isinstance(item, (dict, list)) and item:
                lines.append(f"{prefix}{key_text}:")
                if dumped.startswith("\n"):
                    lines.append(dumped[1:])
                else:
                    lines.append(dumped)
            else:
                lines.append(f"{prefix}{key_text}: {dumped}")
        return "\n" + "\n".join(lines) if indent else "\n".join(lines)
    return json.dumps(value, ensure_ascii=False)


def _openapi_schema_ref(name: str | None) -> dict | None:
    if not name:
        return None
    title = SCHEMA_FILE_TO_TITLE[name]
    return {"$ref": f"#/components/schemas/{title}"}


def _api_envelope(data_schema: dict | None) -> dict:
    properties = {
        "code": {"type": "integer"},
        "error_code": {"type": ["integer", "null"]},
        "message_key": {"type": ["string", "null"]},
        "message": {"type": "string"},
        "data": data_schema if data_schema is not None else {"type": "null"},
        "details": {"type": "object"},
        "message_params": {"type": "object"},
    }
    return {
        "type": "object",
        "required": ["code", "message", "data"],
        "properties": properties,
        "additionalProperties": False,
    }


def _error_responses() -> dict:
    error_ref = {"$ref": "#/components/schemas/ErrorResponse"}
    return {
        "400": {"description": "Bad request", "content": {"application/json": {"schema": error_ref}}},
        "401": {"description": "Unauthorized", "content": {"application/json": {"schema": error_ref}}},
        "403": {"description": "Forbidden", "content": {"application/json": {"schema": error_ref}}},
        "404": {"description": "Not found", "content": {"application/json": {"schema": error_ref}}},
        "409": {"description": "Conflict", "content": {"application/json": {"schema": error_ref}}},
        "503": {"description": "Unavailable", "content": {"application/json": {"schema": error_ref}}},
    }


def _paged_list_ids() -> set[str]:
    return {"KB01", "F01", "S01", "A01", "R01"}


def _list_ids() -> set[str]:
    return {"KB06", "F04", "F11", "P01", "A08", "R06", "O03"}


def build_openapi() -> dict:
    paths: dict[str, dict] = {}
    for item in MATRIX:
        path_item = paths.setdefault(item["path"], {})
        operation: dict[str, Any] = {
            "operationId": item["id"],
            "summary": f"{item['method']} {item['path']}",
            "tags": [item["surface"]],
            "x-stability": item["stability"],
        }
        if item.get("feature"):
            operation["x-feature"] = item["feature"]
        if item.get("notes"):
            operation["description"] = item["notes"]
        if not item.get("auth"):
            operation["security"] = []
        if item.get("request"):
            if item.get("content_type") == "multipart/form-data":
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "multipart/form-data": {
                            "schema": {
                                "type": "object",
                                "required": ["file"],
                                "properties": {
                                    "file": {"type": "string", "format": "binary"},
                                    "metadata": {"type": "string", "description": "JSON object serialized as string"},
                                },
                            }
                        }
                    },
                }
            else:
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {"schema": _openapi_schema_ref(item["request"])},
                    },
                }
        success = str(item["success_status"])
        envelope = item.get("envelope", "api")
        if envelope == "raw":
            success_schema = _openapi_schema_ref(item["response"])
            content = {"application/json": {"schema": success_schema}}
        elif envelope == "binary":
            content = {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}
        else:
            data_schema = _openapi_schema_ref(item["response"])
            if item["id"] in _paged_list_ids() and data_schema is not None:
                data_schema = {
                    "allOf": [
                        {"$ref": "#/components/schemas/PageData"},
                        {
                            "type": "object",
                            "properties": {"items": {"type": "array", "items": data_schema}},
                        },
                    ]
                }
            elif item["id"] in _list_ids() and data_schema is not None:
                data_schema = {"type": "array", "items": data_schema}
            content = {"application/json": {"schema": _api_envelope(data_schema)}}
        responses = {
            success: {
                "description": "Success" if item["success_status"] < 300 else "Accepted",
                "content": content,
            }
        }
        if envelope != "raw":
            responses.update(_error_responses())
        elif item["id"] == "H01":
            responses["503"] = {
                "description": "Not ready",
                "content": {"application/json": {"schema": _openapi_schema_ref("health-ready")}},
            }
        operation["responses"] = responses
        path_item[item["method"].lower()] = operation

    components_schemas = {schema["title"]: _component_schema(schema) for schema in SCHEMAS.values()}
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "NodeSKClaw Knowledge Frontend Contract",
            "version": "1.0.0",
            "description": "Curated frontend-facing API surface. Contract version is independent from HTTP /api/v1 and /api/v2 path versions.",
        },
        "servers": [
            {
                "url": "{knowledgeBaseUrl}",
                "variables": {"knowledgeBaseUrl": {"default": "http://127.0.0.1:4530"}},
            }
        ],
        "security": [{"bearerAuth": []}],
        "components": {
            "securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer"}},
            "schemas": components_schemas,
        },
        "paths": paths,
    }


def _ts_type(schema: Any) -> str:
    if schema is True:
        return "unknown"
    if not isinstance(schema, dict):
        return "unknown"
    if "$ref" in schema:
        return URN_TO_TITLE.get(schema["$ref"], "unknown")
    if "enum" in schema:
        return " | ".join(json.dumps(item) for item in schema["enum"])
    types = schema.get("type")
    if isinstance(types, list):
        parts = []
        for item in types:
            if item == "null":
                parts.append("null")
            elif item == "array":
                parts.append(f"{_ts_type(schema.get('items', True))}[]")
            else:
                cloned = dict(schema)
                cloned["type"] = item
                parts.append(_ts_type(cloned))
        return " | ".join(dict.fromkeys(parts))
    if types == "array":
        return f"{_ts_type(schema.get('items', True))}[]"
    if types == "object" or "properties" in schema:
        props = schema.get("properties")
        if props:
            required = set(schema.get("required") or [])
            fields = []
            for key, prop in props.items():
                optional = "?" if key not in required else ""
                fields.append(f"{key}{optional}: {_ts_type(prop)}")
            extra = schema.get("additionalProperties")
            if extra is True:
                fields.append("[key: string]: unknown")
            return "{ " + "; ".join(fields) + " }"
        if schema.get("additionalProperties") is True:
            return "Record<string, unknown>"
        if isinstance(schema.get("additionalProperties"), dict):
            return f"Record<string, {_ts_type(schema['additionalProperties'])}>"
        return "Record<string, unknown>"
    if types == "string":
        return "string"
    if types in {"integer", "number"}:
        return "number"
    if types == "boolean":
        return "boolean"
    if types == "null":
        return "null"
    return "unknown"


def _ts_interface(name: str, schema: dict) -> str:
    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    lines = [f"export interface {schema['title']} {{"]
    for key, prop in properties.items():
        optional = "?" if key not in required else ""
        lines.append(f"  {key}{optional}: {_ts_type(prop)};")
    extra = schema.get("additionalProperties")
    if extra is True:
        lines.append("  [key: string]: unknown;")
    elif isinstance(extra, dict):
        lines.append(f"  [key: string]: {_ts_type(extra)};")
    lines.append("}")
    return "\n".join(lines)


def build_typescript() -> str:
    chunks = [
        "// knowledge-frontend-contract v1.0.0",
        "// Generated from scripts/frontend_contract_spec.py. Do not edit by hand.",
        "",
        "export type ApiResponse<T> = {",
        "  code: number;",
        "  error_code?: number | null;",
        "  message_key?: string | null;",
        "  message: string;",
        "  data: T | null;",
        "  details?: Record<string, unknown>;",
        "  message_params?: Record<string, string>;",
        "};",
        "",
        "export type PageData<T> = {",
        "  items: T[];",
        "  total: number;",
        "  page: number;",
        "  page_size: number;",
        "};",
        "",
    ]
    skip = {"api-response", "page-data"}
    for name, schema in SCHEMAS.items():
        if name in skip:
            continue
        chunks.append(_ts_interface(name, schema))
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def _checksum_lines(root: Path) -> list[str]:
    files = sorted(_bundle_files(root))
    return [f"{_sha256_file(root / relative)}  {relative}" for relative in files]


def build_manifest(head: str) -> dict:
    return {
        "schema": "nodeskclaw.knowledge.frontend-contract.v1",
        "name": "knowledge-frontend-contract",
        "version": "1.0.0",
        "suggested_tag": SUGGESTED_TAG,
        "source": {
            "repository": "loudon84/nodeskclaw",
            "branch": "feat/knowledge-v2.0",
            "commit": head,
            "runtime": "RAGFlow v0.27.0",
        },
        "auth": {
            "type": "bearer",
            "issuer": "nodeskclaw-backend",
            "knowledge_login_endpoint": None,
            "rule": "reuse opaque backend bearer token",
        },
        "api_roots": ["/api/v2", "/api/v1"],
        "identity": {
            "public": [
                "knowledge_base_id",
                "knowledge_set_id",
                "source_file_id",
                "file_version_id",
                "application_id",
                "release_id",
                "evidence_id",
                "artifact_id",
            ],
            "provider_runtime_ids_public": False,
            "forbidden_keys": list(PROVIDER_RUNTIME_ID_KEYS),
        },
        "compatibility_policy": {
            "major_breaking_rule": "removing/renaming stable or stable-compat endpoints or stable fields requires v2.0.0",
            "minor_rule": "additive optional fields/endpoints allowed",
            "unknown_enum_rule": "frontend must render unknown enum values safely",
            "stable_compat": "semantically frozen on /api/v1; path may move to /api/v2 only with an overlap window",
        },
        "endpoint_count": len(MATRIX),
        "generated_at": "2026-09-13T07:10:00+00:00",
        "artifacts": {},
    }


def generate() -> None:
    root = CONTRACT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    (root / "schemas").mkdir(exist_ok=True)
    (root / "http").mkdir(exist_ok=True)
    (root / "typescript").mkdir(exist_ok=True)
    (root / "fixtures").mkdir(exist_ok=True)

    for name, schema in SCHEMAS.items():
        _write_json_lf(root / "schemas" / f"{name}.schema.json", schema)

    _write_json_lf(
        root / "http" / "endpoint-matrix.json",
        {
            "schema": "knowledge.frontend.endpoint-matrix.v1",
            "version": "1.0.0",
            "endpoint_count": len(MATRIX),
            "stability_values": list(STABILITY_VALUES),
            "endpoints": MATRIX,
        },
    )
    openapi = build_openapi()
    yaml_text = _dump_yaml(openapi)
    if not yaml_text.endswith("\n"):
        yaml_text += "\n"
    _write_text_lf(root / "openapi.frontend.yaml", yaml_text)
    _write_text_lf(root / "typescript" / "knowledge-contract.ts", build_typescript())

    head = _git_head()
    manifest = build_manifest(head)
    _write_json_lf(root / "manifest.json", manifest)
    sums = _checksum_lines(root)
    artifacts = {}
    for line in sums:
        digest, relative = line.split("  ", 1)
        artifacts[relative] = digest
    manifest["artifacts"] = artifacts
    _write_json_lf(root / "manifest.json", manifest)
    sums = _checksum_lines(root)
    _write_text_lf(root / "SHA256SUMS", "\n".join(sums) + "\n")
    print(f"generated {root} endpoints={len(MATRIX)} files={len(sums)}")


def _parse_sha256sums(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if "\r" in text:
        raise SystemExit(f"SHA256SUMS must be LF-only: {path}")
    listed: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        listed[relative] = digest
    return listed


def _collect_property_names(value: Any, acc: set[str]) -> None:
    if isinstance(value, dict):
        props = value.get("properties")
        if isinstance(props, dict):
            acc.update(props.keys())
        for item in value.values():
            _collect_property_names(item, acc)
    elif isinstance(value, list):
        for item in value:
            _collect_property_names(item, acc)


def _collect_json_keys(value: Any, acc: set[str]) -> None:
    if isinstance(value, dict):
        acc.update(value.keys())
        for item in value.values():
            _collect_json_keys(item, acc)
    elif isinstance(value, list):
        for item in value:
            _collect_json_keys(item, acc)


def _registry():
    try:
        from referencing import Registry, Resource
    except ImportError as exc:
        raise SystemExit(f"jsonschema/referencing required: {exc}") from exc

    registry = Registry()
    for schema in SCHEMAS.values():
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return registry


def _validate_schema(schema: dict, payload: Any) -> None:
    from jsonschema import Draft202012Validator

    Draft202012Validator(schema, registry=_registry()).validate(payload)


def check_contract() -> None:
    root = CONTRACT_ROOT
    if not root.exists():
        raise SystemExit(f"Contract directory missing: {root}")
    required = [
        "README.md",
        "RELEASE.md",
        "FRONTEND-INTEGRATION.md",
        "STATE-MACHINES.md",
        "manifest.json",
        "SHA256SUMS",
        "openapi.frontend.yaml",
        "http/endpoint-matrix.json",
        "typescript/knowledge-contract.ts",
    ]
    missing = [name for name in required if not (root / name).exists()]
    if missing:
        raise SystemExit(f"missing required files: {missing}")

    checksum_path = root / "SHA256SUMS"
    listed = _parse_sha256sums(checksum_path)
    disk = _bundle_files(root)
    if "manifest.json" not in listed:
        raise SystemExit("SHA256SUMS must include manifest.json")
    if set(listed) != disk:
        raise SystemExit(
            "SHA256SUMS closure mismatch: "
            f"missing={sorted(disk - set(listed))} extra={sorted(set(listed) - disk)}"
        )
    for relative, digest in listed.items():
        actual = _sha256_file(root / relative)
        if actual != digest:
            raise SystemExit(f"SHA256SUMS mismatch: {relative}")

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("endpoint_count") != len(MATRIX):
        raise SystemExit("manifest.endpoint_count does not match matrix")
    if manifest.get("suggested_tag") != SUGGESTED_TAG:
        raise SystemExit("manifest.suggested_tag mismatch")
    artifacts = manifest.get("artifacts") or {}
    for relative, digest in listed.items():
        if relative == "manifest.json":
            continue
        if artifacts.get(relative) != digest:
            raise SystemExit(f"manifest.artifacts mismatch: {relative}")

    matrix_file = json.loads((root / "http" / "endpoint-matrix.json").read_text(encoding="utf-8"))
    if matrix_file.get("endpoints") != MATRIX:
        raise SystemExit("endpoint-matrix.json drift; run generate")
    ids = [item["id"] for item in MATRIX]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate endpoint ids")
    for item in MATRIX:
        if item["stability"] not in STABILITY_VALUES:
            raise SystemExit(f"unknown stability: {item['id']} {item['stability']}")
        if item.get("request") and item["request"] not in SCHEMAS:
            raise SystemExit(f"unknown request schema: {item['id']}")
        if item.get("response") and item["response"] not in SCHEMAS:
            raise SystemExit(f"unknown response schema: {item['id']}")

    generated_openapi = _normalize_lf(_dump_yaml(build_openapi()) + "\n")
    committed_openapi = _normalize_lf((root / "openapi.frontend.yaml").read_text(encoding="utf-8"))
    if generated_openapi != committed_openapi:
        raise SystemExit("openapi.frontend.yaml drift; run generate")
    generated_ts = build_typescript()
    committed_ts = (root / "typescript" / "knowledge-contract.ts").read_text(encoding="utf-8").replace("\r\n", "\n")
    if generated_ts != committed_ts:
        raise SystemExit("typescript/knowledge-contract.ts drift; run generate")

    property_names: set[str] = set()
    public_schema_names = (
        "knowledge-base",
        "knowledge-set",
        "source-file",
        "ingestion-job",
        "evidence-item",
        "retrieval-response",
        "evidence",
        "application",
        "release",
    )
    for name in public_schema_names:
        schema = SCHEMAS[name]
        if schema.get("additionalProperties") is not False and name not in {"retrieval-response"}:
            if name != "application-readiness":
                pass
        _collect_property_names(schema, property_names)
        if schema.get("additionalProperties") is not False and name in {
            "knowledge-base",
            "source-file",
            "ingestion-job",
            "evidence-item",
            "evidence",
        }:
            raise SystemExit(f"{name} must set additionalProperties false")
    leaked = set(PROVIDER_RUNTIME_ID_KEYS) & property_names
    if leaked:
        raise SystemExit(f"provider runtime ids declared in public schemas: {sorted(leaked)}")

    for filename, target in FIXTURE_SCHEMA.items():
        payload = json.loads((root / "fixtures" / filename).read_text(encoding="utf-8"))
        keys: set[str] = set()
        _collect_json_keys(payload, keys)
        if set(PROVIDER_RUNTIME_ID_KEYS) & keys:
            raise SystemExit(f"fixture contains provider runtime ids: {filename}")
        if isinstance(target, tuple):
            _validate_schema(SCHEMAS[target[0]], payload)
            _validate_schema(SCHEMAS[target[1]], payload.get("data"))
        else:
            _validate_schema(SCHEMAS[target], payload)

    from jsonschema.exceptions import ValidationError

    for filename, schema_name in NEGATIVE_FIXTURES.items():
        payload = json.loads((root / "fixtures" / filename).read_text(encoding="utf-8"))
        try:
            _validate_schema(SCHEMAS[schema_name], payload)
        except ValidationError:
            continue
        raise SystemExit(f"{filename} unexpectedly passed {schema_name}")

    print("knowledge-frontend-contract v1.0.0 check passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "check"])
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if args.command == "generate":
        generate()
        check_contract()
        return
    check_contract()


if __name__ == "__main__":
    main()
