from typing import Annotated, Any
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
from app.services.hermes_agents.mcp_gateway_authorization_service import McpGatewayAuthorizationService
from app.services.hermes_external.hermes_agent_diagnostics_service import HermesAgentDiagnosticsService
from app.services.hermes_external.hermes_api_server_client import HermesApiServerClient
from app.services.hermes_external.hermes_bound_agent_scope_service import HermesBoundAgentScopeService
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_external import core_file_service, profile_service
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.schemas.external_docker_profiles import (
    CoreFileSaveRequest,
    CoreFileValidateRequest,
    ProfileCreateRequest,
    ProfileDeleteRequest,
)
from app.services.hermes_external._common import require_external_docker_instance

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
    include_unavailable: Annotated[bool, Query()] = True,
    include_unbound: Annotated[bool, Query()] = False,
    dispatchable_only: Annotated[bool, Query()] = False,
    managed_mode: Annotated[str | None, Query()] = None,
    refresh: Annotated[bool, Query()] = False,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    include_unbound_effective = include_unbound
    if include_unbound and user:
        can_view_unbound = await PermissionChecker.has_permission(
            db, user.id, org.id, "hermes_agent:manage",
        )
        if not can_view_unbound:
            include_unbound_effective = False
    service = HermesDockerBindingService(db)
    if refresh:
        await service.probe_all(org.id, include_unbound=include_unbound_effective)
        await db.commit()
    pairs = await service.list_instances_for_api(
        org.id,
        include_unbound=include_unbound_effective,
        include_unavailable=include_unavailable,
        managed_mode=managed_mode,
    )
    scope = HermesBoundAgentScopeService(db)
    mcp_auth = McpGatewayAuthorizationService(db)
    items = []
    for record, instance in pairs:
        summary = scope.to_agent_summary(record, instance)
        if dispatchable_only and not summary.get("task_dispatchable"):
            continue
        summary = await mcp_auth.enrich_agent_summary(record, summary)
        items.append(_to_summary(summary))
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
    instance = await service.get_linked_instance(record)
    scope = HermesBoundAgentScopeService(db)
    mcp_auth = McpGatewayAuthorizationService(db)
    summary = scope.to_agent_summary(record, instance)
    summary = await mcp_auth.enrich_agent_summary(record, summary)
    return _ok(_to_summary(summary).model_dump())


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
    records = await service.probe_all(org.id, include_unbound=False)
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


from app.api.hermes_skill._agent_profile_context import (
    host_data_dir_context as _host_data_dir_context,
    require_agent_record as _require_agent_record,
    resolve_bound_instance as _resolve_bound_instance,
)


@router.get("/agents/{profile_name}/profiles")
async def list_agent_profiles(
    profile_name: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    record = await _require_agent_record(db, org.id, profile_name)
    instance = await _resolve_bound_instance(db, org.id, record)
    if instance is not None:
        data = profile_service.list_profiles(instance)
    else:
        ctx = _host_data_dir_context(record, profile_name)
        data = profile_service.list_profiles_for_host_data_dir(
            ctx["host_data_dir"],
            instance_dir=ctx["instance_dir"],
            agent_profile_name=ctx["agent_profile_name"],
        )
    audit = SkillAuditLogger(db)
    await audit.log(
        action="profile.list",
        target_id=profile_name,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"count": len(data.items), "instance_id": record.instance_id},
    )
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{profile_name}/profiles")
async def create_agent_profile(
    profile_name: str,
    body: ProfileCreateRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    record = await _require_agent_record(db, org.id, profile_name)
    instance = await _resolve_bound_instance(db, org.id, record)
    if instance is not None:
        result = profile_service.create_profile(
            instance,
            body.profile,
            from_profile=body.from_profile,
        )
    else:
        ctx = _host_data_dir_context(record, profile_name)
        result = profile_service.create_profile_for_host_data_dir(
            ctx["host_data_dir"],
            body.profile,
            from_profile=body.from_profile,
        )
    audit = SkillAuditLogger(db)
    await audit.log(
        action="profile.create",
        target_id=body.profile,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"agent_profile": profile_name, "from_profile": body.from_profile, "instance_id": record.instance_id},
    )
    await db.commit()
    return _ok(result.model_dump())


