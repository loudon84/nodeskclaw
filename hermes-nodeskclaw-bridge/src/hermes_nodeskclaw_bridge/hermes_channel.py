"""Hermes-side adapter that maps NoDeskClaw tunnel messages to Hermes API calls."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any

import httpx

from .client import TunnelClient

logger = logging.getLogger("hermes_nodeskclaw_bridge.hermes")

_CJK_RE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff"
    r"\U00020000-\U0002a6df\U0002a700-\U0002ebef]"
)
_THINK_OPEN_RE = re.compile(r"<\s*(?:think(?:ing)?|thought|antthinking)\s*>", re.I)
_THINK_CLOSE_RE = re.compile(r"<\s*/\s*(?:think(?:ing)?|thought|antthinking)\s*>", re.I)

_PREAMBLE_BUF_LIMIT = 2000
_CALLBACK_RETRY_DELAYS = (0.5, 1.5)


class HermesChannel:
    """Translate tunnel chat requests into Hermes API server requests."""

    def __init__(
        self,
        client: TunnelClient,
        *,
        hermes_base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._client = client
        self._hermes_base_url = (
            hermes_base_url
            or os.environ.get("HERMES_BASE_URL")
            or "http://127.0.0.1:8642"
        ).rstrip("/")
        self._api_key = api_key or os.environ.get("HERMES_API_KEY") or os.environ.get("API_SERVER_KEY")
        self._model = model or os.environ.get("HERMES_MODEL_NAME") or os.environ.get("API_SERVER_MODEL_NAME") or "hermes-agent"

    async def handle_chat_request(
        self,
        request_id: str,
        trace_id: str,
        messages: list[dict[str, Any]],
        workspace_id: str,
        no_reply: bool,
    ) -> None:
        session_id = _session_id_for(workspace_id, request_id)
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if session_id:
            headers["X-Hermes-Session-Id"] = session_id

        payload = {
            "model": self._model,
            "messages": [_normalize_message(msg) for msg in messages],
        }

        if no_reply:
            await self._inject_context(headers, payload)
            await self._client.send_response_done(request_id, trace_id)
            return

        await self._stream_response(headers, payload, request_id, trace_id)


    async def handle_learning_task(self, task: dict[str, Any]) -> None:
        callback_url = str(task.get("callback_url") or "")
        if not callback_url:
            logger.warning("Hermes learning task missing callback_url")
            return

        try:
            content = await self._complete_text(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are processing a NoDeskClaw skill gene task. "
                            "Return only one JSON object. Do not use markdown unless it is inside JSON string values."
                        ),
                    },
                    {"role": "user", "content": _build_learning_prompt(task)},
                ],
                session_id=f"learning:{task.get('task_id', '')}",
            )
            result = _extract_learning_result(task, content)
        except Exception as exc:
            logger.error("Hermes learning task failed: %s", exc)
            result = _failed_learning_result(task, str(exc))

        await _post_learning_callback(callback_url, result)

    async def _complete_text(self, messages: list[dict[str, Any]], *, session_id: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if session_id:
            headers["X-Hermes-Session-Id"] = session_id

        body = {"model": self._model, "messages": messages, "stream": False}
        url = f"{self._hermes_base_url}/v1/chat/completions"
        async with httpx.AsyncClient(timeout=httpx.Timeout(1800.0, connect=10.0)) as http:
            response = await http.post(url, headers=headers, json=body)
            if response.status_code != 200:
                error_msg = _extract_error_message(response.status_code, response.content)
                raise RuntimeError(error_msg)
            return _extract_completion_text(response.json())

    async def _inject_context(self, headers: dict[str, str], payload: dict[str, Any]) -> None:
        body = dict(payload)
        body["stream"] = False
        body["max_tokens"] = 1
        url = f"{self._hermes_base_url}/v1/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=60) as http:
                await http.post(url, headers=headers, json=body)
        except Exception as exc:
            logger.debug("Hermes no_reply context injection failed: %s", exc)

    async def _stream_response(
        self,
        headers: dict[str, str],
        payload: dict[str, Any],
        request_id: str,
        trace_id: str,
    ) -> None:
        body = dict(payload)
        body["stream"] = True
        url = f"{self._hermes_base_url}/v1/chat/completions"
        filt = _ThinkingPreambleFilter()

        async with httpx.AsyncClient(timeout=httpx.Timeout(1800.0, connect=10.0)) as http:
            async with http.stream("POST", url, headers=headers, json=body) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    error_msg = _extract_error_message(response.status_code, error_text)
                    await self._client.send_response_error(request_id, trace_id, error_msg)
                    return

                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    content = _extract_chunk_text(chunk)
                    if content:
                        visible = filt.feed(content)
                        if visible:
                            await self._client.send_response_chunk(request_id, trace_id, visible)

        remaining = filt.flush()
        if remaining:
            await self._client.send_response_chunk(request_id, trace_id, remaining)
        await self._client.send_response_done(request_id, trace_id)


def _session_id_for(workspace_id: str, request_id: str) -> str:
    if workspace_id:
        return f"workspace:{workspace_id}"
    return f"nodeskclaw:{request_id}"


def _normalize_message(message: dict[str, Any]) -> dict[str, str]:
    role = str(message.get("role") or "user")
    content = _normalize_content(message.get("content", ""))
    return {"role": role, "content": content}


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def _extract_chunk_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    delta = choices[0].get("delta", {})
    if not isinstance(delta, dict):
        return ""
    content = delta.get("content", "")
    return content if isinstance(content, str) else ""


class _ThinkingPreambleFilter:
    """Strip LLM self-narration (English thinking preamble) from streaming output.

    MiniMax-M2.7 often prefixes its Chinese reply with English internal
    monologue like "The user is asking...", "I should...", "Let me...".
    This filter buffers the initial stream, detects CJK characters as the
    start of the real response, and discards everything before that point.

    Also strips ``<think>...</think>`` tagged blocks anywhere in the stream.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._preamble_done = False
        self._inside_think = False
        self._pending_tag = ""

    def feed(self, text: str) -> str:
        out = self._strip_think_tags(text)
        if not out:
            return ""
        if self._preamble_done:
            return out
        self._buf += out
        if len(self._buf) > _PREAMBLE_BUF_LIMIT:
            self._preamble_done = True
            return self._buf

        m = _CJK_RE.search(self._buf)
        if m:
            self._preamble_done = True
            visible = self._buf[m.start():]
            stripped = self._buf[: m.start()]
            if stripped.strip():
                logger.debug("Stripped thinking preamble (%d chars)", len(stripped))
            return visible
        return ""

    def flush(self) -> str:
        if self._preamble_done:
            return ""
        self._preamble_done = True
        return self._buf

    def _strip_think_tags(self, text: str) -> str:
        result: list[str] = []
        buf = self._pending_tag + text
        self._pending_tag = ""

        while buf:
            if self._inside_think:
                cm = _THINK_CLOSE_RE.search(buf)
                if cm is None:
                    break
                buf = buf[cm.end():]
                self._inside_think = False
            else:
                om = _THINK_OPEN_RE.search(buf)
                if om is None:
                    tail_check = min(15, len(buf))
                    if "<" in buf[-tail_check:]:
                        cut = buf.rfind("<", len(buf) - tail_check)
                        result.append(buf[:cut])
                        self._pending_tag = buf[cut:]
                    else:
                        result.append(buf)
                    break
                result.append(buf[: om.start()])
                buf = buf[om.end():]
                self._inside_think = True

        return "".join(result)



