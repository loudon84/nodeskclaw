from __future__ import annotations

import json
from typing import Any

from app.acp_gateway.errors import AcpGatewayError


def parse_frame(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AcpGatewayError("ACP_PROTOCOL_ERROR", "invalid json") from exc
    if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
        raise AcpGatewayError("ACP_PROTOCOL_ERROR", "jsonrpc 2.0 required")
    return payload


def result_frame(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def notify_frame(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "method": method, "params": params}


def error_frame(request_id: Any, error_code: str, message: str) -> dict[str, Any]:
    return AcpGatewayError(error_code, message).to_jsonrpc(request_id)
