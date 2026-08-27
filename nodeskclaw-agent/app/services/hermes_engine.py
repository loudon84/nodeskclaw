from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

logger = logging.getLogger(__name__)


def build_chat_completions_payload(
    *,
    model_name: str,
    runtime_skill_id: str,
    prompt: str,
    context: dict | None = None,
) -> dict[str, Any]:
    user_content = prompt
    if context:
        user_content = f"{prompt}\n\n结构化上下文：\n{json.dumps(context, ensure_ascii=False)}"
    return {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"你是 Hermes Agent。本次任务指定 skill: {runtime_skill_id}。"
                    f"请优先按照该 skill 的流程完成用户任务。"
                ),
            },
            {"role": "user", "content": user_content},
        ],
        "stream": True,
    }


async def fetch_credential_lease(
    *,
    org_id: str,
    lease_ref: dict[str, Any],
) -> dict[str, Any] | None:
    central_url = f"{settings.SKILL_AGENT_CENTRAL_BASE_URL.rstrip('/')}/api/v1/internal/v1/skill-agent/credentials/mint"
    headers = {
        "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
        "X-Exec-Org-Id": org_id,
        "Content-Type": "application/json",
    }
    body = {
        "instance_id": lease_ref.get("instance_id"),
        "agent_profile": lease_ref.get("agent_profile"),
        "scope": lease_ref.get("scope") or "hermes:invoke",
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0)) as client:
            resp = await client.post(central_url, headers=headers, json=body)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Failed to fetch credential lease: status=%d %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Error fetching credential lease from central: %s", exc)
    return None


async def execute_hermes_run(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    route_snapshot: dict[str, Any],
    org_id: str | None = None,
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[dict[str, Any]]:
    yield {"event_type": "run.progress", "payload": {"stage": "preparing", "message": "preparing hermes"}}
    if cancel_event and cancel_event.is_set():
        yield {"event_type": "run.cancelled", "payload": {"message": "cancelled before hermes call"}}
        return
    
    # Check if we need to resolve credential lease at attempt time
    lease_ref = route_snapshot.get("credential_lease_ref")
    minted_lease = None
    if lease_ref and org_id:
        minted_lease = await fetch_credential_lease(org_id=org_id, lease_ref=lease_ref)

    gateway_url = (
        (minted_lease.get("gateway_url") if minted_lease else None)
        or route_snapshot.get("gateway_url")
        or route_snapshot.get("hermes_base_url")
        or ""
    ).rstrip("/")
    if not gateway_url:
        yield {
            "event_type": "run.progress",
            "payload": {"stage": "processing", "message": "no hermes gateway; stub complete"},
        }
        yield {
            "event_type": "run.completed",
            "payload": {
                "summary": f"stub completed for {tool_name}",
                "content": arguments,
            },
        }
        return

    prompt = str(arguments.get("prompt") or "").strip() or str(arguments)
    context = arguments.get("context") if isinstance(arguments.get("context"), dict) else None
    runtime_skill_id = str(route_snapshot.get("runtime_skill_id") or tool_name)
    model_name = str(
        (minted_lease.get("model") if minted_lease else None)
        or route_snapshot.get("model")
        or route_snapshot.get("agent_profile")
        or "hermes"
    )
    payload = build_chat_completions_payload(
        model_name=model_name,
        runtime_skill_id=runtime_skill_id,
        prompt=prompt,
        context=context,
    )
    headers: dict[str, str] = {"Content-Type": "application/json"}
    cred_lease = route_snapshot.get("credential_lease")
    token = (
        (minted_lease.get("token") if minted_lease else None)
        or (cred_lease.get("token") if isinstance(cred_lease, dict) else None)
        or route_snapshot.get("gateway_token")
        or route_snapshot.get("api_token")
    )
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{gateway_url}/v1/chat/completions"
    yield {"event_type": "run.progress", "payload": {"stage": "tool_calling", "message": "calling hermes"}}

    content_parts: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type or "stream" in content_type:
                    async for line in response.aiter_lines():
                        if cancel_event and cancel_event.is_set():
                            yield {"event_type": "run.cancelled", "payload": {"message": "cancelled during stream"}}
                            return
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        delta = ""
                        choices = chunk.get("choices") or []
                        if choices:
                            delta = ((choices[0].get("delta") or {}).get("content")) or ""
                            if not delta:
                                delta = ((choices[0].get("message") or {}).get("content")) or ""
                        if delta:
                            content_parts.append(delta)
                            yield {
                                "event_type": "run.progress",
                                "payload": {
                                    "stage": "streaming",
                                    "message": delta[:200],
                                    "delta": delta,
                                },
                            }
                else:
                    data = response.json()
                    choices = data.get("choices") or []
                    if choices:
                        content_parts.append(((choices[0].get("message") or {}).get("content")) or "")
                    yield {
                        "event_type": "run.progress",
                        "payload": {"stage": "processing", "message": "hermes response received"},
                    }

        content = "".join(content_parts)
        yield {
            "event_type": "run.completed",
            "payload": {"summary": content[:500], "content": content},
        }
    except Exception as exc:
        logger.exception("hermes execute failed tool=%s", tool_name)
        yield {
            "event_type": "run.failed",
            "payload": {"error": str(exc)[:500]},
        }
