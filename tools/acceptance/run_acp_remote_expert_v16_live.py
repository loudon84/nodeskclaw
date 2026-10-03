from __future__ import annotations

import json
import os
import sys

LIVE_CASES = [f"LIVE-ACP-{index:03d}" for index in range(1, 19)]
REQUIRED_ENV = (
    "NODESKCLAW_BACKEND_URL",
    "NODESKCLAW_ACP_PROFILE",
    "ACP_TCK_AVAILABLE",
    "ZED_ACP_CLIENT_AVAILABLE",
)


def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        print(
            json.dumps(
                {
                    "SMC_ACCEPTANCE_RESULT": "FAIL",
                    "production_gate": "unpassed",
                    "conformance": "ACP_V1_ADAPTER_PROFILE_CONFORMANT",
                    "reason": "missing_live_credentials",
                    "missing": missing,
                    "cases": LIVE_CASES,
                    "zed_live": "unpassed",
                },
                ensure_ascii=False,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "SMC_ACCEPTANCE_RESULT": "FAIL",
                "production_gate": "unpassed",
                "conformance": "ACP_V1_ADAPTER_PROFILE_CONFORMANT",
                "reason": "live_acp_execution_not_run",
                "cases": LIVE_CASES,
                "zed_live": "unpassed",
            },
            ensure_ascii=False,
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
