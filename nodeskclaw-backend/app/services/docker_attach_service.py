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
from app.services.docker_constants import (
    DOCKER_HOST_DATA_DIR,
    get_docker_attach_scan_dirs,
)
from app.services.hermes_expert.expert_filesystem import validate_profile_slug
from app.services.runtime.compute.base import http_probe

logger = logging.getLogger(__name__)

DEFAULT_CONTAINER_PORT = 8787

class _ProfileDir:
    def __init__(self, profile: str, data_dir: str, compose_path: str | None = None) -> None:
        self.profile = profile
        self.data_dir = data_dir
        self.compose_path = compose_path

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


def _parse_ports(inspect_data: dict) -> tuple[int | None, int | None]:
    ports = (inspect_data.get("NetworkSettings") or {}).get("Ports") or {}
    for key, bindings in ports.items():
        if not bindings:
            continue
        binding = bindings[0] if isinstance(bindings, list) and bindings else None
        if not binding:
            continue
        host_port_raw = binding.get("HostPort")
        if not host_port_raw:
            continue
        container_port_raw = key.split("/")[0]
        try:
            return int(host_port_raw), int(container_port_raw)
        except (TypeError, ValueError):
            continue
    return None, DEFAULT_CONTAINER_PORT


def _parse_health_status(inspect_data: dict) -> str | None:
    health = (inspect_data.get("State") or {}).get("Health")
    if not isinstance(health, dict):
        return None
    return health.get("Status")