def _build_learning_prompt(task: dict[str, Any]) -> str:
    mode = str(task.get("mode") or "learn")
    if mode == "forget":
        return _build_forget_prompt(task)
    if mode == "create":
        return _build_create_prompt(task)
    return _build_learn_prompt(task)


def _build_learn_prompt(task: dict[str, Any]) -> str:
    gene_slug = str(task.get("gene_slug") or "")
    gene_content = str(task.get("gene_content") or "")
    force_deep = bool(task.get("force_deep_learn"))
    prompt = f"[Gene Learning Task] task_id: {task.get('task_id')}\n\n"
    prompt += f"Learn the gene \"{gene_slug}\".\n\nGene content:\n```\n{gene_content}\n```\n\n"
    learning = task.get("learning")
    if isinstance(learning, dict):
        objectives = learning.get("objectives")
        if isinstance(objectives, list) and objectives:
            prompt += "Learning objectives:\n" + "\n".join(f"- {item}" for item in objectives) + "\n\n"
        scenarios = learning.get("scenarios")
        if isinstance(scenarios, list) and scenarios:
            prompt += "Practice scenarios:\n"
            for scenario in scenarios:
                if isinstance(scenario, dict):
                    prompt += f"- Scenario: {scenario.get('prompt')}\n  Context: {scenario.get('context') or 'N/A'}\n"
            prompt += "\n"
    if force_deep:
        prompt += "You cannot choose direct_install. Produce a complete personalized SKILL.md with YAML frontmatter.\n\n"
        decisions = '"learned" or "failed"'
    else:
        prompt += "Choose direct_install if the existing content is already complete; choose learned if you personalize it.\n\n"
        decisions = '"direct_install", "learned", or "failed"'
    prompt += f"Return only JSON: {{\"decision\": {decisions}, \"content\": \"SKILL.md when learned\", \"self_eval\": 0.0, \"reason\": \"...\"}}"
    return prompt


