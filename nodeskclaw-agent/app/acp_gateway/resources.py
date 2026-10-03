from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlparse

from app.acp_gateway.errors import AcpGatewayError

ATTACHMENT_PREFIX = "nodeskclaw://attachment/"
ARTIFACT_PREFIX = "nodeskclaw://artifact/"


def canonical_prompt_digest(prompt: Any) -> str:
    return hashlib.sha256(
        json.dumps(prompt, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def parse_prompt_attachments(prompt: Any) -> list[str]:
    refs: list[str] = []
    blocks = prompt if isinstance(prompt, list) else [prompt]
    for block in blocks:
        refs.extend(_scan_block(block))
    return refs


def _scan_block(block: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(block, dict):
        uri = str(block.get("uri") or block.get("url") or "")
        if uri:
            _assert_allowed_uri(uri)
            if uri.startswith(ATTACHMENT_PREFIX):
                refs.append(uri[len(ATTACHMENT_PREFIX) :])
        for value in block.values():
            refs.extend(_scan_block(value))
    elif isinstance(block, list):
        for item in block:
            refs.extend(_scan_block(item))
    elif isinstance(block, str):
        if "://" in block:
            _assert_allowed_uri(block)
            if block.startswith(ATTACHMENT_PREFIX):
                refs.append(block[len(ATTACHMENT_PREFIX) :])
    return refs


def _assert_allowed_uri(uri: str) -> None:
    if uri.startswith(ATTACHMENT_PREFIX) or uri.startswith(ARTIFACT_PREFIX):
        return
    parsed = urlparse(uri)
    if parsed.scheme in {"file", "http", "https"}:
        raise AcpGatewayError("ACP_RESOURCE_DENIED", "resource link not allowed")
    if parsed.scheme:
        raise AcpGatewayError("ACP_RESOURCE_DENIED", "resource link not allowed")


def artifact_resource_link(*, agent_ref: str, run_id: str, artifact_id: str) -> str:
    return f"/api/v1/remote-experts/{agent_ref}/acp/runs/{run_id}/artifacts/{artifact_id}"


def public_artifact_uri(*, run_id: str, artifact_id: str) -> str:
    return f"{ARTIFACT_PREFIX}{run_id}/{artifact_id}"
