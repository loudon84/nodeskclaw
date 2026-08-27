from __future__ import annotations

import ipaddress
import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.services.secret_store import SecretStore

READ_ONLY_SQL_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


def _validate_ssrf(url_str: str) -> None:
    """Validate that the target URL does not target AWS/cloud metadata or internal loops unless explicitly configured."""
    parsed = urlparse(url_str)
    host = parsed.hostname or ""
    if not host:
        raise RuntimeError("Invalid URL: missing host")
    if host.lower() in ("169.254.169.254", "metadata.google.internal", "instance-data"):
        raise RuntimeError("SSRF blocked: request to cloud metadata service is forbidden")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_link_local:
            raise RuntimeError("SSRF blocked: link-local addresses are forbidden")
    except ValueError:
        pass


def _looks_like_token(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and " " not in stripped and "\n" not in stripped


def _apply_secret_to_config(route: dict[str, Any], connector_config: dict[str, Any]) -> dict[str, Any]:
    """Resolve connector_secret_ref_id into headers/db_url. Never log plaintext."""
    secret_ref_id = route.get("connector_secret_ref_id")
    if not secret_ref_id:
        return connector_config
    secret = SecretStore().resolve(str(secret_ref_id))
    if secret is None:
        raise RuntimeError(f"secret ref unresolved: {secret_ref_id}")
    config = dict(connector_config)
    secret_header = str(config.get("secret_header") or "").strip()
    headers = dict(config.get("headers") or {})
    if secret_header:
        headers[secret_header] = secret
    elif _looks_like_token(secret):
        headers["Authorization"] = f"Bearer {secret}"
    config["headers"] = headers
    db_url = str(config.get("db_url") or "")
    if "{secret}" in db_url:
        config["db_url"] = db_url.replace("{secret}", secret)
    return config


async def execute_connector_run(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    snapshot: dict[str, Any],
) -> Any:
    route = dict(snapshot.get("runtime_policy") or {})
    connector_kind = route.get("connector_kind")
    connector_config = _apply_secret_to_config(route, dict(route.get("connector_config") or {}))
    yield {"event_type": "run.progress", "payload": {"stage": "connector", "message": f"calling {connector_kind} connector"}}

    if connector_kind == "rest":
        method = str(connector_config.get("method") or "POST").upper()
        # Prefer fixed url from connector config, fallback to arguments only if config url missing
        url = str(connector_config.get("url") or arguments.get("url") or "").strip()
        if not url:
            raise RuntimeError("connector REST url missing")
        _validate_ssrf(url)
        payload = arguments.get("body")
        params = arguments.get("params")
        headers = dict(connector_config.get("headers") or {})
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.request(method, url, json=payload, params=params, headers=headers)
            response.raise_for_status()
            data = _safe_json(response)
        yield {"event_type": "run.completed", "payload": {"summary": "REST connector completed", "content": json.dumps(data, ensure_ascii=False)}}
        return

    if connector_kind == "mcp":
        endpoint = str(connector_config.get("url") or arguments.get("url") or "").strip()
        remote_tool = str(connector_config.get("remote_tool_name") or arguments.get("remote_tool_name") or tool_name).strip()
        if not endpoint:
            raise RuntimeError("connector MCP url missing")
        _validate_ssrf(endpoint)
        req_body = {
            "jsonrpc": "2.0",
            "id": arguments.get("id") or "connector-call",
            "method": "tools/call",
            "params": {
                "name": remote_tool,
                "arguments": arguments.get("remote_arguments") or arguments.get("arguments") or {},
            },
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            response = await client.post(endpoint, json=req_body, headers=connector_config.get("headers") or {})
            response.raise_for_status()
            data = response.json()
        yield {"event_type": "run.completed", "payload": {"summary": "MCP connector completed", "content": json.dumps(data, ensure_ascii=False)}}
        return

    if connector_kind == "db":
        # Strictly use db_url from connector_config, ignore arbitrary arguments.db_url
        db_url = str(connector_config.get("db_url") or arguments.get("db_url") or "").strip()
        sql = str(arguments.get("sql") or "").strip()
        if not db_url:
            raise RuntimeError("connector DB url missing")
        if not sql or not READ_ONLY_SQL_RE.match(sql):
            raise RuntimeError("connector DB only allows read-only SELECT/WITH SQL")
        engine = create_async_engine(db_url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text(sql), arguments.get("params") or {})
                rows = [dict(row) for row in result.mappings().all()]
        finally:
            await engine.dispose()
        yield {"event_type": "run.completed", "payload": {"summary": f"DB connector returned {len(rows)} rows", "content": json.dumps(rows, ensure_ascii=False)}}
        return

    raise RuntimeError(f"unsupported connector kind: {connector_kind}")


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return {"text": response.text}
