"""Bind existing Docker containers as managed AI employee instances."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.cluster import Cluster, ClusterStatus
from app.models.deploy_record import DeployAction, DeployRecord, DeployStatus
from app.models.instance import Instance, InstanceStatus
from app.models.instance_member import InstanceMember, InstanceRole
from app.models.user import User
from app.schemas.docker_attach import (
    AttachableContainerInfo,
    AttachExistingInstanceRequest,
)
from app.services.deploy_service import EXPERT_RUNTIME
from app.services.docker_constants import get_docker_public_host
from app.services.docker_instance_layout_resolver import (
    layout_to_advanced_config,
    resolve_from_inspect,
)
from app.services.hermes_expert.expert_filesystem import validate_profile_slug
from app.services.runtime.compute.base import http_probe
from app.utils.display_status import compute_docker_display_status

logger = logging.getLogger(__name__)

DEFAULT_CONTAINER_PORT = 8787


def _container_name_for_profile(profile: str) -> str:
    return f"hermes-{profile}"


def _parse_image_tag(image: str | None) -> str:
    if not image:
        return "latest"
    if "@" in image:
        image = image.split("@", 1)[0]
    if ":" in image.rsplit("/", 1)[-1]:
        return image.rsplit(":", 1)[-1] or "latest"
    return "latest"


async def _docker_inspect(container_name: str) -> dict | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "inspect",
            container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0 or not stdout:
            return None
        data = json.loads(stdout.decode())
        if not data:
            return None
        return data[0]
    except Exception:
        logger.warning("docker inspect failed for %s", container_name, exc_info=True)
        return None


def _parse_health_status(inspect_data: dict) -> str | None:
    health = (inspect_data.get("State") or {}).get("Health")
    if not isinstance(health, dict):
        return None
    return health.get("Status")


def _profile_from_container_name(container_name: str) -> str | None:
    if not container_name.startswith("hermes-"):
        return None
    profile = container_name[len("hermes-"):].strip().lower()
    try:
        validate_profile_slug(profile)
    except BadRequestError:
        return None
    return profile


async def _build_container_info(
    layout,
    inspect_data: dict,
    *,
    data_dir: str,
    already_attached: bool,
    matched_instance_id: str | None,
) -> AttachableContainerInfo:
    state = inspect_data.get("State") or {}
    created_at = inspect_data.get("Created")
    gateway_status = None
    runtime_status = None
    mcp_status = None
    last_error = None
    last_probe_at = None

    if layout.gateway_url:
        from app.services.hermes_external.hermes_gateway_probe_service import HermesGatewayProbeService
        from app.services.hermes_external.hermes_runtime_status_service import HermesRuntimeStatusService

        probe = await HermesGatewayProbeService().probe_url(layout.gateway_url)
        gateway_status = probe.gateway_status
        last_probe_at = probe.last_probe_at.isoformat()
        last_error = probe.last_error
        docker_status = str(state.get("Status") or "unknown").lower()
        pair = HermesRuntimeStatusService().compute(
            docker_status=docker_status,
            gateway_status=gateway_status,
            gateway_port=layout.gateway_host_port,
        )
        runtime_status = pair.gateway_runtime_status
        mcp_status = pair.mcp_status
    elif layout.env_file:
        last_error = "missing HERMES_GATEWAY_PORT"
        runtime_status = "unconfigured"
        mcp_status = "unconfigured"
        gateway_status = "unconfigured"

    return AttachableContainerInfo(
        profile=layout.profile,
        container_name=layout.container_name,
        image=(inspect_data.get("Config") or {}).get("Image"),
        status=state.get("Status") or "unknown",
        health_status=_parse_health_status(inspect_data),
        host_port=layout.host_port,
        container_port=layout.container_port,
        data_dir=data_dir or layout.instance_root,
        compose_path=layout.compose_path,
        already_attached=already_attached,
        matched_instance_id=matched_instance_id,
        created_at=created_at,
        public_url=layout.public_url,
        health_url=layout.health_url,
        gateway_port=layout.gateway_host_port,
        gateway_url=layout.gateway_url,
        gateway_status=gateway_status,
        runtime_status=runtime_status,
        mcp_status=mcp_status,
        last_probe_at=last_probe_at,
        last_error=last_error,
        instance_root=layout.instance_root or None,
        host_data_dir=layout.host_data_dir or None,
        container_data_dir=layout.container_data_dir,
        env_file=layout.env_file or None,
        compose_project=layout.project_name,
        lifecycle_mode=layout.lifecycle_mode,
        attachable=layout.attachable,
        warnings=layout.warnings,
    )


async def _get_docker_cluster(cluster_id: str, db: AsyncSession) -> Cluster:
    result = await db.execute(
        select(Cluster).where(
            Cluster.id == cluster_id,
            Cluster.deleted_at.is_(None),
        )
    )
    cluster = result.scalar_one_or_none()
    if not cluster:
        raise NotFoundError("集群不存在", "errors.cluster.not_found")
    if cluster.compute_provider != "docker":
        raise BadRequestError(
            message="仅支持 Docker 集群绑定已有容器",
            message_key="errors.docker_attach.docker_cluster_required",
        )
    if cluster.status != ClusterStatus.connected:
        raise BadRequestError(
            message="Docker 集群未连接",
            message_key="errors.docker_attach.cluster_not_connected",
        )
    return cluster


async def _find_attachment_match(
    db: AsyncSession,
    org_id: str,
    profile: str,
    container_name: str,
) -> Instance | None:
    slug_result = await db.execute(
        select(Instance).where(
            Instance.org_id == org_id,
            Instance.slug == profile,
            Instance.deleted_at.is_(None),
        )
    )
    by_slug = slug_result.scalar_one_or_none()
    if by_slug:
        return by_slug

    result = await db.execute(
        select(Instance).where(
            Instance.org_id == org_id,
            Instance.deleted_at.is_(None),
            Instance.compute_provider == "docker",
        )
    )
    for instance in result.scalars().all():
        if not instance.advanced_config:
            continue
        try:
            advanced = json.loads(instance.advanced_config)
        except json.JSONDecodeError:
            continue
        if advanced.get("external_container_name") == container_name:
            return instance
    return None


async def _docker_ps_hermes_containers() -> list[str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "ps",
            "-a",
            "--filter",
            "name=hermes-",
            "--format",
            "{{.Names}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0 or not stdout:
            return []
        return [
            line.strip()
            for line in stdout.decode().splitlines()
            if line.strip().startswith("hermes-")
        ]
    except Exception:
        logger.warning("docker ps hermes containers failed", exc_info=True)
        return []


async def list_attachable_containers(
    db: AsyncSession,
    cluster_id: str,
    org_id: str,
    runtime: str,
) -> list[AttachableContainerInfo]:
    await _get_docker_cluster(cluster_id, db)
    if runtime != EXPERT_RUNTIME:
        raise BadRequestError(
            message="当前仅支持绑定 Hermes 专家服务容器",
            message_key="errors.docker_attach.unsupported_runtime",
        )

    items: list[AttachableContainerInfo] = []
    seen_container_names: set[str] = set()

    for container_name in await _docker_ps_hermes_containers():
        if container_name in seen_container_names:
            continue

        profile = _profile_from_container_name(container_name)
        if not profile:
            continue

        inspect_data = await _docker_inspect(container_name)
        if inspect_data is None:
            continue

        seen_container_names.add(container_name)
        scan_entry = None
        if profile:
            from app.services.docker_constants import get_docker_attach_scan_dirs
            for root in get_docker_attach_scan_dirs():
                candidate = root / profile
                if candidate.is_dir():
                    scan_entry = candidate
                    break

        layout = resolve_from_inspect(inspect_data, scan_entry=scan_entry)
        matched = await _find_attachment_match(db, org_id, profile, container_name)
        data_dir = layout.instance_root or (scan_entry and str(scan_entry)) or ""

        items.append(
            await _build_container_info(
                layout,
                inspect_data,
                data_dir=data_dir,
                already_attached=matched is not None,
                matched_instance_id=matched.id if matched else None,
            )
        )

    return sorted(items, key=lambda x: (x.host_port or 0, x.profile))


async def _probe_health(health_url: str | None, host_port: int | None) -> str:
    if health_url:
        result = await http_probe(health_url.rsplit("/health", 1)[0], path="/health")
        if result.get("healthy") is True:
            return "healthy"
        return "unhealthy"
    if host_port:
        result = await http_probe(f"http://localhost:{host_port}", path="/health")
        if result.get("healthy") is True:
            return "healthy"
        return "unhealthy"
    return "unknown"


def _rewrite_docker_callback_url(url: str | None) -> str:
    if not url:
        return ""
    from app.services.deploy_service import _rewrite_docker_callback_url

    return _rewrite_docker_callback_url(url)


def _map_docker_status_to_instance_status(docker_status: str) -> str:
    if docker_status == "running":
        return InstanceStatus.running
    if docker_status in {"exited", "created", "dead"}:
        return "stopped"
    if docker_status == "restarting":
        return InstanceStatus.restarting
    return "unknown"


async def attach_existing_container(
    db: AsyncSession,
    user: User,
    req: AttachExistingInstanceRequest,
    org_id: str,
) -> Instance:
    await _get_docker_cluster(req.cluster_id, db)
    if req.runtime != EXPERT_RUNTIME:
        raise BadRequestError(
            message="当前仅支持绑定 Hermes 专家服务容器",
            message_key="errors.docker_attach.unsupported_runtime",
        )

    container_name = req.container_name.strip()
    profile = validate_profile_slug(req.profile or _profile_from_container_name(container_name) or "")
    slug = validate_profile_slug(req.slug or profile, "slug")
    if slug != profile:
        raise BadRequestError(
            message="slug 必须与 profile 一致",
            message_key="errors.docker_attach.slug_profile_mismatch",
        )

    expected_container_name = _container_name_for_profile(profile)
    if container_name != expected_container_name:
        raise BadRequestError(
            message=f"容器名必须为 {expected_container_name}",
            message_key="errors.docker_attach.invalid_container_name",
        )

    inspect_data = await _docker_inspect(expected_container_name)
    if inspect_data is None:
        raise NotFoundError(
            message=f"容器 {expected_container_name} 不存在",
            message_key="errors.docker_attach.container_not_found",
        )

    scan_entry = None
    from app.services.docker_constants import get_docker_attach_scan_dirs
    for root in get_docker_attach_scan_dirs():
        candidate = root / profile
        if candidate.is_dir():
            scan_entry = candidate
            break

    layout = resolve_from_inspect(
        inspect_data,
        scan_entry=scan_entry,
        lifecycle_mode=req.lifecycle_mode,
    )
    if not layout.attachable:
        raise BadRequestError(
            message="无法识别容器 /data/hermes 的宿主机映射目录，请检查 volume 映射",
            message_key="errors.docker_attach.host_data_dir_missing",
        )

    if layout.host_data_dir and not Path(layout.host_data_dir).is_dir():
        raise BadRequestError(
            message=f"宿主机数据目录不存在: {layout.host_data_dir}",
            message_key="errors.docker_attach.host_data_dir_not_found",
        )

    host_port = layout.host_port or req.host_port
    if host_port is None:
        raise BadRequestError(
            message="无法识别 WebUI 端口",
            message_key="errors.docker_attach.host_port_missing",
        )

    matched = await _find_attachment_match(db, org_id, profile, expected_container_name)
    if matched:
        raise ConflictError(
            message=f"容器 {expected_container_name} 已绑定到实例",
            message_key="errors.docker_attach.already_attached",
        )

    docker_status = (inspect_data.get("State") or {}).get("Status") or "unknown"
    health_status = await _probe_health(layout.health_url, host_port)
    instance_status = _map_docker_status_to_instance_status(docker_status)

    image = (inspect_data.get("Config") or {}).get("Image") or req.image
    display_name = (req.display_name or req.name).strip()

    gateway_token = secrets.token_hex(24)
    env_vars = {
        "GATEWAY_TOKEN": gateway_token,
        "OPENCLAW_GATEWAY_TOKEN": gateway_token,
        "NODESKCLAW_TOKEN": gateway_token,
        "DOCKER_HOST_PORT": str(host_port),
    }
    api_url = _rewrite_docker_callback_url(settings.AGENT_API_BASE_URL)
    tunnel_url = _rewrite_docker_callback_url(settings.TUNNEL_BASE_URL)
    if api_url:
        env_vars["NODESKCLAW_API_URL"] = api_url
    if tunnel_url:
        env_vars["NODESKCLAW_TUNNEL_URL"] = tunnel_url

    advanced_config = layout_to_advanced_config(layout)
    if req.compose_path:
        advanced_config["compose"]["compose_path"] = req.compose_path
        advanced_config["paths"]["compose_path"] = req.compose_path

    public_host = get_docker_public_host()
    ingress_domain = f"{public_host}:{host_port}"

    instance = Instance(
        name=display_name,
        slug=profile,
        cluster_id=req.cluster_id,
        namespace=f"docker-{profile}",
        image_version=_parse_image_tag(image),
        replicas=1,
        service_type="docker",
        ingress_domain=ingress_domain,
        compute_provider="docker",
        runtime=EXPERT_RUNTIME,
        status=instance_status,
        health_status=health_status,
        proxy_token=gateway_token,
        wp_api_key=f"nodeskclaw-wp-{secrets.token_hex(32)}",
        env_vars=json.dumps(env_vars),
        advanced_config=json.dumps(advanced_config),
        storage_size="20Gi",
        created_by=user.id,
        org_id=org_id,
    )
    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    env_vars["NODESKCLAW_INSTANCE_ID"] = str(instance.id)
    instance.env_vars = json.dumps(env_vars)
    await db.commit()

    db.add(InstanceMember(
        instance_id=instance.id,
        user_id=user.id,
        role=InstanceRole.admin,
    ))

    now = datetime.now(timezone.utc)
    db.add(DeployRecord(
        instance_id=instance.id,
        revision=1,
        action=DeployAction.create,
        image_version=instance.image_version,
        status=DeployStatus.success,
        triggered_by=user.id,
        started_at=now,
        finished_at=now,
    ))
    await db.commit()
    await db.refresh(instance)

    if layout.env_file:
        from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
        binding = HermesDockerBindingService(db)
        await binding.upsert_from_env(
            org_id,
            layout.env_file,
            probe=True,
            instance_id=instance.id,
            managed_mode=layout.lifecycle_mode,
        )
        await db.commit()

    logger.info(
        "attached existing docker container: instance=%s profile=%s container=%s port=%s lifecycle=%s",
        instance.id,
        profile,
        expected_container_name,
        host_port,
        layout.lifecycle_mode,
    )
    return instance


async def sync_docker_instance_status(instance: Instance) -> dict:
    advanced = json.loads(instance.advanced_config or "{}")
    container_name = (
        advanced.get("external_container_name")
        or (advanced.get("compose") or {}).get("container_name")
        or _container_name_for_profile(instance.slug)
    )
    inspect_data = await _docker_inspect(container_name)
    if inspect_data is None:
        instance.health_status = "unhealthy"
        display_status = compute_docker_display_status("missing", instance.health_status)
        return {
            "status": "missing",
            "health_status": instance.health_status,
            "display_status": display_status,
            "last_error": "container missing",
        }

    docker_status = (inspect_data.get("State") or {}).get("Status") or "unknown"
    webui = advanced.get("webui") or {}
    health_url = webui.get("health_url")
    host_port = webui.get("host_port")
    health_status = await _probe_health(health_url, host_port)
    instance_status = _map_docker_status_to_instance_status(docker_status)
    instance.status = instance_status
    instance.health_status = health_status
    display_status = compute_docker_display_status(docker_status, health_status)
    last_error = None if display_status == "running" else "health check failed"
    return {
        "status": instance_status,
        "health_status": health_status,
        "display_status": display_status,
        "last_error": last_error,
    }
