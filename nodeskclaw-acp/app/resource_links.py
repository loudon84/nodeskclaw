from __future__ import annotations

from urllib.parse import urlparse

from app.errors import AdapterError, attachment_ref_invalid, resource_link_unsupported


def parse_prompt_blocks(blocks: list) -> tuple[str, list[str]]:
    texts: list[str] = []
    refs: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            raise AdapterError("ACP_PROMPT_UNSUPPORTED_CONTENT", "仅支持文本与附件 ResourceLink")
        kind = str(block.get("type") or block.get("kind") or "")
        if kind in {"text", "Text"}:
            text = block.get("text")
            if text is None:
                raise AdapterError("ACP_PROMPT_UNSUPPORTED_CONTENT", "仅支持文本与附件 ResourceLink")
            texts.append(str(text))
            continue
        if kind in {"resource_link", "resourceLink"}:
            refs.append(_attachment_ref(block))
            continue
        raise AdapterError("ACP_PROMPT_UNSUPPORTED_CONTENT", "仅支持文本与附件 ResourceLink")
    seen: list[str] = []
    for ref in refs:
        if ref not in seen:
            seen.append(ref)
    return "\n\n".join(texts).strip(), seen


def _attachment_ref(block: dict) -> str:
    uri = str(block.get("uri") or "")
    parsed = urlparse(uri)
    if parsed.scheme != "nodeskclaw":
        raise resource_link_unsupported()
    host = parsed.netloc or (parsed.path.split("/")[0] if parsed.path else "")
    path = parsed.path
    if parsed.netloc:
        parts = [item for item in path.split("/") if item]
    else:
        parts = [item for item in path.split("/") if item]
        if parts:
            host = parts[0]
            parts = parts[1:]
    if host != "attachment" or len(parts) != 1:
        raise resource_link_unsupported()
    ref = parts[0].strip()
    if not ref:
        raise attachment_ref_invalid()
    return ref


def artifact_resource_link(run_id: str, payload: dict) -> dict:
    artifact_id = str(payload.get("artifact_id") or payload.get("id") or "")
    name = str(payload.get("name") or payload.get("artifact_name") or "artifact")
    item: dict = {
        "type": "resource_link",
        "uri": f"nodeskclaw://artifact/{run_id}/{artifact_id}",
        "name": name,
    }
    mime = payload.get("mimeType") or payload.get("mime_type")
    if mime:
        item["mimeType"] = str(mime)
    size = payload.get("size")
    if size is not None:
        item["size"] = size
    return item
