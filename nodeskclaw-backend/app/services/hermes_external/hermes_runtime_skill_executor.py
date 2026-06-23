"""Execute Hermes runtime skills via API_SERVER /v1/chat/completions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.exceptions import AppException, BadRequestError
from app.services.hermes_external import hermes_instance_skill_service as instance_skill_service
from app.services.hermes_external.hermes_env_parser import parse_env_file

logger = logging.getLogger(__name__)

DEFAULT_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prompt": {
            "type": "string",
            "description": "用户任务说明",
        },
        "context": {
            "type": "object",
            "description": "结构化上下文",
        },
    },
    "required": ["prompt"],
}


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
    }


async def execute_runtime_skill_via_api_server(
    *,
    gateway_url: str | None,
    env_file: str | None,
    agent_profile: str,
    runtime_skill_id: str,
    prompt: str,
    context: dict | None = None,
    timeout_seconds: int | None = None,
) -> str:
    if not prompt.strip():
        raise BadRequestError(
            "缺少 prompt 参数",
            "errors.hermes.mcp_tool_name_invalid",
        )

    client = instance_skill_service.resolve_api_server_client(gateway_url, env_file)
    model_name = agent_profile
    if env_file:
        try:
            env = parse_env_file(Path(env_file), require_gateway_port=False)
            model_name = (env.api_server_model_name or agent_profile).strip() or agent_profile
        except Exception:
            logger.debug("Failed to parse api_server_model_name from env_file")

    payload = build_chat_completions_payload(
        model_name=model_name,
        runtime_skill_id=runtime_skill_id,
        prompt=prompt.strip(),
        context=context,
    )

    result = await client.chat_completions(
        payload,
        timeout_seconds=timeout_seconds,
    )

    if not result.ok:
        error_code = result.error or "chat_completion_failed"
        raise AppException(
            code=50201,
            error_code=50201,
            message="Hermes chat/completions 调用失败",
            message_key="errors.hermes.chat_completion_failed",
            status_code=502,
            message_params={"detail": error_code},
        )

    data = result.data if isinstance(result.data, dict) else {}
    choices = data.get("choices") if isinstance(data.get("choices"), list) else []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") if isinstance(choices[0].get("message"), dict) else {}
        content_text = str(message.get("content") or "")
        if content_text:
            return content_text
    return str(data)
