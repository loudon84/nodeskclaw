import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings

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


def _emit_semantic_from_choice(
    choice: dict[str, Any],
    *,
    source_prefix: str,
    counter: list[int],
) -> list[dict[str, Any]]:
    """Map only explicit structured Provider fields into semantic events."""
    events: list[dict[str, Any]] = []
    delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}

    def _next_id(kind: str) -> str:
        counter[0] += 1
        return f"{source_prefix}:{kind}:{counter[0]}"

    content = delta.get("content") or message.get("content") or ""
    if isinstance(content, str) and content:
        events.append(
            {
                "event_type": "assistant.message",
                "payload": {"text": content},
                "source": "agent",
                "source_event_id": _next_id("assistant"),
            }
        )

    summary = None
    for src in (delta, message, choice):
        if isinstance(src.get("reasoning_summary"), str) and src["reasoning_summary"]:
            summary = src["reasoning_summary"]
            break
    if summary:
        events.append(
            {
                "event_type": "reasoning.summary",
                "payload": {"summary": summary},
                "source": "agent",
                "source_event_id": _next_id("reasoning"),
            }
        )

    tool_calls = delta.get("tool_calls") or message.get("tool_calls") or []
    if isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            tool_name = tc.get("name") or fn.get("name")
            call_id = tc.get("id") or tc.get("call_id")
            status = tc.get("status") or "started"
            if not isinstance(tool_name, str) or not tool_name:
                continue
            if not isinstance(call_id, str) or not call_id:
                continue
            if status not in {"started", "completed", "failed"}:
                status = "started"
            events.append(
                {
                    "event_type": "tool.call",
                    "payload": {
                        "tool_name": tool_name,
                        "call_id": call_id,
                        "status": status,
                    },
                    "source": "agent",
                    "source_event_id": _next_id(f"tool:{call_id}"),
                }
            )

    clarify = None
    for src in (delta, message, choice):
        if isinstance(src.get("clarify"), dict):
            clarify = src["clarify"]
            break
        if isinstance(src.get("clarification"), dict):
            clarify = src["clarification"]
            break
    if clarify and isinstance(clarify.get("question"), str) and clarify["question"]:
        payload: dict[str, Any] = {"question": clarify["question"]}
        if isinstance(clarify.get("options"), list):
            payload["options"] = clarify["options"]
        events.append(
            {
                "event_type": "clarify.requested",
                "payload": payload,
                "source": "agent",
                "source_event_id": _next_id("clarify"),
            }
        )

    approval = None
    for src in (delta, message, choice):
        if isinstance(src.get("approval"), dict):
            approval = src["approval"]
            break
    if (
        approval
        and isinstance(approval.get("approval_id"), str)
        and approval["approval_id"]
        and isinstance(approval.get("summary"), str)
        and approval["summary"]
    ):
        events.append(
            {
                "event_type": "approval.requested",
                "payload": {
                    "approval_id": approval["approval_id"],
                    "summary": approval["summary"],
                },
                "source": "agent",
                "source_event_id": _next_id("approval"),
            }
        )

    return events


