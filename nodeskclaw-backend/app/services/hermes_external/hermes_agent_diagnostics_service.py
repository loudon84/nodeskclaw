from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.services.hermes_external.docker_container_inspect_service import DockerContainerInspectService
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_external.hermes_gateway_probe_service import HermesGatewayProbeService


@dataclass
class DiagnosticCheck:
    name: str
    status: str
    message: str


class HermesAgentDiagnosticsService:
    def __init__(self) -> None:
        self._inspect = DockerContainerInspectService()
        self._probe = HermesGatewayProbeService()

    async def build_checks(self, record: HermesAgentInstance) -> list[DiagnosticCheck]:
        checks: list[DiagnosticCheck] = []
        env_path = Path(record.env_file) if record.env_file else None
        if env_path and env_path.is_file():
            checks.append(DiagnosticCheck("env_file_exists", "pass", ".env exists"))
            try:
                env_data = parse_env_file(env_path, require_gateway_port=False)
                if env_data.gateway_port:
                    checks.append(DiagnosticCheck(
                        "gateway_port_configured",
                        "pass",
                        f"HERMES_GATEWAY_PORT={env_data.gateway_port}",
                    ))
                else:
                    checks.append(DiagnosticCheck(
                        "gateway_port_configured",
                        "fail",
                        "HERMES_GATEWAY_PORT missing",
                    ))
            except Exception as exc:
                checks.append(DiagnosticCheck("gateway_port_configured", "fail", str(exc)))
        else:
            checks.append(DiagnosticCheck("env_file_exists", "fail", ".env missing"))

        inspect_result = await self._inspect.inspect(
            record.container_name,
            gateway_port=record.gateway_port,
            webui_port=record.webui_port,
        )
        if inspect_result.docker_status == "missing":
            checks.append(DiagnosticCheck(
                "container_exists",
                "fail",
                f"container {record.container_name} not found",
            ))
        else:
            checks.append(DiagnosticCheck(
                "container_exists",
                "pass",
                f"container {record.container_name} exists",
            ))
            if inspect_result.docker_status == "running":
                checks.append(DiagnosticCheck("container_running", "pass", "container is running"))
            else:
                checks.append(DiagnosticCheck(
                    "container_running",
                    "fail",
                    f"container status is {inspect_result.docker_status}",
                ))

        if record.gateway_url:
            probe = await self._probe.probe_url(record.gateway_url)
            if probe.gateway_status == "online":
                checks.append(DiagnosticCheck(
                    "gateway_probe",
                    "pass",
                    f"GET {probe.probe_path} returned {probe.status_code}",
                ))
            else:
                checks.append(DiagnosticCheck(
                    "gateway_probe",
                    "fail",
                    probe.last_error or probe.gateway_status,
                ))
        else:
            checks.append(DiagnosticCheck("gateway_probe", "fail", "gateway_url not configured"))

        return checks
