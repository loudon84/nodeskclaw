#!/usr/bin/env python3
"""Provider Live runner for Remote ACP v2. Missing env => BLOCKED, exit 1."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REQUIRED_ENV = (
    "NODESKCLAW_BACKEND_URL",
    "NODESKCLAW_ACCESS_TOKEN",
    "NODESKCLAW_ORG_ID",
    "REMOTE_ACP_AGENT_REF",
)

SCENARIOS = (
    "initialize",
    "session/new",
    "prompt streaming",
    "session/resume",
    "attachment",
    "approval",
    "cancel",
    "artifact",
    "terminal",
    "disconnect/reconnect",
)


def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    payload = {
        "SMC_ACCEPTANCE_RESULT": "FAIL",
        "status": "BLOCKED",
        "production_gate": "unpassed",
        "frontendContractGate": "pending",
        "reason": "missing_live_credentials" if missing else "live_remote_acp_execution_not_run",
        "missing": missing,
        "scenarios": list(SCENARIOS),
        "evidence_dir": "docs_agent/evidence/remote-acp-v2",
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
