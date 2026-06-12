"""Expert instance orchestration on top of deploy_service."""

from __future__ import annotations

import asyncio
import json
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.cluster import Cluster
from app.models.instance import Instance
from app.models.user import User
from app.schemas.deploy import DeployRequest
from app.services import deploy_service
from app.services.docker_attach_service import sync_docker_instance_status
from app.services.docker_constants import (
    HERMES_EXPERT_PORT_END,
    HERMES_EXPERT_PORT_START,
    get_docker_public_url,
)
from app.services.hermes_expert.expert_filesystem import validate_profile_slug
from app.services.hermes_expert.expert_skill_service import EXPERT_RUNTIME, ExpertSkillService
from app.services.hermes_expert.schemas import (
    CreateExpertInstanceRequest,
    CreateExpertInstanceResponse,
    ExpertHealthInfo,
    ExpertInstanceInfo,
)
from app.services.runtime.compute.base import http_probe
from app.services.runtime.registries.runtime_registry import RUNTIME_REGISTRY
from app.utils.display_status import compute_docker_display_status, compute_display_status

WEBUI_PASSWORD_KEY = "HERMES_WEBUI_PASSWORD"


class ExpertInstanceService:
    def __init__(self) -> None:
        self.skill_service = ExpertSkillService()

    async def create_instance(
        self,
        req: CreateExpertInstanceRequest,
        user: User,
        db: AsyncSession,
        org_id: str | None = None,
    ) -> CreateExpertInstanceResponse:
        effective_org_id = org_id or user.current_org_id
        if not effective_org_id:
            raise BadRequestError("缺少目标组织", "errors.org.org_required")

        profile = validate_profile_slug(req.profile)
        template = validate_profile_slug(req.expert_template, "expert_template")
        if RUNTIME_REGISTRY.get(EXPERT_RUNTIME) is None:
            raise BadRequestError(
                message="Hermes 专家 runtime 未注册",
                message_key="errors.validation.invalid_runtime",
            )

        cluster = await self._get_docker_cluster(req.cluster_id, db)
        hindsight_api_url = (
            req.hindsight_api_url
            or settings.HERMES_EXPERT_DEFAULT_HINDSIGHT_API_URL
            or ""
        ).strip()
        hindsight_bank_id = (req.hindsight_bank_id or f"hermes-{profile}").strip()
        webui_port = req.webui_port
        if webui_port is not None and (
            webui_port < HERMES_EXPERT_PORT_START or webui_port > HERMES_EXPERT_PORT_END
        ):
            raise BadRequestError(
                message=f"WebUI 端口必须在 {HERMES_EXPERT_PORT_START}-{HERMES_EXPERT_PORT_END} 范围内",
                message_key="errors.hermes_expert.invalid_port",
            )

        webui_password = secrets.token_urlsafe(16)
        slug = profile
        advanced_config: dict[str, Any] = {
            "expert": {
                "profile": profile,
                "template": template,
                "template_version": "0.1.0",
            },
            "webui": {
                "host": settings.HERMES_EXPERT_DEFAULT_BIND_HOST,
                "port": webui_port,
                "container_port": 8787,
            },
            "hindsight": {
                "mode": "local_external",
                "api_url": hindsight_api_url,
                "bank_id": hindsight_bank_id,
            },
            "obsidian": {
                "enabled": req.init_obsidian_vault,
                "vault_path": "obsidian-vault",
            },
            "skills": {
                "default_bundle": req.default_skill_bundle or template,
                "install_default": req.install_default_skills,
                "index_path": "skills/.index.json",
            },
            "compose": {
                "project_name": f"hermes-{profile}",
            },
        }
        if webui_port is not None:
            advanced_config["webui"]["port"] = webui_port

        env_vars = dict(req.env_vars or {})
        env_vars[WEBUI_PASSWORD_KEY] = webui_password
        if webui_port is not None:
            env_vars["DOCKER_HOST_PORT"] = str(webui_port)

        deploy_req = DeployRequest(
            cluster_id=cluster.id,
            name=req.name.strip(),
            slug=slug,
            org_id=effective_org_id,
            image_version=req.image_version or "latest",
            env_vars=env_vars,
            advanced_config=advanced_config,
            llm_configs=req.llm_configs,
            runtime=EXPERT_RUNTIME,
            storage_size="20Gi",
        )

        deploy_id, ctx = await deploy_service.deploy_instance(
            deploy_req,
            user,
            db,
            org_id=effective_org_id,
        )
        task = asyncio.create_task(
            deploy_service.execute_deploy_pipeline(ctx),
            name=f"deploy-expert-{deploy_id}",
        )
        deploy_service.register_deploy_task(deploy_id, task)

        host = settings.HERMES_EXPERT_DEFAULT_BIND_HOST or "localhost"
        port_display = webui_port or HERMES_EXPERT_PORT_START
        return CreateExpertInstanceResponse(
            instance_id=ctx.instance_id,
            deploy_id=deploy_id,
            profile=profile,
            webui_url=get_docker_public_url(port_display) if host == "localhost" else f"http://{host}:{port_display}",
            webui_password=webui_password,
            status="deploying",
        )

    async def list_instances(
        self,
        db: AsyncSession,
        org_id: str | None,
        *,
        refresh_status: bool = False,
    ) -> list[ExpertInstanceInfo]:
        query = select(Instance).where(
            not_deleted(Instance),
            Instance.runtime == EXPERT_RUNTIME,
        )
        if org_id:
            query = query.where(Instance.org_id == org_id)
        query = query.order_by(Instance.created_at.desc())
        result = await db.execute(query)
        instances = list(result.scalars().all())
        if refresh_status:
            for instance in instances:
                if instance.compute_provider == "docker":
                    await sync_docker_instance_status(instance)
            await db.commit()
        return [self._to_info(inst) for inst in instances]

    async def get_instance(self, instance_id: str, db: AsyncSession) -> ExpertInstanceInfo:
        instance = await self._get_expert_instance(instance_id, db)
        return self._to_info(instance)

    async def get_logs(self, instance_id: str, db: AsyncSession, *, tail: int = 100) -> str:
        from app.services import instance_service
        instance = await self._get_expert_instance(instance_id, db)
        return await instance_service.get_pod_logs(
            instance_id, instance.slug, db, tail_lines=tail,
        )

    async def restart(self, instance_id: str, db: AsyncSession) -> None:
        instance = await self._get_expert_instance(instance_id, db)
        await self._run_lifecycle_action(instance, "restart")

    async def stop(self, instance_id: str, db: AsyncSession) -> None:
        instance = await self._get_expert_instance(instance_id, db)
        await self._run_lifecycle_action(instance, "stop")
        instance.status = "stopped"
        await db.commit()

    async def start(self, instance_id: str, db: AsyncSession) -> None:
        instance = await self._get_expert_instance(instance_id, db)
        await self._run_lifecycle_action(instance, "start")
        instance.status = "running"
        await db.commit()

    async def detach(self, instance_id: str, db: AsyncSession) -> None:
        from app.services import instance_service

        instance = await self._get_expert_instance(instance_id, db)
        advanced = json.loads(instance.advanced_config or "{}")
        if advanced.get("attach_mode") != "external":
            raise BadRequestError(
                message="仅外部关联实例支持解除关联",
                message_key="errors.docker_attach.detach_not_supported",
            )
        await instance_service.finalize_instance_deletion_once(instance_id, db)

    async def sync_status(self, instance_id: str, db: AsyncSession) -> dict:
        instance = await self._get_expert_instance(instance_id, db)
        if instance.compute_provider != "docker":
            display_status = compute_display_status(instance.status, instance.health_status or "unknown")
            return {
                "status": instance.status,
                "health_status": instance.health_status,
                "display_status": display_status,
                "last_error": None,
            }
        payload = await sync_docker_instance_status(instance)
        await db.commit()
        return payload

    async def delete(self, instance_id: str, db: AsyncSession) -> None:
        from app.services import instance_service

        instance = await self._get_expert_instance(instance_id, db)
        advanced = json.loads(instance.advanced_config or "{}")
        if advanced.get("attach_mode") == "external":
            await self.detach(instance_id, db)
            return
        await instance_service.delete_instance(instance_id, db, delete_k8s=True)

    async def health(self, instance_id: str, db: AsyncSession) -> ExpertHealthInfo:
        instance = await self._get_expert_instance(instance_id, db)
        info = self._to_info(instance)
        if not info.webui_url:
            return ExpertHealthInfo(healthy=None, detail="no endpoint configured")
        rt_spec = RUNTIME_REGISTRY.get(EXPERT_RUNTIME)
        probe_path = rt_spec.health_probe_path if rt_spec else "/health"
        result = await http_probe(info.webui_url, path=probe_path or "/")
        return ExpertHealthInfo(
            healthy=result.get("healthy"),
            detail=str(result.get("detail") or ""),
            webui_url=info.webui_url,
        )

    async def _get_docker_cluster(self, cluster_id: str, db: AsyncSession) -> Cluster:
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
                message="Hermes 专家服务当前仅支持 Docker 集群",
                message_key="errors.hermes_expert.docker_cluster_required",
            )
        return cluster

    async def _get_expert_instance(self, instance_id: str, db: AsyncSession) -> Instance:
        result = await db.execute(
            select(Instance).where(
                Instance.id == instance_id,
                Instance.deleted_at.is_(None),
            )
        )
        instance = result.scalar_one_or_none()
        if not instance:
            raise NotFoundError("实例不存在", "errors.instance.not_found")
        if instance.runtime != EXPERT_RUNTIME:
            raise BadRequestError(
                message="该实例不是 Hermes 专家服务",
                message_key="errors.hermes_expert.invalid_runtime",
            )
        return instance

    def _to_info(self, instance: Instance) -> ExpertInstanceInfo:
        advanced = json.loads(instance.advanced_config) if instance.advanced_config else {}
        expert = advanced.get("expert") or {}
        webui = advanced.get("webui") or {}
        hindsight = advanced.get("hindsight") or {}
        env_vars = json.loads(instance.env_vars) if instance.env_vars else {}
        port = webui.get("host_port") or webui.get("port") or env_vars.get("DOCKER_HOST_PORT")
        webui_url = webui.get("public_url") or webui.get("url")
        if not webui_url and instance.ingress_domain:
            scheme = webui.get("public_scheme") or "http"
            webui_url = f"{scheme}://{instance.ingress_domain}"
        elif not webui_url and port:
            webui_url = get_docker_public_url(int(port))

        docker_status = instance.status
        if instance.compute_provider == "docker" and instance.status == "running":
            display_status = compute_docker_display_status(
                "running",
                instance.health_status or "unknown",
            )
        elif instance.compute_provider == "docker" and instance.status in {"stopped", "exited"}:
            display_status = "stopped"
        else:
            display_status = compute_display_status(
                instance.status,
                instance.health_status or "unknown",
            )

        return ExpertInstanceInfo(
            instance_id=instance.id,
            name=instance.name,
            profile=str(expert.get("profile") or advanced.get("profile") or instance.slug),
            expert=str(expert.get("template") or expert.get("profile") or instance.slug),
            expert_template=str(expert.get("template") or expert.get("profile") or instance.slug),
            runtime=instance.runtime,
            status=instance.status,
            display_status=display_status,
            webui_url=webui_url,
            webui_port=int(port) if port else None,
            hindsight_bank_id=str(hindsight.get("bank_id") or ""),
            cluster_id=instance.cluster_id,
            created_at=instance.created_at,
        )

    async def _run_lifecycle_action(self, instance: Instance, action: str) -> None:
        advanced = json.loads(instance.advanced_config or "{}")
        lifecycle_mode = advanced.get("lifecycle_mode", "managed_container")
        if lifecycle_mode == "linked_only":
            raise BadRequestError(
                message="当前实例为仅关联模式，不支持生命周期操作",
                message_key="errors.docker_attach.lifecycle_not_allowed",
            )

        compose = advanced.get("compose") or {}
        compose_path = compose.get("compose_path") or advanced.get("compose_path")
        env_file = compose.get("env_file") or (advanced.get("paths") or {}).get("env_file")
        project_name = compose.get("project_name")
        container_name = self._container_name(instance)

        use_compose = (
            lifecycle_mode == "managed_compose"
            and compose_path
            and env_file
            and project_name
        )

        if use_compose:
            cmd = ["docker", "compose", "-f", compose_path, "--env-file", env_file, "-p", project_name]
            if action == "start":
                cmd.extend(["up", "-d"])
            elif action == "stop":
                cmd.append("stop")
            else:
                cmd.append("restart")
        else:
            if action == "start":
                cmd = ["docker", "start", container_name]
            elif action == "stop":
                cmd = ["docker", "stop", container_name]
            else:
                cmd = ["docker", "restart", container_name]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            message_key = {
                "start": "errors.hermes_expert.start_failed",
                "stop": "errors.hermes_expert.stop_failed",
                "restart": "errors.hermes_expert.restart_failed",
            }[action]
            raise BadRequestError(
                message=f"{'启动' if action == 'start' else '停止' if action == 'stop' else '重启'}容器失败: {stderr.decode().strip()[:200]}",
                message_key=message_key,
            )

    @staticmethod
    def _container_name(instance: Instance) -> str:
        advanced = json.loads(instance.advanced_config) if instance.advanced_config else {}
        compose = advanced.get("compose") or {}
        if compose.get("container_name"):
            return str(compose["container_name"])
        expert = advanced.get("expert") or {}
        profile = str(expert.get("profile") or instance.slug)
        return f"hermes-{profile}"