async def fetch_credential_lease(
    *,
    org_id: str,
    run_id: str,
    attempt_id: str,
    lease_ref: dict[str, Any],
) -> dict[str, Any] | None:
    central_url = f"{settings.SKILL_AGENT_CENTRAL_BASE_URL.rstrip('/')}/api/v1/internal/v1/skill-agent/credentials/mint"
    headers = {
        "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
        "X-Exec-Org-Id": org_id,
        "Content-Type": "application/json",
    }
    body = {
        "run_id": run_id,
        "attempt_id": attempt_id,
        "instance_id": lease_ref.get("instance_id"),
        "agent_profile": lease_ref.get("agent_profile"),
        "scope": lease_ref.get("scope") or "hermes:invoke",
        "target": lease_ref.get("target"),
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
    run_id: str | None = None,
    attempt_id: str | None = None,
    cancel_event: asyncio.Event | None = None,
) -> AsyncIterator[dict[str, Any]]:
    yield {"event_type": "run.progress", "payload": {"stage": "preparing", "message": "preparing hermes"}}
    if cancel_event and cancel_event.is_set():
        yield {"event_type": "run.cancelled", "payload": {"message": "cancelled before hermes call"}}
        return

    # Plaintext token/env_file fallback is strictly removed; presence of raw gateway_token is rejected
    if "gateway_token" in route_snapshot or "env_file" in route_snapshot:
        yield {
            "event_type": "run.failed",
            "payload": {"error": f"Plaintext credential/env_file in snapshot rejected for {tool_name} (fail-closed)"},
        }
        return

    # Resolve credential lease at attempt time via Credential Broker
    lease_ref = route_snapshot.get("credential_lease_ref")
    minted_lease = None
    if lease_ref:
        if not org_id or not run_id or not attempt_id:
            yield {
                "event_type": "run.failed",
                "payload": {"error": f"Missing execution context (org_id/run_id/attempt_id) for credential lease on {tool_name}"},
            }
            return
        minted_lease = await fetch_credential_lease(
            org_id=org_id,
            run_id=run_id,
            attempt_id=attempt_id,
            lease_ref=lease_ref,
        )
        if not minted_lease or not minted_lease.get("token"):
            yield {
                "event_type": "run.failed",
                "payload": {"error": f"Credential lease acquisition failed for {tool_name} (fail-closed)"},
            }
            return

    gateway_url = (
        (minted_lease.get("gateway_url") if minted_lease else None)
        or route_snapshot.get("gateway_url")
        or route_snapshot.get("hermes_base_url")
        or ""
    ).rstrip("/")
    if not gateway_url:
        yield {
            "event_type": "run.failed",
            "payload": {"error": f"No Hermes gateway configured for {tool_name}"},
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
    if minted_lease and minted_lease.get("token"):
        headers["Authorization"] = f"Bearer {minted_lease['token']}"
    url = f"{gateway_url}/v1/chat/completions"
    yield {"event_type": "run.progress", "payload": {"stage": "tool_calling", "message": "calling hermes"}}

    content_parts: list[str] = []
    event_counter = [0]
    source_prefix = f"hermes:{run_id or 'run'}:{attempt_id or 'attempt'}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type or "stream" in content_type:
                    yield {
                        "event_type": "run.progress",
                        "payload": {"stage": "streaming", "message": "streaming"},
                    }
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
                        choices = chunk.get("choices") or []
                        for choice in choices:
                            if not isinstance(choice, dict):
                                continue
                            for semantic in _emit_semantic_from_choice(
                                choice,
                                source_prefix=source_prefix,
                                counter=event_counter,
                            ):
                                text = (semantic.get("payload") or {}).get("text")
                                if semantic["event_type"] == "assistant.message" and isinstance(text, str):
                                    content_parts.append(text)
                                yield semantic
                else:
                    data = response.json()
                    choices = data.get("choices") or []
                    yield {
                        "event_type": "run.progress",
                        "payload": {"stage": "processing", "message": "hermes response received"},
                    }
                    for choice in choices:
                        if not isinstance(choice, dict):
                            continue
                        for semantic in _emit_semantic_from_choice(
                            choice,
                            source_prefix=source_prefix,
                            counter=event_counter,
                        ):
                            text = (semantic.get("payload") or {}).get("text")
                            if semantic["event_type"] == "assistant.message" and isinstance(text, str):
                                content_parts.append(text)
                            yield semantic

        content = "".join(content_parts)
        yield {
            "event_type": "run.completed",
            "payload": {"summary": content[:500], "content": content},
        }
    except Exception as exc:
        logger.exception("hermes execute failed tool=%s", tool_name)
        err_msg = str(exc)[:500]
        if minted_lease and minted_lease.get("token"):
            err_msg = err_msg.replace(minted_lease["token"], "[REDACTED]")
        yield {
            "event_type": "run.failed",
            "payload": {"error": err_msg},
        }
