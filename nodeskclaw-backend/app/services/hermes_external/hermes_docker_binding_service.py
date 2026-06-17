from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.instance import Instance
from app.services.docker_constants import get_docker_public_url, get_hermes_agent_host_ip, get_hermes_instances_root
from app.services.hermes_external.binding_type import get_instance_binding_type
from app.services.hermes_external.docker_container_inspect_service import DockerContainerInspectService
from app.services.hermes_external.hermes_env_parser import HermesEnvData, parse_env_file
from app.services.hermes_external.hermes_api_server_probe_service import HermesApiServerProbeService


@dataclass
class BindScanItem:
    id: str
    profile_name: str
    container_name: str
    docker_status: str
    docker_health: str
    webui_url: str | None
    gateway_url: str | None
    api_server_enabled: bool | None
    api_server_model_name: str | None
    has_api_server_key: bool
    api_server_status: str
    agent_call_status: str
    runtime_status: str
    mcp_status: str
    last_error: str | None
    bound: bool = True


@dataclass
class BindScanResult:
    scanned: int
    bound: int
    failed: int
    items: list[BindScanItem]


class HermesDockerBindingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._inspect = DockerContainerInspectService()
        self._probe = HermesApiServerProbeService()

    async def scan_existing(
        self,
        org_id: str,
        *,
        instances_root: str | None = None,
        probe_after_scan: bool | None = None,
        call_test: bool | None = None,
        instance_id: str | None = None,
    ) -> BindScanResult:
        root = Path(instances_root) if instances_root else get_hermes_instances_root()
        should_probe = (
            settings.HERMES_AUTO_PROBE_AFTER_SCAN if probe_after_scan is None else probe_after_scan
        )
        should_call_test = settings.HERMES_ENABLE_CALL_TEST if call_test is None else call_test
        items: list[BindScanItem] = []
        failed = 0
        scanned = 0

        if not root.is_dir():
            return BindScanResult(scanned=0, bound=0, failed=0, items=[])

        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue
            env_file = entry / ".env"
            if not env_file.is_file():
                continue
            scanned += 1
            try:
                item = await self._bind_directory(
                    org_id,
                    entry,
                    env_file,
                    probe=should_probe,
                    call_test=should_call_test,
                    instance_id=instance_id,
                )
                items.append(item)
            except Exception as exc:
                failed += 1
                profile = entry.name
                items.append(BindScanItem(
                    id="",
                    profile_name=profile,
                    container_name=f"hermes-{profile}",
                    docker_status="unknown",
                    docker_health="unknown",
                    webui_url=None,
                    gateway_url=None,
                    gateway_status="unknown",
                    runtime_status="unknown",
                    mcp_status="unknown",
                    last_error=str(exc),
                    bound=False,
                ))

        return BindScanResult(
            scanned=scanned,
            bound=len([i for i in items if i.bound]),
            failed=failed,
            items=items,
        )

    async def upsert_from_env(
        self,
        org_id: str,
        env_file: str | Path,
        *,
        probe: bool = True,
        instance_id: str | None = None,
        managed_mode: str | None = None,
    ) -> HermesAgentInstance:
        path = Path(env_file)
        env_data = parse_env_file(path, require_gateway_port=False)
        return await self._upsert_env_data(
            org_id,
            path.parent,
            path,
            env_data,
            probe=probe,
            instance_id=instance_id,
            managed_mode=managed_mode,
        )

    async def get_by_profile(self, org_id: str, profile_name: str) -> HermesAgentInstance | None:
        result = await self.db.execute(
            select(HermesAgentInstance).where(
                not_deleted(HermesAgentInstance),
                HermesAgentInstance.org_id == org_id,
                HermesAgentInstance.profile_name == profile_name,
            )
        )
        return result.scalar_one_or_none()

    async def list_instances(
        self,
        org_id: str,
        *,
        include_unavailable: bool = True,
        managed_mode: str | None = None,
    ) -> list[HermesAgentInstance]:
        pairs = await self.list_all_with_instances(org_id)
        records: list[HermesAgentInstance] = []
        for record, _instance in pairs:
            if managed_mode and record.managed_mode != managed_mode:
                continue
            if not include_unavailable and record.gateway_runtime_status != "ready":
                continue
            records.append(record)
        return records

    async def list_bound_pairs(self, org_id: str) -> list[tuple[HermesAgentInstance, Instance]]:
        from app.services.hermes_external.hermes_bound_agent_scope_service import (
            HermesBoundAgentScopeService,
        )
        return await HermesBoundAgentScopeService(self.db).list_bound_pairs(org_id)

    async def list_all_with_instances(
        self,
        org_id: str,
    ) -> list[tuple[HermesAgentInstance, Instance | None]]:
        stmt = (
            select(HermesAgentInstance)
            .where(
                not_deleted(HermesAgentInstance),
                HermesAgentInstance.org_id == org_id,
            )
            .order_by(HermesAgentInstance.profile_name)
        )
        result = await self.db.execute(stmt)
        records = list(result.scalars().all())
        pairs: list[tuple[HermesAgentInstance, Instance | None]] = []
        for record in records:
            instance = None
            if record.instance_id:
                inst_result = await self.db.execute(
                    select(Instance).where(
                        Instance.id == record.instance_id,
                        not_deleted(Instance),
                    )
                )
                instance = inst_result.scalar_one_or_none()
            pairs.append((record, instance))
        return pairs

    async def list_instances_for_api(
        self,
        org_id: str,
        *,
        include_unbound: bool = False,
        include_unavailable: bool = True,
        managed_mode: str | None = None,
    ) -> list[tuple[HermesAgentInstance, Instance | None]]:
        pairs = (
            await self.list_all_with_instances(org_id)
            if include_unbound
            else [(record, instance) for record, instance in await self.list_bound_pairs(org_id)]
        )
        filtered: list[tuple[HermesAgentInstance, Instance | None]] = []
        for record, instance in pairs:
            if managed_mode and record.managed_mode != managed_mode:
                continue
            if not include_unavailable and record.gateway_runtime_status != "ready":
                continue
            filtered.append((record, instance))
        return filtered

    async def get_linked_instance(self, record: HermesAgentInstance) -> Instance | None:
        if not record.instance_id:
            return None
        result = await self.db.execute(
            select(Instance).where(
                Instance.id == record.instance_id,
                not_deleted(Instance),
            )
        )
        return result.scalar_one_or_none()

    async def probe_one(self, org_id: str, profile_name: str) -> HermesAgentInstance:
        record = await self.get_by_profile(org_id, profile_name)
        if not record:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Hermes Agent 实例不存在", "errors.hermes.agent_instance_not_found")
        return await self._probe_record(record)

    async def probe_all(self, org_id: str, *, include_unbound: bool = False) -> list[HermesAgentInstance]:
        if include_unbound:
            records = [record for record, _instance in await self.list_all_with_instances(org_id)]
        else:
            records = [record for record, _instance in await self.list_bound_pairs(org_id)]
        updated: list[HermesAgentInstance] = []
        for record in records:
            updated.append(await self._probe_record(record))
        await self.db.flush()
        return updated

    async def link_instance(self, org_id: str, profile_name: str, instance_id: str) -> HermesAgentInstance | None:
        record = await self.get_by_profile(org_id, profile_name)
        if not record:
            return None
        record.instance_id = instance_id
        await self.db.flush()
        return record

    async def _bind_directory(
        self,
        org_id: str,
        instance_dir: Path,
        env_file: Path,
        *,
        probe: bool,
        call_test: bool,
        instance_id: str | None,
    ) -> BindScanItem:
        env_data = parse_env_file(env_file, require_gateway_port=False)
        record = await self._upsert_env_data(
            org_id,
            instance_dir,
            env_file,
            env_data,
            probe=probe,
            call_test=call_test,
            instance_id=instance_id,
        )
        return BindScanItem(
            id=record.id,
            profile_name=record.profile_name,
            container_name=record.container_name,
            docker_status=record.docker_status,
            docker_health=record.docker_health,
            webui_url=record.webui_url,
            gateway_url=record.gateway_url,
            api_server_enabled=env_data.api_server_enabled,
            api_server_model_name=env_data.api_server_model_name,
            has_api_server_key=env_data.has_api_server_key,
            api_server_status=record.gateway_status,
            agent_call_status=record.mcp_status,
            runtime_status=record.gateway_runtime_status,
            mcp_status=record.mcp_status,
            last_error=record.last_error,
            bound=True,
        )

    async def _upsert_env_data(
        self,
        org_id: str,
        instance_dir: Path,
        env_file: Path,
        env_data: HermesEnvData,
        *,
        probe: bool,
        call_test: bool = False,
        instance_id: str | None,
        managed_mode: str | None = None,
    ) -> HermesAgentInstance:
        now = datetime.now(timezone.utc)
        host_ip = get_hermes_agent_host_ip()
        profile = env_data.profile_name or instance_dir.name
        container_name = env_data.container_name or f"hermes-{profile}"

        webui_url = get_docker_public_url(env_data.webui_port) if env_data.webui_port else None
        gateway_url = get_docker_public_url(env_data.gateway_port) if env_data.gateway_port else None

        inspect_result = await self._inspect.inspect(
            container_name,
            gateway_port=env_data.gateway_port,
            webui_port=env_data.webui_port,
        )

        compose_file = None
        compose_project = None
        for candidate in (instance_dir / "docker-compose.yml", instance_dir.parent / "docker-compose.yml"):
            if candidate.is_file():
                compose_file = str(candidate)
                break
        labels = ((inspect_result.inspect_data or {}).get("Config") or {}).get("Labels") or {}
        compose_project = labels.get("com.docker.compose.project")

        api_server_status = "unconfigured"
        runtime_status = "unconfigured"
        agent_call_status = "not_callable"
        last_error = inspect_result.last_error or ("; ".join(env_data.errors) if env_data.errors else None)
        last_probe_at = None

        if not env_data.gateway_port:
            api_server_status = "unconfigured"
            runtime_status = "unconfigured"
            agent_call_status = "not_callable"
            last_error = last_error or "missing HERMES_GATEWAY_PORT"
        elif not inspect_result.gateway_port_mapped:
            api_server_status = "offline"
            runtime_status = "degraded" if inspect_result.docker_status == "running" else "unavailable"
            agent_call_status = "not_callable"
            last_error = last_error or "HERMES_GATEWAY_PORT not mapped to API_SERVER_PORT"
        else:
            if probe and gateway_url:
                probe_result = await self._probe.probe_env(
                    env_file=env_file,
                    gateway_url=gateway_url,
                    call_test=call_test,
                )
                api_server_status = probe_result.api_server_status
                runtime_status = probe_result.runtime_status
                agent_call_status = probe_result.agent_call_status
                last_probe_at = probe_result.last_probe_at
                last_error = probe_result.last_error or last_error
            else:
                api_server_status = "unknown"
                runtime_status = "unknown" if inspect_result.docker_status == "running" else "unavailable"
                agent_call_status = "unknown"

        record = await self.get_by_profile(org_id, profile)
        if not record:
            record = HermesAgentInstance(
                id=str(uuid.uuid4()),
                org_id=org_id,
                profile_name=profile,
                container_name=container_name,
            )
            self.db.add(record)

        record.instance_id = instance_id or record.instance_id
        record.container_name = container_name
        record.container_id = inspect_result.container_id
        record.image = inspect_result.image
        record.docker_status = inspect_result.docker_status
        record.docker_health = inspect_result.docker_health
        record.host_ip = host_ip
        record.webui_port = env_data.webui_port
        record.webui_url = webui_url
        record.gateway_port = env_data.gateway_port
        record.gateway_url = gateway_url
        record.gateway_status = api_server_status
        record.gateway_runtime_status = runtime_status
        record.mcp_status = agent_call_status
        record.instance_dir = str(instance_dir)
        record.data_dir = env_data.data_dir
        record.env_file = str(env_file)
        record.compose_file = compose_file
        record.compose_project = compose_project
        record.managed_mode = managed_mode or record.managed_mode or "external_docker"
        record.last_probe_at = last_probe_at
        record.last_seen_at = now
        record.last_error = last_error

        await self.db.flush()
        return record

    async def _probe_record(self, record: HermesAgentInstance) -> HermesAgentInstance:
        if not record.gateway_url:
            record.gateway_status = "unconfigured"
            record.gateway_runtime_status = "unconfigured"
            record.mcp_status = "not_callable"
            record.last_error = record.last_error or "missing HERMES_GATEWAY_PORT"
            return record

        inspect_result = await self._inspect.inspect(
            record.container_name,
            gateway_port=record.gateway_port,
            webui_port=record.webui_port,
        )
        record.docker_status = inspect_result.docker_status
        record.docker_health = inspect_result.docker_health
        record.container_id = inspect_result.container_id
        record.image = inspect_result.image

        probe_result = await self._probe.probe_env(
            env_file=record.env_file or "",
            gateway_url=record.gateway_url,
            call_test=False,
        )
        record.gateway_status = probe_result.api_server_status
        record.gateway_runtime_status = probe_result.runtime_status
        record.mcp_status = probe_result.agent_call_status
        record.last_probe_at = probe_result.last_probe_at
        record.last_error = probe_result.last_error or inspect_result.last_error
        await self.db.flush()
        return record

    @staticmethod
    def to_api_dict(record: HermesAgentInstance, instance: Instance | None = None) -> dict:
        env = None
        if record.env_file:
            try:
                env = parse_env_file(Path(record.env_file), require_gateway_port=False)
            except Exception:
                env = None
        binding_type = None
        employee_name = None
        instance_status = None
        is_bound = False
        if instance is not None:
            binding_type = get_instance_binding_type(instance)
            employee_name = instance.name
            status = instance.status
            instance_status = status.value if hasattr(status, "value") else str(status)
            is_bound = binding_type == "external_docker"
        return {
            "id": record.id,
            "profile_name": record.profile_name,
            "container_name": record.container_name,
            "container_id": record.container_id,
            "image": record.image,
            "docker_status": record.docker_status,
            "docker_health": record.docker_health,
            "host_ip": record.host_ip,
            "webui_port": record.webui_port,
            "webui_url": record.webui_url,
            "gateway_port": record.gateway_port,
            "gateway_url": record.gateway_url,
            "api_server_enabled": env.api_server_enabled if env else None,
            "api_server_model_name": env.api_server_model_name if env else None,
            "has_api_server_key": env.has_api_server_key if env else None,
            "api_server_status": record.gateway_status,
            "agent_call_status": record.mcp_status,
            "gateway_status": record.gateway_status,
            "runtime_status": record.gateway_runtime_status,
            "mcp_status": record.mcp_status,
            "instance_dir": record.instance_dir,
            "data_dir": record.data_dir,
            "env_file": record.env_file,
            "compose_file": record.compose_file,
            "compose_project": record.compose_project,
            "managed_mode": record.managed_mode,
            "instance_id": record.instance_id,
            "employee_name": employee_name,
            "binding_type": binding_type,
            "instance_status": instance_status,
            "is_bound": is_bound,
            "last_probe_at": record.last_probe_at.isoformat() if record.last_probe_at else None,
            "last_seen_at": record.last_seen_at.isoformat() if record.last_seen_at else None,
            "last_error": record.last_error,
        }
