"""Shared helpers for Hermes agent profile API routes."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.hermes_external._common import require_external_docker_instance, resolve_paths
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService


async def require_agent_record(db: AsyncSession, org_id: str, profile_name: str):
    service = HermesDockerBindingService(db)
    record = await service.get_by_profile(org_id, profile_name)
    if not record:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Hermes Agent 实例不存在", "errors.hermes.agent_instance_not_found")
    if not record.data_dir and not record.instance_id:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(
            "未找到已绑定的 Hermes Docker 实例",
            "errors.hermes.agent_instance_not_found",
        )
    return record


async def resolve_bound_instance(db: AsyncSession, org_id: str, record):
    if not record.instance_id:
        return None
    return await require_external_docker_instance(record.instance_id, db, org_id)


def host_data_dir_context(record, agent_profile_name: str) -> dict:
    instance_dir = Path(record.instance_dir) if record.instance_dir else None
    return {
        "host_data_dir": Path(record.data_dir),
        "instance_dir": instance_dir,
        "agent_profile_name": agent_profile_name,
        "container_name": record.container_name,
        "gateway_url": record.gateway_url,
    }


async def host_dir_from_agent(db: AsyncSession, org_id: str, agent_profile: str, record=None):
    record = record or await require_agent_record(db, org_id, agent_profile)
    instance = await resolve_bound_instance(db, org_id, record)
    if instance is not None:
        ep = resolve_paths(instance)
        return ep.host_data_dir, record, instance
    if not record.data_dir:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(
            "实例缺少 Hermes 数据目录，无法管理 Profile",
            "errors.hermes.data_dir_missing",
        )
    ctx = host_data_dir_context(record, agent_profile)
    return ctx["host_data_dir"], record, None
