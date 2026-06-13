"""Shared helpers for external Docker Hermes services."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.services.hermes_external.binding_type import get_instance_binding_type
from app.services.hermes_external.path_resolver import HermesExternalPathResolver
from app.services import instance_service

if TYPE_CHECKING:
    from app.models.instance import Instance
    from app.services.hermes_external.path_resolver import HermesExternalPaths

_path_resolver = HermesExternalPathResolver()


async def require_external_docker_instance(
    instance_id: str,
    db: AsyncSession,
    org_id: str | None = None,
) -> Instance:
    try:
        instance = await instance_service.get_instance(instance_id, db, org_id)
    except NotFoundError as exc:
        raise exc
    if get_instance_binding_type(instance) != "external_docker":
        raise BadRequestError(
            message="该实例不是外部绑定 Docker 实例",
            message_key="errors.external_docker.not_external_docker",
        )
    return instance


def resolve_paths(instance: Instance) -> HermesExternalPaths:
    return _path_resolver.resolve(instance)


def load_advanced_config(instance: Instance) -> dict:
    raw = instance.advanced_config
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return {}


def get_lifecycle_config(instance: Instance) -> dict:
    advanced = load_advanced_config(instance)
    compose = advanced.get("compose") or {}
    paths = advanced.get("paths") or {}
    return {
        "lifecycle_mode": advanced.get("lifecycle_mode", "managed_container"),
        "compose_path": compose.get("compose_path") or advanced.get("compose_path"),
        "env_file": compose.get("env_file") or paths.get("docker_env_file") or paths.get("env_file"),
        "project_name": compose.get("project_name"),
        "service_name": compose.get("service_name"),
        "container_name": advanced.get("external_container_name"),
    }
