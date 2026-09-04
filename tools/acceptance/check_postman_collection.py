#!/usr/bin/env python3
"""Static Quality & Safety Checker for Postman Collection and acceptance assets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

VACUOUS_PATTERNS = [
    re.compile(r"pm\.expect\(\s*true\s*\)\.to\.be\.true", re.IGNORECASE),
    re.compile(r"pm\.expect\(\s*1\s*\)\.to\.equal\(\s*1\s*\)", re.IGNORECASE),
    re.compile(r"pm\.expect\(\s*\"ok\"\s*\)\.to\.equal\(\s*\"ok\"\s*\)", re.IGNORECASE),
]

KNOWN_PLAINTEXT_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{36,}"),
]

FORBIDDEN_REPO_SECRET_LITERALS = [
    "postman-acceptance-agent-token-secure-32b",
    "acceptance-edge-token-secure-32b",
    "change-me-skill-agent-token",
    "acceptance-jwt-secret-key-32b",
]

ENV_VAR_PATTERN = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
STATUS_LIST_PATTERN = re.compile(r"(?:to\.be\.)?oneOf\(\s*\[([^\]]+)\]", re.IGNORECASE)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?im)^\s*(?:\{\s*)?[\"']?[A-Za-z0-9_-]*(?:token|secret|password|api[_-]?key)[A-Za-z0-9_-]*[\"']?\s*:\s*[\"']?(?!\$\{|\{\{)([A-Za-z0-9][A-Za-z0-9._~+/@:-]{15,})"
)

DEFAULT_REPO_SCAN_PATHS = [
    "docker-compose.acceptance.yml",
    "tests/postman",
    "tools/acceptance",
    "reports",
]

RUNTIME_ENV_VAR_NAMES = {
    "RUN_ID",
    "JOB_ID",
    "ARTIFACT_ID",
    "INSTALLATION_ID",
    "run_id",
    "task_id",
}


def _iter_collection_items(items: list[Any]) -> Iterable[dict[str, Any]]:
    for item in items:
        if not isinstance(item, dict):
            continue
        nested = item.get("item")
        if nested:
            yield from _iter_collection_items(nested)
            continue
        if item.get("request"):
            yield item


def _has_permissive_mixed_status(script_text: str) -> bool:
    for matched in STATUS_LIST_PATTERN.finditer(script_text):
        status_codes = {int(code) for code in re.findall(r"\b[1-5]\d{2}\b", matched.group(1))}
        if any(200 <= code < 300 for code in status_codes) and any(code >= 400 for code in status_codes):
            return True
    return False


def check_collection(
    collection_path: Path | str,
    env_template_path: Path | str | None = None,
) -> list[str]:
    errors: list[str] = []
    collection_path = Path(collection_path)

    if not collection_path.exists():
        return [f"Collection file not found: {collection_path}"]

    try:
        data = json.loads(collection_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Invalid JSON in {collection_path}: {exc}"]

    if not isinstance(data, dict):
        return [f"Root of collection must be a JSON object: {collection_path}"]

    items = list(_iter_collection_items(data.get("item") or []))
    if not items:
        return [f"Collection has no executable items: {collection_path}"]

    known_env_vars: set[str] = set()
    if env_template_path:
        env_p = Path(env_template_path)
        if env_p.exists():
            try:
                env_data = json.loads(env_p.read_text(encoding="utf-8"))
                for v in env_data.get("values") or []:
                    if v.get("key"):
                        known_env_vars.add(v["key"])
            except Exception:
                pass

    jwt_items = 0
    internal_only_items = 0

    for idx, item in enumerate(items):
        name = str(item.get("name") or f"Item_{idx}")
        req = item.get("request") or {}
        body = req.get("body") or {}
        raw_body = str(body.get("raw") or "")

        if ".repeat(" in raw_body:
            errors.append(f"Item '{name}' contains raw body with unparsed dynamic JS expression .repeat()")

        for secret_re in KNOWN_PLAINTEXT_SECRET_PATTERNS:
            if secret_re.search(raw_body):
                errors.append(f"Item '{name}' contains hardcoded plaintext secret matching {secret_re.pattern}")

        for literal in FORBIDDEN_REPO_SECRET_LITERALS:
            if literal in raw_body:
                errors.append(f"Item '{name}' contains forbidden repository secret literal")

        events = item.get("event") or []
        has_tests = False
        for ev in events:
            if ev.get("listen") == "test":
                script = ev.get("script") or {}
                exec_lines = script.get("exec") or []
                script_text = "\n".join(exec_lines) if isinstance(exec_lines, list) else str(exec_lines)
                if re.search(r"pm\.(?:expect|response\.to)\b", script_text):
                    has_tests = True
                if _has_permissive_mixed_status(script_text):
                    errors.append(f"Item '{name}' contains permissive mixed success/error status assertion")
                for vac_re in VACUOUS_PATTERNS:
                    if vac_re.search(script_text):
                        errors.append(f"Item '{name}' contains vacuous assertion matching '{vac_re.pattern}'")

        if not has_tests:
            errors.append(f"Item '{name}' has no test assertions")

        headers = req.get("header") or []
        header_map = {str(h.get("key") or "").lower(): str(h.get("value") or "") for h in headers}
        auth_header = header_map.get("authorization", "")
        internal_header = header_map.get("x-skill-agent-token", "")

        if auth_header.startswith("Bearer {{") or auth_header.startswith("Bearer {{JWT_TOKEN"):
            jwt_items += 1
        elif internal_header.startswith("{{INTERNAL_TOKEN") or internal_header.startswith("{{internal_token"):
            internal_only_items += 1

        if known_env_vars:
            url_raw = str((req.get("url") or {}).get("raw") or "")
            used_vars = set(ENV_VAR_PATTERN.findall(url_raw))
            for h in headers:
                used_vars.update(ENV_VAR_PATTERN.findall(str(h.get("value") or "")))
            used_vars.update(ENV_VAR_PATTERN.findall(raw_body))
            for v in used_vars:
                if v not in known_env_vars and v not in RUNTIME_ENV_VAR_NAMES:
                    errors.append(f"Item '{name}' references unknown environment variable '{v}' not in template")

    if jwt_items == 0:
        errors.append("Collection must include at least one Backend JWT public-contract request")

    if internal_only_items == 0:
        errors.append("Collection must include at least one internal harness request (Edge/Bundle/internal)")

    return errors


def scan_acceptance_secrets(paths: list[Path | str] | None = None) -> list[str]:
    errors: list[str] = []
    scan_paths = [Path(p) for p in (paths or DEFAULT_REPO_SCAN_PATHS)]

    for root in scan_paths:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".yml", ".yaml", ".json", ".py", ".env", ".template", ".md", ".txt", ".xml"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if SECRET_ASSIGNMENT_PATTERN.search(text) or any(pattern.search(text) for pattern in KNOWN_PLAINTEXT_SECRET_PATTERNS):
                errors.append(f"Secret-like value found in {path.as_posix()}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Static Checker for Postman Collections and acceptance assets")
    parser.add_argument(
        "collection",
        nargs="?",
        default="tests/postman/nodeskclaw_acceptance_closure.postman_collection.json",
        help="Path to postman collection json",
    )
    parser.add_argument(
        "--env-template",
        default="tests/postman/nodeskclaw_agent_acceptance.postman_environment.template.json",
        help="Path to postman environment template json",
    )
    parser.add_argument(
        "--scan-repo",
        action="store_true",
        help="Scan compose/env/scripts/reports for forbidden repository secret literals",
    )
    parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Additional path to include in repository secret scan",
    )
    args = parser.parse_args()

    errors = check_collection(args.collection, args.env_template)
    if args.scan_repo:
        extra = args.scan_path or None
        errors.extend(scan_acceptance_secrets(extra))

    if errors:
        print(f"Collection static check FAILED with {len(errors)} errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    print(f"Collection static check PASSED for {args.collection}")


if __name__ == "__main__":
    main()
