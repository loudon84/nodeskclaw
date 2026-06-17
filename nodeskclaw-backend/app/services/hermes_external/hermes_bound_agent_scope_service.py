from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.instance import Instance
from app.services.hermes_external.binding_type import get_instance_binding_type
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file


class HermesBoundAgentScopeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_bound_pairs(self, org_id: str) -> list[tuple[HermesAgentInstance, Instance]]:
        stmt = (
            select(HermesAgentInstance, Instance)
            .join(Instance, HermesAgentInstance.instance_id == Instance.id)
            .where(
                not_deleted(HermesAgentInstance),
                HermesAgentInstance.org_id == org_id,
                HermesAgentInstance.instance_id.isnot(None),
                not_deleted(Instance),
            )
            .order_by(HermesAgentInstance.profile_name)
        )
        result = await self.db.execute(stmt)
        pairs: list[tuple[HermesAgentInstance, Instance]] = []
        for record, instance in result.all():
            if get_instance_binding_type(instance) == "external_docker":
                pairs.append((record, instance))
        return pairs

    async def list_bound_instance_ids(self, org_id: str) -> list[str]:
        pairs = await self.list_bound_pairs(org_id)
        return [instance.id for _record, instance in pairs]

    async def list_dispatchable_pairs(self, org_id: str) -> list[tuple[HermesAgentInstance, Instance]]:
        pairs = await self.list_bound_pairs(org_id)
        return [
            (record, instance)
            for record, instance in pairs
            if self.is_dispatchable(record, instance)
        ]

    async def assert_bound_instance(
        self,
        org_id: str,
        instance_id: str,
    ) -> tuple[HermesAgentInstance, Instance]:
        for record, instance in await self.list_bound_pairs(org_id):
            if instance.id == instance_id:
                return record, instance
        raise BadRequestError(
            "任务只能下发给已绑定的 Hermes Agent AI 员工实例",
            "errors.hermes.agent_not_bound",
            message_params={"agent_id": instance_id},
        )

    async def assert_dispatchable_instance(
        self,
        org_id: str,
        instance_id: str,
    ) -> tuple[HermesAgentInstance, Instance]:
        record, instance = await self.assert_bound_instance(org_id, instance_id)
        if not self.is_dispatchable(record, instance):
            reason = self._dispatchable_failure_reason(record, instance)
            message_key = {
                "gateway_missing": "errors.hermes.agent_gateway_missing",
                "api_key_missing": "errors.hermes.agent_api_key_missing",
                "runtime_not_ready": "errors.hermes.agent_runtime_not_ready",
            }.get(reason, "errors.hermes.agent_not_dispatchable")
            raise BadRequestError(
                "该 Hermes Agent 当前不可接收任务",
                message_key,
                message_params={"agent_id": instance_id},
            )
        return record, instance

    @staticmethod
    def is_bound(record: HermesAgentInstance, instance: Instance | None) -> bool:
        if instance is None or not record.instance_id:
            return False
        if record.instance_id != instance.id:
            return False
        return get_instance_binding_type(instance) == "external_docker"

    @staticmethod
    def has_api_server_key(record: HermesAgentInstance) -> bool:
        if not record.env_file:
            return False
        try:
            env = parse_env_file(Path(record.env_file), require_gateway_port=False)
        except Exception:
            return False
        return bool(env.has_api_server_key)

    @classmethod
    def is_dispatchable(cls, record: HermesAgentInstance, instance: Instance) -> bool:
        if not cls.is_bound(record, instance):
            return False
        if not record.gateway_url:
            return False
        if record.gateway_status != "online":
            return False
        if record.mcp_status != "callable":
            return False
        if record.gateway_runtime_status != "ready":
            return False
        return cls.has_api_server_key(record)

    @classmethod
    def _dispatchable_failure_reason(cls, record: HermesAgentInstance, instance: Instance) -> str:
        if not record.gateway_url:
            return "gateway_missing"
        if not cls.has_api_server_key(record):
            return "api_key_missing"
        if (
            record.gateway_status != "online"
            or record.mcp_status != "callable"
            or record.gateway_runtime_status != "ready"
        ):
            return "runtime_not_ready"
        return "not_dispatchable"

    @classmethod
    def to_agent_summary(cls, record: HermesAgentInstance, instance: Instance | None = None) -> dict:
        data = HermesDockerBindingService.to_api_dict(record, instance)
        data["task_dispatchable"] = (
            cls.is_dispatchable(record, instance)
            if instance is not None
            else False
        )
        return data