def _build_create_prompt(task: dict[str, Any]) -> str:
    prompt = f"[Gene Creation Task] task_id: {task.get('task_id')}\n\n"
    prompt += str(task.get("creation_prompt") or "Based on your work experience, create a new gene.") + "\n\n"
    prompt += (
        "Generate a complete gene package. Return only JSON: "
        "{\"decision\": \"created\" or \"failed\", \"content\": \"SKILL.md content\", "
        "\"self_eval\": 0.0, \"meta\": {\"gene_name\": \"...\", \"gene_slug\": \"...\", "
        "\"gene_description\": \"...\", \"suggested_tags\": [\"...\"], \"suggested_category\": \"...\"}, "
        "\"reason\": \"...\"}"
    )
    return prompt


def _build_forget_prompt(task: dict[str, Any]) -> str:
    prompt = f"[Gene Forgetting Task] task_id: {task.get('task_id')}\n\n"
    prompt += f"Review whether to forget or simplify the gene \"{task.get('gene_slug') or ''}\".\n\n"
    if task.get("gene_content"):
        prompt += f"Current gene skill content:\n```\n{task.get('gene_content')}\n```\n\n"
    if task.get("learning_output"):
        prompt += f"Personalized learning output:\n```\n{task.get('learning_output')}\n```\n\n"
    prompt += (
        "Return only JSON: {\"decision\": \"forgotten\", \"simplified\", or \"forget_failed\", "
        "\"content\": \"forgetting summary or simplified SKILL.md\", \"self_eval\": 0.0, \"reason\": \"...\"}"
    )
    return prompt


def _extract_completion_text(body: dict[str, Any]) -> str:
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        return content if isinstance(content, str) else ""
    text = first.get("text")
    return text if isinstance(text, str) else ""


def _extract_learning_result(task: dict[str, Any], raw: str) -> dict[str, Any]:
    data = _parse_json_object(raw)
    mode = str(task.get("mode") or "learn")
    result = {
        "task_id": str(task.get("task_id") or data.get("task_id") or ""),
        "instance_id": str(task.get("instance_id") or data.get("instance_id") or os.environ.get("NODESKCLAW_INSTANCE_ID") or ""),
        "mode": mode,
        "decision": str(data.get("decision") or _default_success_decision(mode)),
        "content": data.get("content"),
        "self_eval": data.get("self_eval"),
        "meta": data.get("meta"),
        "reason": data.get("reason"),
    }
    return {k: v for k, v in result.items() if v is not None}


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = _strip_think_blocks(raw).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.I | re.S)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Hermes learning response did not contain a JSON object")
    parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Hermes learning response JSON must be an object")
    return parsed


def _strip_think_blocks(raw: str) -> str:
    text = re.sub(r"<\s*(?:think(?:ing)?|thought|antthinking)\s*>.*?<\s*/\s*(?:think(?:ing)?|thought|antthinking)\s*>", "", raw, flags=re.I | re.S)
    text = re.sub(r"<\s*(?:think(?:ing)?|thought|antthinking)\s*>.*$", "", text, flags=re.I | re.S)
    return text


def _default_success_decision(mode: str) -> str:
    if mode == "create":
        return "created"
    if mode == "forget":
        return "forgotten"
    return "learned"


def _failed_learning_result(task: dict[str, Any], reason: str) -> dict[str, Any]:
    mode = str(task.get("mode") or "learn")
    return {
        "task_id": str(task.get("task_id") or ""),
        "instance_id": str(task.get("instance_id") or os.environ.get("NODESKCLAW_INSTANCE_ID") or ""),
        "mode": mode,
        "decision": "forget_failed" if mode == "forget" else "failed",
        "reason": reason,
    }


async def _post_learning_callback(callback_url: str, result: dict[str, Any]) -> None:
    last_error: Exception | None = None
    attempts = len(_CALLBACK_RETRY_DELAYS) + 1
    async with httpx.AsyncClient(timeout=60) as http:
        for attempt in range(1, attempts + 1):
            try:
                response = await http.post(callback_url, headers={"Content-Type": "application/json"}, json=result)
                if response.status_code < 400:
                    return
                error = RuntimeError(f"Learning callback failed: HTTP {response.status_code} {response.text[:300]}")
                if response.status_code != 429 and response.status_code < 500:
                    raise error
                last_error = error
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc

            if attempt < attempts:
                logger.warning(
                    "Hermes learning callback attempt %d/%d failed: %s",
                    attempt,
                    attempts,
                    last_error,
                )
                await asyncio.sleep(_CALLBACK_RETRY_DELAYS[attempt - 1])

    raise RuntimeError(f"Learning callback failed after {attempts} attempts: {last_error}") from last_error

def _extract_error_message(status_code: int, raw_body: bytes) -> str:
    default = f"Hermes API returned {status_code}"
    if not raw_body:
        return default
    text = raw_body.decode("utf-8", errors="replace")
    try:
        body = json.loads(text)
    except json.JSONDecodeError:
        return f"{default}: {text[:300]}"
    error = body.get("error")
    if isinstance(error, dict):
        detail = error.get("message")
        if detail:
            return f"Hermes API {status_code}: {detail}"
    if isinstance(error, str) and error:
        return f"Hermes API {status_code}: {error}"
    return f"{default}: {text[:300]}"
