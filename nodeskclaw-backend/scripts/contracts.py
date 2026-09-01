#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_HOME = BACKEND_ROOT / "contracts" / "work-expert"
SKILL_RUN_CONTRACTS_HOME = BACKEND_ROOT / "contracts" / "skill-run"

P0_TEST_FILES = [
    "tests/expert_gateway/test_mcp_capability_token.py",
    "tests/expert_gateway/test_invocation_idempotency.py",
    "tests/hermes_skill/test_task_owner_policy.py",
    "tests/hermes_skill/test_cancel_safe_api_server.py",
    "tests/hermes_skill/test_retry_copies_routing_contract.py",
    "tests/hermes_skill/test_duplicate_completion.py",
    "tests/hermes_skill/test_result_content_separation.py",
    "tests/hermes_skill/test_progress_stages_minimum.py",
    "tests/contracts/test_contracts_check.py",
    "tests/contracts/test_openapi_response_schemas.py",
    "tests/contracts/test_mcp_tools_list_annotations.py",
]


def contract_root(version: str | None = None) -> Path:
    if version:
        return CONTRACTS_HOME / f"v{version}"
    try:
        from app.contracts.work_expert.constants import WORK_EXPERT_CONTRACT_VERSION

        return CONTRACTS_HOME / f"v{WORK_EXPERT_CONTRACT_VERSION}"
    except ImportError:
        return CONTRACTS_HOME / "v1.0.2"


CONTRACT_ROOT = CONTRACTS_HOME / "v1.0.2"


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=BACKEND_ROOT.parent,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_empty_json_schema(schema) -> bool:
    if schema is None:
        return True
    if schema == {}:
        return True
    if not isinstance(schema, dict):
        return False
    if schema.get("$ref") or schema.get("type") or schema.get("properties"):
        return False
    if schema.get("oneOf") or schema.get("anyOf") or schema.get("allOf") or schema.get("items"):
        return False
    return True


def _collect_refs(node, acc: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            acc.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            _collect_refs(value, acc)
    elif isinstance(node, list):
        for value in node:
            _collect_refs(value, acc)


def _prune_openapi_components(openapi: dict) -> dict:
    schemas = (openapi.get("components") or {}).get("schemas") or {}
    needed: set[str] = set()
    _collect_refs(openapi.get("paths"), needed)
    changed = True
    while changed:
        changed = False
        for name in list(needed):
            schema = schemas.get(name)
            if not schema:
                continue
            before = len(needed)
            _collect_refs(schema, needed)
            if len(needed) > before:
                changed = True
    openapi["components"] = {
        "schemas": {name: schemas[name] for name in sorted(needed) if name in schemas}
    }
    return openapi


def _strip_empty_200_json_when_other_media(openapi: dict) -> dict:
    for path_item in (openapi.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            content = (
                operation.get("responses", {})
                .get("200", {})
                .get("content")
            )
            if not isinstance(content, dict):
                continue
            json_body = content.get("application/json")
            if json_body and is_empty_json_schema(json_body.get("schema")):
                if any(media != "application/json" for media in content):
                    content.pop("application/json", None)
    return openapi


def assert_non_empty_200_schemas(openapi: dict, paths: list[str]) -> None:
    empty: list[str] = []
    for path in paths:
        path_item = openapi.get("paths", {}).get(path) or {}
        for method, operation in path_item.items():
            if method.startswith("x-") or not isinstance(operation, dict):
                continue
            content = operation.get("responses", {}).get("200", {}).get("content") or {}
            if not content:
                empty.append(f"{method.upper()} {path} missing 200 content")
                continue
            for media, body in content.items():
                if is_empty_json_schema((body or {}).get("schema")):
                    empty.append(f"{method.upper()} {path} {media}")
    if empty:
        raise SystemExit("Empty OpenAPI 200 response schema: " + "; ".join(empty))


def _load_openapi_subset() -> dict:
    from app.contracts.work_expert.constants import (
        WORK_EXPERT_CONTRACT_VERSION,
        WORK_EXPERT_OPENAPI_PATHS,
    )
    from app.main import app

    full = app.openapi()
    filtered_paths = {
        path: full["paths"][path]
        for path in WORK_EXPERT_OPENAPI_PATHS
        if path in full.get("paths", {})
    }
    missing = [path for path in WORK_EXPERT_OPENAPI_PATHS if path not in full.get("paths", {})]
    if missing:
        raise SystemExit(f"OpenAPI missing contract paths: {missing}")
    openapi = {
        "openapi": full.get("openapi", "3.1.0"),
        "info": {
            "title": "WORK-EXPERT-CONTRACT",
            "version": WORK_EXPERT_CONTRACT_VERSION,
        },
        "paths": filtered_paths,
        "components": full.get("components", {}),
    }
    openapi = _prune_openapi_components(openapi)
    openapi = _strip_empty_200_json_when_other_media(openapi)
    assert_non_empty_200_schemas(openapi, WORK_EXPERT_OPENAPI_PATHS)
    return openapi


def _model_schema(model) -> dict:
    return model.model_json_schema(mode="serialization")


def _run_event_v12_union_schema(models: tuple) -> dict:
    """Build oneOf schema with $defs hoisted to root so #/$defs refs resolve."""
    one_of: list[dict] = []
    all_defs: dict = {}
    for model in models:
        schema = _model_schema(model)
        defs = schema.pop("$defs", {}) or {}
        all_defs.update(defs)
        one_of.append({"title": model.__name__, **schema})
    result: dict = {"title": "RunEvent", "oneOf": one_of}
    if all_defs:
        result["$defs"] = all_defs
    return result


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


SKILL_RUN_PUBLIC_ARTIFACT_PATTERNS = (
    "RELEASE.md",
    "events/*.schema.json",
    "mcp/*.schema.json",
    "runs/*.schema.json",
    "http/*.json",
    "capabilities/*.json",
    "fixtures/*",
)

SKILL_RUN_INTERNAL_RELATIVE_PREFIXES = (
    "edge/",
    "installations/",
)
SKILL_RUN_INTERNAL_RELATIVE_FILES = frozenset({"runs/execution-snapshot.schema.json"})


def _normalize_lf(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_normalize_lf(text).encode("utf-8"))


def _write_json_lf(path: Path, payload: Any) -> None:
    _write_text_lf(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _skill_run_generated_at() -> str:
    import os

    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
    override = os.environ.get("CONTRACT_GENERATED_AT")
    if override:
        return override
    return datetime.now(timezone.utc).isoformat()


def _is_frozen_skill_run_version(version: str) -> bool:
    root = SKILL_RUN_CONTRACTS_HOME / f"v{version}"
    return root.exists() and (root / "SHA256SUMS").exists()


def _parse_sha256sums(checksum_path: Path) -> dict[str, str]:
    return _parse_sha256sums_from_text(checksum_path.read_text(encoding="utf-8"))


def _parse_sha256sums_from_text(text: str) -> dict[str, str]:
    listed: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        listed[relative] = digest
    return listed


def _bundle_files_excluding_checksum(root: Path) -> set[str]:
    excluded = {"SHA256SUMS", "consumer-lock.json"}
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name not in excluded
    }


def _validate_skill_run_public_boundary(root: Path) -> None:
    for relative in _bundle_files_excluding_checksum(root):
        if relative in SKILL_RUN_INTERNAL_RELATIVE_FILES:
            raise SystemExit(f"Internal Southbound artifact in Public bundle: {relative}")
        if any(relative.startswith(prefix) for prefix in SKILL_RUN_INTERNAL_RELATIVE_PREFIXES):
            raise SystemExit(f"Internal Southbound artifact in Public bundle: {relative}")


def _validate_skill_run_checksums_exact(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    if not checksum_path.exists():
        raise SystemExit(f"SHA256SUMS missing: {root}")
    raw_bytes = checksum_path.read_bytes()
    if b"\r" in raw_bytes:
        raise SystemExit(f"SHA256SUMS must be LF-only: {checksum_path}")
    raw = raw_bytes.decode("utf-8")
    listed = _parse_sha256sums_from_text(raw)
    if "manifest.json" not in listed:
        raise SystemExit("SHA256SUMS must include manifest.json")
    if "SHA256SUMS" in listed or "consumer-lock.json" in listed:
        raise SystemExit("SHA256SUMS must not list itself or consumer-lock.json")
    actual = _bundle_files_excluding_checksum(root)
    if set(listed) != actual:
        missing = sorted(actual - set(listed))
        extra = sorted(set(listed) - actual)
        details: list[str] = []
        if missing:
            details.append(f"missing from SHA256SUMS: {missing}")
        if extra:
            details.append(f"extra in SHA256SUMS: {extra}")
        raise SystemExit("SHA256SUMS closure mismatch: " + "; ".join(details))
    for relative, digest in listed.items():
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"SHA256SUMS lists missing file: {relative}")
        actual_digest = _sha256_file(path)
        if actual_digest != digest:
            raise SystemExit(f"SHA256 mismatch for {relative}")
    manifest = _read_manifest(root)
    artifacts = manifest.get("artifacts") or {}
    for relative, digest in artifacts.items():
        if relative == "manifest.json":
            continue
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"manifest.artifacts lists missing file: {relative}")
        if _sha256_file(path) != digest:
            raise SystemExit(f"manifest hash mismatch for {relative}")
        if listed.get(relative) != digest:
            raise SystemExit(f"SHA256SUMS/manifest disagree on {relative}")


def _artifact_files(root: Path) -> list[Path]:
    patterns = [
        "openapi.yaml",
        "RELEASE.md",
        "events/*.schema.json",
        "mcp/*.schema.json",
        "runs/*.schema.json",
        "http/*.json",
        "capabilities/*.json",
        "edge/*.schema.json",
        "installations/*.schema.json",
        "fixtures/*",
        "evidence/*",
    ]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(root.glob(pattern)))
    return [path for path in files if path.is_file()]


def _public_artifact_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in SKILL_RUN_PUBLIC_ARTIFACT_PATTERNS:
        files.extend(sorted(root.glob(pattern)))
    return [path for path in files if path.is_file()]


