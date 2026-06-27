from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.common import ApiResponse
from app.schemas.expert import (
    ExpertCreateBody,
    ExpertItem,
    ExpertListResponse,
    ExpertTeamCreateBody,
    ExpertTeamItem,
    ExpertTeamListResponse,
    ExpertTeamMemberBody,
    ExpertTeamUpdateBody,
    ExpertUpdateBody,
)
from app.schemas.expert_log import ExpertInvocationLogDetail, ExpertInvocationLogListResponse
from app.schemas.expert_mcp import ExpertHealthResponse
from app.schemas.expert_skill import ExpertSkillItem, ExpertSkillListResponse, ExpertSkillSyncResult, ExpertSkillUpdateBody
from app.schemas.expert_team_skill import ExpertTeamSkillItem, ExpertTeamSkillListResponse, ExpertTeamSkillUpdateBody
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_health_service import ExpertHealthService
from app.services.expert_gateway.expert_invocation_log_service import ExpertInvocationLogService
from app.services.expert_gateway.expert_mcp_gateway_service import ExpertMcpGatewayService
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService
from app.services.expert_gateway.expert_skill_service import ExpertSkillService
from app.services.expert_gateway.expert_team_service import ExpertTeamService
from app.services.expert_gateway.expert_team_skill_service import ExpertTeamSkillService
from app.services.mcp_skill_gateway.auth import McpAuthFailure, resolve_mcp_user

router = APIRouter()


