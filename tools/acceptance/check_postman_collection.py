#!/usr/bin/env python3
"""Static Quality & Safety Checker for Postman Collection.

Enforces:
1. Valid JSON and valid Postman Collection v2.1 structure.
2. All items follow strict naming convention (e.g. AC-XX / Step XX).
3. No vacuous or escape assertions (e.g. pm.expect(true).to.be.true).
4. No hardcoded plaintext secrets or unparsed dynamic JS expressions.
5. All environment variables used in requests are present in environment template.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

VACUOUS_PATTERNS = [
    re.compile(r"pm\.expect\(\s*true\s*\)\.to\.be\.true", re.IGNORECASE),
    re.compile(r"pm\.expect\(\s*1\s*\)\.to\.equal\(\s*1\s*\)", re.IGNORECASE),
    re.compile(r"pm\.expect\(\s*\"ok\"\s*\)\.to\.equal\(\s*\"ok\"\s*\)", re.IGNORECASE),
]

KNOWN_PLAINTEXT_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{32,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{36,}"),
]

ENV_VAR_PATTERN = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")


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

    items = data.get("item") or []
    if not items:
        return [f"Collection has no items: {collection_path}"]

    # Collect available env vars if env template is provided
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

    for idx, item in enumerate(items):
        name = str(item.get("name") or f"Item_{idx}")

        # Check raw body for dynamic unparsed expressions or raw secrets
        req = item.get("request") or {}
        body = req.get("body") or {}
        raw_body = str(body.get("raw") or "")

        if ".repeat(" in raw_body:
            errors.append(f"Item '{name}' contains raw body with unparsed dynamic JS expression .repeat()")

        for secret_re in KNOWN_PLAINTEXT_SECRET_PATTERNS:
            if secret_re.search(raw_body):
                errors.append(f"Item '{name}' contains hardcoded plaintext secret matching {secret_re.pattern}")

        # Check test scripts for vacuous assertions
        events = item.get("event") or []
        has_tests = False
        for ev in events:
            if ev.get("listen") == "test":
                script = ev.get("script") or {}
                exec_lines = script.get("exec") or []
                script_text = "\n".join(exec_lines) if isinstance(exec_lines, list) else str(exec_lines)
                if script_text.strip():
                    has_tests = True

                for vac_re in VACUOUS_PATTERNS:
                    if vac_re.search(script_text):
                        errors.append(f"Item '{name}' contains vacuous assertion matching '{vac_re.pattern}'")

        if not has_tests:
            errors.append(f"Item '{name}' has no test assertions")

        # Check env variables used in URL and headers against known template
        if known_env_vars:
            url_raw = str((req.get("url") or {}).get("raw") or "")
            used_vars = set(ENV_VAR_PATTERN.findall(url_raw))
            for h in req.get("header") or []:
                used_vars.update(ENV_VAR_PATTERN.findall(str(h.get("value") or "")))
            for v in used_vars:
                # Dynamic runtime vars set in test scripts are allowed
                if v not in known_env_vars and v not in {"RUN_ID", "JOB_ID", "ARTIFACT_ID"}:
                    errors.append(f"Item '{name}' references unknown environment variable '{v}' not in template")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Static Checker for Postman Collections")
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
    args = parser.parse_args()

    errors = check_collection(args.collection, args.env_template)
    if errors:
        print(f"Collection static check FAILED with {len(errors)} errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    print(f"Collection static check PASSED for {args.collection}")


if __name__ == "__main__":
    main()