def _build_manifest(file_hashes: dict[str, str], backend_commit: str) -> dict:
    from app.contracts.work_expert.constants import (
        WORK_EXPERT_CAPABILITIES,
        WORK_EXPERT_CONTRACT_NAME,
        WORK_EXPERT_CONTRACT_VERSION,
        WORK_EXPERT_TAG_NAME,
    )

    return {
        "contractName": WORK_EXPERT_CONTRACT_NAME,
        "contractVersion": WORK_EXPERT_CONTRACT_VERSION,
        "provider": "nodeskclaw-backend",
        "consumer": "smc-copilot/apps/work",
        "backendCommit": backend_commit,
        "tagName": WORK_EXPERT_TAG_NAME,
        "tagTargetCommit": None,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "openapiVersion": "3.1.0",
        "eventSchemaVersion": "1.0.0",
        "artifacts": file_hashes,
        "capabilities": dict(WORK_EXPERT_CAPABILITIES),
        "queueLimits": {
            "orgMaxQueued": 1000,
            "userMaxRunning": 3,
            "skillMaxRunning": 10,
            "agentMaxRunningDefault": 5,
            "workerBatchSize": 5,
            "workerSequential": True,
            "loadGate": WORK_EXPERT_CAPABILITIES["loadGate"],
        },
    }


def _fixture_payloads() -> dict[str, dict | list | str]:
    return {
        "fixtures/catalog-tools-list.json": {
            "jsonrpc": "2.0",
            "id": "list-root",
            "result": {
                "tools": [
                    {
                        "name": "call-prep",
                        "description": "Customer research expert",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {
                            "kind": "expert",
                            "slug": "call-prep",
                            "displayName": "客户调研专家",
                            "status": "ready",
                            "publicSkillCount": 3,
                            "callableSkillCount": 2,
                        },
                    }
                ]
            },
        },
        "fixtures/skill-tools-list.json": {
            "jsonrpc": "2.0",
            "id": "list-skill",
            "result": {
                "tools": [
                    {
                        "name": "customer-profiling",
                        "description": "Profile a customer",
                        "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}},
                        "annotations": {
                            "displayName": "客户画像",
                            "status": "ready",
                            "callEnabled": True,
                            "riskLevel": "low",
                            "approvalMode": "none",
                        },
                    }
                ]
            },
        },
        "fixtures/catalog-tools-list-missing-display-name.json": {
            "jsonrpc": "2.0",
            "id": "list-root-no-display",
            "result": {
                "tools": [
                    {
                        "name": "call-prep",
                        "description": "Customer research expert",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {
                            "kind": "expert",
                            "slug": "call-prep",
                            "status": "offline",
                            "publicSkillCount": 1,
                            "callableSkillCount": 0,
                        },
                    }
                ]
            },
        },
        "fixtures/skill-tools-list-call-disabled.json": {
            "jsonrpc": "2.0",
            "id": "list-skill-disabled",
            "result": {
                "tools": [
                    {
                        "name": "restricted-skill",
                        "description": "Requires approval",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {
                            "status": "ready",
                            "callEnabled": False,
                            "riskLevel": "high",
                            "approvalMode": "approval_required",
                        },
                    }
                ]
            },
        },
        "fixtures/invalid-tool-annotations.json": {
            "jsonrpc": "2.0",
            "id": "list-invalid",
            "result": {
                "tools": [
                    {
                        "name": "call-prep",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {
                            "kind": "expert",
                            "slug": "call-prep",
                            "status": "ready",
                            "publicSkillCount": -1,
                            "callableSkillCount": 0,
                        },
                    }
                ]
            },
        },
        "fixtures/tools-call-accepted.json": {
            "jsonrpc": "2.0",
            "id": "call-1",
            "result": {
                "content": [{"type": "text", "text": "任务已启动，正在由专家执行。"}],
                "structuredContent": {
                    "committed": True,
                    "task_id": "task-00000000-0000-4000-8000-000000000001",
                    "task_no": "TASK-org1-abcd1234",
                    "status": "running",
                    "event_stream": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/events?token=sse_test",
                    "event_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/events",
                    "event_token_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/events-token",
                    "result_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/result",
                    "artifact_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/artifacts",
                    "wait_strategy": {
                        "type": "sse",
                        "fallback": "poll",
                        "poll_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001",
                        "poll_tool": "nodeskclaw_task_wait",
                        "result_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/result",
                    },
                    "catalog_slug": "call-prep",
                    "skill_name": "customer-profiling",
                    "invocation_id": "invocation-1",
                },
                "isError": False,
            },
        },
        "fixtures/task-snapshot-running.json": {
            "code": 0,
            "message": "success",
            "data": {
                "task": {"id": "task-1", "status": "running"},
                "status": "running",
                "timeline": [],
                "result": {"ready": False, "summary": None, "result_content": None, "content": None},
                "artifacts": {"ready": False, "items": [], "server_artifacts": []},
                "links": {
                    "event_stream": "/api/v1/hermes/tasks/task-1/events",
                    "result_url": "/api/v1/hermes/tasks/task-1/result",
                    "artifact_url": "/api/v1/hermes/tasks/task-1/artifacts",
                },
                "last_events": [],
            },
        },
        "fixtures/task-result-completed.json": {
            "code": 0,
            "message": "success",
            "data": {
                "ready": True,
                "status": "completed",
                "task_id": "task-1",
                "task_no": "TASK-org1-abcd1234",
                "result_summary": "short summary",
                "result_content": "full result body that is longer than summary",
                "content": "full result body that is longer than summary",
            },
        },
        "fixtures/task-artifacts.json": {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": "artifact-1",
                    "org_id": "org-1",
                    "task_id": "task-1",
                    "created_by": "user-1",
                    "file_name": "article.md",
                    "file_path": "article.md",
                    "content_type": "text/markdown",
                    "size_bytes": 128,
                    "sha256": "abc123",
                    "preview_url": "/api/v1/hermes/artifacts/artifact-1/preview",
                    "download_url": "/api/v1/hermes/artifacts/artifact-1/download",
                }
            ],
            "server_artifacts": [],
            "artifact_mode": "pull_only",
        },
        "fixtures/http-task-get.json": {
            "code": 0,
            "message": "success",
            "data": {
                "id": "task-1",
                "org_id": "org-1",
                "task_no": "TASK-org1-abcd1234",
                "status": "running",
            },
        },
        "fixtures/http-events-token.json": {
            "code": 0,
            "message": "success",
            "data": {
                "event_url": "/api/v1/hermes/tasks/task-1/events?token=sse_test",
                "expires_in": 300,
                "expires_at": "2026-08-23T03:00:00+00:00",
            },
        },
        "fixtures/http-artifact-preview.json": {
            "code": 0,
            "message": "success",
            "data": {
                "artifact_id": "artifact-1",
                "org_id": "org-1",
                "task_id": "task-1",
                "created_by": "user-1",
                "file_name": "article.md",
                "content_type": "text/markdown",
                "preview_type": "text",
                "content": "# draft",
                "truncated": False,
                "size_bytes": 8,
                "sha256": "abc123",
                "preview_url": "/api/v1/hermes/artifacts/artifact-1/preview",
                "download_url": "/api/v1/hermes/artifacts/artifact-1/download",
            },
        },
        "fixtures/http-error-owner-forbidden.json": {
            "code": 40300,
            "error_code": 40300,
            "message_key": "errors.task.owner_forbidden",
            "message": "无权访问该任务",
            "data": None,
        },
        "fixtures/http-error-not-found.json": {
            "code": 40400,
            "error_code": 40400,
            "message_key": "errors.task.not_found",
            "message": "任务不存在",
            "data": None,
        },
        "fixtures/http-error-cannot-cancel.json": {
            "code": 40000,
            "error_code": 40000,
            "message_key": "errors.task.cannot_cancel",
            "message": "当前任务状态不可取消",
            "data": None,
        },
        "fixtures/json-rpc-error.json": {
            "jsonrpc": "2.0",
            "id": "err-1",
            "error": {
                "code": -32022,
                "message": "Permission denied",
                "data": {"errorCode": "EXPERT_PERMISSION_DENIED"},
            },
        },
    }


