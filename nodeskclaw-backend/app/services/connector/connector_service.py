from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.base import not_deleted
from app.models.connector.binding import SkillConnectorBinding
from app.models.connector.definition import ConnectorDefinition, ConnectorKind
from app.models.connector.edge_node import EdgeNode
from app.models.connector.instance import ConnectorInstance, ConnectorPlacement
from app.models.connector.secret_ref import SecretRef
from app.models.connector.tool import ConnectorTool
from app.models.hermes_skill.skill_release import HermesSkillRelease, SkillReleaseStatus

logger = logging.getLogger(__name__)


def _contains_plaintext_credentials(config: Any, *, key: str = "") -> bool:
    if isinstance(config, dict):
        return any(
            _contains_plaintext_credentials(value, key=str(config_key))
            for config_key, value in config.items()
        )
    if isinstance(config, list):
        return any(_contains_plaintext_credentials(value) for value in config)
    if not isinstance(config, str) or not config:
        return False

    normalized_key = key.lower().replace("-", "_")
    if normalized_key in {"authorization", "token", "password", "api_key", "apikey", "auth_token"} or normalized_key.endswith(
        ("_authorization", "_token", "_password", "_api_key", "_apikey")
    ):
        return True
    if normalized_key in {"url", "db_url", "endpoint"}:
        parsed = urlparse(config)
        return bool(parsed.username or parsed.password)
    return False


class ConnectorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_definition(self, org_id: str, definition_id: str) -> ConnectorDefinition:
        result = await self.db.execute(
            select(ConnectorDefinition).where(
                not_deleted(ConnectorDefinition),
                ConnectorDefinition.org_id == org_id,
                ConnectorDefinition.id == definition_id,
            )
        )
        definition = result.scalar_one_or_none()
        if not definition:
            raise NotFoundError("Connector 定义不存在", "errors.connector.definition_not_found")
        return definition

    async def _get_instance(self, org_id: str, instance_id: str) -> ConnectorInstance:
        result = await self.db.execute(
            select(ConnectorInstance).where(
                not_deleted(ConnectorInstance),
                ConnectorInstance.org_id == org_id,
                ConnectorInstance.id == instance_id,
            )
        )
        instance = result.scalar_one_or_none()
        if not instance:
            raise NotFoundError("Connector 实例不存在", "errors.connector.instance_not_found")
        return instance

    async def _get_tool(self, org_id: str, tool_id: str) -> ConnectorTool:
        result = await self.db.execute(
            select(ConnectorTool).where(
                not_deleted(ConnectorTool),
                ConnectorTool.org_id == org_id,
                ConnectorTool.id == tool_id,
            )
        )
        tool = result.scalar_one_or_none()
        if not tool:
            raise NotFoundError("Connector Tool 不存在", "errors.connector.tool_not_found")
        return tool

    async def _get_secret_ref(self, org_id: str, secret_ref_id: str) -> SecretRef:
        result = await self.db.execute(
            select(SecretRef).where(
                not_deleted(SecretRef),
                SecretRef.org_id == org_id,
                SecretRef.id == secret_ref_id,
            )
        )
        ref = result.scalar_one_or_none()
        if not ref:
            raise NotFoundError("SecretRef 不存在", "errors.connector.secret_ref_not_found")
        return ref

    async def _assert_definition_name_available(self, org_id: str, name: str) -> None:
        result = await self.db.execute(
            select(ConnectorDefinition.id).where(
                not_deleted(ConnectorDefinition),
                ConnectorDefinition.org_id == org_id,
                ConnectorDefinition.name == name,
            )
        )
        if result.scalar_one_or_none():
            raise ConflictError(
                "Connector 定义名称已存在",
                "errors.connector.definition_name_conflict",
            )

    async def _assert_instance_name_available(
        self, definition_id: str, name: str, *, exclude_id: str | None = None
    ) -> None:
        query = select(ConnectorInstance.id).where(
            not_deleted(ConnectorInstance),
            ConnectorInstance.definition_id == definition_id,
            ConnectorInstance.name == name,
        )
        if exclude_id:
            query = query.where(ConnectorInstance.id != exclude_id)
        result = await self.db.execute(query)
        if result.scalar_one_or_none():
            raise ConflictError(
                "Connector 实例名称已存在",
                "errors.connector.instance_name_conflict",
            )

    async def _assert_secret_ref_name_available(self, org_id: str, name: str) -> None:
        result = await self.db.execute(
            select(SecretRef.id).where(
                not_deleted(SecretRef),
                SecretRef.org_id == org_id,
                SecretRef.name == name,
            )
        )
        if result.scalar_one_or_none():
            raise ConflictError(
                "SecretRef 名称已存在",
                "errors.connector.secret_ref_name_conflict",
            )

    async def _validate_instance_placement(
        self,
        *,
        org_id: str,
        placement: str,
        edge_node_id: str | None,
        secret_ref_id: str | None,
    ) -> None:
        if placement == ConnectorPlacement.EDGE.value and not edge_node_id:
            raise BadRequestError(
                "Edge 放置必须指定 edge_node_id",
                "errors.connector.edge_node_required",
            )
        if edge_node_id:
            result = await self.db.execute(
                select(EdgeNode.id).where(
                    not_deleted(EdgeNode),
                    EdgeNode.org_id == org_id,
                    EdgeNode.id == edge_node_id,
                )
            )
            if not result.scalar_one_or_none():
                raise BadRequestError(
                    "Edge 节点不存在",
                    "errors.connector.edge_node_not_found",
                )
        if secret_ref_id:
            await self._get_secret_ref(org_id, secret_ref_id)

    @staticmethod
    def _validate_instance_config(config: dict | None) -> None:
        if _contains_plaintext_credentials(config or {}):
            raise BadRequestError(
                "Connector 配置不允许明文凭证",
                "errors.connector.plaintext_credentials_forbidden",
            )

    async def is_instance_bound_to_published_release(self, instance_id: str) -> bool:
        result = await self.db.execute(
            select(SkillConnectorBinding.id)
            .join(
                HermesSkillRelease,
                HermesSkillRelease.id == SkillConnectorBinding.skill_release_id,
            )
            .where(
                not_deleted(SkillConnectorBinding),
                not_deleted(HermesSkillRelease),
                SkillConnectorBinding.connector_instance_id == instance_id,
                HermesSkillRelease.status == SkillReleaseStatus.PUBLISHED.value,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def create_definition(
        self,
        *,
        org_id: str,
        name: str,
        kind: str,
        title: str | None = None,
        description: str | None = None,
        operator_user_id: str | None = None,
    ) -> ConnectorDefinition:
        if kind not in {k.value for k in ConnectorKind}:
            raise BadRequestError("无效的 Connector kind", "errors.connector.invalid_kind")
        await self._assert_definition_name_available(org_id, name)
        definition = ConnectorDefinition(
            org_id=org_id,
            name=name,
            kind=kind,
            title=title,
            description=description,
            created_by=operator_user_id,
        )
        self.db.add(definition)
        await self.db.flush()
        return definition

    async def list_definitions(self, org_id: str) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(ConnectorDefinition)
            .where(not_deleted(ConnectorDefinition), ConnectorDefinition.org_id == org_id)
            .order_by(ConnectorDefinition.created_at.desc())
        )
        definitions = list(result.scalars().all())
        if not definitions:
            return []

        def_ids = [d.id for d in definitions]
        inst_counts = dict(
            (await self.db.execute(
                select(ConnectorInstance.definition_id, func.count())
                .where(
                    not_deleted(ConnectorInstance),
                    ConnectorInstance.definition_id.in_(def_ids),
                )
                .group_by(ConnectorInstance.definition_id)
            )).all()
        )
        public_counts = dict(
            (await self.db.execute(
                select(ConnectorInstance.definition_id, func.count())
                .join(ConnectorTool, ConnectorTool.instance_id == ConnectorInstance.id)
                .where(
                    not_deleted(ConnectorInstance),
                    not_deleted(ConnectorTool),
                    ConnectorInstance.definition_id.in_(def_ids),
                    ConnectorTool.is_public.is_(True),
                )
                .group_by(ConnectorInstance.definition_id)
            )).all()
        )

        items: list[dict[str, Any]] = []
        for definition in definitions:
            items.append(
                {
                    "definition": definition,
                    "instance_count": int(inst_counts.get(definition.id, 0)),
                    "public_tool_count": int(public_counts.get(definition.id, 0)),
                }
            )
        return items

    async def get_definition(self, org_id: str, definition_id: str) -> ConnectorDefinition:
        return await self._get_definition(org_id, definition_id)

    async def update_definition(
        self,
        *,
        org_id: str,
        definition_id: str,
        title: str | None = None,
        description: str | None = None,
    ) -> ConnectorDefinition:
        definition = await self._get_definition(org_id, definition_id)
        if title is not None:
            definition.title = title
        if description is not None:
            definition.description = description
        await self.db.flush()
        return definition

    async def delete_definition(self, org_id: str, definition_id: str) -> None:
        definition = await self._get_definition(org_id, definition_id)
        definition.soft_delete()
        await self.db.flush()

    async def create_instance(
        self,
        *,
        org_id: str,
        definition_id: str,
        name: str,
        placement: str = ConnectorPlacement.CENTRAL.value,
        edge_node_id: str | None = None,
        secret_ref_id: str | None = None,
        config: dict | None = None,
        is_active: bool = True,
        operator_user_id: str | None = None,
    ) -> ConnectorInstance:
        self._validate_instance_config(config)
        await self._get_definition(org_id, definition_id)
        await self._assert_instance_name_available(definition_id, name)
        await self._validate_instance_placement(
            org_id=org_id,
            placement=placement,
            edge_node_id=edge_node_id,
            secret_ref_id=secret_ref_id,
        )
        instance = ConnectorInstance(
            org_id=org_id,
            definition_id=definition_id,
            name=name,
            placement=placement,
            edge_node_id=edge_node_id,
            secret_ref_id=secret_ref_id,
            config=config,
            is_active=is_active,
            created_by=operator_user_id,
        )
        self.db.add(instance)
        await self.db.flush()
        return instance

    async def list_instances(self, org_id: str, definition_id: str | None = None) -> list[ConnectorInstance]:
        query = select(ConnectorInstance).where(
            not_deleted(ConnectorInstance),
            ConnectorInstance.org_id == org_id,
        )
        if definition_id:
            query = query.where(ConnectorInstance.definition_id == definition_id)
        result = await self.db.execute(query.order_by(ConnectorInstance.created_at.desc()))
        return list(result.scalars().all())

    async def get_instance_read(self, org_id: str, instance_id: str) -> dict[str, Any]:
        instance = await self._get_instance(org_id, instance_id)
        secret_ref_name = None
        if instance.secret_ref_id:
            ref = await self._get_secret_ref(org_id, instance.secret_ref_id)
            secret_ref_name = ref.name
        return {"instance": instance, "secret_ref_name": secret_ref_name}

    async def update_instance(
        self,
        *,
        org_id: str,
        instance_id: str,
        updates: dict[str, Any],
    ) -> ConnectorInstance:
        instance = await self._get_instance(org_id, instance_id)
        if "config" in updates:
            self._validate_instance_config(updates["config"])
        connection_fields = {"placement", "edge_node_id", "secret_ref_id", "config"}
        connection_changed = bool(connection_fields & set(updates.keys()))
        if connection_changed and await self.is_instance_bound_to_published_release(instance_id):
            raise BadRequestError(
                "实例已绑定到已发布 Release，不能修改连接参数。请新建实例并发布新 Release。",
                "errors.connector.instance_locked_by_published_release",
            )

        if "name" in updates:
            name = updates["name"]
            if name != instance.name:
                await self._assert_instance_name_available(
                    instance.definition_id, name, exclude_id=instance_id
                )
            instance.name = name

        new_placement = updates.get("placement", instance.placement)
        new_edge_node_id = updates.get("edge_node_id", instance.edge_node_id)
        new_secret_ref_id = updates.get("secret_ref_id", instance.secret_ref_id)

        if connection_changed:
            await self._validate_instance_placement(
                org_id=org_id,
                placement=new_placement,
                edge_node_id=new_edge_node_id,
                secret_ref_id=new_secret_ref_id,
            )
            if "placement" in updates:
                instance.placement = updates["placement"]
            if "edge_node_id" in updates:
                instance.edge_node_id = updates["edge_node_id"]
            if "secret_ref_id" in updates:
                instance.secret_ref_id = updates["secret_ref_id"]
            if "config" in updates:
                instance.config = updates["config"]

        if "is_active" in updates:
            instance.is_active = updates["is_active"]

        await self.db.flush()
        return instance

    async def delete_instance(self, org_id: str, instance_id: str) -> None:
        instance = await self._get_instance(org_id, instance_id)
        instance.soft_delete()
        await self.db.flush()

    async def create_tool(
        self,
        *,
        org_id: str,
        instance_id: str,
        tool_name: str,
        title: str | None = None,
        description: str | None = None,
        input_schema: dict | None = None,
        is_public: bool = False,
        extra_metadata: dict | None = None,
    ) -> ConnectorTool:
        await self._get_instance(org_id, instance_id)
        result = await self.db.execute(
            select(ConnectorTool.id).where(
                not_deleted(ConnectorTool),
                ConnectorTool.instance_id == instance_id,
                ConnectorTool.tool_name == tool_name,
            )
        )
        if result.scalar_one_or_none():
            raise ConflictError(
                "Connector Tool 名称已存在",
                "errors.connector.tool_name_conflict",
            )
        tool = ConnectorTool(
            org_id=org_id,
            instance_id=instance_id,
            tool_name=tool_name,
            title=title,
            description=description,
            input_schema=input_schema,
            is_public=is_public,
            extra_metadata=extra_metadata,
        )
        self.db.add(tool)
        await self.db.flush()
        return tool

    async def list_tools(self, org_id: str, instance_id: str | None = None) -> list[ConnectorTool]:
        query = select(ConnectorTool).where(
            not_deleted(ConnectorTool),
            ConnectorTool.org_id == org_id,
        )
        if instance_id:
            query = query.where(ConnectorTool.instance_id == instance_id)
        result = await self.db.execute(query.order_by(ConnectorTool.created_at.desc()))
        return list(result.scalars().all())

    async def list_public_tools(self, org_id: str) -> list[ConnectorTool]:
        result = await self.db.execute(
            select(ConnectorTool)
            .join(ConnectorInstance, ConnectorInstance.id == ConnectorTool.instance_id)
            .where(
                not_deleted(ConnectorTool),
                not_deleted(ConnectorInstance),
                ConnectorTool.org_id == org_id,
                ConnectorTool.is_public.is_(True),
                ConnectorInstance.is_active.is_(True),
            )
            .order_by(ConnectorTool.tool_name)
        )
        return list(result.scalars().all())

    async def get_public_tool_bundle(self, org_id: str, tool_name: str) -> dict[str, Any]:
        result = await self.db.execute(
            select(ConnectorTool, ConnectorInstance, ConnectorDefinition)
            .join(ConnectorInstance, ConnectorInstance.id == ConnectorTool.instance_id)
            .join(ConnectorDefinition, ConnectorDefinition.id == ConnectorInstance.definition_id)
            .where(
                not_deleted(ConnectorTool),
                not_deleted(ConnectorInstance),
                not_deleted(ConnectorDefinition),
                ConnectorTool.org_id == org_id,
                ConnectorTool.tool_name == tool_name,
                ConnectorTool.is_public.is_(True),
                ConnectorInstance.is_active.is_(True),
            )
            .limit(1)
        )
        row = result.one_or_none()
        if not row:
            raise NotFoundError("Connector Tool 不存在", "errors.connector.tool_not_found")
        connector_tool, instance, definition = row
        secret_ref_name = None
        if instance.secret_ref_id:
            ref = await self._get_secret_ref(org_id, instance.secret_ref_id)
            secret_ref_name = ref.name
        return {
            "tool": connector_tool,
            "instance": instance,
            "definition": definition,
            "secret_ref_name": secret_ref_name,
        }

    async def update_tool(
        self,
        *,
        org_id: str,
        tool_id: str,
        title: str | None = None,
        description: str | None = None,
        input_schema: dict | None = None,
        is_public: bool | None = None,
        extra_metadata: dict | None = None,
    ) -> ConnectorTool:
        tool = await self._get_tool(org_id, tool_id)
        if title is not None:
            tool.title = title
        if description is not None:
            tool.description = description
        if input_schema is not None:
            tool.input_schema = input_schema
        if is_public is not None:
            tool.is_public = is_public
        if extra_metadata is not None:
            tool.extra_metadata = extra_metadata
        await self.db.flush()
        return tool

    async def delete_tool(self, org_id: str, tool_id: str) -> None:
        tool = await self._get_tool(org_id, tool_id)
        tool.soft_delete()
        await self.db.flush()

    async def create_secret_ref(
        self,
        *,
        org_id: str,
        name: str,
        edge_node_id: str | None = None,
        description: str | None = None,
        operator_user_id: str | None = None,
    ) -> SecretRef:
        await self._assert_secret_ref_name_available(org_id, name)
        if edge_node_id:
            result = await self.db.execute(
                select(EdgeNode.id).where(
                    not_deleted(EdgeNode),
                    EdgeNode.org_id == org_id,
                    EdgeNode.id == edge_node_id,
                )
            )
            if not result.scalar_one_or_none():
                raise BadRequestError(
                    "Edge 节点不存在",
                    "errors.connector.edge_node_not_found",
                )
        ref = SecretRef(
            org_id=org_id,
            name=name,
            edge_node_id=edge_node_id,
            description=description,
            created_by=operator_user_id,
        )
        self.db.add(ref)
        await self.db.flush()
        return ref

    async def list_secret_refs(self, org_id: str) -> list[SecretRef]:
        result = await self.db.execute(
            select(SecretRef)
            .where(not_deleted(SecretRef), SecretRef.org_id == org_id)
            .order_by(SecretRef.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_binding(
        self,
        *,
        org_id: str,
        skill_release_id: str,
        connector_instance_id: str,
        role: str | None = None,
    ) -> SkillConnectorBinding:
        release_result = await self.db.execute(
            select(HermesSkillRelease).where(
                not_deleted(HermesSkillRelease),
                HermesSkillRelease.org_id == org_id,
                HermesSkillRelease.id == skill_release_id,
            )
        )
        release = release_result.scalar_one_or_none()
        if not release:
            raise NotFoundError("SkillRelease 不存在", "errors.skill_release.not_found")
        await self._get_instance(org_id, connector_instance_id)

        dup = await self.db.execute(
            select(SkillConnectorBinding.id).where(
                not_deleted(SkillConnectorBinding),
                SkillConnectorBinding.skill_release_id == skill_release_id,
                SkillConnectorBinding.connector_instance_id == connector_instance_id,
            )
        )
        if dup.scalar_one_or_none():
            raise ConflictError(
                "绑定已存在",
                "errors.connector.binding_conflict",
            )

        binding = SkillConnectorBinding(
            org_id=org_id,
            skill_release_id=skill_release_id,
            connector_instance_id=connector_instance_id,
            role=role,
        )
        self.db.add(binding)
        await self.db.flush()
        return binding

    async def list_bindings(
        self,
        org_id: str,
        *,
        skill_release_id: str | None = None,
        connector_instance_id: str | None = None,
    ) -> list[SkillConnectorBinding]:
        query = select(SkillConnectorBinding).where(
            not_deleted(SkillConnectorBinding),
            SkillConnectorBinding.org_id == org_id,
        )
        if skill_release_id:
            query = query.where(SkillConnectorBinding.skill_release_id == skill_release_id)
        if connector_instance_id:
            query = query.where(SkillConnectorBinding.connector_instance_id == connector_instance_id)
        result = await self.db.execute(query.order_by(SkillConnectorBinding.created_at.desc()))
        return list(result.scalars().all())

    async def delete_binding(self, org_id: str, binding_id: str) -> None:
        result = await self.db.execute(
            select(SkillConnectorBinding).where(
                not_deleted(SkillConnectorBinding),
                SkillConnectorBinding.org_id == org_id,
                SkillConnectorBinding.id == binding_id,
            )
        )
        binding = result.scalar_one_or_none()
        if not binding:
            raise NotFoundError("绑定不存在", "errors.connector.binding_not_found")
        binding.soft_delete()
        await self.db.flush()
