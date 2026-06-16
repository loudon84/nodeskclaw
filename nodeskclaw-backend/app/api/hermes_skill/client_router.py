from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_skill.hermes_client_service import HermesClientService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter(prefix="/client", tags=["Hermes Client"])


class ReadinessCheckRequest(BaseModel):
    agent_alias: str | None = None
    tool_name: str | None = None
    profile: str | None = None
    workspace_id: str | None = None


def _ok(data=None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/bootstrap")
async def client_bootstrap(
    request: Request,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    service = HermesClientService(db)
    desktop_ctx = service.parse_desktop_headers(request)
    data = await service.build_bootstrap(user, org, desktop_ctx)
    return _ok(data)


@router.get("/agents")
async def list_client_agents(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    service = HermesClientService(db)
    items = await service.list_client_agents(org.id, user.id)
    return _ok({"items": items})


@router.get("/agents/{agent_alias}")
async def get_client_agent(
    agent_alias: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    service = HermesClientService(db)
    agent = await service.get_client_agent(org.id, user.id, agent_alias)
    if agent is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Agent 未找到", "errors.hermes.agent_not_found")
    return _ok(agent)


@router.get("/tools")
async def list_client_tools(
    agent_alias: str | None = Query(None),
    agent_id: str | None = Query(None),
    profile: str | None = Query(None),
    workspace_id: str | None = Query(None),
    category: str | None = Query(None),
    keyword: str | None = Query(None),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:invoke")
    service = HermesClientService(db)
    data = await service.list_client_tools(
        org.id,
        user.id,
        agent_alias=agent_alias,
        agent_id=agent_id,
        profile=profile,
        workspace_id=workspace_id,
        category=category,
        keyword=keyword,
    )
    return _ok(data)


@router.post("/readiness-check")
async def readiness_check(
    body: ReadinessCheckRequest,
    request: Request,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:view")
    service = HermesClientService(db)
    desktop_ctx = service.parse_desktop_headers(request)
    data = await service.run_readiness_check(
        org.id,
        user.id,
        agent_alias=body.agent_alias,
        tool_name=body.tool_name,
        profile=body.profile,
        workspace_id=body.workspace_id,
        desktop_ctx=desktop_ctx,
    )
    return _ok(data)