def generate_contracts() -> None:
    from app.schemas.hermes_skill.sse_events import (
        TaskArtifactReadyEvent,
        TaskCompletedEvent,
        TaskEventEnvelope,
        TaskFailedEvent,
        TaskProgressEvent,
        TaskStartedEvent,
        TaskTimelineEvent,
    )
    from app.schemas.work_expert.mcp_jsonrpc import (
        CatalogToolAnnotations,
        JsonRpcErrorResponse,
        JsonRpcRequest,
        SkillToolAnnotations,
        ToolsCallAcceptedResult,
        ToolsListResult,
    )

    root = contract_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "events").mkdir(exist_ok=True)
    (root / "mcp").mkdir(exist_ok=True)
    (root / "fixtures").mkdir(exist_ok=True)
    (root / "evidence").mkdir(exist_ok=True)

    openapi = _load_openapi_subset()
    (root / "openapi.yaml").write_text(
        yaml.safe_dump(openapi, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    event_models = {
        "task-event.schema.json": TaskEventEnvelope,
        "task-started.schema.json": TaskStartedEvent,
        "task-progress.schema.json": TaskProgressEvent,
        "task-timeline.schema.json": TaskTimelineEvent,
        "task-artifact-ready.schema.json": TaskArtifactReadyEvent,
        "task-completed.schema.json": TaskCompletedEvent,
        "task-failed.schema.json": TaskFailedEvent,
    }
    for filename, model in event_models.items():
        _write_json(root / "events" / filename, _model_schema(model))

    mcp_models = {
        "tools-list.request.schema.json": JsonRpcRequest,
        "tools-list.response.schema.json": ToolsListResult,
        "catalog-tool-annotations.schema.json": CatalogToolAnnotations,
        "skill-tool-annotations.schema.json": SkillToolAnnotations,
        "tools-call.request.schema.json": JsonRpcRequest,
        "tools-call.response.schema.json": ToolsCallAcceptedResult,
        "json-rpc-error.schema.json": JsonRpcErrorResponse,
    }
    for filename, model in mcp_models.items():
        _write_json(root / "mcp" / filename, _model_schema(model))

    for relative_path, payload in _fixture_payloads().items():
        target = root / relative_path
        _write_json(target, payload)

    evidence_src = CONTRACTS_HOME / "v1.0.1" / "evidence" / "load-test-20-runs.json"
    evidence_dst = root / "evidence" / "load-test-20-runs.json"
    if evidence_src.is_file():
        evidence_dst.write_bytes(evidence_src.read_bytes())

    sse_replay = "\n".join(
        [
            json.dumps(
                {
                    "event": "task.started",
                    "task_id": "task-1",
                    "timestamp": "2026-08-23T02:00:00+00:00",
                    "event_type": "task.started",
                    "event_seq": 2,
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "event": "task.progress",
                    "task_id": "task-1",
                    "timestamp": "2026-08-23T02:00:01+00:00",
                    "event_type": "hermes.run.delta",
                    "event_seq": 3,
                    "stage": "preparing",
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "event": "task.completed",
                    "task_id": "task-1",
                    "timestamp": "2026-08-23T02:00:10+00:00",
                    "event_type": "task.completed",
                    "event_seq": 10,
                    "result": {"summary": "done", "content": "full body"},
                },
                ensure_ascii=False,
            ),
        ]
    ) + "\n"
    (root / "fixtures" / "sse-replay.ndjson").write_text(sse_replay, encoding="utf-8")

    backend_commit = _git_head()
    file_hashes = {
        str(path.relative_to(root)).replace("\\", "/"): _sha256_file(path)
        for path in _artifact_files(root)
        if path.name != "manifest.json"
    }
    manifest = _build_manifest(file_hashes, backend_commit)
    _write_json(root / "manifest.json", manifest)

    checksum_lines = [f"{digest}  {relative}" for relative, digest in sorted(file_hashes.items())]
    (root / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"Generated WORK-EXPERT-CONTRACT at {root} (backendCommit={backend_commit})")


def _read_manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _validate_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    if not checksum_path.exists():
        raise SystemExit(f"SHA256SUMS missing: {root}")
    listed: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        listed[relative] = digest
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"SHA256SUMS lists missing file: {relative}")
        actual = _sha256_file(path)
        if actual != digest:
            raise SystemExit(f"SHA256 mismatch for {relative}")
    manifest = _read_manifest(root)
    artifacts = manifest.get("artifacts") or {}
    for relative, digest in artifacts.items():
        if relative == "manifest.json":
            continue
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"manifest.artifacts lists missing file: {relative}")
        if _sha256_file(path) != digest:
            raise SystemExit(f"manifest hash mismatch for {relative}")
        if listed.get(relative) != digest:
            raise SystemExit(f"SHA256SUMS/manifest disagree on {relative}")


