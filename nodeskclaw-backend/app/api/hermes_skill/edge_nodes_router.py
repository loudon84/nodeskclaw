"""Edge node identity lifecycle routes."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.connector import EdgeNodeCreate, EdgeNodeCreateResult, EdgeNodeRead
from app.services.connector.edge_node_service import EdgeNodeService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/edge-nodes")
async def list_edge_nodes(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    nodes = await EdgeNodeService(db).list_nodes(org.id)
    return _ok(
        {
            "items": [EdgeNodeRead.model_validate(n).model_dump() for n in nodes],
            "total": len(nodes),
        }
    )


@router.post("/edge-nodes")
async def register_edge_node(
    body: EdgeNodeCreate,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    node, bootstrap, expires_at = await EdgeNodeService(db).register(
        org_id=org.id,
        name=body.name,
        operator_user_id=user.id,
    )
    await db.commit()
    result = EdgeNodeCreateResult(
        node=EdgeNodeRead.model_validate(node),
        bootstrap=bootstrap,
        expires_at=expires_at,
    )
    return _ok(result.model_dump())


@router.post("/edge-nodes/{node_id}/disable")
async def disable_edge_node(
    node_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    node = await EdgeNodeService(db).disable_node(org.id, node_id, user.id)
    await db.commit()
    return _ok(EdgeNodeRead.model_validate(node).model_dump())


@router.post("/edge-nodes/{node_id}/enable")
async def enable_edge_node(
    node_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    node = await EdgeNodeService(db).enable_node(org.id, node_id, user.id)
    await db.commit()
    return _ok(EdgeNodeRead.model_validate(node).model_dump())


@router.post("/edge-nodes/{node_id}/rotate")
async def rotate_edge_node(
    node_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    node = await EdgeNodeService(db).start_rotation(org.id, node_id, user.id)
    await db.commit()
    return _ok(EdgeNodeRead.model_validate(node).model_dump())


@router.post("/edge-nodes/{node_id}/revoke")
async def revoke_edge_node(
    node_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:manage")
    node = await EdgeNodeService(db).revoke_node(org.id, node_id, user.id)
    await db.commit()
    return _ok(EdgeNodeRead.model_validate(node).model_dump())
