from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.services.secret_store import SecretStore

READ_ONLY_SQL_RE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
WRITE_SQL_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|ALTER|CREATE|DROP|GRANT|REVOKE|TRUNCATE|COPY|CALL|DO)\b",
    re.IGNORECASE,
)


def _is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
        or ip.is_loopback
        or ip.is_private
    )


def _matches_allowlist(host: str, addresses: list[str], port: int, allowlist: list[Any]) -> bool:
    normalized_host = host.lower().rstrip(".")
    for entry in allowlist:
        if isinstance(entry, dict):
            candidate = str(entry.get("host") or entry.get("cidr") or "").strip().lower().rstrip(".")
            entry_port = entry.get("port")
        else:
            raw_entry = str(entry).strip().lower().rstrip(".")
            if not raw_entry:
                continue
            parsed = urlparse(raw_entry if "://" in raw_entry else f"//{raw_entry}")
            candidate = (parsed.hostname or raw_entry).lower().rstrip(".")
            entry_port = parsed.port
        if entry_port is not None and int(entry_port) != port:
            continue
        if candidate.startswith("*.") and normalized_host.endswith(candidate[1:]):
            return True
        if normalized_host == candidate:
            return True
        try:
            network = ipaddress.ip_network(candidate, strict=False)
        except ValueError:
            continue
        if any(ipaddress.ip_address(address) in network for address in addresses):
            return True
    return False


