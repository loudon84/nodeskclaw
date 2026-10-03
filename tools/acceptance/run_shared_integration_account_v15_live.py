from __future__ import annotations

import json
import os
import sys

LIVE_CASES = [f"LIVE-SHARED-{index:03d}" for index in range(1, 19)]
REQUIRED_ENV = (
    "NODESKCLAW_BACKEND_URL",
    "NODESKCLAW_TASK_URL",
    "NODESKCLAW_AGENT_URL",
    "COMPOSIO_API_KEY",
    "NODESKCLAW_SHARED_INTEGRATION_TEST_ACCOUNT",
)


def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
    if missing:
        print(
            json.dumps(
                {
                    "SMC_ACCEPTANCE_RESULT": "FAIL",
                    "production_gate": "unpassed",
                    "reason": "missing_live_credentials",
                    "missing": missing,
                    "cases": LIVE_CASES,
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
                "reason": "live_shared_integration_execution_not_run",
                "cases": LIVE_CASES,
            },
            ensure_ascii=False,
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