def _ok(data=None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


async def _resolve_bearer_user(
    authorization: str | None,
    db: AsyncSession,
):
    auth = await resolve_mcp_user(authorization, db)
    if isinstance(auth, McpAuthFailure):
        from app.services.mcp_skill_gateway.errors import mcp_error_v2

        return None, mcp_error_v2(1, auth.error_code, auth.reason)
    return auth, None


@router.get("/health", response_model=ExpertHealthResponse, tags=["Expert MCP Gateway"])
async def expert_health(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    auth, err = await _resolve_bearer_user(authorization, db)
    if err:
        return ExpertHealthResponse(
            ok=False,
            status="unauthorized",
            gateway={"name": "expert-mcp-gateway", "version": "v6.1"},
            catalog={"publishedExperts": 0, "publicSkills": 0, "callableSkills": 0},
            runtimes=[],
        )
    return await ExpertHealthService(db).get_health(auth.org.id)


@router.post("/mcp", tags=["Expert MCP Gateway"])
async def expert_mcp_root(
    body: dict,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    auth, err = await _resolve_bearer_user(authorization, db)
    if err:
        return err
    result = await ExpertMcpGatewayService(db).dispatch_root(
        auth.org.id,
        auth.user.id,
        body,
        headers=dict(request.headers),
    )
    await db.commit()
    return result


@router.post("/mcp/{slug}", tags=["Expert MCP Gateway"])
async def expert_mcp_slug(
    slug: str,
    body: dict,
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    auth, err = await _resolve_bearer_user(authorization, db)
    if err:
        return err
    result = await ExpertMcpGatewayService(db).dispatch_catalog_item(
        auth.org.id,
        auth.user.id,
        slug,
        body,
        headers=dict(request.headers),
    )
    await db.commit()
    return result


@router.get("/experts", response_model=ApiResponse[ExpertListResponse], tags=["Expert MCP Gateway"])
async def list_experts(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    items = await ExpertCatalogService(db).list_experts(org.id)
    return _ok(ExpertListResponse(items=items, total=len(items)))


@router.get("/experts/by-agent/{hermes_agent_id}", response_model=ApiResponse[ExpertItem | None], tags=["Expert MCP Gateway"])
async def get_expert_by_agent(
    hermes_agent_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    expert = await ExpertCatalogService(db).get_by_agent_id(org.id, hermes_agent_id)
    if expert is None:
        return _ok(None)
    items = await ExpertCatalogService(db).list_experts(org.id)
    item = next((i for i in items if i.id == expert.id), None)
    return _ok(item)


@router.post("/experts", response_model=ApiResponse[ExpertItem], tags=["Expert MCP Gateway"])
async def create_expert(
    body: ExpertCreateBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    item = await ExpertCatalogService(db).create_expert(org.id, user.id, body)
    await db.commit()
    return _ok(item)


@router.patch("/experts/{expert_id}", response_model=ApiResponse[ExpertItem], tags=["Expert MCP Gateway"])
async def update_expert(
    expert_id: str,
    body: ExpertUpdateBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    item = await ExpertCatalogService(db).update_expert(org.id, user.id, expert_id, body)
    await db.commit()
    return _ok(item)


@router.post("/experts/{expert_id}/publish", response_model=ApiResponse[ExpertItem], tags=["Expert MCP Gateway"])
async def publish_expert(
    expert_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    item = await ExpertCatalogService(db).publish_expert(org.id, user.id, expert_id)
    await db.commit()
    return _ok(item)


@router.post("/experts/{expert_id}/unpublish", response_model=ApiResponse[ExpertItem], tags=["Expert MCP Gateway"])
async def unpublish_expert(
    expert_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    item = await ExpertCatalogService(db).unpublish_expert(org.id, user.id, expert_id)
    await db.commit()
    return _ok(item)


@router.get("/experts/{expert_id}/skills", response_model=ApiResponse[ExpertSkillListResponse], tags=["Expert MCP Gateway"])
async def list_expert_skills(
    expert_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert_skill:manage")
    items = await ExpertSkillService(db).list_skills(org.id, expert_id)
    return _ok(ExpertSkillListResponse(items=items, total=len(items)))


@router.post("/experts/{expert_id}/sync-tools", response_model=ApiResponse[ExpertSkillSyncResult], tags=["Expert MCP Gateway"])
async def sync_expert_tools(
    expert_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert_skill:manage")
    result = await ExpertSkillService(db).sync_tools(org.id, user.id, expert_id)
    await db.commit()
    return _ok(result)


@router.patch("/expert-skills/{skill_id}", response_model=ApiResponse[ExpertSkillItem], tags=["Expert MCP Gateway"])
async def update_expert_skill(
    skill_id: str,
    body: ExpertSkillUpdateBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert_skill:manage")
    item = await ExpertSkillService(db).update_skill(org.id, user.id, skill_id, body)
    await db.commit()
    return _ok(item)


@router.get("/admin/invocation-logs", response_model=ApiResponse[ExpertInvocationLogListResponse], tags=["Expert MCP Gateway"])
async def list_invocation_logs(
    expert_slug: str | None = Query(default=None),
    skill_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    catalog_kind: str | None = Query(default=None),
    orchestration_mode: str | None = Query(default=None),
    started_from: datetime | None = Query(default=None),
    started_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert_log:view")
    items, total = await ExpertInvocationLogService(db).list_logs(
        org.id,
        expert_slug=expert_slug,
        skill_name=skill_name,
        status=status,
        user_id=user_id,
        keyword=keyword,
        catalog_kind=catalog_kind,
        orchestration_mode=orchestration_mode,
        started_from=started_from,
        started_to=started_to,
        page=page,
        page_size=page_size,
    )
    return _ok(ExpertInvocationLogListResponse(items=items, total=total))


@router.get("/admin/invocation-logs/{log_id}", response_model=ApiResponse[ExpertInvocationLogDetail], tags=["Expert MCP Gateway"])
async def get_invocation_log(
    log_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert_log:detail")
    detail = await ExpertInvocationLogService(db).get_log(org.id, log_id)
    if detail is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(message="调用日志不存在", message_key="errors.expert.log_not_found")
    return _ok(detail)


@router.get("/teams", response_model=ApiResponse[ExpertTeamListResponse], tags=["Expert MCP Gateway"])
async def list_teams(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    items = await ExpertTeamService(db).list_teams(org.id)
    return _ok(ExpertTeamListResponse(items=items, total=len(items)))


@router.post("/teams", response_model=ApiResponse[ExpertTeamItem], tags=["Expert MCP Gateway"])
async def create_team(
    body: ExpertTeamCreateBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    item = await ExpertTeamService(db).create_team(org.id, user.id, body)
    await db.commit()
    return _ok(item)


@router.patch("/teams/{team_id}", response_model=ApiResponse[ExpertTeamItem], tags=["Expert MCP Gateway"])
async def update_team(
    team_id: str,
    body: ExpertTeamUpdateBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    item = await ExpertTeamService(db).update_team(org.id, user.id, team_id, body)
    await db.commit()
    return _ok(item)


@router.post("/teams/{team_id}/members", tags=["Expert MCP Gateway"])
async def add_team_member(
    team_id: str,
    body: ExpertTeamMemberBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:manage")
    await ExpertTeamService(db).add_member(org.id, team_id, body)
    await db.commit()
    return _ok({"team_id": team_id, "expert_id": body.expert_id})


@router.get("/teams/{team_id}/skills", response_model=ApiResponse[ExpertTeamSkillListResponse], tags=["Expert MCP Gateway"])
async def list_team_skills(
    team_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert_skill:manage")
    items = await ExpertTeamSkillService(db).list_skills(org.id, team_id)
    return _ok(ExpertTeamSkillListResponse(items=items, total=len(items)))


@router.post("/teams/{team_id}/sync-tools", response_model=ApiResponse[ExpertSkillSyncResult], tags=["Expert MCP Gateway"])
async def sync_team_tools(
    team_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert_skill:manage")
    result = await ExpertTeamSkillService(db).sync_tools(org.id, user.id, team_id)
    await db.commit()
    return _ok(result)


@router.patch("/team-skills/{skill_id}", response_model=ApiResponse[ExpertTeamSkillItem], tags=["Expert MCP Gateway"])
async def update_team_skill(
    skill_id: str,
    body: ExpertTeamSkillUpdateBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert_skill:manage")
    item = await ExpertTeamSkillService(db).update_skill(org.id, user.id, skill_id, body)
    await db.commit()
    return _ok(item)