async def _validate_ssrf(
    url_str: str,
    *,
    edge_allowlist: list[str] | None = None,
) -> list[str]:
    """Resolve every HTTP target and enforce central-private and Edge frozen-allowlist boundaries."""
    parsed = urlparse(url_str)
    host = parsed.hostname or ""
    if parsed.scheme not in ("http", "https") or not host:
        raise RuntimeError("Invalid URL: missing host")
    low_host = host.lower().rstrip(".")
    if (
        low_host in ("169.254.169.254", "metadata.google.internal", "instance-data", "localhost", "127.0.0.1")
        or low_host.endswith((".internal", ".local"))
    ):
        raise RuntimeError("SSRF blocked: request to cloud metadata/internal host is forbidden")
    addresses: list[str]
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            resolved = await asyncio.get_running_loop().getaddrinfo(
                host,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except OSError as exc:
            raise RuntimeError("SSRF blocked: DNS resolution failed") from exc
        addresses = [str(item[4][0]) for item in resolved if item and item[4]]
        if not addresses:
            raise RuntimeError("SSRF blocked: DNS resolution returned no addresses")

    if edge_allowlist is not None:
        if not _matches_allowlist(low_host, addresses, parsed.port or (443 if parsed.scheme == "https" else 80), edge_allowlist):
            raise RuntimeError("SSRF blocked: Edge target is not in frozen allowlist")
    elif any(_is_forbidden_ip(ipaddress.ip_address(address)) for address in addresses):
        raise RuntimeError("SSRF blocked: forbidden IP range")
    return addresses


class SSRFSafeTransport(httpx.AsyncHTTPTransport):
    def __init__(self, *, edge_allowlist: list[Any] | None = None) -> None:
        super().__init__()
        self._edge_allowlist = edge_allowlist

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        original_url = request.url
        addresses = await _validate_ssrf(str(original_url), edge_allowlist=self._edge_allowlist)
        request.url = original_url.copy_with(host=addresses[0])
        request.headers["Host"] = original_url.netloc.decode("ascii")
        request.extensions["sni_hostname"] = original_url.host
        try:
            return await super().handle_async_request(request)
        finally:
            request.url = original_url

def _looks_like_token(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and " " not in stripped and "\n" not in stripped


def _apply_secret_to_config(route: dict[str, Any], connector_config: dict[str, Any]) -> dict[str, Any]:
    """Resolve connector_secret_ref_id into headers/db_url. Never log plaintext."""
    secret_ref_id = route.get("connector_secret_ref_id")
    if not secret_ref_id:
        return connector_config
    # Fail-closed secret resolution before use
    secret = SecretStore().resolve(str(secret_ref_id), fail_closed=True)
    if not secret:
        raise RuntimeError(f"secret ref unresolved: {secret_ref_id} (fail-closed)")
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


def _edge_allowlist(route: dict[str, Any]) -> list[Any] | None:
    if route.get("placement") != "edge":
        return None
    network_policy = route.get("network_policy") or {}
    allowlist = route.get("network_allowlist") or network_policy.get("allowlist")
    if not isinstance(allowlist, list) or not all(isinstance(item, (str, dict)) for item in allowlist):
        return []
    return list(allowlist)


def _validate_read_only_sql(sql: str) -> None:
    if not sql or not READ_ONLY_SQL_RE.match(sql) or ";" in sql or WRITE_SQL_RE.search(sql):
        raise RuntimeError("connector DB only allows a single read-only SELECT/WITH SQL statement")


async def _await_cancellable(awaitable: Any, cancel_event: asyncio.Event | None) -> Any:
    if cancel_event is None:
        return await awaitable
    if cancel_event.is_set():
        raise asyncio.CancelledError("connector run cancelled")
    operation = asyncio.create_task(awaitable)
    cancellation = asyncio.create_task(cancel_event.wait())
    done, pending = await asyncio.wait({operation, cancellation}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    if cancellation in done:
        operation.cancel()
        await asyncio.gather(operation, return_exceptions=True)
        raise asyncio.CancelledError("connector run cancelled")
    return operation.result()


def _raise_if_cancelled(cancel_event: asyncio.Event | None) -> None:
    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError("connector run cancelled")


async def execute_connector_run(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    route_snapshot: dict[str, Any],
    org_id: str | None = None,
    cancel_event: asyncio.Event | None = None,
) -> Any:
    if cancel_event and cancel_event.is_set():
        raise asyncio.CancelledError("connector run cancelled before dispatch")
    route = dict(route_snapshot or {})
    connector_kind = route.get("connector_kind")
    connector_config = _apply_secret_to_config(route, dict(route.get("connector_config") or {}))
    edge_allowlist = _edge_allowlist(route)
    yield {"event_type": "run.progress", "payload": {"stage": "connector", "message": f"calling {connector_kind} connector"}}

    if connector_kind == "rest":
        method = str(connector_config.get("method") or "POST").upper()
        # Strictly prefer fixed url from connector config; reject unconfigured dynamic override
        url = str(connector_config.get("url") or "").strip()
        if not url:
            raise RuntimeError("connector REST url missing in binding config")
        await _validate_ssrf(url, edge_allowlist=edge_allowlist)
        payload = arguments.get("body")
        params = arguments.get("params")
        headers = dict(connector_config.get("headers") or {})
        async with httpx.AsyncClient(
            transport=SSRFSafeTransport(edge_allowlist=edge_allowlist),
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
        ) as client:
            response = await _await_cancellable(
                client.request(method, url, json=payload, params=params, headers=headers),
                cancel_event,
            )
            _raise_if_cancelled(cancel_event)
            # Re-validate final destination URL after redirects
            await _validate_ssrf(str(response.url), edge_allowlist=edge_allowlist)
            response.raise_for_status()
            data = _safe_json(response)
        yield {"event_type": "run.completed", "payload": {"summary": "REST connector completed", "content": json.dumps(data, ensure_ascii=False)}}
        return

    if connector_kind == "mcp":
        endpoint = str(connector_config.get("url") or "").strip()
        remote_tool = str(connector_config.get("remote_tool_name") or tool_name).strip()
        if not endpoint:
            raise RuntimeError("connector MCP url missing in binding config")
        await _validate_ssrf(endpoint, edge_allowlist=edge_allowlist)
        req_body = {
            "jsonrpc": "2.0",
            "id": arguments.get("id") or "connector-call",
            "method": "tools/call",
            "params": {
                "name": remote_tool,
                "arguments": arguments.get("remote_arguments") or arguments.get("arguments") or {},
            },
        }
        async with httpx.AsyncClient(
            transport=SSRFSafeTransport(edge_allowlist=edge_allowlist),
            timeout=httpx.Timeout(60.0, connect=10.0),
            follow_redirects=True,
        ) as client:
            response = await _await_cancellable(
                client.post(endpoint, json=req_body, headers=connector_config.get("headers") or {}),
                cancel_event,
            )
            _raise_if_cancelled(cancel_event)
            await _validate_ssrf(str(response.url), edge_allowlist=edge_allowlist)
            response.raise_for_status()
            data = response.json()
        yield {"event_type": "run.completed", "payload": {"summary": "MCP connector completed", "content": json.dumps(data, ensure_ascii=False)}}
        return

    if connector_kind == "db":
        # Strictly use db_url from connector_config, completely ignore arguments.db_url
        db_url = str(connector_config.get("db_url") or "").strip()
        sql = str(arguments.get("sql") or "").strip()
        if not db_url:
            raise RuntimeError("connector DB url missing in binding config")
        _validate_read_only_sql(sql)
        engine = create_async_engine(db_url)
        try:
            async with engine.connect() as conn, conn.begin():
                await _await_cancellable(conn.execute(text("SET TRANSACTION READ ONLY")), cancel_event)
                timeout_ms = min(max(int(connector_config.get("statement_timeout_ms") or 30000), 1), 60000)
                await _await_cancellable(
                    conn.execute(
                        text("SELECT set_config('statement_timeout', CAST(:timeout_ms AS text), true)"),
                        {"timeout_ms": timeout_ms},
                    ),
                    cancel_event,
                )
                result = await _await_cancellable(
                    conn.execute(text(sql), arguments.get("params") or {}),
                    cancel_event,
                )
                _raise_if_cancelled(cancel_event)
                row_limit = min(max(int(connector_config.get("row_limit") or 1000), 1), 1000)
                rows = [dict(row) for row in result.mappings().fetchmany(row_limit)]
        finally:
            await engine.dispose()
        yield {"event_type": "run.completed", "payload": {"summary": f"DB connector returned {len(rows)} rows", "content": json.dumps(rows, ensure_ascii=False)}}
        return

    raise RuntimeError(f"unsupported connector kind: {connector_kind}")


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"text": response.text}
