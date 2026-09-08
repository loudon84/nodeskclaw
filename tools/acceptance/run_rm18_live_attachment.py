#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import run_rm13_live_native as rm13

BLOCKER = "RM18_LIVE_ATTACHMENT_BLOCKED"
CLAIMS = ("CLM-02", "CLM-03", "CLM-04", "CLM-07", "CLM-09", "CLM-12", "CLM-27")
CANDIDATE_PATH = ROOT / ".smc" / "runs" / "RM-18" / "verification-candidate.json"
ARTIFACT_INPUT_MARKERS = (
    "/artifacts/",
    "artifact_id",
    "chat_attachment:",
)


class LiveBlocked(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def emit_result(claims: dict[str, str]) -> None:
    payload = {"claims": {cid: {"result": claims[cid]} for cid in CLAIMS}}
    print("SMC_ACCEPTANCE_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def fail_claims(reason: str) -> dict[str, str]:
    _ = reason
    return {cid: "FAIL" for cid in CLAIMS}


def missing_claims(reason: str) -> dict[str, str]:
    _ = reason
    return {cid: "MISSING" for cid in CLAIMS}


def portal_envelope(payload: Any) -> bool:
    return isinstance(payload, dict) and ("code" in payload or "data" in payload) and "attachment_ref" not in payload


def canonical_error(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    keys = set(payload)
    return keys >= {"error_code", "message_key", "message"} and isinstance(payload.get("error_code"), str)


def jsonrpc_canonical(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    data = error.get("data")
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("error_code"), str):
        return None
    if "message_key" not in data or "message" not in data:
        return None
    return data


def uses_artifact_as_input(payload: Any) -> bool:
    raw = json.dumps(payload, ensure_ascii=False)
    return any(marker in raw for marker in ARTIFACT_INPUT_MARKERS if marker != "artifact_id") and (
        "/api/v1/runs/" in raw and "/artifacts/" in raw and "/download" in raw
    )


def select_attachment_tool(tools: list[Any], preferred: str) -> str | None:
    named = [
        item
        for item in tools
        if isinstance(item, dict) and bool(item.get("supportsAttachments")) and item.get("name")
    ]
    if not named:
        return None
    if preferred and any(item.get("name") == preferred for item in named):
        return preferred
    return str(named[0]["name"])


def upload_public_attachment(base: str, token: str, org_id: str, timeout: int) -> tuple[int, Any]:
    boundary = "----rm18attachment" + uuid.uuid4().hex
    filename = "report.pdf"
    file_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Org-Id": org_id,
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    request = Request(
        f"{base.rstrip('/')}/api/v1/attachments",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return int(response.status), rm13._json_body(raw)
    except HTTPError as exc:
        raw = exc.read() if exc.fp else b""
        return int(exc.code), rm13._json_body(raw)
    except URLError as exc:
        raise LiveBlocked(BLOCKER, f"upload unreachable: {exc.reason}") from exc


def probe_candidate() -> int:
    if not CANDIDATE_PATH.is_file():
        print("VERIFICATION_CANDIDATE_MISSING", file=sys.stderr)
        return 2
    data = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    candidate_id = str(data.get("candidate_id") or "").strip()
    if not candidate_id:
        print("VERIFICATION_CANDIDATE_EMPTY", file=sys.stderr)
        return 2
    print(candidate_id)
    return 0


def preflight_env() -> int:
    missing = rm13.missing_live_vars()
    if missing:
        print("REAL_HERMES_RUNTIME_UNAVAILABLE")
        for name in missing:
            print(f"missing: {name}")
        return 2
    print("RM-18 live env complete")
    return 0


# @lat: [[architecture/skill-agent#RM-18 Public Attachment Input]]
def run_live() -> dict[str, Any]:
    backend = rm13.require_named("RM13_BACKEND_BASE_URL", "RM12_BACKEND_BASE_URL")
    user_jwt = rm13.require_named("RM13_USER_JWT", "RM12_USER_JWT")
    org_id = rm13.require_named("RM13_ORG_ID", "RM12_ORG_ID")
    preferred_tool = os.environ.get("RM18_TOOL_NAME") or rm13.require_named("RM13_TOOL_NAME", "RM12_TOOL_NAME")
    agent_base = rm13.require_named("RM13_AGENT_BASE_URL", "RM12_AGENT_BASE_URL")
    agent_token = rm13.require_named("SKILL_AGENT_INTERNAL_TOKEN")
    rm13.require_named("RM13_HERMES_BASE_URL")
    rm13.require_named("RM13_HERMES_API_SERVER_KEY")
    rm13.require_named("RM13_AGENT_DATABASE_URL")
    timeout = rm13.timeout_seconds()

    catalog_status, catalog = rm13.mcp_call(
        backend, user_jwt, org_id, "tools/list", {}, timeout=timeout
    )
    if catalog_status != 200:
        raise LiveBlocked(BLOCKER, f"tools/list HTTP {catalog_status}")
    result = catalog.get("result") if isinstance(catalog, dict) else {}
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        raise LiveBlocked(BLOCKER, "tools/list missing tools")
    tool_name = select_attachment_tool(tools, preferred_tool)
    if not tool_name:
        raise LiveBlocked(
            "VERIFICATION_BLOCKED",
            "no Catalog tool advertises reachable supportsAttachments=true",
        )

    upload_status, receipt = upload_public_attachment(backend, user_jwt, org_id, timeout)
    if upload_status != 200:
        raise LiveBlocked(BLOCKER, f"upload HTTP {upload_status}")
    if not isinstance(receipt, dict):
        raise LiveBlocked(BLOCKER, "upload returned non-object")
    if portal_envelope(receipt):
        raise LiveBlocked(BLOCKER, "upload used Portal envelope")
    if "attachment_ref" not in receipt:
        raise LiveBlocked(BLOCKER, "upload missing attachment_ref")
    if "workspace_id" in receipt:
        raise LiveBlocked(BLOCKER, "upload receipt leaked workspace_id")
    if not receipt.get("expires_at") or not receipt.get("checksum_sha256"):
        raise LiveBlocked(BLOCKER, "upload receipt missing TTL or checksum")
    attachment_ref = str(receipt["attachment_ref"])
    if not attachment_ref.startswith("att_"):
        raise LiveBlocked(BLOCKER, "upload ref is not opaque att_ token")
    leaks = rm13.scan_public_surface(receipt)
    if leaks:
        raise LiveBlocked(BLOCKER, "upload receipt public surface leak")

    invalid_status, invalid_payload = rm13.mcp_call(
        backend,
        user_jwt,
        org_id,
        "tools/call",
        {
            "name": tool_name,
            "arguments": rm13.tool_arguments(),
            "client_context": {"attachment_refs": ["artifact_id", "att_unknown_other_user"]},
        },
        timeout=timeout,
        idempotency_key=f"rm18-invalid-{uuid.uuid4()}",
    )
    invalid_error = jsonrpc_canonical(invalid_payload)
    if invalid_status not in {200, 400, 403, 404, 410, 422}:
        raise LiveBlocked(BLOCKER, f"invalid ref unexpected HTTP {invalid_status}")
    if invalid_error is None:
        raise LiveBlocked(BLOCKER, "invalid ref did not return nested canonical error")
    if invalid_error.get("error_code") not in {
        "ATTACHMENT_REF_INVALID",
        "ATTACHMENT_NOT_FOUND",
        "ATTACHMENT_SCOPE_DENIED",
        "ATTACHMENT_EXPIRED",
        "ATTACHMENT_NOT_SUPPORTED",
    }:
        raise LiveBlocked(BLOCKER, "invalid ref error_code mismatch")
    invalid_structured = (invalid_payload.get("result") or {}) if isinstance(invalid_payload, dict) else {}
    if isinstance(invalid_structured, dict) and invalid_structured.get("structuredContent", {}).get("run_id"):
        raise LiveBlocked(BLOCKER, "invalid ref created executable Run")

    call_status, call_payload = rm13.mcp_call(
        backend,
        user_jwt,
        org_id,
        "tools/call",
        {
            "name": tool_name,
            "arguments": rm13.tool_arguments(),
            "client_context": {"attachment_refs": [attachment_ref]},
        },
        timeout=timeout,
        idempotency_key=f"rm18-ok-{uuid.uuid4()}",
    )
    if call_status != 200:
        raise LiveBlocked(BLOCKER, f"tools/call HTTP {call_status}")
    envelope = rm13.envelope_from_mcp(call_payload)
    accepted_refs = envelope.get("attachment_refs")
    if accepted_refs != [attachment_ref]:
        raise LiveBlocked(BLOCKER, "accepted attachment_refs mismatch")
    if uses_artifact_as_input(call_payload):
        raise LiveBlocked(BLOCKER, "accepted used Artifact download as input")
    leaks.extend(rm13.scan_public_surface(call_payload))
    if leaks:
        raise LiveBlocked(BLOCKER, "tools/call public surface leak")
    run_id = str(envelope.get("run_id") or "")
    if not run_id:
        raise LiveBlocked(BLOCKER, "accepted missing run_id")
    rm13.wait_until_agent_has_run(agent_base, agent_token, org_id, run_id, timeout)
    binding = rm13.wait_for_binding(run_id, timeout)
    if not str(binding.get("runtime_run_id") or ""):
        raise LiveBlocked(BLOCKER, "attempt runtime binding missing")
    return {
        "schema": "smc.rm18.live-v140.v1",
        "policy": "REAL_PROCESS",
        "result": "PASS",
        "auth_type": "user_jwt",
        "tool_name": tool_name,
        "attachment_ref_prefix": "att_",
        "timestamp": rm13.utcnow(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-env", action="store_true")
    parser.add_argument("--probe-candidate", action="store_true")
    args = parser.parse_args()
    if args.preflight_env:
        return preflight_env()
    if args.probe_candidate:
        return probe_candidate()
    claims = fail_claims("not-run")
    try:
        evidence = run_live()
    except (LiveBlocked, rm13.LiveBlocked) as exc:
        code = getattr(exc, "code", BLOCKER)
        print(f"{code}: {exc}", file=sys.stderr)
        if code == "VERIFICATION_BLOCKED":
            emit_result(missing_claims(str(exc)))
            return 2
        emit_result(claims)
        return 1
    if evidence.get("result") != "PASS":
        emit_result(claims)
        return 1
    emit_result({cid: "PASS" for cid in CLAIMS})
    print("RM-18 live public attachment PASS")
    print("auth_type=" + str(evidence.get("auth_type") or ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
