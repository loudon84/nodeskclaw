#!/usr/bin/env python3
"""Cross-platform Newman Two-Run Runner and Aggregator."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REQUIRED_ENV_VARS = (
    "SKILL_AGENT_INTERNAL_TOKEN",
    "SKILL_AGENT_EDGE_TOKEN",
    "JWT_TOKEN",
    "ACCEPTANCE_ORG_ID",
    "ACCEPTANCE_USER_ID",
)


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def generate_env_file(template_path: Path, output_path: Path) -> None:
    if not template_path.exists():
        raise FileNotFoundError(f"Template environment file not found: {template_path}")

    internal_token = _require_env("SKILL_AGENT_INTERNAL_TOKEN")
    edge_token = _require_env("SKILL_AGENT_EDGE_TOKEN")
    jwt_token = _require_env("JWT_TOKEN")
    agent_url = os.getenv("AGENT_BASE_URL", "http://127.0.0.1:4580")
    backend_url = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:4510")
    org_id = _require_env("ACCEPTANCE_ORG_ID")
    user_id = _require_env("ACCEPTANCE_USER_ID")
    org_prefix = os.getenv("ACCEPTANCE_ORG_PREFIX", "acceptance")

    if not org_id.startswith(org_prefix):
        raise RuntimeError(
            f"ACCEPTANCE_ORG_ID must use isolated prefix '{org_prefix}', got '{org_id}'"
        )

    content = template_path.read_text(encoding="utf-8")
    content = content.replace("${SKILL_AGENT_INTERNAL_TOKEN}", internal_token)
    content = content.replace("${SKILL_AGENT_EDGE_TOKEN}", edge_token)
    content = content.replace("${JWT_TOKEN}", jwt_token)
    content = content.replace("${ACCEPTANCE_ORG_ID}", org_id)
    content = content.replace("${ACCEPTANCE_USER_ID}", user_id)
    content = content.replace("http://127.0.0.1:4520", agent_url)
    content = content.replace("http://127.0.0.1:4580", agent_url)
    content = content.replace("http://127.0.0.1:4510", backend_url)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Generated resolved environment file: {output_path}")


def redact_report_files(report_paths: tuple[Path, ...], secret_values: tuple[str, ...]) -> None:
    for path in report_paths:
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for secret in secret_values:
            if secret:
                content = content.replace(secret, "[REDACTED]")
        path.write_text(content, encoding="utf-8")


def construct_newman_command(
    collection_path: Path | str,
    env_path: Path | str,
    report_xml_path: Path | str,
    report_json_path: Path | str | None = None,
    delay_ms: int = 50,
) -> list[str]:
    newman_cmd = shutil.which("newman")
    base_cmd = [newman_cmd] if newman_cmd else [shutil.which("npx") or "npx", "newman"]
    reporters = "cli,junit,json"
    cmd = base_cmd + [
        "run",
        str(collection_path),
        "-e",
        str(env_path),
        "--reporters",
        reporters,
        "--reporter-junit-export",
        str(report_xml_path),
        "--delay-request",
        str(delay_ms),
    ]
    if report_json_path:
        cmd += ["--reporter-json-export", str(report_json_path)]
    return cmd


def run_newman(
    collection_path: Path,
    env_path: Path,
    report_xml_path: Path,
    iteration: int,
    report_json_path: Path | None = None,
) -> bool:
    print(f"\n================ Running Newman Acceptance Pass #{iteration} ================")
    cmd = construct_newman_command(collection_path, env_path, report_xml_path, report_json_path)
    if not shutil.which("newman") and not shutil.which("npx"):
        print("ERROR: Neither 'newman' nor 'npx' found in PATH.")
        return False

    print(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd, check=False)
    return res.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Newman Two-Run Acceptance Runner")
    parser.add_argument(
        "--collection",
        default="tests/postman/nodeskclaw_acceptance_closure.postman_collection.json",
        help="Path to postman collection",
    )
    parser.add_argument(
        "--env-template",
        default="tests/postman/nodeskclaw_agent_acceptance.postman_environment.template.json",
        help="Path to environment template",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory to store reports",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate files and construct commands without running Newman",
    )
    args = parser.parse_args()

    for name in REQUIRED_ENV_VARS:
        if not os.getenv(name, "").strip():
            if args.validate_only:
                print(f"ERROR: Missing required environment variable for Newman: {name}")
                sys.exit(1)
            print(f"ERROR: Missing required environment variable: {name}")
            sys.exit(1)

    collection_path = Path(args.collection).resolve()
    env_template_path = Path(args.env_template).resolve()
    reports_dir = Path(args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    check_script = Path("tools/acceptance/check_postman_collection.py").resolve()
    if check_script.exists():
        chk_res = subprocess.run(
            [
                sys.executable,
                str(check_script),
                str(collection_path),
                "--env-template",
                str(env_template_path),
                "--scan-repo",
            ],
            check=False,
        )
        if chk_res.returncode != 0:
            print("Static collection validation failed. Aborting runs.")
            sys.exit(1)

    xml_1 = reports_dir / "newman_run1_junit.xml"
    xml_2 = reports_dir / "newman_run2_junit.xml"
    json_1 = reports_dir / "newman_run1.json"
    json_2 = reports_dir / "newman_run2.json"
    reports = (xml_1, xml_2, json_1, json_2)
    secret_values = tuple(os.getenv(name, "") for name in REQUIRED_ENV_VARS)

    with tempfile.TemporaryDirectory(prefix="nodeskclaw-newman-") as temp_dir:
        rendered_env = Path(temp_dir) / "acceptance_environment.json"
        generate_env_file(env_template_path, rendered_env)
        cmd1 = construct_newman_command(collection_path, rendered_env, xml_1, json_1)
        cmd2 = construct_newman_command(collection_path, rendered_env, xml_2, json_2)

        if args.validate_only:
            print("\n--- Newman Validation & Command Construction Successful ---")
            print("Run 1 Command:", " ".join(cmd1))
            print("Run 2 Command:", " ".join(cmd2))
            sys.exit(0)

        ok_1 = run_newman(collection_path, rendered_env, xml_1, iteration=1, report_json_path=json_1)
        if not ok_1:
            print("\nERROR: Newman Run #1 Failed.")
            redact_report_files(reports, secret_values)
            sys.exit(1)

        ok_2 = run_newman(collection_path, rendered_env, xml_2, iteration=2, report_json_path=json_2)
        if not ok_2:
            print("\nERROR: Newman Run #2 Failed.")
            redact_report_files(reports, secret_values)
            sys.exit(1)

    if any(not path.is_file() or path.stat().st_size == 0 for path in reports):
        print("ERROR: Newman completed without all required JUnit and JSON reports.")
        redact_report_files(reports, secret_values)
        sys.exit(1)

    redact_report_files(reports, secret_values)

    print("\n================ Newman Two-Run Suite Completed Successfully ================")
    summary = {
        "status": "PASSED",
        "run_1_junit": str(xml_1),
        "run_2_junit": str(xml_2),
        "run_1_json": str(json_1),
        "run_2_json": str(json_2),
    }
    (reports_dir / "newman_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
