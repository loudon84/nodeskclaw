import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask, EventType
from app.models.instance import Instance
from app.services.hermes_external.hermes_bound_agent_scope_service import HermesBoundAgentScopeService

logger = logging.getLogger(__name__)


def _parse_advanced_config(instance: Instance) -> dict:
    if not instance.advanced_config:
        return {}
    if isinstance(instance.advanced_config, dict):
        return instance.advanced_config
    try:
        data = json.loads(instance.advanced_config)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _is_external_docker_with_gateway(instance: Instance) -> bool:
    from app.services.hermes_external.binding_type import get_instance_binding_type
    if get_instance_binding_type(instance) != "external_docker":
        return False
    advanced = _parse_advanced_config(instance)
    gateway = advanced.get("gateway") or {}
    return bool(
        advanced.get("gateway_url")
        or advanced.get("hermes_base_url")
        or gateway.get("public_url")
    )


def _is_hermes_agent_instance(instance: Instance) -> bool:
    advanced = _parse_advanced_config(instance)
    runtime_type = advanced.get("runtime_type")
    if runtime_type:
        return runtime_type == "hermes_agent"
    if _is_external_docker_with_gateway(instance):
        return True
    return instance.runtime in ("hermes_agent", "hermes")


class HermesAgentAdapter:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _read_env_value(env_file: str, key: str) -> str | None:
        try:
            text = Path(env_file).read_text(encoding="utf-8")
        except OSError:
            return None

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() != key:
                continue
            v = v.strip()
            if len(v) >= 2 and ((v[0] == v[-1]) and v[0] in {"'", '"'}):
                v = v[1:-1]
            return v

        return None

    @staticmethod
    def _get_api_server_key(instance: Instance) -> str | None:
        advanced = _parse_advanced_config(instance)
        paths = advanced.get("paths") or {}
        env_file = ""
        if isinstance(paths, dict):
            env_file = str(paths.get("env_file") or "")
        if not env_file:
            env_file = str(advanced.get("env_file") or "")
        if not env_file or not Path(env_file).is_file():
            return None
        return HermesAgentAdapter._read_env_value(env_file, "API_SERVER_KEY")

    @staticmethod
    def _get_auth_headers(instance: Instance, *, require_key: bool) -> dict[str, str]:
        api_server_key = HermesAgentAdapter._get_api_server_key(instance)
        if not api_server_key:
            if require_key:
                raise BadRequestError(
                    "实例 .env 缺少 API_SERVER_KEY，NoDeskClaw 无法调用该 Hermes Agent。",
                    "errors.task.agent_api_key_missing",
                )
            return {}
        return {
            "Authorization": f"Bearer {api_server_key}",
            "Content-Type": "application/json",
        }

    async def submit_run(
        self,
        task: HermesTask,
        arguments: dict,
    ) -> dict:
        if not task.agent_id:
            raise BadRequestError(
                "任务只能下发给已绑定的 Hermes Agent AI 员工实例",
                "errors.hermes.agent_not_bound",
            )
        await HermesBoundAgentScopeService(self.db).assert_dispatchable_instance(
            task.org_id, task.agent_id,
        )
        instance = await self._get_instance(task.agent_id, task.org_id)
        if not _is_hermes_agent_instance(instance):
            raise BadRequestError("实例不是 Hermes Agent 类型", "errors.task.agent_not_hermes")

        base_url = self._get_base_url(instance)
        if not base_url:
            raise BadRequestError("Hermes Agent 地址未配置", "errors.task.agent_no_base_url")

        output_dir = await self.compute_output_dir_for_task(task)

        payload = {
            "task_id": task.id,
            "skill_id": task.skill_id,
            "tool_name": task.tool_name,
            "profile_id": task.profile_id,
            "workspace_id": task.workspace_id,
            "arguments": arguments,
            "output_dir": output_dir,
        }

        timeout = httpx.Timeout(
            connect=settings.HERMES_AGENT_CONNECT_TIMEOUT_SECONDS,
            read=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
            write=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
            pool=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
        )
        require_key = _is_external_docker_with_gateway(instance)
        headers = self._get_auth_headers(instance, require_key=require_key)
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            response = await client.post(f"{base_url}/v1/runs", json=payload)

        if response.status_code >= 400:
            body = response.text[:2000]
            logger.warning(
                "Hermes Agent /v1/runs failed: status=%s base_url=%s task_id=%s skill_id=%s tool_name=%s body=%s",
                response.status_code,
                base_url,
                task.id,
                task.skill_id,
                task.tool_name,
                body,
            )
            raise BadRequestError(
                f"Agent 返回错误: {response.status_code}; body={body[:500]}",
                "errors.task.agent_run_error",
            )

        run_data = response.json()
        data_block = run_data.get("data") if isinstance(run_data.get("data"), dict) else {}
        run_id = run_data.get("run_id") or run_data.get("id") or data_block.get("id")
        if not run_id:
            from app.core.exceptions import TaskAgentRunIdMissingError
            raise TaskAgentRunIdMissingError()
        task.hermes_run_id = run_id
        await self.db.flush()

        return run_data

    async def cancel_run(self, task: HermesTask) -> None:
        if not task.hermes_run_id:
            return
        if task.agent_id:
            await HermesBoundAgentScopeService(self.db).assert_bound_instance(
                task.org_id, task.agent_id,
            )
        instance = await self._get_instance(task.agent_id, task.org_id)
        base_url = self._get_base_url(instance)
        if not base_url:
            return

        timeout = httpx.Timeout(
            connect=settings.HERMES_AGENT_CONNECT_TIMEOUT_SECONDS,
            read=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
            write=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
            pool=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
        )
        headers = self._get_auth_headers(instance, require_key=False)
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            try:
                response = await client.delete(f"{base_url}/v1/runs/{task.hermes_run_id}")
                if response.status_code < 400:
                    return
            except httpx.HTTPError as exc:
                logger.warning("cancel_run DELETE 请求失败: %s", exc)
            try:
                await client.post(f"{base_url}/v1/runs/{task.hermes_run_id}/cancel")
            except httpx.HTTPError as exc:
                logger.warning("cancel_run POST 请求失败: %s", exc)

    async def read_run_events(self, task: HermesTask) -> AsyncIterator[dict]:
        if not task.hermes_run_id:
            return
        if task.agent_id:
            await HermesBoundAgentScopeService(self.db).assert_bound_instance(
                task.org_id, task.agent_id,
            )
        instance = await self._get_instance(task.agent_id, task.org_id)
        base_url = self._get_base_url(instance)
        if not base_url:
            return

        timeout = httpx.Timeout(
            connect=settings.HERMES_AGENT_CONNECT_TIMEOUT_SECONDS,
            read=settings.HERMES_AGENT_DEFAULT_TIMEOUT_SECONDS,
        )
        headers = self._get_auth_headers(instance, require_key=False)
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            async with client.stream(
                "GET",
                f"{base_url}/v1/runs/{task.hermes_run_id}/events",
            ) as response:
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event_data = json.loads(line[6:])
                        yield event_data
                    except json.JSONDecodeError:
                        continue

    async def get_run(self, task: HermesTask) -> dict:
        if not task.hermes_run_id:
            raise BadRequestError("任务尚未关联 Hermes Run", "errors.task.no_hermes_run")
        if task.agent_id:
            await HermesBoundAgentScopeService(self.db).assert_bound_instance(
                task.org_id, task.agent_id,
            )
        instance = await self._get_instance(task.agent_id, task.org_id)
        base_url = self._get_base_url(instance)
        if not base_url:
            raise BadRequestError("Hermes Agent 地址未配置", "errors.task.agent_no_base_url")

        timeout = httpx.Timeout(
            connect=settings.HERMES_AGENT_CONNECT_TIMEOUT_SECONDS,
            read=settings.HERMES_AGENT_READ_TIMEOUT_SECONDS,
        )
        headers = self._get_auth_headers(instance, require_key=False)
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            response = await client.get(f"{base_url}/v1/runs/{task.hermes_run_id}")

        if response.status_code >= 400:
            raise BadRequestError(
                f"获取 Run 状态失败: {response.status_code}",
                "errors.task.agent_get_run_error",
            )
        return response.json()

    async def get_run_status(self, task: HermesTask) -> dict:
        run_data = await self.get_run(task)
        data_block = run_data.get("data") if isinstance(run_data.get("data"), dict) else {}
        status = (
            run_data.get("status")
            or run_data.get("state")
            or data_block.get("status")
            or data_block.get("state")
            or "unknown"
        )
        return {"status": status}

    @staticmethod
    def convert_events(hermes_events: list[dict]) -> list[dict]:
        from app.services.hermes_skill.hermes_run_state_resolver import HermesRunStateResolver
        return HermesRunStateResolver.convert_events(hermes_events)

    @staticmethod
    def _get_base_url(instance: Instance) -> str | None:
        advanced = _parse_advanced_config(instance)
        hermes_base_url = advanced.get("hermes_base_url")
        if hermes_base_url:
            return str(hermes_base_url).rstrip("/")
        gateway_url = advanced.get("gateway_url")
        if gateway_url:
            return str(gateway_url).rstrip("/")
        gateway = advanced.get("gateway") or {}
        gateway_public = gateway.get("public_url")
        if gateway_public:
            return str(gateway_public).rstrip("/")

        from app.services.hermes_external.binding_type import get_instance_binding_type
        if get_instance_binding_type(instance) == "external_docker":
            webui = advanced.get("webui") or {}
            webui_url = webui.get("public_url")
            if webui_url:
                return str(webui_url).rstrip("/")

        from app.services.instance_service import _compute_endpoint_url
        endpoint_url = advanced.get("endpoint_url") or _compute_endpoint_url(instance)
        if endpoint_url:
            return str(endpoint_url).rstrip("/")

        if instance.ingress_domain:
            domain = instance.ingress_domain
            if not domain.startswith(("http://", "https://")):
                domain = f"https://{domain}"
            return domain.rstrip("/")
        return None

    async def compute_output_dir_for_task(self, task: HermesTask) -> str:
        instance = await self._get_instance(task.agent_id, task.org_id)
        advanced = _parse_advanced_config(instance)
        output_dir_mode = advanced.get("output_dir_mode", "relative")

        if output_dir_mode == "absolute":
            from app.services.hermes_skill.artifact_service import ArtifactService
            artifact_service = ArtifactService(self.db)
            outputs_dir = await artifact_service.compute_outputs_dir(task)
            return str(outputs_dir)

        return f".{settings.HERMES_OUTPUT_BASE_DIR_NAME.lstrip('.')}/runs/{task.id}/outputs"

    async def _get_instance(self, agent_id: str, org_id: str) -> Instance:
        stmt = select(Instance).where(
            not_deleted(Instance),
            Instance.id == agent_id,
            Instance.org_id == org_id,
        )
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            raise NotFoundError("Agent 实例不存在", "errors.task.agent_not_found")
        return instance
