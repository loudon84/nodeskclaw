from __future__ import annotations

import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.remote_acp.constants import (
    ACP_PROTOCOL_VERSION,
    CATALOG_CONTRACT_DIGEST,
    CATALOG_CONTRACT_VERSION,
    FRONTEND_CONTRACT_DIGEST,
    FRONTEND_CONTRACT_VERSION,
    INTERNAL_SUBPROTOCOL,
    PUBLIC_SUBPROTOCOL,
    REMOTE_ACP_CONTRACT_DIGEST,
    REMOTE_ACP_CONTRACT_VERSION,
    TRANSPORT_PROFILE,
)
from app.core.config import settings
from app.core.deps import async_session_factory, get_db, require_org_member
from app.core.hooks import emit
from app.core.security import authenticate_bearer_token
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService
from app.services.remote_acp.authorize import (
    assert_no_query_credentials,
    authorize_expert_invoke,
    load_org_for_user,
    require_subprotocol,
)
from app.services.remote_acp.capability import mint_execution_capability
from app.services.remote_acp.errors import ARTIFACT_DENIED, AUTH_REQUIRED, RemoteAcpError, ROUTE_FAILED
from app.services.remote_acp.placement import agent_ws_url, assert_runtime_ready
from app.services.remote_acp.proxy import proxy_text_frames
from fastapi import Response
from urllib.parse import quote

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/remote-experts", tags=["Remote Experts"])


def discovery_payload() -> dict[str, str | int]:
    return {
        "frontendContractVersion": FRONTEND_CONTRACT_VERSION,
        "frontendContractDigest": FRONTEND_CONTRACT_DIGEST,
        "catalogContractVersion": CATALOG_CONTRACT_VERSION,
        "catalogContractDigest": CATALOG_CONTRACT_DIGEST,
        "remoteAcpContractVersion": REMOTE_ACP_CONTRACT_VERSION,
        "remoteAcpContractDigest": REMOTE_ACP_CONTRACT_DIGEST,
        "acpProtocolVersion": ACP_PROTOCOL_VERSION,
        "transportProfile": TRANSPORT_PROFILE,
    }


@router.get("/contracts")
async def remote_acp_contracts():
    return discovery_payload()


@router.get("/{agent_ref}/acp/runs/{run_id}/artifacts/{artifact_id}")
async def download_acp_artifact(
    agent_ref: str,
    run_id: str,
    artifact_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await ExpertPermissionService.require(db, user.id, org.id, "expert:invoke")
    url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}/internal/v1/runs/{run_id}/artifacts/{artifact_id}/bytes"
    headers = {
        "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
        "X-Exec-Org-Id": org.id,
        "X-Exec-User-Id": user.id,
        "X-Agent-Ref": agent_ref,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
        response = await client.get(url, headers=headers)
    if response.status_code >= 400:
        return ARTIFACT_DENIED.to_response()
    filename = artifact_id
    return Response(
        content=response.content,
        media_type=response.headers.get("content-type") or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{quote(filename)}"',
            "Cache-Control": "no-store",
            "X-Checksum-SHA256": response.headers.get("X-Checksum-SHA256") or "",
        },
    )


@router.websocket("/{agent_ref}/acp")
async def remote_acp_public_ingress(websocket: WebSocket, agent_ref: str) -> None:
    try:
        assert_no_query_credentials(websocket.query_params)
        require_subprotocol(websocket.headers.get("sec-websocket-protocol", ""), PUBLIC_SUBPROTOCOL)
        auth = websocket.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            raise AUTH_REQUIRED
        org_id = websocket.headers.get("x-org-id") or ""
        trace_id = websocket.headers.get("x-trace-id") or str(uuid.uuid4())
        if not org_id:
            raise AUTH_REQUIRED
        async with async_session_factory() as db:
            try:
                user = await authenticate_bearer_token(auth.split(" ", 1)[1], db)
            except Exception as exc:
                raise AUTH_REQUIRED from exc
            org = await load_org_for_user(db, user, org_id)
            item = await authorize_expert_invoke(db, user, org.id, agent_ref)
            assert_runtime_ready(item)
            capability = mint_execution_capability(
                internal_token=settings.SKILL_AGENT_INTERNAL_TOKEN,
                org_id=org.id,
                user_id=user.id,
                agent_ref=agent_ref,
                trace_id=trace_id,
            )
            await emit(
                "operation_audit",
                action="remote_acp.connect",
                actor_type="user",
                actor_id=user.id,
                org_id=org.id,
                resource_type="remote_expert",
                resource_id=agent_ref,
            )
        import websockets

        headers = {
            "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
            "X-NodeSkClaw-Execution-Capability": capability,
            "X-Trace-Id": trace_id,
        }
        try:
            agent_ws = await websockets.connect(
                agent_ws_url(),
                additional_headers=headers,
                subprotocols=[INTERNAL_SUBPROTOCOL],
                open_timeout=5,
            )
        except TypeError:
            agent_ws = await websockets.connect(
                agent_ws_url(),
                extra_headers=headers,
                subprotocols=[INTERNAL_SUBPROTOCOL],
                open_timeout=5,
            )
        except Exception as exc:
            logger.info("remote acp route failed: %s", type(exc).__name__)
            raise ROUTE_FAILED from exc
        await websocket.accept(subprotocol=PUBLIC_SUBPROTOCOL)
        try:
            await proxy_text_frames(websocket, agent_ws)
        finally:
            await agent_ws.close()
    except RemoteAcpError as exc:
        await websocket.send_denial_response(exc.to_response())
