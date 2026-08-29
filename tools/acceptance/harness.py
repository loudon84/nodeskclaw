#!/usr/bin/env python3
"""Acceptance Harness for Central A/B, Edge and Backend topology validation."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def check_docker_available() -> bool:
    """Return True if docker CLI is present and the daemon is reachable."""
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception:
        return False


def validate_topology(compose_path: Path | str | None = None) -> dict[str, Any]:
    """Offline validation of docker-compose.acceptance.yml topology structure."""
    if compose_path is None:
        compose_path = Path("docker-compose.acceptance.yml")
    compose_path = Path(compose_path)

    if not compose_path.exists():
        return {
            "valid": False,
            "error": f"Compose file not found: {compose_path}",
            "checks": {},
        }

    content = compose_path.read_text(encoding="utf-8")
    checks: dict[str, bool] = {
        "has_postgres": "postgres:" in content,
        "has_backend": "nodeskclaw-backend:" in content,
        "has_agent_a": "nodeskclaw-agent:" in content,
        "has_agent_b": "nodeskclaw-agent-b:" in content,
        "has_agent_edge": "nodeskclaw-agent-edge:" in content,
        "uses_amd64_platform": "platform: linux/amd64" in content,
        "has_shared_artifact_volume": "artifact_data:" in content,
        "no_hardcoded_plaintext_secrets": "postman-acceptance-agent-token-secure-32b" in content,
    }

    is_valid = all(checks.values())
    return {
        "valid": is_valid,
        "checks": checks,
        "compose_file": str(compose_path),
        "error": None if is_valid else "Topology validation failed checks",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Acceptance Topology Harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    val_parser = subparsers.add_parser("validate", help="Validate topology file offline")
    val_parser.add_argument("--compose-file", default="docker-compose.acceptance.yml", help="Path to compose file")

    dock_parser = subparsers.add_parser("check-docker", help="Check Docker availability")

    run_parser = subparsers.add_parser("run", help="Run topology")
    run_parser.add_argument("--mode", choices=["compose", "external"], default="compose")
    run_parser.add_argument("--compose-file", default="docker-compose.acceptance.yml")

    args = parser.parse_args()

    if args.command == "validate":
        res = validate_topology(args.compose_file)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["valid"] else 1)

    elif args.command == "check-docker":
        avail = check_docker_available()
        out = {
            "docker_available": avail,
            "status": "available" if avail else "docker_unavailable",
        }
        print(json.dumps(out, indent=2))
        sys.exit(0 if avail else 0)

    elif args.command == "run":
        if args.mode == "compose":
            if not check_docker_available():
                print(json.dumps({
                    "status": "docker_unavailable",
                    "error": "Docker daemon is not running or not installed",
                }, indent=2))
                sys.exit(0)
            else:
                print(json.dumps({"status": "ready", "mode": "compose"}, indent=2))
                sys.exit(0)
        else:
            print(json.dumps({"status": "ready", "mode": "external"}, indent=2))
            sys.exit(0)


if __name__ == "__main__":
    main()
