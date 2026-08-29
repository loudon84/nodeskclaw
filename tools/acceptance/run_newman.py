#!/usr/bin/env python3
"""Cross-platform Newman Two-Run Runner and Aggregator.
Runs Postman Acceptance Suite twice (Run 1: Clean pass; Run 2: Idempotent re-run),
exports JUnit XML reports and a combined summary JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


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


def run_newman(
    collection_path: Path,
    env_path: Path,
    report_xml_path: Path,
    iteration: int,
) -> bool:
    print(f"\n================ Running Newman Acceptance Pass #{iteration} ================")
    newman_cmd = shutil.which("newman")
    if not newman_cmd:
        npx_cmd = shutil.which("npx")
        if not npx_cmd:
            print("ERROR: Neither 'newman' nor 'npx' found in PATH.")
            return False
        cmd = [
            npx_cmd,
            "newman",
            "run",
            str(collection_path),
            "-e",
            str(env_path),
            "--reporters",
            "cli,junit",
            "--reporter-junit-export",
            str(report_xml_path),
            "--delay-request",
            "50",
        ]
    else:
        cmd = [
            newman_cmd,
            "run",
            str(collection_path),
            "-e",
            str(env_path),
            "--reporters",
            "cli,junit",
            "--reporter-junit-export",
            str(report_xml_path),
            "--delay-request",
            "50",
        ]

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
    args = parser.parse_args()

    collection_path = Path(args.collection).resolve()
    env_template_path = Path(args.env_template).resolve()
    reports_dir = Path(args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Static validation of collection
    check_script = Path("tools/acceptance/check_postman_collection.py").resolve()
    if check_script.exists():
        chk_res = subprocess.run([sys.executable, str(check_script), str(collection_path)], check=False)
        if chk_res.returncode != 0:
            print("Static collection validation failed. Aborting runs.")
            sys.exit(1)

    # 2. Render runtime environment file
    rendered_env = reports_dir / "rendered_acceptance_environment.json"
    generate_env_file(env_template_path, rendered_env)

    # 3. First pass (clean pass)
    xml_1 = reports_dir / "newman-run1.xml"
    success_1 = run_newman(collection_path, rendered_env, xml_1, iteration=1)

    # 4. Second pass (idempotent re-run)
    xml_2 = reports_dir / "newman-run2.xml"
    success_2 = run_newman(collection_path, rendered_env, xml_2, iteration=2)

    summary = {
        "collection": str(collection_path),
        "run1": {
            "success": success_1,
            "report_xml": str(xml_1),
        },
        "run2": {
            "success": success_2,
            "report_xml": str(xml_2),
        },
        "both_passed": success_1 and success_2,
    }

    summary_file = reports_dir / "acceptance_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWritten acceptance summary: {summary_file}")

    if not (success_1 and success_2):
        print("Acceptance two-run verification FAILED.")
        sys.exit(1)

    print("Acceptance two-run verification SUCCEEDED.")


if __name__ == "__main__":
    main()
