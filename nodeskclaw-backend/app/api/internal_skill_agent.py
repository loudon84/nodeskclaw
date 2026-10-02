from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.services.hermes_external.hermes_docker_binding_service import HermesDockerBindingService
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.remote_agent_binding_service import list_public_connector_tools, resolve_connector_call_route

router = APIRouter(prefix="/internal/v1/skill-agent", tags=["Internal Skill Agent"])


def _verify_internal_token(x_skill_agent_token: str | None = Header(default=None, alias="X-Skill-Agent-Token")) -> None:
    expected_curr = settings.SKILL_AGENT_INTERNAL_TOKEN
    expected_prev = settings.SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS
    if not x_skill_agent_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing skill agent internal token",
        )
    curr_match = expected_curr and hmac.compare_digest(x_skill_agent_token, expected_curr)
    prev_match = expected_prev and hmac.compare_digest(x_skill_agent_token, expected_prev)
    if not curr_match and not prev_match:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing skill agent internal token",
        )


# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Credential Lease API Server Key]]
def _load_hermes_api_server_credential(
    env_file: str | None,
    agent_profile: str | None,
) -> tuple[str, str | None] | None:
    if not env_file:
        return None
    try:
        env = parse_env_file(Path(env_file), require_gateway_port=False)
    except Exception:
        return None
    api_server_key = (env.raw.get("API_SERVER_KEY") or "").strip()
    if not api_server_key:
        return None
    model_name = (env.api_server_model_name or agent_profile or "").strip() or None
    return api_server_key, model_name


class MintCredentialRequest(BaseModel):
    run_id: str
    attempt_id: str
    instance_id: str | None = None
    agent_profile: str | None = None
    scope: str = "hermes:invoke"
    target: str | None = None


class MintCredentialResponse(BaseModel):
    token: str
    expires_in: int
    gateway_url: str | None = None
    model: str | None = None


@router.post(
    "/credentials/mint",
    response_model=MintCredentialResponse,
    dependencies=[Depends(_verify_internal_token)],
)
# @lat: [[architecture/skill-agent#Hermes Engine Adapter#Credential Lease API Server Key]]
async def mint_credential_lease(
    body: MintCredentialRequest,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
) -> MintCredentialResponse:
    if not x_exec_org_id:
        raise HTTPException(status_code=400, detail="missing X-Exec-Org-Id header")

    if not body.run_id or not body.run_id.strip() or not body.attempt_id or not body.attempt_id.strip():
        raise HTTPException(status_code=400, detail="missing run_id or attempt_id for credential lease binding")

    record: HermesAgentInstance | None = None
    if body.instance_id:
        result = await db.execute(
            select(HermesAgentInstance).where(
                not_deleted(HermesAgentInstance),
                HermesAgentInstance.id == body.instance_id,
                HermesAgentInstance.org_id == x_exec_org_id,
            )
        )
        record = result.scalar_one_or_none()

    if not record and body.agent_profile:
        record = await HermesDockerBindingService(db).get_by_profile(
            x_exec_org_id, body.agent_profile
        )

    if not record:
        raise HTTPException(status_code=404, detail="hermes agent instance not found")

    credential = _load_hermes_api_server_credential(record.env_file, body.agent_profile)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="hermes API_SERVER_KEY unavailable",
        )
    token, model_name = credential
    gateway_url = str(record.gateway_url).rstrip("/") if record.gateway_url else None
    ttl_secs = settings.SKILL_AGENT_CREDENTIAL_LEASE_TTL_SECONDS
    return MintCredentialResponse(
        token=token,
        expires_in=ttl_secs,
        gateway_url=gateway_url,
        model=model_name,
    )


class ReviewAttemptAuthorizationRequest(BaseModel):
    attempt_id: str
    run_id: str
    user_id: str
    tool_name: str
    skill_id: str | None = None
    skill_db_id: str | None = None
    agent_id: str | None = None


class ReviewAttemptAuthorizationResponse(BaseModel):
    allowed: bool
    attempt_id: str
    expires_in: int
    reason: str | None = None


