from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.edge_control_channel import EdgeControlChannel
from app.services.context_revalidate import ContextRevalidationError, revalidate_execution_context
from app.services.edge_skill_installer import EdgeSkillInstaller
from app.services.engine_port import execute_engine
from app.services.execution_observability import (
    bind_from_snapshot,
    normalize_request_trace_id,
    observe_stage,
    record_metric,
)

logger = logging.getLogger(__name__)


class EdgeWorker:
    """Outbound Edge role: heartbeat, claim jobs from Central, execute connectors, post events."""

    def __init__(self) -> None:
        self._running = False
        self._base_url = settings.SKILL_AGENT_CENTRAL_BASE_URL.rstrip("/")
        self._token = settings.SKILL_AGENT_EDGE_TOKEN
        self._node_id = settings.SKILL_AGENT_EDGE_NODE_ID
        self._spool_dir = Path("./data/edge_spool")
        self._spool_dir.mkdir(parents=True, exist_ok=True)
        self._installer = EdgeSkillInstaller()
        self._channel = EdgeControlChannel(settings.SKILL_AGENT_SECRET_STORE)
        self.last_heartbeat_at: datetime | None = None

    def stop(self) -> None:
        self._running = False

    def _request_headers(
        self,
        *,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        payload: Any = b""
        if json_body is not None:
            payload = json.dumps(json_body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        state = self._channel.load()
        if not state or state.identity_version <= 0 or not state.issuer_key_id:
            raise RuntimeError("edge identity not bound")
        headers, _updated = self._channel.sign_request_headers(
            state,
            method=method,
            path=path,
            payload=payload,
        )
        return headers

    async def _ensure_enrolled(self, client: httpx.AsyncClient) -> None:
        state = self._channel.load()
        if not state and self._token and self._node_id:
            state = self._channel.ensure_bootstrap_identity(
                node_id=self._node_id,
                org_id="",
                bootstrap=self._token,
            )
        if not state or state.identity_version > 0 or not state.bootstrap:
            return
        url = f"{self._base_url}/api/v1/internal/edge/enroll"
        body = {"node_id": state.node_id, "public_key": state.public_key}
        response = await client.post(
            url,
            headers={"X-Edge-Bootstrap": state.bootstrap},
            json=body,
        )
        response.raise_for_status()
        data = response.json().get("data") or {}
        self._channel.apply_bind_response(state, data)

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
            await self._ensure_enrolled(client)
            while self._running:
                try:
                    await self._heartbeat(client)
                    await self._reconcile_desired_installations(client)
                    await self._pull_and_fulfill_on_demand_requests(client)
                    await self._flush_spool(client)
                    job = await self._claim_job(client)
                    if job:
                        record_metric("edge_jobs_claimed_total", labels={"outcome": "ok"})
                        await self._execute_job(client, job)
                    else:
                        await asyncio.sleep(settings.SKILL_AGENT_EDGE_POLL_SECONDS)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("EdgeWorker poll error")
                    await asyncio.sleep(settings.SKILL_AGENT_EDGE_POLL_SECONDS)

    async def _report_installation_error(
        self,
        client: httpx.AsyncClient,
        *,
        installation_id: str,
        generation: int,
        error_code: str,
    ) -> None:
        report_url = f"{self._base_url}/api/v1/internal/edge/installations/actual"
        report_body = {
            "installation_id": installation_id,
            "actual_status": "error",
            "generation": generation,
            "meta": {
                "reconciled_by": "edge_worker",
                "node_id": self._node_id,
                "error_code": error_code,
            },
        }
        rep_res = await client.post(
            report_url,
            headers=self._request_headers(
                method="POST",
                path="/api/v1/internal/edge/installations/actual",
                json_body=report_body,
            ),
            json=report_body,
        )
        rep_res.raise_for_status()

    async def _download_installation_bundle(
        self,
        client: httpx.AsyncClient,
        *,
        installation_id: str,
        generation: int,
    ) -> bytes:
        url = (
            f"{self._base_url}/api/v1/internal/edge/installations/"
            f"{installation_id}/bundle?generation={generation}"
        )
        response = await client.get(
            url,
            headers=self._request_headers(
                method="GET",
                path=f"/api/v1/internal/edge/installations/{installation_id}/bundle",
            ),
        )
        response.raise_for_status()
        return response.content

    async def _reconcile_desired_installations(self, client: httpx.AsyncClient) -> None:
        """Fetch desired installations for this node, reconcile state with real installer and report actual status."""
        try:
            url = f"{self._base_url}/api/v1/internal/edge/installations/desired"
            response = await client.get(
                url,
                headers=self._request_headers(
                    method="GET",
                    path="/api/v1/internal/edge/installations/desired",
                ),
            )
            if response.status_code != 200:
                return
            data = response.json().get("data") or {}
            state = self._channel.load()
            raw_items = data.get("items") or []
            items: list[dict[str, Any]] = []
            if state:
                for wrapped in raw_items:
                    payload = self._channel.unwrap_or_none(state, wrapped)
                    if payload:
                        items.append(payload)

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
                    self._installer.uninstall(skill_id=skill_id)
                    if inst_id in local_state:
                        local_state.pop(inst_id, None)
                        local_state_file.write_text(json.dumps(local_state), encoding="utf-8")
                    report_body = {
                        "installation_id": inst_id,
                        "actual_status": "uninstalled",
                        "generation": desired_gen,
                        "meta": {"reconciled_by": "edge_worker", "node_id": self._node_id, "action": "uninstalled"},
                    }
                    rep_res = await client.post(
                        report_url,
                        headers=self._request_headers(
                            method="POST",
                            path="/api/v1/internal/edge/installations/actual",
                            json_body=report_body,
                        ),
                        json=report_body,
                    )
                    rep_res.raise_for_status()
                elif desired_gen != actual_gen:
                    bundle = inst.get("bundle")
                    if not isinstance(bundle, dict):
                        await self._report_installation_error(
                            client,
                            installation_id=inst_id,
                            generation=desired_gen,
                            error_code="errors.skill.bundle_unavailable",
                        )
                        continue
                    try:
                        release_id = bundle.get("release_id")
                        bundle_ref = bundle.get("bundle_ref")
                        bundle_version = bundle.get("version")
                        bundle_sha256 = bundle.get("sha256")
                        bundle_size = bundle.get("size")
                        if not all(
                            isinstance(value, str) and value.strip()
                            for value in (release_id, bundle_ref, bundle_version, bundle_sha256)
                        ):
                            raise ValueError("Incomplete bundle descriptor")
                        if len(bundle_sha256) != 64 or any(char not in "0123456789abcdefABCDEF" for char in bundle_sha256):
                            raise ValueError("Invalid bundle SHA-256")
                        if isinstance(bundle_size, bool) or not isinstance(bundle_size, int) or bundle_size < 0:
                            raise ValueError("Invalid bundle size")
                        zip_bytes = await self._download_installation_bundle(
                            client,
                            installation_id=inst_id,
                            generation=desired_gen,
                        )
                        self._installer.install(
                            skill_id=skill_id,
                            version=str(desired_gen),
                            zip_bytes=zip_bytes,
                            expected_sha256=bundle_sha256,
                            expected_size=bundle_size,
                            meta={
                                "installation_id": inst_id,
                                "node_id": self._node_id,
                                "release_id": release_id,
                                "bundle_ref": bundle_ref,
                            },
                        )
                        if not self._installer.is_installed(skill_id=skill_id, version=str(desired_gen)):
                            raise RuntimeError(f"Skill {skill_id} installation side effect verification failed")

                        local_state[inst_id] = {
                            "skill_id": skill_id,
                            "generation": desired_gen,
                        }
                        local_state_file.write_text(json.dumps(local_state), encoding="utf-8")
                        report_body = {
                            "installation_id": inst_id,
                            "actual_status": "ready",
                            "generation": desired_gen,
                            "meta": {
                                "reconciled_by": "edge_worker",
                                "node_id": self._node_id,
                                "action": "installed",
                                "release_id": release_id,
                                "bundle_ref": bundle_ref,
                                "sha256": bundle_sha256,
                            },
                        }
                        rep_res = await client.post(
                            report_url,
                            headers=self._request_headers(
                                method="POST",
                                path="/api/v1/internal/edge/installations/actual",
                                json_body=report_body,
                            ),
                            json=report_body,
                        )
                        rep_res.raise_for_status()
                    except Exception as exc:
                        logger.warning("installation reconcile failed for %s: %s", inst_id, exc)
                        await self._report_installation_error(
                            client,
                            installation_id=inst_id,
                            generation=desired_gen,
                            error_code="errors.skill.install_failed",
                        )
        except Exception:
            logger.exception("reconcile desired installations failed")

    async def _pull_and_fulfill_on_demand_requests(self, client: httpx.AsyncClient) -> None:
        """Poll Central for on-demand artifact requests and fulfill them via outbound upload."""
        try:
            url = f"{self._base_url}/api/v1/internal/edge/artifacts/on-demand-requests"
            response = await client.get(
                url,
                headers=self._request_headers(
                    method="GET",
                    path="/api/v1/internal/edge/artifacts/on-demand-requests",
                ),
            )
            if response.status_code != 200:
                return
            data = response.json().get("data") or {}
            state = self._channel.load()
            raw_items = data.get("items") or []
            items: list[dict[str, Any]] = []
            if state:
                for wrapped in raw_items:
                    payload = self._channel.unwrap_or_none(state, wrapped)
                    if payload:
                        items.append(payload)
            for req in items:
                req_name = req.get("name")
                job_id = req.get("job_id")
                deliv_gen = int(req.get("delivery_generation") or 1)
                run_gen = int(req.get("run_generation") or 1)
                attempt_id = req.get("attempt_id")
                step_id = req.get("step_id")
                if not req_name or not job_id:
                    continue
                # Look for local file in spool dir or artifacts
                local_file = self._spool_dir / req_name
                if local_file.exists():
                    try:
                        content_bytes = local_file.read_bytes()
                        await self._upload_artifact(
                            client,
                            job_id,
                            artifact_id=req.get("artifact_id") or str(uuid.uuid4()),
                            name=req_name,
                            content_bytes=content_bytes,
                            delivery_generation=deliv_gen,
                            attempt_id=attempt_id,
                            step_id=step_id,
                            run_generation=run_gen,
                        )
                    except Exception:
                        logger.debug("fulfill on-demand artifact %s failed", req_name, exc_info=True)
        except Exception:
            logger.debug("pull on-demand requests failed", exc_info=True)

    async def _heartbeat(self, client: httpx.AsyncClient) -> None:
        url = f"{self._base_url}/api/v1/internal/edge/heartbeat"
        body = {
            "node_id": self._node_id,
            "status_meta": {"role": "edge"},
        }
        response = await client.post(
            url,
            headers=self._request_headers(
                method="POST",
                path="/api/v1/internal/edge/heartbeat",
                json_body=body,
            ),
            json=body,
        )
        response.raise_for_status()
        self.last_heartbeat_at = datetime.now(timezone.utc)

    async def _claim_job(self, client: httpx.AsyncClient) -> dict[str, Any] | None:
        url = f"{self._base_url}/api/v1/internal/edge/jobs"
        response = await client.get(
            url,
            headers=self._request_headers(method="GET", path="/api/v1/internal/edge/jobs"),
        )
        if response.status_code == 204:
            return None
        response.raise_for_status()
        if not response.content:
            return None
        data = response.json()
        state = self._channel.load()
        if state and isinstance(data, dict) and "envelope" in data:
            job = self._channel.verify_command_envelope(state, data)
            return job if isinstance(job, dict) and job.get("id") else None
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
                        record_metric("spool_replay_total", labels={"outcome": "ok"})
                    except httpx.HTTPStatusError as err:
                        if err.response.status_code == 403:
                            logger.warning("Spool event rejected with 403 (preempted) for job %s, discarding", job_id)
                            spool_file.unlink(missing_ok=True)
                            record_metric("spool_replay_total", labels={"outcome": "discarded"})
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
        body = {"events": events, "delivery_generation": delivery_generation}
        headers = self._request_headers(
            method="POST",
            path=f"/api/v1/internal/edge/jobs/{job_id}/events",
            json_body=body,
        )
        headers["X-Delivery-Generation"] = str(delivery_generation)
        response = await client.post(
            url,
            headers=headers,
            json=body,
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
        """Copy the route snapshot without resolving secret material into the job payload."""
        prepared = dict(snapshot)
        policy = dict(prepared.get("runtime_policy") or {})
        policy["connector_config"] = dict(policy.get("connector_config") or {})
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
        attempt_id: str | None = None,
        step_id: str | None = None,
        run_generation: int | None = None,
        upload_mode: str = "eager",
        idempotency_key: str | None = None,
    ) -> None:
        """Upload job artifact to central backend internal edge endpoint."""
        url = f"{self._base_url}/api/v1/internal/edge/jobs/{job_id}/artifacts/upload"
        checksum = hashlib.sha256(content_bytes).hexdigest()
        b64_content = base64.b64encode(content_bytes).decode("ascii")
        body = {
            "artifact_id": artifact_id,
            "name": name,
            "content_type": content_type,
            "content_base64": b64_content,
            "checksum_sha256": checksum,
            "delivery_generation": delivery_generation,
            "attempt_id": attempt_id,
            "step_id": step_id,
            "run_generation": run_generation,
            "size": len(content_bytes),
            "upload_mode": upload_mode,
            "idempotency_key": idempotency_key,
        }
        headers = self._request_headers(
            method="POST",
            path=f"/api/v1/internal/edge/jobs/{job_id}/artifacts/upload",
            json_body=body,
        )
        headers["X-Delivery-Generation"] = str(delivery_generation)
        res = await client.post(url, headers=headers, json=body)
        res.raise_for_status()

    async def _request_artifact(
        self,
        client: httpx.AsyncClient,
        job_id: str,
        *,
        name: str,
        artifact_id: str | None = None,
        delivery_generation: int = 1,
    ) -> bytes:
        """Pull central artifact on demand with SHA256 integrity verification."""
        url = f"{self._base_url}/api/v1/internal/edge/jobs/{job_id}/artifacts/request"
        body: dict[str, Any] = {"name": name}
        if artifact_id:
            body["artifact_id"] = artifact_id
        headers = self._request_headers(
            method="POST",
            path=f"/api/v1/internal/edge/jobs/{job_id}/artifacts/request",
            json_body=body,
        )
        headers["X-Delivery-Generation"] = str(delivery_generation)
        res = await client.post(url, headers=headers, json=body)
        res.raise_for_status()
        data = res.json().get("data") or {}
        b64_content = data.get("content_base64") or ""
        expected_checksum = str(data.get("checksum_sha256") or "").lower()
        content_bytes = base64.b64decode(b64_content)
        actual_checksum = hashlib.sha256(content_bytes).hexdigest().lower()
        if expected_checksum and actual_checksum != expected_checksum:
            raise RuntimeError(f"Edge requested artifact checksum mismatch for '{name}': {actual_checksum} != {expected_checksum}")
        return content_bytes


    async def _execute_job(self, client: httpx.AsyncClient, job: dict[str, Any]) -> None:
        job_id = str(job["id"])
        tool_name = str(job.get("tool_name") or "connector")
        arguments = dict(job.get("arguments") or {})
        snapshot = dict(job.get("snapshot") or {})
        attempt_id = job.get("attempt_id")
        step_id = job.get("step_id")
        delivery_generation = int(job.get("delivery_generation") or job.get("generation") or 1)
        request_trace_id = normalize_request_trace_id(job.get("request_trace_id"))
        if not request_trace_id:
            request_trace_id = normalize_request_trace_id(snapshot.get("request_trace_id"))
        bind_from_snapshot(
            snapshot,
            run_id=str(job.get("run_id") or job_id),
            attempt_id=attempt_id,
            step_id=step_id,
            delivery_generation=delivery_generation,
            edge_node_id=self._node_id,
        )
        observe_stage("edge_execute", outcome="started", engine="connector")

        stop_renew = asyncio.Event()
        cancel_event = asyncio.Event()

        async def _renew_loop():
            renew_url = f"{self._base_url}/api/v1/internal/edge/jobs/{job_id}/lease/renew"
            renew_body = {"delivery_generation": delivery_generation}
            while not stop_renew.is_set():
                try:
                    await asyncio.sleep(20.0)
                    if stop_renew.is_set():
                        break
                    headers = self._request_headers(
                        method="POST",
                        path=f"/api/v1/internal/edge/jobs/{job_id}/lease/renew",
                        json_body=renew_body,
                    )
                    headers["X-Delivery-Generation"] = str(delivery_generation)
                    res = await client.post(renew_url, headers=headers, json=renew_body)
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
                    res = await client.get(
                        cancel_url,
                        headers=self._request_headers(
                            method="GET",
                            path=f"/api/v1/internal/edge/jobs/{job_id}/cancel",
                        ),
                    )
                    if res.status_code == 200:
                        wrapped = res.json().get("data") or {}
                        state = self._channel.load()
                        payload = (
                            self._channel.verify_command_envelope(state, wrapped)
                            if state
                            else None
                        )
                        if payload and (payload.get("cancelled") or payload.get("cancel_requested")):
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
            runtime_policy = prepared.get("runtime_policy") or {}
            required_artifacts = runtime_policy.get("required_artifacts") or []
            if isinstance(required_artifacts, str):
                required_artifacts = [required_artifacts]
            for art_spec in required_artifacts:
                art_name = art_spec if isinstance(art_spec, str) else str(art_spec.get("name") or "")
                art_id = None if isinstance(art_spec, str) else art_spec.get("artifact_id")
                if art_name:
                    try:
                        fetched_bytes = await self._request_artifact(
                            client,
                            job_id,
                            name=art_name,
                            artifact_id=art_id,
                            delivery_generation=delivery_generation,
                        )
                        logger.info("edge successfully fetched required artifact '%s' (%d bytes)", art_name, len(fetched_bytes))
                    except Exception as req_exc:
                        logger.warning("edge failed to fetch required artifact '%s': %s", art_name, req_exc)
                        raise RuntimeError(f"Edge missing required artifact '{art_name}': {req_exc}")

            try:
                execution_context = prepared.get("execution_context")
                context_version = prepared.get("context_version")
                if execution_context is not None or context_version is not None:
                    await revalidate_execution_context(
                        snapshot=prepared,
                        run_id=str(job.get("run_id") or job_id),
                        attempt_id=attempt_id,
                        generation=delivery_generation,
                        org_id=str(prepared.get("org_id") or ""),
                        user_id=str(prepared.get("user_id") or ""),
                    )
            except ContextRevalidationError as exc:
                logger.warning("context revalidation denied job_id=%s: %s", job_id, exc)
                await self._send_or_spool_event(
                    client,
                    job_id,
                    {
                        "event_type": "run.failed",
                        "payload": {"error": "context revalidation denied", "reason": "context_revalidation_denied"},
                        "source": "edge",
                        "source_event_id": f"{job_id}:run.failed:{int(asyncio.get_event_loop().time() * 1000)}",
                        "delivery_generation": delivery_generation,
                        "attempt_id": attempt_id,
                        "step_id": step_id,
                    },
                    delivery_generation=delivery_generation,
                    attempt_id=attempt_id,
                    step_id=step_id,
                    request_trace_id=request_trace_id,
                )
                return

            async for event in execute_engine(
                engine=engine_name,
                tool_name=tool_name,
                arguments=arguments,
                route_snapshot=runtime_policy,
                cancel_event=cancel_event,
            ):
                if cancel_event.is_set():
                    raise asyncio.CancelledError
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
                if request_trace_id:
                    safe_event["request_trace_id"] = request_trace_id
                await self._send_or_spool_event(
                    client,
                    job_id,
                    safe_event,
                    delivery_generation=delivery_generation,
                    attempt_id=attempt_id,
                    step_id=step_id,
                    request_trace_id=request_trace_id,
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
        except asyncio.CancelledError:
            cancelled_event = {
                "event_type": "run.cancelled",
                "payload": {"reason": "cancel_requested"},
                "source": "edge",
                "source_event_id": f"{job_id}:run.cancelled:{int(asyncio.get_event_loop().time() * 1000)}",
                "delivery_generation": delivery_generation,
                "attempt_id": attempt_id,
                "step_id": step_id,
            }
            await self._send_or_spool_event(
                client,
                job_id,
                cancelled_event,
                delivery_generation=delivery_generation,
                attempt_id=attempt_id,
                step_id=step_id,
                request_trace_id=request_trace_id,
            )
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
                request_trace_id=request_trace_id,
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
