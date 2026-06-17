"""Wait for Hermes Docker container and API Server recovery after restart."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.services.hermes_external.hermes_api_server_probe_service import HermesApiServerProbeService


@dataclass
class RuntimeRecoveryResult:
    recovered: bool
    docker_status: str
    api_server_status: str
    agent_call_status: str
    runtime_status: str
    error_code: str | None = None
    message: str | None = None


async def _docker_container_status(container_name: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "inspect",
        "--format",
        "{{json .State.Status}}",
        container_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    if proc.returncode != 0:
        return "unknown"
    try:
        return json.loads(stdout.decode().strip().strip('"'))
    except (json.JSONDecodeError, ValueError):
        return "unknown"


async def wait_for_runtime_recovery(
    *,
    container_name: str,
    gateway_url: str | None,
    env_file: Path,
) -> RuntimeRecoveryResult:
    timeout = settings.HERMES_RESTART_WAIT_TIMEOUT_SECONDS
    interval = settings.HERMES_RESTART_POLL_INTERVAL_SECONDS
    probe = HermesApiServerProbeService()
    deadline = asyncio.get_event_loop().time() + timeout
    last_docker_status = "unknown"
    last_probe = None

    while asyncio.get_event_loop().time() < deadline:
        last_docker_status = await _docker_container_status(container_name)
        if last_docker_status != "running":
            await asyncio.sleep(interval)
            continue

        if not gateway_url or not env_file.is_file():
            return RuntimeRecoveryResult(
                recovered=False,
                docker_status=last_docker_status,
                api_server_status="unknown",
                agent_call_status="unknown",
                runtime_status="degraded",
                error_code="HERMES_RUNTIME_RECOVERY_TIMEOUT",
                message="容器已运行，但缺少 Gateway 或 Runtime .env，无法确认 API Server 状态",
            )

        last_probe = await probe.probe_env(
            env_file=env_file,
            gateway_url=gateway_url,
            call_test=False,
        )
        if last_probe.runtime_status == "ready":
            return RuntimeRecoveryResult(
                recovered=True,
                docker_status=last_docker_status,
                api_server_status=last_probe.api_server_status,
                agent_call_status=last_probe.agent_call_status,
                runtime_status=last_probe.runtime_status,
                message="Runtime 已恢复",
            )
        await asyncio.sleep(interval)

    return RuntimeRecoveryResult(
        recovered=False,
        docker_status=last_docker_status,
        api_server_status=last_probe.api_server_status if last_probe else "unknown",
        agent_call_status=last_probe.agent_call_status if last_probe else "unknown",
        runtime_status=last_probe.runtime_status if last_probe else "degraded",
        error_code="HERMES_RUNTIME_RECOVERY_TIMEOUT",
        message=f"文件已保存，容器已重启，但 Runtime 未在 {timeout} 秒内恢复",
    )
