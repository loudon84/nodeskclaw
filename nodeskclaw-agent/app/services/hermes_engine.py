import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings
from app.services.native_event_normalizer import NativeEventNormalizer, progress_payload

logger = logging.getLogger(__name__)

GATEWAY_UNREACHABLE_ERROR_CODE = "errors.skill_run.gateway_unreachable"

RUNTIME_UNREACHABLE = "RUNTIME_UNREACHABLE"
RUNTIME_UNAUTHORIZED = "RUNTIME_UNAUTHORIZED"
RUNTIME_VERSION_UNSUPPORTED = "RUNTIME_VERSION_UNSUPPORTED"
RUNTIME_CAPABILITY_MISSING = "RUNTIME_CAPABILITY_MISSING"
RUNTIME_CAPACITY_EXCEEDED = "RUNTIME_CAPACITY_EXCEEDED"
RUNTIME_START_FAILED = "RUNTIME_START_FAILED"
RUNTIME_EVENT_STREAM_FAILED = "RUNTIME_EVENT_STREAM_FAILED"
RUNTIME_STOP_FAILED = "RUNTIME_STOP_FAILED"
RUNTIME_PROTOCOL_INVALID = "RUNTIME_PROTOCOL_INVALID"
RUNTIME_INTERRUPTED = "RUNTIME_INTERRUPTED"
RUNTIME_STATE_UNAVAILABLE = "RUNTIME_STATE_UNAVAILABLE"

HERMES_VERSION_FLOOR = (2026, 8, 31)
HERMES_VERSION_FLOOR_LABEL = "v2026.8.31"
HERMES_PACKAGE_RELEASE_FLOOR = (0, 21, 0)

REQUIRED_FEATURES = frozenset(
    {
        "run_submission",
        "run_status",
        "run_events_sse",
        "run_stop",
        "run_approval_response",
    }
)
APPROVAL_EXTRA_FEATURES = frozenset({"approval_events"})


def _failed(code: str, message: str) -> dict[str, Any]:
    return {"event_type": "run.failed", "payload": {"error": message, "error_code": code}}