def _build_container_info(
    profile: str,
    inspect_data: dict,
    *,
    data_dir: str,
    compose_path: str | None,
    already_attached: bool,
    matched_instance_id: str | None,
) -> AttachableContainerInfo:
    container_name = _container_name_for_profile(profile)
    state = inspect_data.get("State") or {}
    host_port, container_port = _parse_ports(inspect_data)
    created_at = inspect_data.get("Created")
    return AttachableContainerInfo(
        profile=profile,
        container_name=container_name,
        image=(inspect_data.get("Config") or {}).get("Image"),
        status=state.get("Status") or "unknown",
        health_status=_parse_health_status(inspect_data),
        host_port=host_port,
        container_port=container_port,
        data_dir=data_dir,
        compose_path=compose_path,
        already_attached=already_attached,
        matched_instance_id=matched_instance_id,
        created_at=created_at,
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


def _list_profile_dirs() -> list[_ProfileDir]:
    profiles: list[_ProfileDir] = []
    seen: set[str] = set()

    for root in get_docker_attach_scan_dirs():
        if not root.is_dir():
            logger.info("docker attach scan dir not found: %s", root)
            continue

        for entry in sorted(root.iterdir()):
            if not entry.is_dir():
                continue

            profile = entry.name.strip().lower()
            try:
                validate_profile_slug(profile)
            except BadRequestError:
                continue

            container_name = _container_name_for_profile(profile)
            if container_name in seen:
                continue
            seen.add(container_name)

            compose_path = entry / "docker-compose.yml"
            profiles.append(
                _ProfileDir(
                    profile=profile,
                    data_dir=str(entry),
                    compose_path=str(compose_path) if compose_path.exists() else None,
                )
            )

    return profiles

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


def _profile_from_container_name(container_name: str) -> str | None:
    if not container_name.startswith("hermes-"):
        return None
    profile = container_name[len("hermes-"):].strip().lower()
    try:
        validate_profile_slug(profile)
    except BadRequestError:
        return None
    return profile


def _data_dir_from_mounts(inspect_data: dict, profile: str) -> str:
    mounts = inspect_data.get("Mounts") or []
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        destination = str(mount.get("Destination") or "")
        source = str(mount.get("Source") or "")
        if destination in {"/data/hermes", "/root/.hermes"} and source:
            return source

    return str(Path(DOCKER_HOST_DATA_DIR) / profile)


def _compose_path_for_data_dir(data_dir: str) -> str | None:
    path = Path(data_dir) / "docker-compose.yml"
    return str(path) if path.exists() else None

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

    # 1. 先按配置目录扫描
    for profile_dir in _list_profile_dirs():
        profile = profile_dir.profile
        container_name = _container_name_for_profile(profile)
        inspect_data = await _docker_inspect(container_name)
        if inspect_data is None:
            continue

        seen_container_names.add(container_name)
        matched = await _find_attachment_match(db, org_id, profile, container_name)

        items.append(
            _build_container_info(
                profile,
                inspect_data,
                data_dir=profile_dir.data_dir,
                compose_path=profile_dir.compose_path,
                already_attached=matched is not None,
                matched_instance_id=matched.id if matched else None,
            )
        )

    # 2. 再从 docker ps 兜底扫描 hermes-* 容器
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
        data_dir = _data_dir_from_mounts(inspect_data, profile)
        compose_path = _compose_path_for_data_dir(data_dir)
        matched = await _find_attachment_match(db, org_id, profile, container_name)

        items.append(
            _build_container_info(
                profile,
                inspect_data,
                data_dir=data_dir,
                compose_path=compose_path,
                already_attached=matched is not None,
                matched_instance_id=matched.id if matched else None,
            )
        )

    return sorted(items, key=lambda x: (x.host_port or 0, x.profile))


async def _probe_health(host_port: int) -> str:
    result = await http_probe(f"http://localhost:{host_port}", path="/health")
    if result.get("healthy") is True:
        return "healthy"
    return "unknown"


def _rewrite_docker_callback_url(url: str | None) -> str:
    if not url:
        return ""
    from app.services.deploy_service import _rewrite_docker_callback_url

    return _rewrite_docker_callback_url(url)


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

    profile = validate_profile_slug(req.profile)
    slug = validate_profile_slug(req.slug, "slug")
    if slug != profile:
        raise BadRequestError(
            message="slug 必须与 profile 一致",
            message_key="errors.docker_attach.slug_profile_mismatch",
        )

    expected_container_name = _container_name_for_profile(profile)
    if req.container_name != expected_container_name:
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

    status = (inspect_data.get("State") or {}).get("Status")
    if status != "running":
        raise BadRequestError(
            message=f"容器当前状态为 {status or 'unknown'}，仅 running 状态可绑定",
            message_key="errors.docker_attach.container_not_running",
        )

    host_port, container_port = _parse_ports(inspect_data)
    if host_port is None:
        host_port = req.host_port
    if container_port is None:
        container_port = DEFAULT_CONTAINER_PORT

    matched = await _find_attachment_match(db, org_id, profile, expected_container_name)
    if matched:
        raise ConflictError(
            message=f"容器 {expected_container_name} 已绑定到实例",
            message_key="errors.docker_attach.already_attached",
        )

    image = (inspect_data.get("Config") or {}).get("Image") or req.image
    health_status = await _probe_health(host_port)

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

    advanced_config = {
        "attach_mode": "external",
        "external_lifecycle": False,
        "external_dir": profile,
        "external_container_name": expected_container_name,
        "compose_path": req.compose_path or _compose_path_for_data_dir(req.data_dir),
        "expert": {
            "profile": profile,
            "template": profile,
        },
        "webui": {
            "port": host_port,
            "container_port": container_port,
        },
        "compose": {
            "container_name": expected_container_name,
            "compose_path": req.compose_path or _compose_path_for_data_dir(req.data_dir),
        },
    }

    instance = Instance(
        name=req.name.strip(),
        slug=profile,
        cluster_id=req.cluster_id,
        namespace=f"docker-{profile}",
        image_version=_parse_image_tag(image),
        replicas=1,
        service_type="docker",
        ingress_domain=f"localhost:{host_port}",
        compute_provider="docker",
        runtime=EXPERT_RUNTIME,
        status=InstanceStatus.running,
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

    logger.info(
        "attached existing docker container: instance=%s profile=%s container=%s port=%s",
        instance.id,
        profile,
        expected_container_name,
        host_port,
    )
    return instance
