from __future__ import annotations

import json
import os
import sys

LIVE_CASES = [f"LIVE-DESK-{index:03d}" for index in range(1, 22)]
REQUIRED_ENV = (
    "NODESKCLAW_BACKEND_URL",
    "NODESKCLAW_ACCESS_TOKEN",
    "NODESKCLAW_REFRESH_TOKEN",
    "WINDOWS_CLEAN_MACHINE",
)


def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
    payload = {
        "SMC_ACCEPTANCE_RESULT": "FAIL",
        "production_gate": "unpassed",
        "conformance": "ACP_V1_ADAPTER_PROFILE_CONFORMANT",
        "cases": LIVE_CASES,
        "zed_live": "unpassed",
        "work_ui": "not_in_this_repo",
    }
    if missing:
        payload["reason"] = "missing_live_credentials"
        payload["missing"] = missing
        print(json.dumps(payload, ensure_ascii=False))
        return 1
    payload["reason"] = "live_desktop_consumer_execution_not_run"
    print(json.dumps(payload, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
