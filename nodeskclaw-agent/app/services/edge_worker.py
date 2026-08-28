from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.connector_router import execute_connector_run
from app.services.secret_store import SecretStore

logger = logging.getLogger(__name__)


class EdgeWorker:
    """Outbound Edge role: heartbeat, claim jobs from Central, execute connectors, post events."""

    def __init__(self) -> None:
        self._running = False
        self._base_url = settings.SKILL_AGENT_CENTRAL_BASE_URL.rstrip("/")
        self._token = settings.SKILL_AGENT_EDGE_TOKEN
        self._node_id = settings.SKILL_AGENT_EDGE_NODE_ID
        self._secrets = SecretStore()
        self._spool_dir = Path("./data/edge_spool")
        self._spool_dir.mkdir(parents=True, exist_ok=True)

    def stop(self) -> None:
        self._running = False

    def _headers(self) -> dict[str, str]:
        return {"X-Edge-Token": self._token}

    async def start(self) -> None:
        self._running = True
        logger.info(
            "SkillAgent EdgeWorker started node_id=%s central=%s",
            self._node_id or "(unset)",
            self._base_url,
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            while self._running:
                try:
                    await self._heartbeat(client)
                    await self._flush_spool(client)
                    job = await self._claim_job(client)
                    if job:
                        await self._execute_job(client, job)
                    else:
                        await asyncio.sleep(settings.SKILL_AGENT_EDGE_POLL_SECONDS)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("EdgeWorker poll error")
                    await asyncio.sleep(settings.SKILL_AGENT_EDGE_POLL_SECONDS)

    async def _heartbeat(self, client: httpx.AsyncClient) -> None:
        url = f"{self._base_url}/api/v1/internal/edge/heartbeat"
        body = {
            "node_id": self._node_id,
            "status_meta": {"role": "edge"},
        }
        response = await client.post(url, headers=self._headers(), json=body)
        response.raise_for_status()

    async def _claim_job(self, client: httpx.AsyncClient) -> dict[str, Any] | None:
        url = f"{self._base_url}/api/v1/internal/edge/jobs"
        response = await client.get(url, headers=self._headers())
        if response.status_code == 204:
            return None
        response.raise_for_status()
        if not response.content:
            return None
        data = response.json()
        if data is None:
            return None
        if isinstance(data, dict):
            if data.get("job") is not None:
                job = data["job"]
                return job if isinstance(job, dict) and job.get("id") else None
            if data.get("id"):
                return data
            return None
        if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("id"):
            return data[0]
        return None

    async def _flush_spool(self, client: httpx.AsyncClient) -> None:
        """Flush persisted spool files on disk if any previous network failures occurred."""
        for spool_file in list(self._spool_dir.glob("*.json")):
            try:
                data = json.loads(spool_file.read_text(encoding="utf-8"))
                job_id = data.get("job_id")
                events = data.get("events") or []
                if job_id and events:
                    await self._post_events(client, job_id, events)
                spool_file.unlink(missing_ok=True)
            except Exception:
                logger.debug("spool flush retry failed for %s", spool_file.name, exc_info=True)

    async def _spool_events(self, job_id: str, events: list[dict[str, Any]]) -> None:
        try:
            spool_file = self._spool_dir / f"spool_{job_id}_{uuid.uuid4().hex}.json"
            spool_file.write_text(json.dumps({"job_id": job_id, "events": events}), encoding="utf-8")
        except Exception:
            logger.error("failed to write spool file for job_id=%s", job_id, exc_info=True)

    async def _post_events(
        self,
        client: httpx.AsyncClient,
        job_id: str,
        events: list[dict[str, Any]],
        *,
        delivery_generation: int = 1,
    ) -> None:
        url = f"{self._base_url}/api/v1/internal/edge/jobs/{job_id}/events"
        headers = dict(self._headers())
        headers["X-Delivery-Generation"] = str(delivery_generation)
        response = await client.post(
            url,
            headers=headers,
            json={"events": events, "delivery_generation": delivery_generation},
        )
        response.raise_for_status()

    async def _send_or_spool_event(
        self,
        client: httpx.AsyncClient,
        job_id: str,
        event: dict[str, Any],
        *,
        delivery_generation: int = 1,
    ) -> None:
        try:
            await self._post_events(client, job_id, [event], delivery_generation=delivery_generation)
        except Exception:
            logger.warning("failed to stream event for job_id=%s, spooling to disk", job_id)
            await self._spool_events(job_id, [event])

    def _prepare_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Ensure connector config can use SecretStore; fail-closed and never put plaintext into returned events."""
        prepared = dict(snapshot)
        policy = dict(prepared.get("runtime_policy") or {})
        config = dict(policy.get("connector_config") or {})
        secret_ref_id = policy.get("connector_secret_ref_id") or config.get("secret_ref_id")
        if secret_ref_id:
            secret = self._secrets.resolve(str(secret_ref_id), fail_closed=True)
            if not secret:
                raise RuntimeError(f"secret ref unresolved: {secret_ref_id} (fail-closed)")
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
            policy["connector_config"] = config
            prepared["runtime_policy"] = policy
        return prepared

    async def _execute_job(self, client: httpx.AsyncClient, job: dict[str, Any]) -> None:
        job_id = str(job["id"])
        tool_name = str(job.get("tool_name") or "connector")
        arguments = dict(job.get("arguments") or {})
        snapshot = dict(job.get("snapshot") or {})
        delivery_generation = int(job.get("delivery_generation") or job.get("generation") or 1)
        try:
            prepared = self._prepare_snapshot(snapshot)
            async for event in execute_connector_run(
                tool_name=tool_name,
                arguments=arguments,
                snapshot=prepared,
            ):
                safe_event = {
                    "event_type": event.get("event_type"),
                    "payload": dict(event.get("payload") or {}),
                    "source": "edge",
                    "source_event_id": f"{job_id}:{event.get('event_type')}:{int(asyncio.get_event_loop().time() * 1000)}",
                    "delivery_generation": delivery_generation,
                }
                await self._send_or_spool_event(client, job_id, safe_event, delivery_generation=delivery_generation)
        except Exception as exc:
            logger.exception("edge job failed job_id=%s", job_id)
            err_event = {
                "event_type": "run.failed",
                "payload": {"error": str(exc)[:500]},
                "source": "edge",
                "source_event_id": f"{job_id}:run.failed:{int(asyncio.get_event_loop().time() * 1000)}",
                "delivery_generation": delivery_generation,
            }
            await self._send_or_spool_event(client, job_id, err_event, delivery_generation=delivery_generation)


def _looks_like_token(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and " " not in stripped and "\n" not in stripped
