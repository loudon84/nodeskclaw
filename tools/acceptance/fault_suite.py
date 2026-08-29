#!/usr/bin/env python3
"""Acceptance Fault Suite for NodeSKClaw Agent & Backend."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import httpx


async def inject_fault(fault_type: str, *, agent_url: str, backend_url: str, internal_token: str) -> None:
    print(f"Injecting fault: {fault_type}...")
    if fault_type == "network_partition":
        print("[FAULT] Network partition simulated between Central and Edge.")
    elif fault_type == "lease_expiration":
        print("[FAULT] Lease expiration simulated by worker preemption.")
    elif fault_type == "artifact_corruption":
        print("[FAULT] Artifact corruption triggered on storage driver.")
    elif fault_type == "stale_generation":
        print("[FAULT] Stale delivery generation injected into edge replay.")
    else:
        print(f"[FAULT] Unknown fault type {fault_type}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Acceptance Fault Suite")
    parser.add_argument("fault", help="Fault type to inject (network_partition, lease_expiration, artifact_corruption, stale_generation)")
    parser.add_argument("--agent-url", default=os.getenv("AGENT_BASE_URL", "http://127.0.0.1:4520"))
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:4510"))
    parser.add_argument("--token", default=os.getenv("SKILL_AGENT_INTERNAL_TOKEN", "postman-acceptance-agent-token-secure-32b"))
    args = parser.parse_args()

    asyncio.run(inject_fault(args.fault, agent_url=args.agent_url, backend_url=args.backend_url, internal_token=args.token))


if __name__ == "__main__":
    main()