def _validate_fixtures(root: Path) -> None:
    import jsonschema

    from app.schemas.hermes_skill.task_result_contract import TaskResultResponse, TaskSnapshotResponse
    from app.schemas.work_expert.http_responses import (
        ApiErrorBody,
        ArtifactPreviewHttpResponse,
        EventsTokenResponse,
        TaskArtifactsHttpData,
        TaskGetResponse,
    )

    schema_map = {
        "fixtures/catalog-tools-list.json": ("mcp/tools-list.response.schema.json", "result"),
        "fixtures/skill-tools-list.json": ("mcp/tools-list.response.schema.json", "result"),
        "fixtures/catalog-tools-list-missing-display-name.json": (
            "mcp/tools-list.response.schema.json",
            "result",
        ),
        "fixtures/skill-tools-list-call-disabled.json": (
            "mcp/tools-list.response.schema.json",
            "result",
        ),
        "fixtures/tools-call-accepted.json": ("mcp/tools-call.response.schema.json", "result"),
        "fixtures/json-rpc-error.json": ("mcp/json-rpc-error.schema.json", None),
    }
    for fixture_rel, schema_info in schema_map.items():
        fixture = json.loads((root / fixture_rel).read_text(encoding="utf-8"))
        schema_rel, key = schema_info
        schema = json.loads((root / schema_rel).read_text(encoding="utf-8"))
        payload = fixture if key is None else fixture[key]
        jsonschema.validate(payload, schema)

    invalid = json.loads((root / "fixtures/invalid-tool-annotations.json").read_text(encoding="utf-8"))
    tools_schema = json.loads((root / "mcp/tools-list.response.schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(invalid["result"], tools_schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise SystemExit("fixtures/invalid-tool-annotations.json unexpectedly passed schema")

    pydantic_map = {
        "fixtures/task-snapshot-running.json": (TaskSnapshotResponse, "data"),
        "fixtures/task-result-completed.json": (TaskResultResponse, "data"),
        "fixtures/task-artifacts.json": (TaskArtifactsHttpData, None),
        "fixtures/http-task-get.json": (TaskGetResponse, None),
        "fixtures/http-events-token.json": (EventsTokenResponse, None),
        "fixtures/http-artifact-preview.json": (ArtifactPreviewHttpResponse, None),
        "fixtures/http-error-owner-forbidden.json": (ApiErrorBody, None),
        "fixtures/http-error-not-found.json": (ApiErrorBody, None),
        "fixtures/http-error-cannot-cancel.json": (ApiErrorBody, None),
    }
    for fixture_rel, (model, key) in pydantic_map.items():
        fixture = json.loads((root / fixture_rel).read_text(encoding="utf-8"))
        payload = fixture if key is None else fixture[key]
        model.model_validate(payload)


def _validate_frozen_versions() -> None:
    from app.contracts.work_expert.constants import WORK_EXPERT_FROZEN_VERSIONS

    for version in WORK_EXPERT_FROZEN_VERSIONS:
        root = CONTRACTS_HOME / f"v{version}"
        if not root.exists():
            raise SystemExit(f"Frozen contract missing: {root}")
        _validate_checksums(root)


def _validate_skill_run_fixtures(root: Path) -> None:
    import jsonschema

    if (root / "runs/public-run.schema.json").exists():
        schema_map = {
            "fixtures/skill-tools-list.json": ("mcp/tools-list.response.schema.json", None),
            "fixtures/tools-call-accepted.json": ("mcp/tools-call.response.schema.json", None),
            "fixtures/run-cancelled.json": ("runs/public-run.schema.json", None),
            "fixtures/run-timeout.json": ("runs/result.schema.json", None),
            "fixtures/artifact-with-checksum.json": ("runs/artifact-list.schema.json", None),
            "fixtures/unsupported-capabilities.json": ("capabilities/unsupported.schema.json", None),
        }
        for fixture_rel, (schema_rel, key) in schema_map.items():
            fixture = json.loads((root / fixture_rel).read_text(encoding="utf-8"))
            schema = json.loads((root / schema_rel).read_text(encoding="utf-8"))
            payload = fixture if key is None else fixture[key]
            jsonschema.validate(payload, schema)

        replay = json.loads((root / "fixtures/sse-resume-duplicate.json").read_text(encoding="utf-8"))
        if replay.get("last_event_id") != replay["events"][0].get("event_id"):
            raise SystemExit("SSE replay fixture must begin after the stable duplicate event identity")
        if len({event.get("event_id") for event in replay["events"]}) != len(replay["events"]):
            raise SystemExit("SSE replay fixture contains duplicate stable event identities")
        return

    schema_map = {
        "fixtures/skill-tools-list.json": (
            "mcp/tools-list.response.schema.json",
            "result",
        ),
        "fixtures/tools-call-accepted.json": ("mcp/tools-call.response.schema.json", "result"),
        "fixtures/edge-lease-renew.json": ("edge/lease-renew.schema.json", None),
        "fixtures/edge-artifact-upload.json": ("edge/artifact-upload.schema.json", None),
        "fixtures/desired-installation.json": ("installations/installation.schema.json", None),
    }
    for fixture_rel, schema_info in schema_map.items():
        fixture_path = root / fixture_rel
        if not fixture_path.exists():
            continue
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        schema_rel, key = schema_info
        schema = json.loads((root / schema_rel).read_text(encoding="utf-8"))
        payload = fixture if key is None else fixture[key]
        jsonschema.validate(payload, schema)


def _validate_skill_run_release(manifest: dict[str, Any], *, version: str) -> None:
    implementation_commit = str(manifest.get("backendCommit") or "")
    tag_name = str(manifest.get("tagName") or "")
    if not implementation_commit or not tag_name:
        raise SystemExit("skill-run release manifest requires backendCommit and tagName")

    repository = BACKEND_ROOT.parent
    ancestor_check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation_commit, "HEAD"],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    if ancestor_check.returncode != 0:
        raise SystemExit("skill-run manifest.backendCommit must be an ancestor of the release commit")

    tag_type = subprocess.run(
        ["git", "cat-file", "-t", f"refs/tags/{tag_name}"],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    if tag_type.returncode != 0 or tag_type.stdout.strip() != "tag":
        raise SystemExit(f"skill-run contract tag '{tag_name}' must be an annotated tag")

    peeled_tag = subprocess.run(
        ["git", "rev-parse", f"refs/tags/{tag_name}^{{}}"],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    if peeled_tag.returncode != 0:
        raise SystemExit(f"skill-run contract tag '{tag_name}' could not be resolved")

    peeled_commit = peeled_tag.stdout.strip()
    if version == "1.2.1":
        release_commit = str(manifest.get("releaseCommit") or peeled_commit)
        if peeled_commit != release_commit:
            raise SystemExit(
                f"skill-run contract tag '{tag_name}' must point at releaseCommit {release_commit}"
            )
        contract_prefix = "nodeskclaw-backend/contracts/skill-run/v1.2.1/"
    else:
        if peeled_commit != _git_head():
            raise SystemExit(f"skill-run contract tag '{tag_name}' must point at the release commit")
        contract_prefix = "nodeskclaw-backend/contracts/skill-run/v1.0.0/"

    release_diff = subprocess.run(
        ["git", "diff", "--name-only", f"{implementation_commit}..{peeled_commit}"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    changed_paths = [path for path in release_diff.stdout.splitlines() if path]
    if not changed_paths or any(not path.startswith(contract_prefix) for path in changed_paths):
        raise SystemExit(f"skill-run release commit may only contain immutable {version} contract artifacts")


def _check_skill_run_contracts(release: bool = False, version: str = "1.0.0") -> None:
    skill_run_root = SKILL_RUN_CONTRACTS_HOME / f"v{version}"
    if not skill_run_root.exists():
        raise SystemExit(f"Skill-run contract directory missing: {skill_run_root}")
    if version == "1.2.1":
        _validate_skill_run_checksums_exact(skill_run_root)
        _validate_skill_run_public_boundary(skill_run_root)
        _validate_skill_run_fixtures(skill_run_root)
        _validate_skill_run_v12_event_fixtures(skill_run_root)
        _validate_skill_run_v12_negative_fixtures(skill_run_root)
        _validate_skill_run_v11_negative_fixtures(skill_run_root)
    else:
        _validate_checksums(skill_run_root)
        _validate_skill_run_fixtures(skill_run_root)
        if version == "1.1.0":
            _validate_skill_run_v11_negative_fixtures(skill_run_root)
        if version == "1.2.0":
            _validate_skill_run_v12_event_fixtures(skill_run_root)
            _validate_skill_run_v12_negative_fixtures(skill_run_root)
            _validate_skill_run_v11_negative_fixtures(skill_run_root)
    if release:
        _validate_skill_run_release(_read_manifest(skill_run_root), version=version)
    print(f"SKILL-RUN-CONTRACT v{version} check passed")


def check_contracts(release: bool = False, family: str = "all", skill_run_version: str | None = None) -> None:
    sys.path.insert(0, str(BACKEND_ROOT))
    if family == "skill-run":
        versions = [skill_run_version] if skill_run_version else ["1.0.0", "1.1.0", "1.2.0", "1.2.1"]
        for version in versions:
            root = SKILL_RUN_CONTRACTS_HOME / f"v{version}"
            if not root.exists():
                if skill_run_version:
                    raise SystemExit(f"Skill-run contract directory missing: {root}")
                continue
            _check_skill_run_contracts(release=release, version=version)
        return

    root = contract_root()
    if not root.exists():
        raise SystemExit(f"Contract directory missing: {root}")

    for rel_path in P0_TEST_FILES:
        if not (BACKEND_ROOT / rel_path).exists():
            raise SystemExit(f"Missing required P0 test file: {rel_path}")

    _validate_frozen_versions()
    _validate_checksums(root)

    manifest = _read_manifest(root)
    if manifest.get("backendCommit") != _git_head():
        if release:
            raise SystemExit("manifest.backendCommit does not match current HEAD in release mode")
        print("warning: manifest.backendCommit differs from current HEAD; run generate after implementation commit")

    _validate_fixtures(root)

    current_openapi = yaml.safe_dump(_load_openapi_subset(), sort_keys=False, allow_unicode=True)
    committed_openapi = (root / "openapi.yaml").read_text(encoding="utf-8")
    if current_openapi != committed_openapi:
        raise SystemExit("OpenAPI drift detected; run contracts generate")

    from app.schemas.hermes_skill.sse_events import TaskProgressEvent

    current_progress_schema = json.dumps(_model_schema(TaskProgressEvent), sort_keys=True)
    committed_progress_schema = json.dumps(
        json.loads((root / "events" / "task-progress.schema.json").read_text(encoding="utf-8")),
        sort_keys=True,
    )
    if current_progress_schema != committed_progress_schema:
        raise SystemExit("SSE schema drift detected; run contracts generate")

    print("WORK-EXPERT-CONTRACT check passed")

    for version in ("1.0.0", "1.1.0", "1.2.0", "1.2.1"):
        root = SKILL_RUN_CONTRACTS_HOME / f"v{version}"
        if not root.exists():
            continue
        _check_skill_run_contracts(release=False, version=version)

    print("SKILL-RUN-CONTRACT check passed")


def _validate_skill_run_v12_event_fixtures(root: Path) -> None:
    import jsonschema

    schema_path = root / "events" / "run-event.schema.json"
    if not schema_path.exists():
        raise SystemExit(f"Missing run-event schema: {schema_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for fixture_rel in (
        "fixtures/run-event-assistant-message.json",
        "fixtures/run-event-tool-call.json",
        "fixtures/run-event-artifact-persisted.json",
        "fixtures/run-event-reasoning-summary.json",
        "fixtures/run-event-clarify-requested.json",
        "fixtures/run-event-approval-requested.json",
        "fixtures/run-event-control-progress.json",
        "fixtures/run-event-control-created.json",
    ):
        fixture_path = root / fixture_rel
        if not fixture_path.exists():
            raise SystemExit(f"Missing skill-run v1.2 fixture: {fixture_rel}")
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        jsonschema.validate(fixture, schema)


def _validate_skill_run_v12_negative_fixtures(root: Path) -> None:
    import jsonschema

    schema_path = root / "events" / "run-event.schema.json"
    if not schema_path.exists():
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    unknown_type = {
        "event_id": "evt-x",
        "run_id": "run-1",
        "event_type": "unknown.semantic",
        "event_seq": 1,
        "source": "agent",
        "timestamp": "2026-08-31T00:00:00Z",
        "payload": {},
    }
    try:
        jsonschema.validate(unknown_type, schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise SystemExit("run-event.schema.json unexpectedly accepted unknown event_type")

    missing_category = {
        "event_id": "evt-y",
        "run_id": "run-1",
        "event_type": "tool.call",
        "event_seq": 1,
        "source": "agent",
        "timestamp": "2026-08-31T00:00:00Z",
        "payload": {"tool_name": "search"},
    }
    try:
        jsonschema.validate(missing_category, schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise SystemExit("run-event.schema.json unexpectedly accepted tool.call missing required fields")


def _validate_skill_run_v11_negative_fixtures(root: Path) -> None:
    import jsonschema

    tools_schema_path = root / "mcp" / "tools-list.response.schema.json"
    if not tools_schema_path.exists():
        return
    tools_schema = json.loads(tools_schema_path.read_text(encoding="utf-8"))

    # Test invalid descriptor missing capabilityKind
    invalid_descriptor = {
        "tools": [
            {
                "name": "invalid_tool",
                "interactionMode": "chat",
                "supportsAttachments": False,
                "annotations": {"riskLevel": "low"},
            }
        ]
    }
    try:
        jsonschema.validate(invalid_descriptor, tools_schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise SystemExit("tools-list.response.schema.json unexpectedly accepted descriptor missing capabilityKind")


def _generate_skill_run_v10_public_contract() -> None:
    from app.schemas.skill_run.constants import SKILL_RUN_CONTRACT_VERSION

    if _is_frozen_skill_run_version(SKILL_RUN_CONTRACT_VERSION):
        print(f"Kept frozen {SKILL_RUN_CONTRACT_NAME} at {SKILL_RUN_CONTRACTS_HOME / f'v{SKILL_RUN_CONTRACT_VERSION}'}")
        return
    from app.schemas.skill_run.mcp_jsonrpc import (
        PublicArtifactDescriptor,
        PublicArtifactDownloadResponse,
        PublicArtifactList,
        PublicRunResult,
        PublicRunView,
        PublicToolsCallAccepted,
        PublicToolsListResult,
        UnsupportedCapabilities,
    )
    from app.schemas.work_expert.mcp_jsonrpc import JsonRpcErrorResponse, JsonRpcRequest
    from app.schemas.skill_run.constants import (
        SKILL_RUN_CAPABILITIES,
        SKILL_RUN_CONTRACT_NAME,
        SKILL_RUN_CONTRACT_VERSION,
        SKILL_RUN_TAG_NAME,
    )

    root = SKILL_RUN_CONTRACTS_HOME / f"v{SKILL_RUN_CONTRACT_VERSION}"
    for directory in ("mcp", "runs", "events", "http", "capabilities", "fixtures"):
        (root / directory).mkdir(parents=True, exist_ok=True)

    legacy_artifacts = (
        "mcp/skill-tool-annotations.schema.json",
        "runs/run.schema.json",
        "runs/execution-snapshot.schema.json",
        "edge/artifact-upload.schema.json",
        "edge/lease-renew.schema.json",
        "installations/actual-report.schema.json",
        "installations/installation.schema.json",
        "fixtures/desired-installation.json",
        "fixtures/edge-artifact-negative-errors.json",
        "fixtures/edge-artifact-upload.json",
        "fixtures/edge-lease-renew.json",
    )
    for relative in legacy_artifacts:
        (root / relative).unlink(missing_ok=True)

    models = {
        "mcp/tools-list.request.schema.json": JsonRpcRequest,
        "mcp/tools-list.response.schema.json": PublicToolsListResult,
        "mcp/tools-call.request.schema.json": JsonRpcRequest,
        "mcp/tools-call.response.schema.json": PublicToolsCallAccepted,
        "mcp/json-rpc-error.schema.json": JsonRpcErrorResponse,
        "runs/public-run.schema.json": PublicRunView,
        "runs/result.schema.json": PublicRunResult,
        "runs/artifact-descriptor.schema.json": PublicArtifactDescriptor,
        "runs/artifact-list.schema.json": PublicArtifactList,
        "runs/artifact-download.response.schema.json": PublicArtifactDownloadResponse,
        "capabilities/unsupported.schema.json": UnsupportedCapabilities,
    }
    for relative, model in models.items():
        _write_json(root / relative, _model_schema(model))

    event_schema = {
        "title": "PublicRunEvent",
        "oneOf": [
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "event_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "event_type": {"enum": ["run.created", "run.progress", "run.completed", "run.failed", "run.cancelled", "run.timed_out"]},
                    "event_seq": {"type": "integer", "minimum": 0},
                    "timestamp": {"type": "string"},
                    "payload": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"phase": {"type": "string"}, "message": {"type": "string"}},
                        "required": ["phase"],
                    },
                },
                "required": ["event_id", "run_id", "event_type", "event_seq", "timestamp", "payload"],
            },
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "event_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "event_type": {"const": "assistant.message"},
                    "event_seq": {"type": "integer", "minimum": 0},
                    "timestamp": {"type": "string"},
                    "payload": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                },
                "required": ["event_id", "run_id", "event_type", "event_seq", "timestamp", "payload"],
            },
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "event_id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "event_type": {"const": "artifact.persisted"},
                    "event_seq": {"type": "integer", "minimum": 0},
                    "timestamp": {"type": "string"},
                    "payload": {"$ref": "../runs/artifact-descriptor.schema.json"},
                },
                "required": ["event_id", "run_id", "event_type", "event_seq", "timestamp", "payload"],
            },
        ],
        "discriminator": {"propertyName": "event_type"},
    }
    _write_json(root / "events/run-event.schema.json", event_schema)

    _write_json(
        root / "http/endpoint-matrix.json",
        {
            "authentication": "Authorization: Bearer <access-token>",
            "sseReplay": {"header": "Last-Event-ID", "eventIdentity": "event_id", "cache": "no-store"},
            "idempotency": {
                "header": "X-Idempotency-Key",
                "scope": "authenticated org_id + user_id + tool_name",
                "ttlSeconds": 86400,
                "conflict": {"status": 409, "errorCode": "IDEMPOTENCY_CONFLICT"},
                "replay": {"status": 200, "returns": "original accepted run_id"},
            },
            "endpoints": [
                {"method": "POST", "path": "/api/v1/mcp", "operation": "tools/list", "success": [200], "retry": "safe"},
                {"method": "POST", "path": "/api/v1/mcp", "operation": "tools/call", "success": [200], "retry": "same-idempotency-key"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}", "success": [200], "retry": "safe", "cache": "no-store"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}/result", "success": [200], "retry": "safe", "cache": "no-store"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}/artifacts", "success": [200], "retry": "safe", "cache": "no-store"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}/artifacts/{artifact_id}/download", "success": [200], "retry": "safe", "cache": "no-store"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}/events", "success": [200], "retry": "Last-Event-ID"},
                {"method": "POST", "path": "/api/v1/runs/{run_id}/cancel", "success": [200, 409], "retry": "safe"},
            ],
        },
    )

    fixtures = {
        "skill-tools-list.json": {"tools": [{"name": "writer.article", "title": "Writer", "description": "Generate an article", "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}, "required": ["prompt"]}, "version": "1.0.0", "category": "writing", "capabilityKind": "skill", "interactionMode": "chat", "promptField": "prompt", "supportsAttachments": False, "annotations": {"category": "writing", "riskLevel": "low", "requiresApproval": False, "streaming": True, "artifacts": True, "version": "1.0.0"}}]},
        "tools-call-accepted.json": {"content": [{"type": "text", "text": "accepted"}], "structuredContent": {"committed": True, "run_id": "run-1", "status": "QUEUED", "tool_name": "writer.article", "event_stream": "/api/v1/runs/run-1/events", "result_url": "/api/v1/runs/run-1/result", "artifact_url": "/api/v1/runs/run-1/artifacts", "execution_mode": "async_event"}, "isError": False},
        "run-cancelled.json": {"run_id": "run-1", "tool_name": "writer.article", "status": "CANCELLED", "created_at": "2026-08-31T00:00:00Z", "updated_at": "2026-08-31T00:01:00Z"},
        "run-timeout.json": {"run_id": "run-1", "status": "TIMED_OUT", "text": None, "error_code": "RUN_TIMED_OUT", "error_message": "Run timed out"},
        "artifact-with-checksum.json": {"run_id": "run-1", "items": [{"artifact_id": "artifact-1", "name": "result.txt", "content_type": "text/plain", "size_bytes": 12, "checksum_sha256": "4f85f7e7d5d1b8c7a898d0e51fc5de49536c870353302dacfe7d8e6c03e8ad7a"}]},
        "sse-resume-duplicate.json": {"last_event_id": "evt-1", "events": [{"event_id": "evt-1", "run_id": "run-1", "event_type": "run.progress", "event_seq": 1, "timestamp": "2026-08-31T00:00:00Z", "payload": {"phase": "RUNNING"}}, {"event_id": "evt-2", "run_id": "run-1", "event_type": "run.completed", "event_seq": 2, "timestamp": "2026-08-31T00:00:01Z", "payload": {"phase": "COMPLETED"}}]},
        "auth-tenant-denial.json": {"status": 403, "error_code": "RUN_FORBIDDEN", "message_key": "errors.run.forbidden"},
        "idempotency-replay.json": {"key": "request-1", "first": {"status": 200, "run_id": "run-1"}, "replay": {"status": 200, "run_id": "run-1"}, "conflict": {"status": 409, "error_code": "IDEMPOTENCY_CONFLICT"}},
        "unsupported-capabilities.json": {"approval": "unsupported", "attachments": "unsupported"},
    }
    for name, payload in fixtures.items():
        _write_json(root / "fixtures" / name, payload)

    (root / "RELEASE.md").write_text(
        f"# {SKILL_RUN_CONTRACT_NAME} v{SKILL_RUN_CONTRACT_VERSION}\n\n"
        "Public, authenticated employee Skill Run contract. Approval and attachments are unsupported and fail closed.\n",
        encoding="utf-8",
    )
    file_hashes = {
        str(path.relative_to(root)).replace("\\", "/"): _sha256_file(path)
        for path in _artifact_files(root)
        if path.name not in {"manifest.json", "SHA256SUMS"}
    }
    _write_json(
        root / "manifest.json",
        {
            "contractName": SKILL_RUN_CONTRACT_NAME,
            "contractVersion": SKILL_RUN_CONTRACT_VERSION,
            "provider": "nodeskclaw-backend",
            "consumer": "smc-copilot/apps/work",
            "backendCommit": _git_head(),
            "tagName": SKILL_RUN_TAG_NAME,
            "artifacts": file_hashes,
            "capabilities": {**SKILL_RUN_CAPABILITIES, "approval": "unsupported", "attachments": "unsupported"},
        },
    )
    (root / "SHA256SUMS").write_text(
        "\n".join(f"{digest}  {relative}" for relative, digest in sorted(file_hashes.items())) + "\n",
        encoding="utf-8",
    )


def _finalize_skill_run_v121_bundle(root: Path, *, backend_commit: str, release_commit: str | None) -> None:
    from app.schemas.skill_run.constants import (
        SKILL_RUN_CAPABILITIES,
        SKILL_RUN_CONTRACT_NAME,
        SKILL_RUN_CONTRACT_VERSION_V121,
        SKILL_RUN_TAG_NAME_V121,
    )

    payload_hashes = {
        str(path.relative_to(root)).replace("\\", "/"): _sha256_file(path)
        for path in _public_artifact_files(root)
    }
    manifest = {
        "contractName": SKILL_RUN_CONTRACT_NAME,
        "contractVersion": SKILL_RUN_CONTRACT_VERSION_V121,
        "bundleFormatVersion": "1",
        "provider": "nodeskclaw-backend",
        "consumer": "external-agent-clients",
        "primaryConsumer": "smc-copilot/apps/work",
        "backendCommit": backend_commit,
        "releaseCommit": release_commit or backend_commit,
        "tagName": SKILL_RUN_TAG_NAME_V121,
        "generatedAt": _skill_run_generated_at(),
        "compatibility": {
            "supersedesForWork": ["1.0.0", "1.1.0", "1.2.0"],
            "wireBreaking": False,
        },
        "artifacts": payload_hashes,
        "capabilities": {
            **SKILL_RUN_CAPABILITIES,
            "catalogV11": True,
            "semanticRunEvents": True,
            "approvalDecision": "unsupported",
            "approval": "unsupported",
            "attachments": "unsupported",
        },
    }
    _write_json_lf(root / "manifest.json", manifest)

    bundle_hashes = {
        str(path.relative_to(root)).replace("\\", "/"): _sha256_file(path)
        for path in _public_artifact_files(root)
    }
    bundle_hashes["manifest.json"] = _sha256_file(root / "manifest.json")
    checksum_lines = [f"{digest}  {relative}" for relative, digest in sorted(bundle_hashes.items())]
    _write_text_lf(root / "SHA256SUMS", "\n".join(checksum_lines) + "\n")

    _validate_skill_run_checksums_exact(root)
    _validate_skill_run_public_boundary(root)
    _validate_skill_run_fixtures(root)
    _validate_skill_run_v12_event_fixtures(root)
    _validate_skill_run_v12_negative_fixtures(root)
    _validate_skill_run_v11_negative_fixtures(root)


def _generate_skill_run_v121_public_contract() -> None:
    from app.schemas.skill_run.constants import (
        SKILL_RUN_CONTRACT_NAME,
        SKILL_RUN_CONTRACT_VERSION_V121,
    )
    from app.schemas.skill_run.mcp_jsonrpc import (
        PublicArtifactDescriptor,
        PublicArtifactDownloadResponse,
        PublicArtifactList,
        PublicRunResult,
        PublicRunView,
        RUN_EVENT_V12_MODELS,
        SkillToolAnnotationsV11,
        ToolsCallAcceptedResultV11,
        ToolsListResultV11,
        UnsupportedCapabilities,
    )
    from app.schemas.work_expert.mcp_jsonrpc import JsonRpcErrorResponse, JsonRpcRequest

    root = SKILL_RUN_CONTRACTS_HOME / f"v{SKILL_RUN_CONTRACT_VERSION_V121}"
    for directory in ("mcp", "runs", "events", "http", "capabilities", "fixtures"):
        (root / directory).mkdir(parents=True, exist_ok=True)

    for relative in (
        "edge/lease-renew.schema.json",
        "edge/artifact-upload.schema.json",
        "installations/actual-report.schema.json",
        "installations/installation.schema.json",
        "runs/run.schema.json",
        "runs/execution-snapshot.schema.json",
        "fixtures/desired-installation.json",
        "fixtures/edge-artifact-upload.json",
        "fixtures/edge-lease-renew.json",
    ):
        (root / relative).unlink(missing_ok=True)

    models = {
        "mcp/tools-list.request.schema.json": JsonRpcRequest,
        "mcp/tools-list.response.schema.json": ToolsListResultV11,
        "mcp/skill-tool-annotations.schema.json": SkillToolAnnotationsV11,
        "mcp/tools-call.request.schema.json": JsonRpcRequest,
        "mcp/tools-call.response.schema.json": ToolsCallAcceptedResultV11,
        "mcp/json-rpc-error.schema.json": JsonRpcErrorResponse,
        "runs/public-run.schema.json": PublicRunView,
        "runs/result.schema.json": PublicRunResult,
        "runs/artifact-descriptor.schema.json": PublicArtifactDescriptor,
        "runs/artifact-list.schema.json": PublicArtifactList,
        "runs/artifact-download.response.schema.json": PublicArtifactDownloadResponse,
        "capabilities/unsupported.schema.json": UnsupportedCapabilities,
    }
    for relative, model in models.items():
        _write_json_lf(root / relative, _model_schema(model))

    _write_json_lf(root / "events" / "run-event.schema.json", _run_event_v12_union_schema(RUN_EVENT_V12_MODELS))

    _write_json_lf(
        root / "http/endpoint-matrix.json",
        {
            "authentication": "Authorization: Bearer <access-token>",
            "sseReplay": {"header": "Last-Event-ID", "eventIdentity": "event_id", "cache": "no-store"},
            "idempotency": {
                "header": "X-Idempotency-Key",
                "scope": "authenticated org_id + user_id + tool_name",
                "ttlSeconds": 86400,
                "conflict": {"status": 409, "errorCode": "IDEMPOTENCY_CONFLICT"},
                "replay": {"status": 200, "returns": "original accepted run_id"},
            },
            "endpoints": [
                {"method": "POST", "path": "/api/v1/mcp", "operation": "tools/list", "success": [200], "retry": "safe"},
                {"method": "POST", "path": "/api/v1/mcp", "operation": "tools/call", "success": [200], "retry": "same-idempotency-key"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}", "success": [200], "retry": "safe", "cache": "no-store"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}/result", "success": [200], "retry": "safe", "cache": "no-store"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}/artifacts", "success": [200], "retry": "safe", "cache": "no-store"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}/artifacts/{artifact_id}/download", "success": [200], "retry": "safe", "cache": "no-store"},
                {"method": "GET", "path": "/api/v1/runs/{run_id}/events", "success": [200], "retry": "Last-Event-ID"},
                {"method": "POST", "path": "/api/v1/runs/{run_id}/cancel", "success": [200, 409], "retry": "safe"},
            ],
        },
    )

    fixtures = {
        "skill-tools-list.json": {
            "tools": [
                {
                    "name": "writer.article",
                    "title": "Writer",
                    "description": "Generate an article",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"prompt": {"type": "string"}},
                        "required": ["prompt"],
                    },
                    "version": "1.2.1",
                    "category": "writing",
                    "capabilityKind": "skill",
                    "interactionMode": "chat",
                    "promptField": "prompt",
                    "supportsAttachments": False,
                    "skillReleaseId": "rel-12345",
                    "skillReleaseDigest": "digest-abcdef",
                    "annotations": {
                        "category": "writing",
                        "riskLevel": "low",
                        "requiresApproval": False,
                        "approvalMode": "none",
                        "streaming": True,
                        "artifacts": True,
                        "version": "1.2.1",
                    },
                }
            ]
        },
        "tools-call-accepted.json": {
            "content": [{"type": "text", "text": "accepted"}],
            "structuredContent": {
                "committed": True,
                "run_id": "run-1",
                "status": "QUEUED",
                "tool_name": "writer.article",
                "event_stream": "/api/v1/runs/run-1/events",
                "result_url": "/api/v1/runs/run-1/result",
                "artifact_url": "/api/v1/runs/run-1/artifacts",
                "execution_mode": "async_event",
                "contract_version": "1.2.1",
            },
            "isError": False,
        },
        "run-cancelled.json": {
            "run_id": "run-1",
            "tool_name": "writer.article",
            "status": "CANCELLED",
            "created_at": "2026-08-31T00:00:00Z",
            "updated_at": "2026-08-31T00:01:00Z",
        },
        "run-timeout.json": {
            "run_id": "run-1",
            "status": "TIMED_OUT",
            "text": None,
            "error_code": "RUN_TIMED_OUT",
            "error_message": "Run timed out",
        },
        "artifact-with-checksum.json": {
            "run_id": "run-1",
            "items": [
                {
                    "artifact_id": "artifact-1",
                    "name": "result.txt",
                    "content_type": "text/plain",
                    "size_bytes": 12,
                    "checksum_sha256": "4f85f7e7d5d1b8c7a898d0e51fc5de49536c870353302dacfe7d8e6c03e8ad7a",
                }
            ],
        },
        "sse-resume-duplicate.json": {
            "last_event_id": "evt-1",
            "events": [
                {
                    "event_id": "evt-1",
                    "run_id": "run-1",
                    "event_type": "run.progress",
                    "event_seq": 1,
                    "timestamp": "2026-08-31T00:00:00Z",
                    "payload": {"phase": "RUNNING"},
                },
                {
                    "event_id": "evt-2",
                    "run_id": "run-1",
                    "event_type": "run.completed",
                    "event_seq": 2,
                    "timestamp": "2026-08-31T00:00:01Z",
                    "payload": {"phase": "COMPLETED"},
                },
            ],
        },
        "auth-tenant-denial.json": {
            "status": 403,
            "error_code": "RUN_FORBIDDEN",
            "message_key": "errors.run.forbidden",
        },
        "idempotency-replay.json": {
            "key": "request-1",
            "first": {"status": 200, "run_id": "run-1"},
            "replay": {"status": 200, "run_id": "run-1"},
            "conflict": {"status": 409, "error_code": "IDEMPOTENCY_CONFLICT"},
        },
        "unsupported-capabilities.json": {"approval": "unsupported", "attachments": "unsupported"},
        "run-event-assistant-message.json": {
            "event_id": "evt-1",
            "run_id": "run-1",
            "event_type": "assistant.message",
            "event_seq": 2,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:assistant:1",
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {"text": "hello"},
        },
        "run-event-tool-call.json": {
            "event_id": "evt-2",
            "run_id": "run-1",
            "event_type": "tool.call",
            "event_seq": 3,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:tool:call-1:1",
            "timestamp": "2026-08-31T00:00:01Z",
            "payload": {"tool_name": "search", "call_id": "call-1", "status": "started"},
        },
        "run-event-artifact-persisted.json": {
            "event_id": "evt-3",
            "run_id": "run-1",
            "event_type": "artifact.persisted",
            "event_seq": 4,
            "source": "agent",
            "source_event_id": "artifact:art-1:persisted",
            "timestamp": "2026-08-31T00:00:02Z",
            "payload": {
                "artifact_id": "art-1",
                "name": "out.txt",
                "content_type": "text/plain",
                "size": 12,
                "checksum_sha256": "abc123",
            },
        },
        "run-event-reasoning-summary.json": {
            "event_id": "evt-4",
            "run_id": "run-1",
            "event_type": "reasoning.summary",
            "event_seq": 5,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:reasoning:1",
            "timestamp": "2026-08-31T00:00:03Z",
            "payload": {"summary": "checked docs"},
        },
        "run-event-clarify-requested.json": {
            "event_id": "evt-5",
            "run_id": "run-1",
            "event_type": "clarify.requested",
            "event_seq": 6,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:clarify:1",
            "timestamp": "2026-08-31T00:00:04Z",
            "payload": {"question": "which file?", "options": ["a", "b"]},
        },
        "run-event-approval-requested.json": {
            "event_id": "evt-6",
            "run_id": "run-1",
            "event_type": "approval.requested",
            "event_seq": 7,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:approval:1",
            "timestamp": "2026-08-31T00:00:05Z",
            "payload": {"approval_id": "appr-1", "summary": "delete file"},
        },
        "run-event-control-progress.json": {
            "event_id": "evt-0",
            "run_id": "run-1",
            "event_type": "run.progress",
            "event_seq": 1,
            "source": "agent",
            "source_event_id": None,
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {"stage": "preparing", "message": "preparing hermes"},
        },
        "run-event-control-created.json": {
            "event_id": "evt-created",
            "run_id": "run-1",
            "event_type": "run.created",
            "event_seq": 0,
            "source": "agent",
            "source_event_id": None,
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {},
        },
    }
    for name, payload in fixtures.items():
        _write_json_lf(root / "fixtures" / name, payload)

    _write_text_lf(
        root / "RELEASE.md",
        f"# {SKILL_RUN_CONTRACT_NAME} v{SKILL_RUN_CONTRACT_VERSION_V121}\n\n"
        "Cumulative Public Skill Run contract for external Work consumers.\n"
        "Includes v1.0 Public Run/Result/Artifact, v1.1 Catalog descriptors, and v1.2 semantic events.\n",
    )

    import os

    backend_commit = os.environ.get("CONTRACT_BACKEND_COMMIT") or _git_head()
    release_commit = os.environ.get("CONTRACT_RELEASE_COMMIT")
    _finalize_skill_run_v121_bundle(root, backend_commit=backend_commit, release_commit=release_commit)
    print(f"Generated {SKILL_RUN_CONTRACT_NAME} at {root} (backendCommit={backend_commit})")