@router.post(
    "/authorizations/review",
    response_model=ReviewAttemptAuthorizationResponse,
    dependencies=[Depends(_verify_internal_token)],
)
async def review_attempt_authorization(
    body: ReviewAttemptAuthorizationRequest,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
) -> ReviewAttemptAuthorizationResponse:
    if not x_exec_org_id:
        raise HTTPException(status_code=400, detail="missing X-Exec-Org-Id header")

    from app.services.hermes_skill.hermes_skill_authorization_service import (
        HermesSkillAuthorizationService,
    )

    auth_svc = HermesSkillAuthorizationService(db)
    skill_id = body.skill_id or body.tool_name
    skill_db_id = body.skill_db_id or skill_id

    try:
        allowed = await auth_svc.can_invoke(
            org_id=x_exec_org_id,
            user_id=body.user_id,
            skill_db_id=skill_db_id,
            skill_id=skill_id,
            agent_id=body.agent_id,
        )
    except Exception as exc:
        return ReviewAttemptAuthorizationResponse(
            allowed=False,
            attempt_id=body.attempt_id,
            expires_in=0,
            reason=f"authorization check failed: {exc}",
        )

    if not allowed:
        return ReviewAttemptAuthorizationResponse(
            allowed=False,
            attempt_id=body.attempt_id,
            expires_in=0,
            reason="authorization revoked or insufficient invoke permissions",
        )

    ttl = settings.SKILL_AGENT_CREDENTIAL_LEASE_TTL_SECONDS
    return ReviewAttemptAuthorizationResponse(
        allowed=True,
        attempt_id=body.attempt_id,
        expires_in=ttl,
        reason=None,
    )


class RemoteAgentToolCatalogBody(BaseModel):
    org_id: str
    binding_ids: list[str] = []
    account_ids: list[str] = []
    expert_id: str = ""
    user_id: str = ""


class RemoteAgentConnectorRouteBody(BaseModel):
    org_id: str
    binding_ids: list[str] = []
    tool_name: str


class RemoteAgentExternalExecuteBody(BaseModel):
    run_id: str
    tool_name: str
    arguments: dict = {}
    tool_call_id: str = ""
    attempt_id: str = ""
    generation: int = 0
    approval_id: str = ""
    arguments_digest: str = ""


class RemoteAgentExternalCloseBody(BaseModel):
    run_id: str


@router.post("/remote-agent/tools", dependencies=[Depends(_verify_internal_token)])
async def list_remote_agent_tools(
    body: RemoteAgentToolCatalogBody,
    db: AsyncSession = Depends(get_db),
):
    tools = await list_public_connector_tools(db, org_id=body.org_id, binding_ids=body.binding_ids)
    for tool in tools:
        tool["source"] = "connector"
    if body.account_ids and body.expert_id and body.user_id:
        tools.extend(
            await _current_external_tools(
                db,
                org_id=body.org_id,
                user_id=body.user_id,
                expert_id=body.expert_id,
                account_ids=body.account_ids,
            )
        )
    return {"tools": tools}


@router.post("/remote-agent/connector-route", dependencies=[Depends(_verify_internal_token)])
async def remote_agent_connector_route(
    body: RemoteAgentConnectorRouteBody,
    db: AsyncSession = Depends(get_db),
):
    route = await resolve_connector_call_route(
        db,
        org_id=body.org_id,
        binding_ids=body.binding_ids,
        tool_name=body.tool_name,
    )
    if route is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connector tool is not in the run catalog")
    return route


@router.post("/remote-agent/external-execute", dependencies=[Depends(_verify_internal_token)])
async def remote_agent_external_execute(
    body: RemoteAgentExternalExecuteBody,
    db: AsyncSession = Depends(get_db),
):
    return await _execute_external_tool(
        db,
        run_id=body.run_id,
        tool_name=body.tool_name,
        arguments=body.arguments,
        tool_call_id=body.tool_call_id,
        attempt_id=body.attempt_id,
        generation=body.generation,
        approval_id=body.approval_id,
        arguments_digest=body.arguments_digest,
    )


@router.post("/remote-agent/external-close", dependencies=[Depends(_verify_internal_token)])
async def remote_agent_external_close(
    body: RemoteAgentExternalCloseBody,
    db: AsyncSession = Depends(get_db),
):
    await _close_external_session(db, run_id=body.run_id)
    return {"closed": True}


async def _current_external_tools(db: AsyncSession, *, org_id: str, user_id: str, expert_id: str, account_ids: list[str]):
    from app.services.expert_external_action_policy_service import enabled_approval_policies, list_external_tools
    from app.services.integration_account_service import load_accounts_for_run
    from app.services.remote_agent_provider_service import RemoteAgentRouteError

    try:
        rows = await load_accounts_for_run(db, org_id=org_id, user_id=user_id, account_ids=account_ids)
    except RemoteAgentRouteError:
        return []
    policies = await enabled_approval_policies(db, org_id=org_id, expert_id=expert_id)
    return list_external_tools(rows, policies)


