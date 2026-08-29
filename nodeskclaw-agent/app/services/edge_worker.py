from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.engine_port import execute_engine
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
        if not settings.SKILL_AGENT_INSECURE_MODE:
            if not self._base_url.startswith("https://"):
                raise RuntimeError("SkillAgent central URL must use HTTPS in production")

        logger.info(
            "SkillAgent EdgeWorker started node_id=%s central=%s",
            self._node_id or "(unset)",
            self._base_url,
        )
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            while self._running:
                try:
                    await self._heartbeat(client)
                    await self._reconcile_desired_installations(client)
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

    async def _reconcile_desired_installations(self, client: httpx.AsyncClient) -> None:
        """Fetch desired installations for this node, reconcile state and report actual status."""
        try:
            url = f"{self._base_url}/api/v1/internal/edge/installations/desired"
            response = await client.get(url, headers=self._headers())
            if response.status_code != 200:
                return
            data = response.json().get("data") or {}
            items = data.get("items") or []

            local_state_file = self._spool_dir / "edge_installations.json"
            local_state: dict[str, Any] = {}
            if local_state_file.exists():
                try:
                    local_state = json.loads(local_state_file.read_text(encoding="utf-8"))
                except Exception:
                    local_state = {}

            report_url = f"{self._base_url}/api/v1/internal/edge/installations/actual"
            for inst in items:
                inst_id = str(inst.get("id"))
                skill_id = str(inst.get("skill_id") or "")
                desired_status = str(inst.get("desired_status") or "installed")
                desired_gen = int(inst.get("desired_generation") or 1)
                actual_gen = int(inst.get("actual_generation") or 0)

                if desired_status == "uninstalling":
                    if inst_id in local_state:
                        local_state.pop(inst_id, None)
                        local_state_file.write_text(json.dumps(local_state), encoding="utf-8")
                    report_body = {
                        "installation_id": inst_id,
                        "actual_status": "uninstalled",
                        "generation": desired_gen,
                        "meta": {"reconciled_by": "edge_worker", "node_id": self._node_id, "action": "uninstalled"},
                    }
                    rep_res = await client.post(report_url, headers=self._headers(), json=report_body)
                    rep_res.raise_for_status()
                elif desired_gen != actual_gen:
                    local_state[inst_id] = {
                        "skill_id": skill_id,
                        "generation": desired_gen,
                    }
                    local_state_file.write_text(json.dumps(local_state), encoding="utf-8")
                    report_body = {
                        "installation_id": inst_id,
                        "actual_status": "ready",
                        "generation": desired_gen,
                        "meta": {"reconciled_by": "edge_worker", "node_id": self._node_id, "action": "installed"},
                    }
                    rep_res = await client.post(report_url, headers=self._headers(), json=report_body)
                    rep_res.raise_for_status()
        except Exception:
            logger.debug("reconcile desired installations failed", exc_info=True)

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
        for spool_file in list(self._spool_dir.glob("spool_*.json")):
            try:
                data = json.loads(spool_file.read_text(encoding="utf-8"))
                job_id = data.get("job_id")
                events = data.get("events") or []
                delivery_generation = int(data.get("delivery_generation") or 1)
                if job_id and events:
                    try:
                        await self._post_events(client, job_id, events, delivery_generation=delivery_generation)
                        spool_file.unlink(missing_ok=True)
                    except httpx.HTTPStatusError as err:
                        if err.response.status_code == 403:
                            logger.warning("Spool event rejected with 403 (preempted) for job %s, discarding", job_id)
                            spool_file.unlink(missing_ok=True)
                        else:
                            raise
            except Exception:
                logger.debug("spool flush retry failed for %s", spool_file.name, exc_info=True)

    async def _spool_events(
        self,
        job_id: str,
        events: list[dict[str, Any]],
        *,
        delivery_generation: int = 1,
        attempt_id: str | None = None,
        step_id: str | None = None,
        request_trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        try:
            spool_file = self._spool_dir / f"spool_{job_id}_{uuid.uuid4().hex}.json"
            envelope = {
                "job_id": job_id,
                "events": events,
                "delivery_generation": delivery_generation,
                "attempt_id": attempt_id,
                "step_id": step_id,
                "request_trace_id": request_trace_id,
                "idempotency_key": idempotency_key,
            }
            spool_file.write_text(json.dumps(envelope), encoding="utf-8")
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
        attempt_id: str | None = None,
        step_id: str | None = None,
        request_trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> None:
        try:
            await self._post_events(client, job_id, [event], delivery_generation=delivery_generation)
        except Exception:
            logger.warning("failed to stream event for job_id=%s, spooling to disk", job_id)
            await self._spool_events(
                job_id,
                [event],
                delivery_generation=delivery_generation,
                attempt_id=attempt_id,
                step_id=step_id,
                request_trace_id=request_trace_id,
                idempotency_key=idempotency_key,
            )

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

    async def _upload_artifact(
        self,
        client: httpx.AsyncClient,
        job_id: str,
        *,
        artifact_id: str,
        name: str,
        content_bytes: bytes,
        content_type: str = "application/octet-stream",
        delivery_generation: int = 1,
    ) -> None:
        """Upload job artifact to central backend internal edge endpoint."""
        url = f"{self._base_url}/api/v1/internal/edge/jobs/{job_id}/artifacts/upload"
        checksum = hashlib.sha256(content_bytes).hexdigest()
        b64_content = base64.b64encode(content_bytes).decode("ascii")
        headers = dict(self._headers())
        headers["X-Delivery-Generation"] = str(delivery_generation)
        body = {
            "artifact_id": artifact_id,
            "name": name,
            "content_type": content_type,
            "content_base64": b64_content,
            "checksum_sha256": checksum,
            "delivery_generation": delivery_generation,
        }
        res = await client.post(url, headers=headers, json=body)
        res.raise_for_status()

    async def _execute_job(self, client: httpx.AsyncClient, job: dict[str, Any]) -> None:
        job_id = str(job["id"])
        tool_name = str(job.get("tool_name") or "connector")
        arguments = dict(job.get("arguments") or {})
        snapshot = dict(job.get("snapshot") or {})
        attempt_id = job.get("attempt_id")
        step_id = job.get("step_id")
        delivery_generation = int(job.get("delivery_generation") or job.get("generation") or 1)

        stop_renew = asyncio.Event()
        cancel_event = asyncio.Event()

        async def _renew_loop():
            renew_url = f"{self._base_url}/api/v1/internal/edge/jobs/{job_id}/lease/renew"
            headers = dict(self._headers())
            headers["X-Delivery-Generation"] = str(delivery_generation)
            while not stop_renew.is_set():
                try:
                    await asyncio.sleep(20.0)
                    if stop_renew.is_set():
                        break
                    res = await client.post(renew_url, headers=headers, json={"delivery_generation": delivery_generation})
                    if res.status_code == 403:
                        logger.warning("edge job lease preempted job_id=%s generation=%s", job_id, delivery_generation)
                        cancel_event.set()
                        break
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.debug("edge lease renew check error", exc_info=True)

        async def _cancel_loop():
            cancel_url = f"{self._base_url}/api/v1/internal/edge/jobs/{job_id}/cancel"
            while not stop_renew.is_set():
                try:
                    await asyncio.sleep(2.0)
                    if stop_renew.is_set():
                        break
                    res = await client.get(cancel_url, headers=self._headers())
                    if res.status_code == 200:
                        data = res.json().get("data") or {}
                        if data.get("cancelled") or data.get("cancel_requested"):
                            cancel_event.set()
                            break
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass

        renew_task = asyncio.create_task(_renew_loop())
        cancel_task = asyncio.create_task(_cancel_loop())

        try:
            prepared = self._prepare_snapshot(snapshot)
            placement = prepared.get("placement") or {}
            engine_name = str(placement.get("engine") or "connector")

            async for event in execute_engine(
                engine=engine_name,
                tool_name=tool_name,
                arguments=arguments,
                route_snapshot=prepared,
                cancel_event=cancel_event,
            ):
                if cancel_event.is_set():
                    break
                event_type = event.get("event_type")
                payload = dict(event.get("payload") or {})
                safe_event = {
                    "event_type": event_type,
                    "payload": payload,
                    "source": "edge",
                    "source_event_id": f"{job_id}:{event_type}:{int(asyncio.get_event_loop().time() * 1000)}",
                    "delivery_generation": delivery_generation,
                    "attempt_id": attempt_id,
                    "step_id": step_id,
                }
                await self._send_or_spool_event(
                    client,
                    job_id,
                    safe_event,
                    delivery_generation=delivery_generation,
                    attempt_id=attempt_id,
                    step_id=step_id,
                )

                # If artifact produced on edge or on run completion, upload artifact
                if event_type == "run.completed" and (payload.get("content") or payload.get("summary")):
                    content_str = str(payload.get("content") or payload.get("summary") or "")
                    art_id = str(uuid.uuid4())
                    try:
                        await self._upload_artifact(
                            client,
                            job_id,
                            artifact_id=art_id,
                            name="edge_result.txt",
                            content_bytes=content_str.encode("utf-8"),
                            content_type="text/plain; charset=utf-8",
                            delivery_generation=delivery_generation,
                        )
                    except Exception:
                        logger.debug("edge artifact upload failed", exc_info=True)
        except Exception as exc:
            logger.exception("edge job failed job_id=%s", job_id)
            err_event = {
                "event_type": "run.failed",
                "payload": {"error": str(exc)[:500]},
                "source": "edge",
                "source_event_id": f"{job_id}:run.failed:{int(asyncio.get_event_loop().time() * 1000)}",
                "delivery_generation": delivery_generation,
                "attempt_id": attempt_id,
                "step_id": step_id,
            }
            await self._send_or_spool_event(
                client,
                job_id,
                err_event,
                delivery_generation=delivery_generation,
                attempt_id=attempt_id,
                step_id=step_id,
            )
        finally:
            stop_renew.set()
            renew_task.cancel()
            cancel_task.cancel()
            try:
                await renew_task
            except asyncio.CancelledError:
                pass
            try:
                await cancel_task
            except asyncio.CancelledError:
                pass


def _looks_like_token(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped) and " " not in stripped and "\n" not in stripped
