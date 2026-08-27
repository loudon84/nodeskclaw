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
    node, token = await EdgeNodeService(db).register(
        org_id=org.id,
        name=body.name,
        operator_user_id=user.id,
    )
    await db.commit()
    result = EdgeNodeCreateResult(
        node=EdgeNodeRead.model_validate(node),
        token=token,
    )
    return _ok(result.model_dump())
