from __future__ import annotations

import time

from fastapi import APIRouter, WebSocket
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from app.acp_gateway import INTERNAL_SUBPROTOCOL
from app.acp_gateway.capability import verify_execution_capability
from app.acp_gateway.connection import AcpConnection
from app.acp_gateway.errors import AcpGatewayError
from app.auth import require_internal_token
from app.config import settings
from app.db import SessionLocal

router = APIRouter(tags=["internal-acp"])


async def _deny(websocket: WebSocket, error: AcpGatewayError) -> None:
    response = JSONResponse(status_code=error.http_status, content=error.to_http())
    await websocket.send_denial_response(response)


@router.websocket("/internal/v1/acp")
async def internal_acp_gateway(websocket: WebSocket) -> None:
    token = websocket.headers.get("x-skill-agent-token")
    capability = websocket.headers.get("x-nodeskclaw-execution-capability")
    offered = websocket.headers.get("sec-websocket-protocol", "")
    protocols = [item.strip() for item in offered.split(",") if item.strip()]
    try:
        require_internal_token(token)
    except Exception:
        await _deny(websocket, AcpGatewayError("ACP_INTERNAL_AUTH_FAILED", "invalid skill agent token", http_status=401))
        return
    if INTERNAL_SUBPROTOCOL not in protocols:
        await _deny(websocket, AcpGatewayError("ACP_PROTOCOL_ERROR", "unsupported subprotocol", http_status=400))
        return
    claims, error = verify_execution_capability(
        capability,
        current_token=settings.SKILL_AGENT_INTERNAL_TOKEN,
        previous_token=settings.SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS,
        now=int(time.time()),
    )
    if error == "ACP_CAPABILITY_EXPIRED":
        await _deny(websocket, AcpGatewayError(error, "capability expired", http_status=401))
        return
    if not claims:
        await _deny(websocket, AcpGatewayError("ACP_CAPABILITY_INVALID", "capability invalid", http_status=401))
        return
    await websocket.accept(subprotocol=INTERNAL_SUBPROTOCOL)
    async with SessionLocal() as db:
        connection = AcpConnection(websocket, db, claims, capability or "")
        try:
            await connection.serve()
            await db.commit()
        except WebSocketDisconnect:
            await db.commit()
        except Exception:
            await db.rollback()
            raise