# @lat: [[architecture/skill-agent#Configuration#Gateway Reachability Probe]]
async def probe_gateway_url(gateway_url: str, timeout_seconds: int) -> None:
    timeout = httpx.Timeout(timeout_seconds, connect=timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        await client.get(gateway_url)


def parse_hermes_version(raw: Any) -> tuple[int, int, int] | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    dated = re.search(r"(20\d{2})\.(\d{1,2})\.(\d{1,2})", text)
    if dated:
        return int(dated.group(1)), int(dated.group(2)), int(dated.group(3))
    if text.lower().startswith("v"):
        text = text[1:]
    parts = re.findall(r"\d+", text)
    if len(parts) < 3:
        return None
    return int(parts[0]), int(parts[1]), int(parts[2])


def hermes_version_for_floor(raw: Any) -> tuple[int, int, int] | None:
    parsed = parse_hermes_version(raw)
    if parsed is None:
        return None
    if parsed[0] >= 2000:
        return parsed
    if parsed >= HERMES_PACKAGE_RELEASE_FLOOR:
        return HERMES_VERSION_FLOOR
    return parsed


def reported_hermes_version(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    nested = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
    raw = (
        payload.get("version")
        or payload.get("hermes_version")
        or payload.get("runtime_version")
        or nested.get("version")
        or ""
    )
    return str(raw).strip()


def _feature_set(payload: dict[str, Any]) -> set[str]:
    features = payload.get("features") or payload.get("capabilities") or []
    if isinstance(features, dict):
        return {str(k) for k, v in features.items() if v}
    if isinstance(features, list):
        return {str(x) for x in features if x}
    return set()


def build_native_run_payload(
    *,
    model_name: str,
    runtime_skill_id: str,
    prompt: str,
    context: dict | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    user_input = prompt
    if context:
        user_input = f"{prompt}\n\n{json.dumps(context, ensure_ascii=False)}"
    body: dict[str, Any] = {
        "input": user_input,
        "instructions": (
            f"你是 Hermes Agent。本次任务指定 skill: {runtime_skill_id}。"
            f"请优先按照该 skill 的流程完成用户任务。"
        ),
    }
    if model_name:
        body["model"] = model_name
    if session_id:
        body["session_id"] = session_id
    return body


def _map_http_status(status_code: int, *, start: bool = False, stream: bool = False, stop: bool = False) -> str:
    if status_code in (401, 403):
        return RUNTIME_UNAUTHORIZED
    if status_code in (409, 429):
        return RUNTIME_CAPACITY_EXCEEDED
    if status_code in (400, 422):
        return RUNTIME_PROTOCOL_INVALID
    if stop:
        return RUNTIME_STOP_FAILED
    if stream:
        return RUNTIME_EVENT_STREAM_FAILED
    if start:
        return RUNTIME_START_FAILED
    return RUNTIME_START_FAILED


def normalize_hermes_approval_choice(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in {"session", "always"}:
        raise ValueError("client_approval_choice_forbidden")
    if value in {"approve", "approved", "once", "allow"}:
        return "once"
    if value in {"deny", "denied", "reject"}:
        return "deny"
    raise ValueError("invalid_approval_choice")


def gateway_from_snapshot(snapshot: dict[str, Any] | None) -> str:
    data = snapshot or {}
    policy = data.get("runtime_policy") if isinstance(data.get("runtime_policy"), dict) else {}
    return str(
        policy.get("gateway_url")
        or data.get("gateway_url")
        or policy.get("hermes_base_url")
        or data.get("hermes_base_url")
        or ""
    ).rstrip("/")


# @lat: [[architecture/skill-agent#RM-15 Approval Runtime Control]]
async def respond_runtime_approval(
    *,
    attempt_id: str,
    generation: int,
    choice: str,
    gateway_url: str,
    headers: dict[str, str] | None = None,
    runtime_run_id: str | None = None,
) -> str | None:
    mapped = normalize_hermes_approval_choice(choice)
    binding = await load_runtime_binding(attempt_id)
    if not binding or int(binding.get("generation") or 0) != int(generation):
        return "fenced"
    bound_id = binding.get("runtime_run_id")
    target = str(runtime_run_id or bound_id or "")
    if not target or (bound_id and bound_id != target):
        return "fenced"
    auth_headers = dict(headers or {"Content-Type": "application/json"})
    url = f"{gateway_url.rstrip('/')}/v1/runs/{target}/approval"
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        try:
            resp = await client.post(url, headers=auth_headers, json={"choice": mapped})
        except (httpx.TimeoutException, httpx.NetworkError, OSError):
            return RUNTIME_UNREACHABLE
        if resp.status_code == 404:
            return RUNTIME_STATE_UNAVAILABLE
        if resp.status_code >= 400:
            return _map_http_status(resp.status_code)
        return None


async def stop_runtime_attempt(
    *,
    attempt_id: str,
    generation: int,
    gateway_url: str,
    headers: dict[str, str] | None = None,
    runtime_run_id: str | None = None,
) -> str | None:
    binding = await load_runtime_binding(attempt_id)
    if not binding or int(binding.get("generation") or 0) != int(generation):
        return "fenced"
    bound_id = binding.get("runtime_run_id")
    target = str(runtime_run_id or bound_id or "")
    if not target or (bound_id and bound_id != target):
        return "fenced"
    auth_headers = dict(headers or {"Content-Type": "application/json"})
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
        return await _stop_runtime(
            client,
            gateway_url=gateway_url.rstrip("/"),
            runtime_run_id=target,
            headers=auth_headers,
            attempt_id=attempt_id,
            generation=generation,
        )


def _extract_runtime_run_id(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    nested = data.get("data") if isinstance(data.get("data"), dict) else {}
    rid = data.get("id") or data.get("run_id") or nested.get("id") or nested.get("run_id")
    return str(rid) if rid else None


def _extract_status(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    nested = data.get("data") if isinstance(data.get("data"), dict) else {}
    raw = data.get("status") or nested.get("status") or ""
    return str(raw).strip().lower()




async def load_attempt_generation(attempt_id: str) -> int | None:
    from app.db import SessionLocal
    from app.services.run_service import get_runtime_binding

    async with SessionLocal() as db:
        row = await get_runtime_binding(db, attempt_id)
        if not row:
            return None
        return int(row["generation"])


async def persist_native_binding(
    *,
    attempt_id: str,
    generation: int,
    runtime_run_id: str,
    runtime_version: str | None,
    runtime_session_id: str | None,
    runtime_profile: str | None,
    runtime_capability_snapshot: dict[str, Any] | None,
    runtime_idempotency_key: str,
) -> dict[str, Any] | None:
    from app.db import SessionLocal
    from app.services.run_service import persist_runtime_binding

    async with SessionLocal() as db:
        result = await persist_runtime_binding(
            db,
            attempt_id=attempt_id,
            generation=generation,
            runtime_run_id=runtime_run_id,
            runtime_version=runtime_version,
            runtime_session_id=runtime_session_id,
            runtime_profile=runtime_profile,
            runtime_capability_snapshot=runtime_capability_snapshot,
            runtime_idempotency_key=runtime_idempotency_key,
        )
        if result:
            await db.commit()
        return result


async def load_runtime_binding(attempt_id: str) -> dict[str, Any] | None:
    from app.db import SessionLocal
    from app.services.run_service import get_runtime_binding

    async with SessionLocal() as db:
        return await get_runtime_binding(db, attempt_id)


async def mark_native_terminal(*, attempt_id: str, generation: int) -> None:
    from app.db import SessionLocal
    from app.services.run_service import mark_runtime_terminal

    async with SessionLocal() as db:
        await mark_runtime_terminal(db, attempt_id=attempt_id, generation=generation)
        await db.commit()


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


async def _reconcile_status(
    client: httpx.AsyncClient,
    *,
    gateway_url: str,
    runtime_run_id: str,
    headers: dict[str, str],
) -> tuple[str, dict[str, Any] | None, str | None]:
    url = f"{gateway_url}/v1/runs/{runtime_run_id}"
    try:
        resp = await client.get(url, headers=headers)
    except (httpx.TimeoutException, httpx.NetworkError, OSError):
        return "", None, RUNTIME_UNREACHABLE
    if resp.status_code == 404:
        return "not_found", None, RUNTIME_STATE_UNAVAILABLE
    if resp.status_code in (401, 403):
        return "", None, RUNTIME_UNAUTHORIZED
    if resp.status_code >= 400:
        return "", None, RUNTIME_STATE_UNAVAILABLE
    try:
        data = resp.json()
    except Exception:
        return "", None, RUNTIME_PROTOCOL_INVALID
    return _extract_status(data), data if isinstance(data, dict) else None, None


async def _stop_runtime(
    client: httpx.AsyncClient,
    *,
    gateway_url: str,
    runtime_run_id: str,
    headers: dict[str, str],
    attempt_id: str,
    generation: int,
) -> str | None:
    binding = await load_runtime_binding(attempt_id)
    if not binding or int(binding.get("generation") or 0) != int(generation):
        return None
    bound_id = binding.get("runtime_run_id")
    if bound_id and bound_id != runtime_run_id:
        return None
    url = f"{gateway_url}/v1/runs/{runtime_run_id}/stop"
    try:
        resp = await client.post(url, headers=headers)
    except (httpx.TimeoutException, httpx.NetworkError, OSError):
        return RUNTIME_STOP_FAILED
    if resp.status_code == 404:
        return "stop_404"
    if resp.status_code >= 400:
        return _map_http_status(resp.status_code, stop=True)
    return None


def _terminal_from_status(status: str, error_code: str | None) -> dict[str, Any] | None:
    if error_code == RUNTIME_STATE_UNAVAILABLE or status in {"not_found", "run_not_found"}:
        return _failed(RUNTIME_STATE_UNAVAILABLE, "Hermes runtime run state is unavailable")
    if error_code == RUNTIME_INTERRUPTED or status == "interrupted":
        return _failed(RUNTIME_INTERRUPTED, "Hermes runtime run was interrupted")
    if error_code:
        return _failed(error_code, "Hermes runtime status reconciliation failed")
    if status in {"completed", "succeeded", "success"}:
        return {"event_type": "run.completed", "payload": {"summary": "hermes native run completed"}}
    if status in {"failed", "error"}:
        return _failed(RUNTIME_START_FAILED, "Hermes runtime run failed")
    if status in {"cancelled", "canceled"}:
        return {"event_type": "run.cancelled", "payload": {"message": "hermes native run cancelled"}}
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
    yield {"event_type": "run.progress", "payload": progress_payload("PREPARING", "preparing hermes")}
    if cancel_event and cancel_event.is_set():
        yield {"event_type": "run.cancelled", "payload": {"message": "cancelled before hermes call"}}
        return

    if "gateway_token" in route_snapshot or "env_file" in route_snapshot:
        yield {
            "event_type": "run.failed",
            "payload": {"error": f"Plaintext credential/env_file in snapshot rejected for {tool_name} (fail-closed)"},
        }
        return

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

    timeout_seconds = settings.SKILL_AGENT_TIMEOUT_SECONDS
    try:
        await probe_gateway_url(gateway_url, timeout_seconds)
    except (httpx.TimeoutException, httpx.NetworkError, OSError):
        logger.warning(
            "hermes gateway unreachable tool=%s url=%s timeout=%ss",
            tool_name,
            gateway_url,
            timeout_seconds,
        )
        yield {
            "event_type": "run.failed",
            "payload": {
                "error": f"Hermes runtime gateway unreachable within {timeout_seconds}s: {gateway_url}",
                "error_code": RUNTIME_UNREACHABLE,
            },
        }
        return

    if not run_id or not attempt_id:
        yield _failed(RUNTIME_PROTOCOL_INVALID, "Hermes native run requires run_id and attempt_id")
        return

    generation = await load_attempt_generation(attempt_id)
    if generation is None:
        generation = 0

    auth_headers: dict[str, str] = {"Content-Type": "application/json"}
    if minted_lease and minted_lease.get("token"):
        auth_headers["Authorization"] = f"Bearer {minted_lease['token']}"

    needs_approval = bool(
        route_snapshot.get("requires_approval")
        or arguments.get("requires_approval")
        or route_snapshot.get("approval_required")
    )
    required = set(REQUIRED_FEATURES)
    if needs_approval:
        required |= APPROVAL_EXTRA_FEATURES

    prompt = str(arguments.get("prompt") or "").strip() or str(arguments)
    context = arguments.get("context") if isinstance(arguments.get("context"), dict) else None
    runtime_skill_id = str(route_snapshot.get("runtime_skill_id") or tool_name)
    model_name = str(
        (minted_lease.get("model") if minted_lease else None)
        or route_snapshot.get("model")
        or route_snapshot.get("agent_profile")
        or "hermes"
    )
    session_id = route_snapshot.get("session_id") or route_snapshot.get("runtime_session_id")
    native_payload = build_native_run_payload(
        model_name=model_name,
        runtime_skill_id=runtime_skill_id,
        prompt=prompt,
        context=context,
        session_id=str(session_id) if session_id else None,
    )
    idempotency_key = f"{run_id}:{attempt_id}:{generation}"
    source_prefix = f"hermes:{run_id}:{attempt_id}"
    normalizer = NativeEventNormalizer(attempt_id=attempt_id, source_prefix=source_prefix)
    events_subscribed = False

    yield {"event_type": "run.progress", "payload": progress_payload("RUNTIME_STARTING", "calling hermes native run")}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
            try:
                caps_resp = await client.get(f"{gateway_url}/v1/capabilities", headers=auth_headers)
            except (httpx.TimeoutException, httpx.NetworkError, OSError):
                yield _failed(RUNTIME_UNREACHABLE, "Hermes capabilities probe unreachable")
                return
            if caps_resp.status_code in (401, 403):
                yield _failed(RUNTIME_UNAUTHORIZED, "Hermes capabilities probe unauthorized")
                return
            if caps_resp.status_code >= 400:
                yield _failed(RUNTIME_CAPABILITY_MISSING, "Hermes capabilities probe failed")
                return
            try:
                caps_body = caps_resp.json()
            except Exception:
                yield _failed(RUNTIME_PROTOCOL_INVALID, "Hermes capabilities response is not JSON")
                return
            if not isinstance(caps_body, dict):
                yield _failed(RUNTIME_PROTOCOL_INVALID, "Hermes capabilities response is invalid")
                return

            version_raw = reported_hermes_version(caps_body)
            if not version_raw:
                try:
                    health_resp = await client.get(f"{gateway_url}/health", headers=auth_headers)
                except (httpx.TimeoutException, httpx.NetworkError, OSError):
                    yield _failed(RUNTIME_UNREACHABLE, "Hermes health version probe unreachable")
                    return
                if health_resp.status_code in (401, 403):
                    yield _failed(RUNTIME_UNAUTHORIZED, "Hermes health version probe unauthorized")
                    return
                if health_resp.status_code >= 400:
                    yield _failed(RUNTIME_VERSION_UNSUPPORTED, "Hermes health version probe failed")
                    return
                try:
                    health_body = health_resp.json()
                except Exception:
                    yield _failed(RUNTIME_PROTOCOL_INVALID, "Hermes health response is not JSON")
                    return
                version_raw = reported_hermes_version(health_body if isinstance(health_body, dict) else None)
            parsed = hermes_version_for_floor(version_raw)
            if parsed is None or parsed < HERMES_VERSION_FLOOR:
                yield _failed(
                    RUNTIME_VERSION_UNSUPPORTED,
                    f"Hermes runtime version below {HERMES_VERSION_FLOOR_LABEL}",
                )
                return

            present = _feature_set(caps_body)
            missing = sorted(required - present)
            if missing:
                yield _failed(
                    RUNTIME_CAPABILITY_MISSING,
                    "Hermes runtime is missing required capabilities",
                )
                return

            submit_headers = dict(auth_headers)
            submit_headers["Idempotency-Key"] = idempotency_key
            try:
                start_resp = await client.post(
                    f"{gateway_url}/v1/runs",
                    json=native_payload,
                    headers=submit_headers,
                )
            except (httpx.TimeoutException, httpx.NetworkError, OSError):
                yield _failed(RUNTIME_UNREACHABLE, "Hermes native run submit unreachable")
                return
            if start_resp.status_code >= 400:
                yield _failed(
                    _map_http_status(start_resp.status_code, start=True),
                    "Hermes native run submit failed",
                )
                return
            try:
                start_body = start_resp.json()
            except Exception:
                yield _failed(RUNTIME_PROTOCOL_INVALID, "Hermes native run submit returned invalid JSON")
                return
            runtime_run_id = _extract_runtime_run_id(start_body)
            if not runtime_run_id:
                yield _failed(RUNTIME_PROTOCOL_INVALID, "Hermes native run submit omitted run id")
                return
            nested = start_body.get("data") if isinstance(start_body.get("data"), dict) else {}
            runtime_session_id = start_body.get("session_id") or nested.get("session_id")
            runtime_profile = (
                start_body.get("profile")
                or nested.get("profile")
                or route_snapshot.get("agent_profile")
            )

            binding = await persist_native_binding(
                attempt_id=attempt_id,
                generation=generation,
                runtime_run_id=runtime_run_id,
                runtime_version=str(version_raw),
                runtime_session_id=str(runtime_session_id) if runtime_session_id else None,
                runtime_profile=str(runtime_profile) if runtime_profile else None,
                runtime_capability_snapshot=caps_body,
                runtime_idempotency_key=idempotency_key,
            )
            if binding is None:
                yield _failed(RUNTIME_PROTOCOL_INVALID, "Hermes runtime binding persist was rejected")
                return
            runtime_run_id = str(binding.get("runtime_run_id") or runtime_run_id)

            if cancel_event and cancel_event.is_set():
                stop_code = await _stop_runtime(
                    client,
                    gateway_url=gateway_url,
                    runtime_run_id=runtime_run_id,
                    headers=auth_headers,
                    attempt_id=attempt_id,
                    generation=generation,
                )
                if stop_code == "stop_404":
                    status, _data, rec_code = await _reconcile_status(
                        client,
                        gateway_url=gateway_url,
                        runtime_run_id=runtime_run_id,
                        headers=auth_headers,
                    )
                    terminal = _terminal_from_status(status, rec_code)
                    if terminal:
                        yield terminal
                    else:
                        yield {"event_type": "run.cancelled", "payload": {"message": "cancelled after stop 404"}}
                    return
                if stop_code:
                    yield _failed(stop_code, "Hermes runtime stop failed")
                    return
                yield {"event_type": "run.cancelled", "payload": {"message": "cancelled before event stream"}}
                return

            events_url = f"{gateway_url}/v1/runs/{runtime_run_id}/events"
            yield {"event_type": "run.progress", "payload": progress_payload("RUNTIME_RUNNING", "streaming")}
            try:
                async with client.stream("GET", events_url, headers=auth_headers) as response:
                    events_subscribed = True
                    if response.status_code >= 400:
                        yield _failed(
                            _map_http_status(response.status_code, stream=True),
                            "Hermes event stream failed",
                        )
                        return
                    line_iter = response.aiter_lines().__aiter__()
                    while True:
                        if cancel_event and cancel_event.is_set():
                            stop_code = await _stop_runtime(
                                client,
                                gateway_url=gateway_url,
                                runtime_run_id=runtime_run_id,
                                headers=auth_headers,
                                attempt_id=attempt_id,
                                generation=generation,
                            )
                            for leftover in normalizer.close(terminal_status="failed"):
                                yield leftover
                            if stop_code == "stop_404":
                                break
                            if stop_code:
                                yield _failed(stop_code, "Hermes runtime stop failed")
                                return
                            yield {"event_type": "run.cancelled", "payload": {"message": "cancelled during stream"}}
                            await mark_native_terminal(attempt_id=attempt_id, generation=generation)
                            return
                        try:
                            line = await asyncio.wait_for(line_iter.__anext__(), timeout=0.1)
                        except TimeoutError:
                            for semantic in normalizer.flush_due_to_latency():
                                yield semantic
                            continue
                        except StopAsyncIteration:
                            break
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line.split(":", 1)[1].strip()
                        if data_str in {"[DONE]", "done"}:
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(chunk, dict):
                            continue
                        for semantic in normalizer.ingest(chunk):
                            yield semantic
            except (httpx.TimeoutException, httpx.NetworkError, OSError):
                if not events_subscribed:
                    yield _failed(RUNTIME_EVENT_STREAM_FAILED, "Hermes event stream failed")
                    return

            yield {"event_type": "run.progress", "payload": progress_payload("RECONCILING", "reconciling hermes status")}
            status, _data, rec_code = await _reconcile_status(
                client,
                gateway_url=gateway_url,
                runtime_run_id=runtime_run_id,
                headers=auth_headers,
            )
            if status == "stopping":
                yield {"event_type": "run.progress", "payload": progress_payload("STOPPING", "hermes runtime stopping")}
                status, _data, rec_code = await _reconcile_status(
                    client,
                    gateway_url=gateway_url,
                    runtime_run_id=runtime_run_id,
                    headers=auth_headers,
                )
            terminal = _terminal_from_status(status, rec_code)
            close_status = "completed" if status in {"completed", "succeeded", "success"} else "failed"
            for leftover in normalizer.close(terminal_status=close_status):
                yield leftover
            if terminal:
                if terminal["event_type"] in {"run.completed", "run.failed", "run.cancelled"}:
                    await mark_native_terminal(attempt_id=attempt_id, generation=generation)
                yield terminal
                return
            if status not in {"running", "waiting_for_approval", "waiting"}:
                yield _failed(RUNTIME_STATE_UNAVAILABLE, "Hermes runtime status could not be mapped")
                return
            while status in {"running", "waiting_for_approval", "waiting"}:
                phase = "WAITING_APPROVAL" if status in {"waiting_for_approval", "waiting"} else "RUNTIME_RUNNING"
                yield {
                    "event_type": "run.progress",
                    "payload": progress_payload(phase, f"hermes runtime status {status}"),
                }
                if cancel_event and cancel_event.is_set():
                    stop_code = await _stop_runtime(
                        client,
                        gateway_url=gateway_url,
                        runtime_run_id=runtime_run_id,
                        headers=auth_headers,
                        attempt_id=attempt_id,
                        generation=generation,
                    )
                    for leftover in normalizer.close(terminal_status="failed"):
                        yield leftover
                    if stop_code == "stop_404":
                        rec_status, _data, rec_code = await _reconcile_status(
                            client,
                            gateway_url=gateway_url,
                            runtime_run_id=runtime_run_id,
                            headers=auth_headers,
                        )
                        rec_terminal = _terminal_from_status(rec_status, rec_code)
                        if rec_terminal:
                            if rec_terminal["event_type"] in {"run.completed", "run.failed", "run.cancelled"}:
                                await mark_native_terminal(attempt_id=attempt_id, generation=generation)
                            yield rec_terminal
                        else:
                            yield {"event_type": "run.cancelled", "payload": {"message": "cancelled after stop 404"}}
                        return
                    if stop_code and stop_code != "fenced":
                        yield _failed(stop_code, "Hermes runtime stop failed")
                        return
                    yield {"event_type": "run.cancelled", "payload": {"message": "cancelled while waiting for approval"}}
                    await mark_native_terminal(attempt_id=attempt_id, generation=generation)
                    return
                waiter = cancel_event.wait() if cancel_event is not None else asyncio.sleep(0.05)
                try:
                    await asyncio.wait_for(waiter, timeout=0.05)
                except TimeoutError:
                    pass
                status, _data, rec_code = await _reconcile_status(
                    client,
                    gateway_url=gateway_url,
                    runtime_run_id=runtime_run_id,
                    headers=auth_headers,
                )
                terminal = _terminal_from_status(status, rec_code)
                if terminal:
                    close_status = "completed" if status in {"completed", "succeeded", "success"} else "failed"
                    for leftover in normalizer.close(terminal_status=close_status):
                        yield leftover
                    if terminal["event_type"] in {"run.completed", "run.failed", "run.cancelled"}:
                        await mark_native_terminal(attempt_id=attempt_id, generation=generation)
                    yield terminal
                    return
            yield _failed(RUNTIME_STATE_UNAVAILABLE, "Hermes runtime status could not be mapped")
    except Exception:
        logger.exception("hermes execute failed tool=%s", tool_name)
        yield _failed(RUNTIME_START_FAILED, "Hermes native run failed")
