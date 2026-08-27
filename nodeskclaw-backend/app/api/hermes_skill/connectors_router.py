from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.connector import (
    ConnectorDefinitionCreate,
    ConnectorDefinitionRead,
    ConnectorDefinitionUpdate,
    ConnectorInstanceCreate,
    ConnectorInstanceRead,
    ConnectorInstanceUpdate,
    ConnectorToolCreate,
    ConnectorToolRead,
    ConnectorToolUpdate,
    SecretRefCreate,
    SecretRefRead,
    SkillConnectorBindingCreate,
    SkillConnectorBindingRead,
)
from app.services.connector.connector_service import ConnectorService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def _definition_read(item: dict[str, Any]) -> dict:
    definition = item["definition"]
    data = ConnectorDefinitionRead.model_validate(definition).model_dump()
    data["instance_count"] = item.get("instance_count", 0)
    data["public_tool_count"] = item.get("public_tool_count", 0)
    return data


def _instance_read(item: dict[str, Any]) -> dict:
    instance = item["instance"]
    data = ConnectorInstanceRead.model_validate(instance).model_dump()
    data["secret_ref_name"] = item.get("secret_ref_name")
    return data


@router.get("/connectors/definitions")
async def list_connector_definitions(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    items = await ConnectorService(db).list_definitions(org.id)
    return _ok({"items": [_definition_read(i) for i in items], "total": len(items)})


@router.post("/connectors/definitions")
async def create_connector_definition(
    body: ConnectorDefinitionCreate,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    definition = await ConnectorService(db).create_definition(
        org_id=org.id,
        name=body.name,
        kind=body.kind,
        title=body.title,
        description=body.description,
        operator_user_id=user.id,
    )
    await db.commit()
    return _ok(ConnectorDefinitionRead.model_validate(definition).model_dump())


@router.get("/connectors/definitions/{definition_id}")
async def get_connector_definition(
    definition_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    definition = await ConnectorService(db).get_definition(org.id, definition_id)
    return _ok(ConnectorDefinitionRead.model_validate(definition).model_dump())


@router.patch("/connectors/definitions/{definition_id}")
async def update_connector_definition(
    definition_id: str,
    body: ConnectorDefinitionUpdate,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    updates = body.model_dump(exclude_unset=True)
    definition = await ConnectorService(db).update_definition(
        org_id=org.id,
        definition_id=definition_id,
        title=updates.get("title"),
        description=updates.get("description"),
    )
    await db.commit()
    return _ok(ConnectorDefinitionRead.model_validate(definition).model_dump())


@router.delete("/connectors/definitions/{definition_id}")
async def delete_connector_definition(
    definition_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    await ConnectorService(db).delete_definition(org.id, definition_id)
    await db.commit()
    return _ok()


@router.get("/connectors/instances")
async def list_connector_instances(
    definition_id: str | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    service = ConnectorService(db)
    instances = await service.list_instances(org.id, definition_id)
    items = []
    for instance in instances:
        item = await service.get_instance_read(org.id, instance.id)
        items.append(_instance_read(item))
    return _ok({"items": items, "total": len(items)})


@router.post("/connectors/definitions/{definition_id}/instances")
async def create_connector_instance(
    definition_id: str,
    body: ConnectorInstanceCreate,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    instance = await ConnectorService(db).create_instance(
        org_id=org.id,
        definition_id=definition_id,
        name=body.name,
        placement=body.placement,
        edge_node_id=body.edge_node_id,
        secret_ref_id=body.secret_ref_id,
        config=body.config,
        is_active=body.is_active,
        operator_user_id=user.id,
    )
    await db.commit()
    item = await ConnectorService(db).get_instance_read(org.id, instance.id)
    return _ok(_instance_read(item))


@router.get("/connectors/instances/{instance_id}")
async def get_connector_instance(
    instance_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    item = await ConnectorService(db).get_instance_read(org.id, instance_id)
    return _ok(_instance_read(item))


@router.patch("/connectors/instances/{instance_id}")
async def update_connector_instance(
    instance_id: str,
    body: ConnectorInstanceUpdate,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    updates = body.model_dump(exclude_unset=True)
    instance = await ConnectorService(db).update_instance(
        org_id=org.id,
        instance_id=instance_id,
        updates=updates,
    )
    await db.commit()
    item = await ConnectorService(db).get_instance_read(org.id, instance.id)
    return _ok(_instance_read(item))


@router.delete("/connectors/instances/{instance_id}")
async def delete_connector_instance(
    instance_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    await ConnectorService(db).delete_instance(org.id, instance_id)
    await db.commit()
    return _ok()


@router.get("/connectors/tools/public")
async def list_public_connector_tools(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    tools = await ConnectorService(db).list_public_tools(org.id)
    return _ok(
        {
            "items": [ConnectorToolRead.model_validate(t).model_dump() for t in tools],
            "total": len(tools),
        }
    )


@router.get("/connectors/instances/{instance_id}/tools")
async def list_connector_tools(
    instance_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    tools = await ConnectorService(db).list_tools(org.id, instance_id)
    return _ok(
        {
            "items": [ConnectorToolRead.model_validate(t).model_dump() for t in tools],
            "total": len(tools),
        }
    )


@router.post("/connectors/instances/{instance_id}/tools")
async def create_connector_tool(
    instance_id: str,
    body: ConnectorToolCreate,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    tool = await ConnectorService(db).create_tool(
        org_id=org.id,
        instance_id=instance_id,
        tool_name=body.tool_name,
        title=body.title,
        description=body.description,
        input_schema=body.input_schema,
        is_public=body.is_public,
        extra_metadata=body.extra_metadata,
    )
    await db.commit()
    return _ok(ConnectorToolRead.model_validate(tool).model_dump())


@router.patch("/connectors/tools/{tool_id}")
async def update_connector_tool(
    tool_id: str,
    body: ConnectorToolUpdate,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    updates = body.model_dump(exclude_unset=True)
    tool = await ConnectorService(db).update_tool(
        org_id=org.id,
        tool_id=tool_id,
        title=updates.get("title"),
        description=updates.get("description"),
        input_schema=updates.get("input_schema"),
        is_public=updates.get("is_public"),
        extra_metadata=updates.get("extra_metadata"),
    )
    await db.commit()
    return _ok(ConnectorToolRead.model_validate(tool).model_dump())


@router.delete("/connectors/tools/{tool_id}")
async def delete_connector_tool(
    tool_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    await ConnectorService(db).delete_tool(org.id, tool_id)
    await db.commit()
    return _ok()


@router.post("/connectors/secret-refs")
async def create_secret_ref(
    body: SecretRefCreate,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    ref = await ConnectorService(db).create_secret_ref(
        org_id=org.id,
        name=body.name,
        edge_node_id=body.edge_node_id,
        description=body.description,
        operator_user_id=user.id,
    )
    await db.commit()
    return _ok(SecretRefRead.model_validate(ref).model_dump())


@router.get("/connectors/secret-refs")
async def list_secret_refs(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    refs = await ConnectorService(db).list_secret_refs(org.id)
    return _ok(
        {
            "items": [SecretRefRead.model_validate(r).model_dump() for r in refs],
            "total": len(refs),
        }
    )


@router.post("/connectors/bindings")
async def create_skill_connector_binding(
    body: SkillConnectorBindingCreate,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    binding = await ConnectorService(db).create_binding(
        org_id=org.id,
        skill_release_id=body.skill_release_id,
        connector_instance_id=body.connector_instance_id,
        role=body.role,
    )
    await db.commit()
    return _ok(SkillConnectorBindingRead.model_validate(binding).model_dump())


@router.get("/connectors/bindings")
async def list_skill_connector_bindings(
    skill_release_id: str | None = None,
    connector_instance_id: str | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    bindings = await ConnectorService(db).list_bindings(
        org.id,
        skill_release_id=skill_release_id,
        connector_instance_id=connector_instance_id,
    )
    return _ok(
        {
            "items": [SkillConnectorBindingRead.model_validate(b).model_dump() for b in bindings],
            "total": len(bindings),
        }
    )


@router.delete("/connectors/bindings/{binding_id}")
async def delete_skill_connector_binding(
    binding_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    await ConnectorService(db).delete_binding(org.id, binding_id)
    await db.commit()
    return _ok()
