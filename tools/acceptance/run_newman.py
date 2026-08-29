#!/usr/bin/env python3
"""Cross-platform Newman Two-Run Runner and Aggregator.

Runs Postman Acceptance Suite twice (Run 1: Clean pass; Run 2: Idempotent re-run),
exports JUnit XML reports and a combined summary JSON report.
Supports --validate-only mode for command construction and offline validation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def generate_env_file(template_path: Path, output_path: Path) -> None:
    if not template_path.exists():
        raise FileNotFoundError(f"Template environment file not found: {template_path}")

    content = template_path.read_text(encoding="utf-8")
    internal_token = os.getenv("SKILL_AGENT_INTERNAL_TOKEN", "postman-acceptance-agent-token-secure-32b")
    edge_token = os.getenv("SKILL_AGENT_EDGE_TOKEN", "acceptance-edge-token-secure-32b")
    agent_url = os.getenv("AGENT_BASE_URL", "http://127.0.0.1:4520")
    backend_url = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:4510")

    content = content.replace("${SKILL_AGENT_INTERNAL_TOKEN}", internal_token)
    content = content.replace("${SKILL_AGENT_EDGE_TOKEN}", edge_token)
    content = content.replace("http://127.0.0.1:4520", agent_url)
    content = content.replace("http://127.0.0.1:4510", backend_url)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"Generated resolved environment file: {output_path}")


def construct_newman_command(
    collection_path: Path | str,
    env_path: Path | str,
    report_xml_path: Path | str,
    report_json_path: Path | str | None = None,
    delay_ms: int = 50,
) -> list[str]:
    newman_cmd = shutil.which("newman")
    base_cmd = [newman_cmd] if newman_cmd else [shutil.which("npx") or "npx", "newman"]
    reporters = "cli,junit"
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

    collection_path = Path(args.collection).resolve()
    env_template_path = Path(args.env_template).resolve()
    reports_dir = Path(args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Static validation of collection
    check_script = Path("tools/acceptance/check_postman_collection.py").resolve()
    if check_script.exists():
        chk_res = subprocess.run([sys.executable, str(check_script), str(collection_path), "--env-template", str(env_template_path)], check=False)
        if chk_res.returncode != 0:
            print("Static collection validation failed. Aborting runs.")
            sys.exit(1)

    # 2. Render runtime environment file
    rendered_env = reports_dir / "rendered_acceptance_environment.json"
    generate_env_file(env_template_path, rendered_env)

    xml_1 = reports_dir / "newman_run1_junit.xml"
    xml_2 = reports_dir / "newman_run2_junit.xml"
    json_1 = reports_dir / "newman_run1.json"
    json_2 = reports_dir / "newman_run2.json"

    cmd1 = construct_newman_command(collection_path, rendered_env, xml_1, json_1)
    cmd2 = construct_newman_command(collection_path, rendered_env, xml_2, json_2)

    if args.validate_only:
        print("\n--- Newman Validation & Command Construction Successful ---")
        print("Run 1 Command:", " ".join(cmd1))
        print("Run 2 Command:", " ".join(cmd2))
        sys.exit(0)

    # 3. Execution Phase: Pass 1
    ok_1 = run_newman(collection_path, rendered_env, xml_1, iteration=1, report_json_path=json_1)
    if not ok_1:
        print("\nERROR: Newman Run #1 Failed.")
        sys.exit(1)

    # 4. Execution Phase: Pass 2 (Idempotency Re-run)
    ok_2 = run_newman(collection_path, rendered_env, xml_2, iteration=2, report_json_path=json_2)
    if not ok_2:
        print("\nERROR: Newman Run #2 Failed.")
        sys.exit(1)

    print("\n================ Newman Two-Run Suite Completed Successfully ================")
    summary = {
        "status": "PASSED",
        "run_1_junit": str(xml_1),
        "run_2_junit": str(xml_2),
    }
    (reports_dir / "newman_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