@router.delete("/agents/{profile_name}/profiles/{target_profile}")
async def delete_agent_profile(
    profile_name: str,
    target_profile: str,
    body: ProfileDeleteRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    record = await _require_agent_record(db, org.id, profile_name)
    instance = await _resolve_bound_instance(db, org.id, record)
    if instance is not None:
        result = profile_service.delete_profile(
            instance,
            target_profile,
            confirm_profile=body.confirm_profile,
        )
    else:
        ctx = _host_data_dir_context(record, profile_name)
        result = profile_service.delete_profile_for_host_data_dir(
            ctx["host_data_dir"],
            target_profile,
            confirm_profile=body.confirm_profile,
            instance_dir=ctx["instance_dir"],
            agent_profile_name=ctx["agent_profile_name"],
        )
    audit = SkillAuditLogger(db)
    await audit.log(
        action="profile.delete",
        target_id=target_profile,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"agent_profile": profile_name, "instance_id": record.instance_id, "backup_file": result.backup_file},
    )
    await db.commit()
    return _ok(result.model_dump())


@router.get("/agents/{profile_name}/profiles/{target_profile}/core-files/{kind}")
async def read_agent_core_file(
    profile_name: str,
    target_profile: str,
    kind: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    record = await _require_agent_record(db, org.id, profile_name)
    instance = await _resolve_bound_instance(db, org.id, record)
    if instance is not None:
        data = core_file_service.read_core_file(instance, target_profile, kind)
    else:
        ctx = _host_data_dir_context(record, profile_name)
        data = core_file_service.read_core_file_for_host_data_dir(
            ctx["host_data_dir"],
            target_profile,
            kind,
        )
    audit = SkillAuditLogger(db)
    await audit.log(
        action="core_file.read",
        target_id=f"{target_profile}:{kind}",
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"agent_profile": profile_name, "profile": target_profile, "kind": kind},
    )
    await db.commit()
    return _ok(data.model_dump())


@router.post("/agents/{profile_name}/profiles/{target_profile}/core-files/{kind}/validate")
async def validate_agent_core_file(
    profile_name: str,
    target_profile: str,
    kind: str,
    body: CoreFileValidateRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    await _require_agent_record(db, org.id, profile_name)
    data = core_file_service.validate_core_file(kind, body.content)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="core_file.validate",
        target_id=f"{target_profile}:{kind}",
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"agent_profile": profile_name, "profile": target_profile, "kind": kind, "valid": data.valid},
    )
    await db.commit()
    return _ok(data.model_dump())


@router.put("/agents/{profile_name}/profiles/{target_profile}/core-files/{kind}")
async def save_agent_core_file(
    profile_name: str,
    target_profile: str,
    kind: str,
    body: CoreFileSaveRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    record = await _require_agent_record(db, org.id, profile_name)
    instance = await _resolve_bound_instance(db, org.id, record)
    if instance is not None:
        data = await core_file_service.save_core_file(
            instance,
            target_profile,
            kind,
            body.content,
            restart_after_save=body.restart_after_save,
        )
    else:
        ctx = _host_data_dir_context(record, profile_name)
        data = await core_file_service.save_core_file_for_host_data_dir(
            ctx["host_data_dir"],
            target_profile,
            kind,
            body.content,
            restart_after_save=body.restart_after_save,
            container_name=ctx["container_name"],
            gateway_url=ctx["gateway_url"],
        )
    action = "core_file.save_and_restart" if body.restart_after_save else "core_file.save"
    audit = SkillAuditLogger(db)
    await audit.log(
        action=action,
        target_id=f"{target_profile}:{kind}",
        org_id=org.id,
        actor_id=user.id if user else "",
        details={
            "agent_profile": profile_name,
            "profile": target_profile,
            "kind": kind,
            "restarted": data.restarted,
            "runtime_status": data.runtime_status,
            "error_code": data.error_code,
            "instance_id": record.instance_id,
        },
    )
    await db.commit()
    return _ok(data.model_dump())
