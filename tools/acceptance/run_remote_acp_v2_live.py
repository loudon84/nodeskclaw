#!/usr/bin/env python3
"""Provider Live runner for Remote ACP v2. Missing env => BLOCKED, exit 1."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

REQUIRED_ENV = (
    "NODESKCLAW_BACKEND_URL",
    "NODESKCLAW_ACCESS_TOKEN",
    "NODESKCLAW_ORG_ID",
    "REMOTE_ACP_AGENT_REF",
)

SCENARIOS = (
    "initialize",
    "session/new",
    "prompt streaming",
    "session/resume",
    "attachment",
    "approval",
    "cancel",
    "artifact",
    "terminal",
    "disconnect/reconnect",
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from remote_acp_test_client import RemoteAcpTestClient  # noqa: E402


def _http_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = Request(url, headers=headers)
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _ws_url(base: str, agent_ref: str) -> str:
    if base.startswith("https://"):
        ws = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        ws = "ws://" + base[len("http://") :]
    else:
        ws = base
    return f"{ws.rstrip('/')}/api/v1/remote-experts/{agent_ref}/acp"


def _error_code(frame: dict[str, Any]) -> str:
    err = frame.get("error") or {}
    data = err.get("data") or {}
    return str(data.get("error_code") or err.get("code") or "")


def _frame_error(frame: dict[str, Any]) -> dict[str, Any] | None:
    err = frame.get("error")
    if not isinstance(err, dict):
        return None
    data = err.get("data") if isinstance(err.get("data"), dict) else {}
    return {
        "message": err.get("message"),
        "code": err.get("code"),
        "error_code": data.get("error_code"),
        "message_key": data.get("message_key"),
        "data": data or None,
    }


def _extract_run_ids(frames: list[dict[str, Any]]) -> list[str]:
    found: list[str] = []
    blob = json.dumps(frames, ensure_ascii=False)
    for token in (
        "/acp/runs/",
        "nodeskclaw://artifact/",
        '"run_id":',
        '"runId":',
    ):
        start = 0
        while True:
            idx = blob.find(token, start)
            if idx < 0:
                break
            if token in {"/acp/runs/", "nodeskclaw://artifact/"}:
                end = idx + len(token)
                while end < len(blob) and blob[end] not in '"\\/ ?,}':
                    end += 1
                piece = blob[idx:end]
            else:
                piece = blob[idx : idx + 80]
            if piece not in found:
                found.append(piece)
            start = idx + len(token)
    return found[:8]


def _diag(
    *,
    session_id: str | None,
    request_id: str | None,
    frame: dict[str, Any],
    client: RemoteAcpTestClient,
    updates_limit: int = 8,
) -> dict[str, Any]:
    updates = client.updates[-updates_limit:]
    permissions = client.permissions[-5:]
    return {
        "session_id": session_id,
        "request_id": request_id,
        "last_seq": client.last_seq,
        "stopReason": (frame.get("result") or {}).get("stopReason"),
        "result": frame.get("result"),
        "error": _frame_error(frame),
        "update_count": len(client.updates),
        "permission_count": len(client.permissions),
        "run_id_hints": _extract_run_ids(client.updates + client.permissions),
        "last_updates": updates,
        "last_permissions": permissions,
    }


async def _run_scenarios() -> dict[str, Any]:
    base = os.environ["NODESKCLAW_BACKEND_URL"].rstrip("/")
    token = os.environ["NODESKCLAW_ACCESS_TOKEN"]
    org_id = os.environ["NODESKCLAW_ORG_ID"]
    agent_ref = os.environ["REMOTE_ACP_AGENT_REF"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "Accept": "application/json",
    }
    results: dict[str, dict[str, Any]] = {}

    contracts = _http_json(f"{base}/api/v1/remote-experts/contracts", {"Accept": "application/json"})
    catalog = _http_json(f"{base}/api/v1/remote-experts/{agent_ref}", headers)
    if catalog.get("status") != "ready" or not ((catalog.get("capabilities") or {}).get("acp") or {}).get("remote_transport"):
        raise RuntimeError("agent not ACP-ready")

    url = _ws_url(base, agent_ref)
    client = RemoteAcpTestClient(url, token=token, org_id=org_id, trace_id=str(uuid.uuid4()))
    await client.connect()
    try:
        init = await client.initialize()
        protocol = ((init.get("result") or {}).get("protocolVersion"))
        results["initialize"] = {
            "status": "PASS" if protocol == 1 else "FAIL",
            "actual": protocol,
        }

        session_id = await client.session_new()
        results["session/new"] = {
            "status": "PASS" if session_id else "FAIL",
            "actual": "uuid" if session_id else "missing",
        }

        deny = await client.rpc(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "resource_link", "uri": "file:///etc/passwd"}],
            },
            request_id=str(uuid.uuid4()),
            timeout=20,
        )
        results["attachment"] = {
            "status": "PASS" if _error_code(deny) == "ACP_RESOURCE_DENIED" else "FAIL",
            "actual": _error_code(deny) or deny.get("result"),
        }

        client.updates = []
        client.permissions = []
        prompt_id = str(uuid.uuid4())
        prompt_text = (
            "Call write_file now. Create workspace file g4-live-artifact.txt "
            "whose entire contents are exactly g4-live-ok. "
            "Do not call skills_list, skill_view, skill_manage, or memory. "
            "Do not answer with markdown only."
        )
        sent = await client.send_rpc(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": prompt_text}],
            },
            request_id=prompt_id,
        )
        try:
            prompt = await client.wait_response(sent, timeout=180)
        except TimeoutError:
            prompt = {"error": {"message": "no prompt frames within 180s"}}
        streamed = any(frame.get("method") == "session/update" for frame in client.updates)
        stop = (prompt.get("result") or {}).get("stopReason")
        prompt_diag = _diag(
            session_id=session_id,
            request_id=prompt_id,
            frame=prompt,
            client=client,
        )
        results["prompt streaming"] = {
            "status": "PASS" if streamed and "error" not in prompt else "FAIL",
            "actual": {
                "updates": len(client.updates),
                "stopReason": stop,
                "error": prompt.get("error"),
                "diag": prompt_diag,
            },
        }
        results["terminal"] = {
            "status": "PASS" if stop and stop != "ACP_REMOTE_RUN_FAILED" else "FAIL",
            "actual": {"stopReason": stop, "error": _frame_error(prompt), "diag": prompt_diag},
        }
        artifact_hit = json.dumps(client.updates).find("/acp/runs/") >= 0 or json.dumps(client.updates).find("nodeskclaw://artifact/") >= 0
        results["artifact"] = {
            "status": "PASS" if artifact_hit else "FAIL",
            "actual": {
                "resource": "resource_link" if artifact_hit else "missing",
                "run_id_hints": prompt_diag["run_id_hints"],
                "diag": prompt_diag,
            },
        }

        client.updates = []
        client.permissions = []
        approval_prompt = (
            "park-waiting-approval now. "
            "Use the park-waiting-approval skill immediately. "
            "Do not call write_file, skills_list, skill_view, skill_manage, or memory. "
            "Park this Native Run in waiting_for_approval."
        )
        approval_id = str(uuid.uuid4())
        approval_sent = await client.send_rpc(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": [{"type": "text", "text": approval_prompt}],
            },
            request_id=approval_id,
        )
        try:
            approval_frame = await client.wait_response(approval_sent, timeout=180)
        except TimeoutError:
            approval_frame = {"error": {"message": "no approval frames within 180s"}}
        approval_diag = _diag(
            session_id=session_id,
            request_id=approval_id,
            frame=approval_frame,
            client=client,
        )
        results["approval"] = {
            "status": "PASS" if client.permissions else "FAIL",
            "actual": {
                "permissions": len(client.permissions),
                "stopReason": (approval_frame.get("result") or {}).get("stopReason"),
                "error": _frame_error(approval_frame),
                "diag": approval_diag,
            },
        }
        after_seq = client.last_seq
        results["_session"] = {
            "session_id": session_id,
            "after_seq": after_seq,
            "trace_id": client.trace_id,
        }
    finally:
        await client.close()

    reconnect = RemoteAcpTestClient(url, token=token, org_id=org_id, trace_id=str(uuid.uuid4()))
    await reconnect.connect()
    try:
        await reconnect.initialize()
        resumed = await reconnect.session_resume(session_id, after_seq=after_seq)
        results["session/resume"] = {
            "status": "PASS" if (resumed.get("result") or {}).get("sessionId") == session_id else "FAIL",
            "actual": resumed.get("result") or resumed.get("error"),
        }
        results["disconnect/reconnect"] = {
            "status": results["session/resume"]["status"],
            "actual": "resumed_after_close",
        }
    finally:
        await reconnect.close()

    cancel_client = RemoteAcpTestClient(url, token=token, org_id=org_id, trace_id=str(uuid.uuid4()))
    await cancel_client.connect()
    try:
        await cancel_client.initialize()
        cancel_session = await cancel_client.session_new()
        rid = await cancel_client.send_rpc(
            "session/prompt",
            {
                "sessionId": cancel_session,
                "prompt": [
                    {
                        "type": "text",
                        "text": (
                            "Start a long-running task now. Call the terminal tool and run: "
                            "python -c \"import time; [print(i, flush=True) or time.sleep(2) "
                            "for i in range(1, 61)]\". "
                            "Do not summarize early. Do not finish until the command completes. "
                            "Do not call write_file, skills_list, skill_view, skill_manage, or memory."
                        ),
                    }
                ],
            },
            request_id=str(uuid.uuid4()),
        )
        try:
            cancelled = await cancel_client.wait_response(
                rid,
                timeout=45,
                cancel_after=3.0,
                cancel_session_id=cancel_session,
            )
        except TimeoutError:
            cancelled = {"error": {"message": "cancel did not complete within 45s"}}
        stop = (cancelled.get("result") or {}).get("stopReason")
        cancel_diag = _diag(
            session_id=cancel_session,
            request_id=rid,
            frame=cancelled,
            client=cancel_client,
        )
        results["cancel"] = {
            "status": "PASS" if stop == "cancelled" else "FAIL",
            "actual": {
                "stopReason": stop,
                "result": cancelled.get("result"),
                "error": _frame_error(cancelled) or cancelled.get("error"),
                "diag": cancel_diag,
            },
        }
    finally:
        await cancel_client.close()

    return {"contracts": contracts, "agent_ref": agent_ref, "scenarios": results}


def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        payload = {
            "SMC_ACCEPTANCE_RESULT": "FAIL",
            "status": "BLOCKED",
            "production_gate": "unpassed",
            "frontendContractGate": "pending",
            "reason": "missing_live_credentials",
            "missing": missing,
            "scenarios": list(SCENARIOS),
            "evidence_dir": "docs_agent/evidence/remote-acp-v2",
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return 1
    try:
        live = asyncio.run(_run_scenarios())
    except Exception as exc:
        payload = {
            "SMC_ACCEPTANCE_RESULT": "FAIL",
            "status": "FAIL",
            "production_gate": "unpassed",
            "frontendContractGate": "pending",
            "reason": type(exc).__name__,
            "error": str(exc),
            "scenarios": list(SCENARIOS),
            "evidence_dir": "docs_agent/evidence/remote-acp-v2",
        }
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return 1
    scenario_results = live["scenarios"]
    failed = [name for name in SCENARIOS if scenario_results.get(name, {}).get("status") != "PASS"]
    ok = not failed
    payload = {
        "SMC_ACCEPTANCE_RESULT": "PASS" if ok else "FAIL",
        "status": "PASS" if ok else "FAIL",
        "production_gate": "unpassed",
        "frontendContractGate": "pending",
        "reason": "all_scenarios_passed" if ok else "scenario_failed",
        "failed": failed,
        "scenario_results": scenario_results,
        "contracts": live.get("contracts"),
        "agent_ref": live.get("agent_ref"),
        "evidence_dir": "docs_agent/evidence/remote-acp-v2",
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