async def _execute_external_tool(
    db: AsyncSession,
    *,
    run_id: str,
    tool_name: str,
    arguments: dict,
    tool_call_id: str = "",
    attempt_id: str = "",
    generation: int = 0,
    approval_id: str = "",
    arguments_digest: str = "",
):
    from app.models.hermes_skill.hermes_task import HermesTask
    from app.services.expert_external_action_policy_service import enabled_approval_policies, list_external_tools, require_toolkit_coverage
    from app.services.external_action.session_broker import ExternalActionBroker
    from app.services.integration_account_service import load_accounts_for_run, provider_user_id
    from app.services.remote_agent_provider_service import REMOTE_AGENT_TOOL_NAME, RemoteAgentRouteError

    task = await db.get(HermesTask, run_id)
    if task is None or task.deleted_at is not None or task.tool_name != REMOTE_AGENT_TOOL_NAME:
        return {"outcome": "fail_run"}
    snapshot = task.request_snapshot or {}
    account_ids = list(snapshot.get("integration_account_refs") or [])
    expert_id = str(snapshot.get("expert_id") or "")
    try:
        rows = await load_accounts_for_run(
            db,
            org_id=task.org_id,
            user_id=task.user_id,
            account_ids=account_ids,
        )
        policies = await enabled_approval_policies(db, org_id=task.org_id, expert_id=expert_id)
        require_toolkit_coverage(rows, policies)
    except RemoteAgentRouteError:
        return {"outcome": "fail_run"}
    match = next((tool for tool in list_external_tools(rows, policies) if tool["tool_name"] == tool_name), None)
    if match is None:
        return {"outcome": "fail_run"}
    account = next((row for row in rows if row.toolkit_slug == match["toolkit_slug"] and row.connected_account_id), None)
    if account is None or not account.connected_account_id:
        return {"outcome": "fail_run"}
    tools = list_external_tools(rows, policies)
    scope = {
        "provider": "composio",
        "provider_user_id": provider_user_id(task.org_id, task.user_id),
        "run_id": task.id,
        "account_pins": [
            {
                "integration_account_id": row.id,
                "toolkit_slug": row.toolkit_slug,
                "connected_account_id": row.connected_account_id,
            }
            for row in rows
            if row.connected_account_id
        ],
        "toolkit_allowlist": sorted({row.toolkit_slug for row in rows}),
        "tool_allowlist": sorted(tool["tool_name"] for tool in tools),
        "sandbox_enabled": False,
    }
    from app.services.external_action.execution_ledger import ExternalActionLedger
    from app.services.external_action.session_broker import SESSION_METADATA_KEY

    ledger = ExternalActionLedger(db)
    if not tool_call_id:
        return {"outcome": "fail_run"}
    arguments_digest = ExternalActionLedger.digest(arguments if isinstance(arguments, dict) else {})
    replay = await ledger.reserve(
        org_id=task.org_id,
        user_id=task.user_id,
        run_id=task.id,
        attempt_id=attempt_id,
        generation=int(generation or 0),
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        integration_account_id=account.id,
        provider=account.provider,
        toolkit_slug=account.toolkit_slug,
        provider_tool_key=match["provider_tool_key"],
        arguments_digest=arguments_digest,
        approval_id=approval_id or None,
    )
    if replay is not None:
        return replay
    result = await ExternalActionBroker(db).execute(
        task=task,
        provider_user_id=provider_user_id(task.org_id, task.user_id),
        connected_account_id=account.connected_account_id or "",
        toolkit_slug=account.toolkit_slug,
        provider_tool_key=match["provider_tool_key"],
        arguments=arguments if isinstance(arguments, dict) else {},
        scope=scope,
    )
    await db.refresh(task)
    session_ref = str((task.routing_metadata or {}).get(SESSION_METADATA_KEY) or "")
    await ledger.finish(
        run_id=task.id,
        generation=int(generation or 0),
        tool_call_id=tool_call_id,
        outcome=str(result.get("outcome") or "fail_run"),
        result=result.get("result") if isinstance(result.get("result"), dict) else None,
        error_code=None,
        session_ref=session_ref or None,
        request_id=result.get("request_id") if isinstance(result.get("request_id"), str) else None,
    )
    return result


async def _close_external_session(db: AsyncSession, *, run_id: str) -> None:
    from app.models.hermes_skill.hermes_task import HermesTask
    from app.services.external_action.session_broker import ExternalActionBroker

    task = await db.get(HermesTask, run_id)
    if task is None or task.deleted_at is not None:
        return
    await ExternalActionBroker(db).close(task)

