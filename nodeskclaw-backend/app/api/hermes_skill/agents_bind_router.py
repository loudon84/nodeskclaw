from typing import Any
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.hermes_skill.hermes_agent_instance import (
    HermesAgentDiagnosticsResponse,
    HermesAgentInstanceListResponse,
    HermesAgentInstanceSummary,
    ProbeAllAgentsResponse,
    ScanExistingAgentsRequest,
    ScanExistingAgentsResponse,
)
from app.services.hermes_external.hermes_agent_diagnostics_service import HermesAgentDiagnosticsService
from app.services.hermes_external.hermes_api_server_client import HermesApiServerClient
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def _to_summary(data: dict) -> HermesAgentInstanceSummary:
    return HermesAgentInstanceSummary(**data)


@router.post("/agents/scan-existing")
async def scan_existing_agents(
    body: ScanExistingAgentsRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    service = HermesDockerBindingService(db)
    result = await service.scan_existing(
        org.id,
        instances_root=body.instances_root,
        probe_after_scan=body.probe_after_scan,
        call_test=body.call_test,
    )
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.agent.scan_existing",
        target_id=org.id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"scanned": result.scanned, "bound": result.bound, "failed": result.failed},
    )
    await db.commit()
    return _ok(ScanExistingAgentsResponse(
        scanned=result.scanned,
        bound=result.bound,
        failed=result.failed,
        items=[HermesAgentInstanceSummary(
            id=i.id,
            profile_name=i.profile_name,
            container_name=i.container_name,
            docker_status=i.docker_status,
            docker_health=i.docker_health,
            webui_url=i.webui_url,
            gateway_url=i.gateway_url,
            api_server_enabled=i.api_server_enabled,
            api_server_model_name=i.api_server_model_name,
            has_api_server_key=i.has_api_server_key,
            api_server_status=i.api_server_status,
            agent_call_status=i.agent_call_status,
            gateway_status=i.api_server_status,
            runtime_status=i.runtime_status,
            mcp_status=i.mcp_status,
            last_error=i.last_error,
        ) for i in result.items],
    ).model_dump())


@router.get("/agents")
async def list_hermes_agents(
    include_unavailable: bool = Query(default=True),
    managed_mode: str | None = Query(default=None),
    refresh: bool = Query(default=False),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    service = HermesDockerBindingService(db)
    if refresh:
        await service.probe_all(org.id)
        await db.commit()
    records = await service.list_instances(
        org.id,
        include_unavailable=include_unavailable,
        managed_mode=managed_mode,
    )
    items = [_to_summary(HermesDockerBindingService.to_api_dict(r)) for r in records]
    return _ok(HermesAgentInstanceListResponse(items=items).model_dump())


@router.get("/agents/{profile_name}")
async def get_hermes_agent(
    profile_name: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    service = HermesDockerBindingService(db)
    record = await service.get_by_profile(org.id, profile_name)
    if not record:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Hermes Agent 实例不存在", "errors.hermes.agent_instance_not_found")
    return _ok(_to_summary(HermesDockerBindingService.to_api_dict(record)).model_dump())


@router.post("/agents/{profile_name}/probe")
async def probe_hermes_agent(
    profile_name: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    service = HermesDockerBindingService(db)
    record = await service.probe_one(org.id, profile_name)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.agent.probe",
        target_id=profile_name,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"runtime_status": record.gateway_runtime_status},
    )
    await db.commit()
    data = HermesDockerBindingService.to_api_dict(record)
    return _ok({
        "profile_name": data["profile_name"],
        "api_server_status": data["api_server_status"],
        "agent_call_status": data["agent_call_status"],
        "runtime_status": data["runtime_status"],
        "api_server_model_name": data.get("api_server_model_name"),
        "has_api_server_key": data.get("has_api_server_key"),
        "last_probe_at": data["last_probe_at"],
        "last_error": data["last_error"],
    })


@router.post("/agents/probe-all")
async def probe_all_hermes_agents(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    service = HermesDockerBindingService(db)
    records = await service.probe_all(org.id)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.agent.probe_all",
        target_id=org.id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"total": len(records)},
    )
    await db.commit()
    counts = {"ready": 0, "degraded": 0, "unavailable": 0, "unconfigured": 0}
    items = []
    for record in records:
        status = record.gateway_runtime_status
        if status in counts:
            counts[status] += 1
        items.append({
            "profile_name": record.profile_name,
            "runtime_status": record.gateway_runtime_status,
            "api_server_status": record.gateway_status,
            "agent_call_status": record.mcp_status,
        })
    return _ok(ProbeAllAgentsResponse(
        total=len(records),
        ready=counts["ready"],
        degraded=counts["degraded"],
        unavailable=counts["unavailable"],
        unconfigured=counts["unconfigured"],
        items=items,
    ).model_dump())


@router.post("/agents/{profile_name}/test-call")
async def test_call_hermes_agent(
    profile_name: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    service = HermesDockerBindingService(db)
    record = await service.get_by_profile(org.id, profile_name)
    if not record:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Hermes Agent 实例不存在", "errors.hermes.agent_instance_not_found")

    if not record.env_file:
        from app.core.exceptions import BadRequestError
        raise BadRequestError("实例未关联 .env 文件，无法读取 API_SERVER_KEY", "errors.hermes.env_not_found")
    env = parse_env_file(Path(record.env_file), require_gateway_port=False)
    api_key = (env.raw.get("API_SERVER_KEY") or "").strip()
    if not api_key:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(
            "实例 .env 缺少 API_SERVER_KEY，NoDeskClaw 无法调用该 Hermes Agent。",
            "errors.hermes.api_key_missing",
        )
    if not record.gateway_url:
        from app.core.exceptions import BadRequestError
        raise BadRequestError("实例缺少 gateway_url，无法调用 Hermes API Server", "errors.hermes.gateway_url_missing")

    model = env.api_server_model_name or profile_name
    client = HermesApiServerClient(base_url=record.gateway_url, api_key=api_key)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "health check: reply with ok only"}],
        "temperature": 0,
        "max_tokens": 8,
    }
    result = await client.chat_completions(payload)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.agent.test_call",
        target_id=profile_name,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"ok": result.ok, "status_code": result.status_code},
    )
    await db.commit()

    return _ok({
        "profile_name": profile_name,
        "ok": result.ok,
        "status_code": result.status_code,
        "error": result.error,
        "data": result.data if result.ok else None,
    })


@router.get("/agents/{profile_name}/diagnostics")
async def get_hermes_agent_diagnostics(
    profile_name: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    service = HermesDockerBindingService(db)
    record = await service.get_by_profile(org.id, profile_name)
    if not record:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Hermes Agent 实例不存在", "errors.hermes.agent_instance_not_found")
    diag = HermesAgentDiagnosticsService()
    checks = await diag.build_checks(record)
    return _ok(HermesAgentDiagnosticsResponse(
        profile_name=profile_name,
        checks=[{"name": c.name, "status": c.status, "message": c.message} for c in checks],
    ).model_dump())
