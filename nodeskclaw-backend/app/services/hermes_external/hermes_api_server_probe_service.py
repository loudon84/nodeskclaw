from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.services.hermes_external.hermes_api_server_client import HermesApiServerClient
from app.services.hermes_external.hermes_env_parser import parse_env_file


@dataclass
class ApiServerProbeResult:
    api_server_status: str
    agent_call_status: str
    runtime_status: str
    models: dict | None
    last_error: str | None
    last_probe_at: datetime


class HermesApiServerProbeService:
    async def probe_env(
        self,
        *,
        env_file: str | Path,
        gateway_url: str | None,
        call_test: bool = False,
    ) -> ApiServerProbeResult:
        now = datetime.now(timezone.utc)
        env_path = Path(env_file)
        env = parse_env_file(env_path, require_gateway_port=False)

        if not gateway_url:
            return ApiServerProbeResult(
                api_server_status="unconfigured",
                agent_call_status="not_callable",
                runtime_status="unconfigured",
                models=None,
                last_error="gateway_url missing",
                last_probe_at=now,
            )

        if env.api_server_enabled is False:
            return ApiServerProbeResult(
                api_server_status="api_disabled",
                agent_call_status="not_callable",
                runtime_status="api_disabled",
                models=None,
                last_error="API_SERVER_ENABLED is false",
                last_probe_at=now,
            )

        if not env.has_api_server_key:
            return ApiServerProbeResult(
                api_server_status="auth_unconfigured",
                agent_call_status="not_callable",
                runtime_status="auth_unconfigured",
                models=None,
                last_error="API_SERVER_KEY missing",
                last_probe_at=now,
            )

        api_key = (env.raw.get("API_SERVER_KEY") or "").strip()
        if not api_key:
            return ApiServerProbeResult(
                api_server_status="auth_unconfigured",
                agent_call_status="not_callable",
                runtime_status="auth_unconfigured",
                models=None,
                last_error="API_SERVER_KEY missing",
                last_probe_at=now,
            )

        client = HermesApiServerClient(base_url=gateway_url, api_key=api_key)

        health = await client.health()
        if not health.ok:
            status = health.error or "offline"
            runtime = "degraded"
            if status == "unauthorized":
                runtime = "unauthorized"
            return ApiServerProbeResult(
                api_server_status=status,
                agent_call_status="unauthorized" if status == "unauthorized" else "not_callable",
                runtime_status=runtime,
                models=None,
                last_error=f"GET /health failed ({status})",
                last_probe_at=now,
            )

        models = await client.list_models()
        if not models.ok or not isinstance(models.data, dict):
            status = models.error or "invalid_response"
            return ApiServerProbeResult(
                api_server_status="online",
                agent_call_status="degraded",
                runtime_status="degraded",
                models=None,
                last_error=f"GET /v1/models failed ({status})",
                last_probe_at=now,
            )

        models_dict = models.data
        model_name = (env.api_server_model_name or "").strip()
        if model_name:
            items = models_dict.get("data") if isinstance(models_dict.get("data"), list) else []
            found = any(isinstance(i, dict) and i.get("id") == model_name for i in items)
            if not found:
                return ApiServerProbeResult(
                    api_server_status="online",
                    agent_call_status="degraded",
                    runtime_status="degraded",
                    models=models_dict,
                    last_error=f"model not found: {model_name}",
                    last_probe_at=now,
                )

        if call_test:
            payload = {
                "model": model_name or (models_dict.get("data")[0].get("id") if isinstance(models_dict.get("data"), list) and models_dict.get("data") else None),
                "messages": [{"role": "user", "content": "health check: reply with ok only"}],
                "temperature": 0,
                "max_tokens": 8,
            }
            if not payload.get("model"):
                return ApiServerProbeResult(
                    api_server_status="online",
                    agent_call_status="degraded",
                    runtime_status="degraded",
                    models=models_dict,
                    last_error="no model for call_test",
                    last_probe_at=now,
                )
            chat = await client.chat_completions(payload)
            if not chat.ok:
                status = chat.error or "invalid_response"
                return ApiServerProbeResult(
                    api_server_status="online",
                    agent_call_status="degraded",
                    runtime_status="degraded",
                    models=models_dict,
                    last_error=f"POST /v1/chat/completions failed ({status})",
                    last_probe_at=now,
                )

        return ApiServerProbeResult(
            api_server_status="online",
            agent_call_status="callable",
            runtime_status="ready",
            models=models_dict,
            last_error=None,
            last_probe_at=now,
        )