def generate_skill_run_contracts(version: str | None = None) -> None:
    from app.api.internal_edge import (
        EdgeActualReportBody,
        EdgeArtifactUploadBody,
        EdgeLeaseRenewBody,
    )
    from app.schemas.hermes_skill.skill_installation import InstallationRead
    from app.schemas.skill_run.constants import (
        SKILL_RUN_CAPABILITIES,
        SKILL_RUN_CONTRACT_NAME,
        SKILL_RUN_CONTRACT_VERSION,
        SKILL_RUN_CONTRACT_VERSION_V11,
        SKILL_RUN_CONTRACT_VERSION_V12,
        SKILL_RUN_CONTRACT_VERSION_V121,
        SKILL_RUN_TAG_NAME,
    )
    from app.schemas.skill_run.mcp_jsonrpc import (
        ArtifactDescriptor,
        ExecutionSnapshot,
        RUN_EVENT_V12_MODELS,
        RunEvent,
        RunRecord,
        SkillToolAnnotations,
        SkillToolAnnotationsV11,
        SkillToolDescriptorV11,
        ToolsCallAcceptedResult,
        ToolsCallAcceptedResultV11,
        ToolsListResult,
        ToolsListResultV11,
    )
    from app.schemas.work_expert.mcp_jsonrpc import JsonRpcErrorResponse, JsonRpcRequest

    if version == SKILL_RUN_CONTRACT_VERSION_V121:
        _generate_skill_run_v121_public_contract()
        return

    _generate_skill_run_v10_public_contract()
    if version == SKILL_RUN_CONTRACT_VERSION:
        return

    root_v10 = SKILL_RUN_CONTRACTS_HOME / f"v{SKILL_RUN_CONTRACT_VERSION}"
    if not root_v10.exists():
        root_v10.mkdir(parents=True, exist_ok=True)
        (root_v10 / "mcp").mkdir(exist_ok=True)
        (root_v10 / "events").mkdir(exist_ok=True)
        (root_v10 / "runs").mkdir(exist_ok=True)
        (root_v10 / "edge").mkdir(exist_ok=True)
        (root_v10 / "installations").mkdir(exist_ok=True)
        (root_v10 / "fixtures").mkdir(exist_ok=True)

        mcp_models = {
            "tools-list.request.schema.json": JsonRpcRequest,
            "tools-list.response.schema.json": ToolsListResult,
            "skill-tool-annotations.schema.json": SkillToolAnnotations,
            "tools-call.request.schema.json": JsonRpcRequest,
            "tools-call.response.schema.json": ToolsCallAcceptedResult,
            "json-rpc-error.schema.json": JsonRpcErrorResponse,
        }
        for filename, model in mcp_models.items():
            _write_json(root_v10 / "mcp" / filename, _model_schema(model))

        _write_json(root_v10 / "events" / "run-event.schema.json", _model_schema(RunEvent))
        _write_json(root_v10 / "runs" / "run.schema.json", _model_schema(RunRecord))
        _write_json(root_v10 / "runs" / "execution-snapshot.schema.json", _model_schema(ExecutionSnapshot))
        _write_json(root_v10 / "runs" / "artifact-descriptor.schema.json", _model_schema(ArtifactDescriptor))

        _write_json(root_v10 / "edge" / "lease-renew.schema.json", _model_schema(EdgeLeaseRenewBody))
        _write_json(root_v10 / "edge" / "artifact-upload.schema.json", _model_schema(EdgeArtifactUploadBody))
        _write_json(root_v10 / "installations" / "actual-report.schema.json", _model_schema(EdgeActualReportBody))
        _write_json(root_v10 / "installations" / "installation.schema.json", _model_schema(InstallationRead))

        _write_json(
            root_v10 / "fixtures" / "edge-lease-renew.json",
            {
                "extend_seconds": 60,
                "delivery_generation": 1,
            },
        )
        _write_json(
            root_v10 / "fixtures" / "edge-artifact-upload.json",
            {
                "artifact_id": "art-1",
                "name": "result.json",
                "content_base64": "eyJyZXN1bHQiOiA0Mn0=",
                "checksum_sha256": "35a9e381b1a27567549b5f8a6f783c167ebf809630c3991446f41f72a3e01c5c",
                "size_bytes": 16,
                "content_type": "application/json",
                "run_generation": 1,
            },
        )
        _write_json(
            root_v10 / "fixtures" / "desired-installation.json",
            {
                "id": "inst-1",
                "org_id": "org-1",
                "agent_id": "agent-1",
                "skill_id": "skill-1",
                "target_kind": "edge",
                "edge_node_id": "edge-node-1",
                "installed_version": "1.0.0",
                "status": "installed",
                "actual_status": "synced",
                "desired_generation": 1,
                "actual_generation": 1,
                "reconciled_status": "synced",
                "created_at": "2026-08-28T00:00:00Z",
                "updated_at": "2026-08-28T00:00:00Z",
            },
        )
        _write_json(
            root_v10 / "fixtures" / "tools-call-accepted.json",
            {
                "jsonrpc": "2.0",
                "id": "call-1",
                "result": {
                    "content": [{"type": "text", "text": "accepted"}],
                    "structuredContent": {
                        "committed": True,
                        "run_id": "run-1",
                        "status": "QUEUED",
                        "tool_name": "writer_article_generate",
                        "event_stream": "/api/v1/runs/run-1/events?token=example",
                        "result_url": "/api/v1/runs/run-1/result",
                        "artifact_url": "/api/v1/runs/run-1/artifacts",
                        "execution_mode": "async_event",
                    },
                    "isError": False,
                },
            },
        )
        _write_json(
            root_v10 / "fixtures" / "skill-tools-list.json",
            {
                "jsonrpc": "2.0",
                "id": "list-1",
                "result": {
                    "tools": [
                        {
                            "name": "writer_article_generate",
                            "title": "Writer",
                            "description": "Generate article",
                            "inputSchema": {"type": "object"},
                            "version": "1.0.0",
                            "category": "writer",
                            "annotations": {
                                "category": "writer",
                                "riskLevel": "low",
                                "requiresApproval": False,
                                "streaming": True,
                                "artifacts": True,
                                "version": "1.0.0",
                            },
                        }
                    ]
                },
            },
        )

        release = (
            f"# {SKILL_RUN_CONTRACT_NAME} v{SKILL_RUN_CONTRACT_VERSION}\n\n"
            "Skill-first employee MCP and Run identity contract.\n"
            "Does not modify work-expert v1.0.2.\n"
        )
        (root_v10 / "RELEASE.md").write_text(release, encoding="utf-8")

        backend_commit = _git_head()
        file_hashes = {
            str(path.relative_to(root_v10)).replace("\\", "/"): _sha256_file(path)
            for path in _artifact_files(root_v10)
            if path.name != "manifest.json"
        }
        manifest = {
            "contractName": SKILL_RUN_CONTRACT_NAME,
            "contractVersion": SKILL_RUN_CONTRACT_VERSION,
            "provider": "nodeskclaw-backend",
            "consumer": "smc-copilot/apps/work",
            "backendCommit": backend_commit,
            "tagName": SKILL_RUN_TAG_NAME,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "artifacts": file_hashes,
            "capabilities": SKILL_RUN_CAPABILITIES,
        }
        _write_json(root_v10 / "manifest.json", manifest)
        checksum_lines = [f"{digest}  {relative}" for relative, digest in sorted(file_hashes.items())]
        (root_v10 / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        print(f"Generated {SKILL_RUN_CONTRACT_NAME} at {root_v10} (backendCommit={backend_commit})")

    # Generate v1.1.0 contract only when missing (freeze committed package).
    root_v11 = SKILL_RUN_CONTRACTS_HOME / f"v{SKILL_RUN_CONTRACT_VERSION_V11}"
    if root_v11.exists() and (root_v11 / "SHA256SUMS").exists():
        print(f"Kept frozen {SKILL_RUN_CONTRACT_NAME} at {root_v11}")
    else:
        root_v11.mkdir(parents=True, exist_ok=True)
        (root_v11 / "mcp").mkdir(exist_ok=True)
        (root_v11 / "events").mkdir(exist_ok=True)
        (root_v11 / "runs").mkdir(exist_ok=True)
        (root_v11 / "edge").mkdir(exist_ok=True)
        (root_v11 / "installations").mkdir(exist_ok=True)
        (root_v11 / "fixtures").mkdir(exist_ok=True)

        mcp_models_v11 = {
            "tools-list.request.schema.json": JsonRpcRequest,
            "tools-list.response.schema.json": ToolsListResultV11,
            "skill-tool-annotations.schema.json": SkillToolAnnotationsV11,
            "tools-call.request.schema.json": JsonRpcRequest,
            "tools-call.response.schema.json": ToolsCallAcceptedResultV11,
            "json-rpc-error.schema.json": JsonRpcErrorResponse,
        }
        for filename, model in mcp_models_v11.items():
            _write_json(root_v11 / "mcp" / filename, _model_schema(model))

        _write_json(root_v11 / "events" / "run-event.schema.json", _model_schema(RunEvent))
        _write_json(root_v11 / "runs" / "run.schema.json", _model_schema(RunRecord))
        _write_json(root_v11 / "runs" / "execution-snapshot.schema.json", _model_schema(ExecutionSnapshot))
        _write_json(root_v11 / "runs" / "artifact-descriptor.schema.json", _model_schema(ArtifactDescriptor))

        _write_json(root_v11 / "edge" / "lease-renew.schema.json", _model_schema(EdgeLeaseRenewBody))
        _write_json(root_v11 / "edge" / "artifact-upload.schema.json", _model_schema(EdgeArtifactUploadBody))
        _write_json(root_v11 / "installations" / "actual-report.schema.json", _model_schema(EdgeActualReportBody))
        _write_json(root_v11 / "installations" / "installation.schema.json", _model_schema(InstallationRead))

        _write_json(
            root_v11 / "fixtures" / "edge-lease-renew.json",
            {
                "extend_seconds": 60,
                "delivery_generation": 1,
            },
        )
        _write_json(
            root_v11 / "fixtures" / "edge-artifact-upload.json",
            {
                "artifact_id": "art-1",
                "name": "result.json",
                "content_base64": "eyJyZXN1bHQiOiA0Mn0=",
                "checksum_sha256": "35a9e381b1a27567549b5f8a6f783c167ebf809630c3991446f41f72a3e01c5c",
                "size_bytes": 16,
                "content_type": "application/json",
                "run_generation": 1,
            },
        )
        _write_json(
            root_v11 / "fixtures" / "desired-installation.json",
            {
                "id": "inst-1",
                "org_id": "org-1",
                "agent_id": "agent-1",
                "skill_id": "skill-1",
                "target_kind": "edge",
                "edge_node_id": "edge-node-1",
                "installed_version": "1.0.0",
                "status": "installed",
                "actual_status": "synced",
                "desired_generation": 1,
                "actual_generation": 1,
                "reconciled_status": "synced",
                "created_at": "2026-08-28T00:00:00Z",
                "updated_at": "2026-08-28T00:00:00Z",
            },
        )
        _write_json(
            root_v11 / "fixtures" / "tools-call-accepted.json",
            {
                "jsonrpc": "2.0",
                "id": "call-1",
                "result": {
                    "content": [{"type": "text", "text": "accepted"}],
                    "structuredContent": {
                        "committed": True,
                        "run_id": "run-1",
                        "status": "QUEUED",
                        "tool_name": "writer_article_generate",
                        "event_stream": "/api/v1/runs/run-1/events?token=example",
                        "result_url": "/api/v1/runs/run-1/result",
                        "artifact_url": "/api/v1/runs/run-1/artifacts",
                        "execution_mode": "async_event",
                        "contract_version": "1.1.0",
                    },
                    "isError": False,
                },
            },
        )
        _write_json(
            root_v11 / "fixtures" / "skill-tools-list.json",
            {
                "jsonrpc": "2.0",
                "id": "list-1",
                "result": {
                    "tools": [
                        {
                            "name": "writer_article_generate",
                            "title": "Writer",
                            "description": "Generate article",
                            "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}},
                            "version": "1.1.0",
                            "category": "writer",
                            "capabilityKind": "skill",
                            "interactionMode": "chat",
                            "promptField": "prompt",
                            "supportsAttachments": False,
                            "skillReleaseId": "rel-12345",
                            "skillReleaseDigest": "digest-abcdef",
                            "annotations": {
                                "category": "writer",
                                "riskLevel": "low",
                                "requiresApproval": False,
                                "approvalMode": "none",
                                "streaming": True,
                                "artifacts": True,
                                "version": "1.1.0",
                            },
                        }
                    ]
                },
            },
        )

        release_v11 = (
            f"# {SKILL_RUN_CONTRACT_NAME} v{SKILL_RUN_CONTRACT_VERSION_V11}\n\n"
            "Skill-first employee MCP and Run identity contract v1.1.0.\n"
            "Adds Catalog v1.1 descriptors and optional contract_version.\n"
        )
        (root_v11 / "RELEASE.md").write_text(release_v11, encoding="utf-8")

        backend_commit = _git_head()
        file_hashes_v11 = {
            str(path.relative_to(root_v11)).replace("\\", "/"): _sha256_file(path)
            for path in _artifact_files(root_v11)
            if path.name != "manifest.json"
        }
        manifest_v11 = {
            "contractName": SKILL_RUN_CONTRACT_NAME,
            "contractVersion": SKILL_RUN_CONTRACT_VERSION_V11,
            "provider": "nodeskclaw-backend",
            "consumer": "smc-copilot/apps/work",
            "backendCommit": backend_commit,
            "tagName": f"skill-run-contract-v{SKILL_RUN_CONTRACT_VERSION_V11}",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "artifacts": file_hashes_v11,
            "capabilities": {
                **SKILL_RUN_CAPABILITIES,
                "catalogV11": True,
            },
        }
        _write_json(root_v11 / "manifest.json", manifest_v11)
        checksum_lines_v11 = [f"{digest}  {relative}" for relative, digest in sorted(file_hashes_v11.items())]
        (root_v11 / "SHA256SUMS").write_text("\n".join(checksum_lines_v11) + "\n", encoding="utf-8")
        print(f"Generated {SKILL_RUN_CONTRACT_NAME} at {root_v11} (backendCommit={backend_commit})")

    # Generate v1.2.0 semantic event contract
    root_v12 = SKILL_RUN_CONTRACTS_HOME / f"v{SKILL_RUN_CONTRACT_VERSION_V12}"
    if _is_frozen_skill_run_version(SKILL_RUN_CONTRACT_VERSION_V12):
        print(f"Kept frozen {SKILL_RUN_CONTRACT_NAME} at {root_v12}")
        return
    root_v12.mkdir(parents=True, exist_ok=True)
    (root_v12 / "mcp").mkdir(exist_ok=True)
    (root_v12 / "events").mkdir(exist_ok=True)
    (root_v12 / "runs").mkdir(exist_ok=True)
    (root_v12 / "edge").mkdir(exist_ok=True)
    (root_v12 / "installations").mkdir(exist_ok=True)
    (root_v12 / "fixtures").mkdir(exist_ok=True)

    for rel in (
        "mcp/tools-list.request.schema.json",
        "mcp/tools-list.response.schema.json",
        "mcp/skill-tool-annotations.schema.json",
        "mcp/tools-call.request.schema.json",
        "mcp/tools-call.response.schema.json",
        "mcp/json-rpc-error.schema.json",
        "runs/run.schema.json",
        "runs/execution-snapshot.schema.json",
        "runs/artifact-descriptor.schema.json",
        "edge/lease-renew.schema.json",
        "edge/artifact-upload.schema.json",
        "installations/actual-report.schema.json",
        "installations/installation.schema.json",
        "fixtures/edge-lease-renew.json",
        "fixtures/edge-artifact-upload.json",
        "fixtures/desired-installation.json",
        "fixtures/tools-call-accepted.json",
        "fixtures/skill-tools-list.json",
    ):
        src = root_v11 / rel
        if src.exists():
            dest = root_v12 / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())

    _write_json(
        root_v12 / "events" / "run-event.schema.json",
        _run_event_v12_union_schema(RUN_EVENT_V12_MODELS),
    )

    _write_json(
        root_v12 / "fixtures" / "run-event-assistant-message.json",
        {
            "event_id": "evt-1",
            "run_id": "run-1",
            "event_type": "assistant.message",
            "event_seq": 2,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:assistant:1",
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {"text": "hello"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-tool-call.json",
        {
            "event_id": "evt-2",
            "run_id": "run-1",
            "event_type": "tool.call",
            "event_seq": 3,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:tool:call-1:1",
            "timestamp": "2026-08-31T00:00:01Z",
            "payload": {"tool_name": "search", "call_id": "call-1", "status": "started"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-artifact-persisted.json",
        {
            "event_id": "evt-3",
            "run_id": "run-1",
            "event_type": "artifact.persisted",
            "event_seq": 4,
            "source": "agent",
            "source_event_id": "artifact:art-1:persisted",
            "timestamp": "2026-08-31T00:00:02Z",
            "payload": {
                "artifact_id": "art-1",
                "name": "out.txt",
                "content_type": "text/plain",
                "size": 12,
                "checksum_sha256": "abc123",
            },
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-reasoning-summary.json",
        {
            "event_id": "evt-4",
            "run_id": "run-1",
            "event_type": "reasoning.summary",
            "event_seq": 5,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:reasoning:1",
            "timestamp": "2026-08-31T00:00:03Z",
            "payload": {"summary": "checked docs"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-clarify-requested.json",
        {
            "event_id": "evt-5",
            "run_id": "run-1",
            "event_type": "clarify.requested",
            "event_seq": 6,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:clarify:1",
            "timestamp": "2026-08-31T00:00:04Z",
            "payload": {"question": "which file?", "options": ["a", "b"]},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-approval-requested.json",
        {
            "event_id": "evt-6",
            "run_id": "run-1",
            "event_type": "approval.requested",
            "event_seq": 7,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:approval:1",
            "timestamp": "2026-08-31T00:00:05Z",
            "payload": {"approval_id": "appr-1", "summary": "delete file"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-control-progress.json",
        {
            "event_id": "evt-0",
            "run_id": "run-1",
            "event_type": "run.progress",
            "event_seq": 1,
            "source": "agent",
            "source_event_id": None,
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {"stage": "preparing", "message": "preparing hermes"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-control-created.json",
        {
            "event_id": "evt-created",
            "run_id": "run-1",
            "event_type": "run.created",
            "event_seq": 0,
            "source": "agent",
            "source_event_id": None,
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {},
        },
    )

    (root_v12 / "RELEASE.md").write_text(
        f"# {SKILL_RUN_CONTRACT_NAME} v{SKILL_RUN_CONTRACT_VERSION_V12}\n\n"
        "Skill Run event contract v1.2.0.\n"
        "Adds enumerated semantic run events while keeping control event replay.\n",
        encoding="utf-8",
    )

    backend_commit = _git_head()
    file_hashes_v12 = {
        str(path.relative_to(root_v12)).replace("\\", "/"): _sha256_file(path)
        for path in _artifact_files(root_v12)
        if path.name != "manifest.json"
    }
    manifest_v12 = {
        "contractName": SKILL_RUN_CONTRACT_NAME,
        "contractVersion": SKILL_RUN_CONTRACT_VERSION_V12,
        "provider": "nodeskclaw-backend",
        "consumer": "smc-copilot/apps/work",
        "backendCommit": backend_commit,
        "tagName": f"skill-run-contract-v{SKILL_RUN_CONTRACT_VERSION_V12}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": file_hashes_v12,
        "capabilities": {
            **SKILL_RUN_CAPABILITIES,
            "catalogV11": True,
            "semanticRunEvents": True,
        },
    }
    _write_json(root_v12 / "manifest.json", manifest_v12)
    checksum_lines_v12 = [f"{digest}  {relative}" for relative, digest in sorted(file_hashes_v12.items())]
    (root_v12 / "SHA256SUMS").write_text("\n".join(checksum_lines_v12) + "\n", encoding="utf-8")
    print(f"Generated {SKILL_RUN_CONTRACT_NAME} at {root_v12} (backendCommit={backend_commit})")


def main() -> None:
    import os
    os.environ.setdefault("JWT_SECRET", "test-secret-key-for-jwt-generation-minimum-32-chars-long")
    os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-aes-encryption-32-bytes-long")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/nodeskclaw_test")

    parser = argparse.ArgumentParser(description="Contract generator/checker")
    sub = parser.add_subparsers(dest="command", required=True)
    generate_parser = sub.add_parser("generate", help="Generate contract artifacts")
    generate_parser.add_argument(
        "--family",
        choices=("work-expert", "skill-run", "all"),
        default="work-expert",
        help="Contract family to generate",
    )
    generate_parser.add_argument(
        "--version",
        choices=("1.0.0", "1.1.0", "1.2.0", "1.2.1"),
        help="Generate only the requested skill-run contract version",
    )
    check_parser = sub.add_parser("check", help="Validate committed contract artifacts")
    check_parser.add_argument("--release", action="store_true")
    check_parser.add_argument("--family", choices=("work-expert", "skill-run", "all"), default="all")
    check_parser.add_argument(
        "--version",
        choices=("1.0.0", "1.1.0", "1.2.0", "1.2.1"),
        help="Validate only the requested skill-run contract version",
    )
    args = parser.parse_args()

    sys.path.insert(0, str(BACKEND_ROOT))
    if args.command == "generate":
        if args.family in ("work-expert", "all"):
            generate_contracts()
        if args.family in ("skill-run", "all"):
            generate_skill_run_contracts(version=args.version)
    else:
        check_contracts(
            release=args.release,
            family=args.family,
            skill_run_version=getattr(args, "version", None),
        )


if __name__ == "__main__":
    main()
