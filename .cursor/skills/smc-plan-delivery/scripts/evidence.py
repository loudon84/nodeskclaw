#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from common import append_jsonl, atomic_write, find_repo_root, parse_first_table, plan_id, read_jsonl, repo_relative_path, section, split_values, strip_md, utc_now
from workspace import inspect as workspace_inspect
from acceptance import acceptance_enabled, blocking_claims, candidate_status, preflight_verification, verification_meta

VALID_POLICIES = {"LOCAL_TRANSIENT", "LOCAL_DURABLE", "CI_ARTIFACT", "EXTERNAL_ARTIFACT", "REPO_SUMMARY"}
MANIFEST_SCHEMA = "smc.evidence.manifest.v3"


def verification_rows(plan: Path) -> dict[str, dict[str, str]]:
    body = section(plan.read_text(encoding="utf-8"), "Verification Ledger")
    _, rows = parse_first_table(body)
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        vid = strip_md(row.get("Verification ID", "")).upper()
        if vid: result[vid] = row
    return result


def blocking_verifications(plan: Path) -> list[str]:
    return [vid for vid, row in verification_rows(plan).items() if strip_md(row.get("Blocking", "")).lower() == "yes"]


def ledger_path(root: Path, pid: str) -> Path:
    return root / ".smc" / "evidence" / pid / "ledger.jsonl"


def safe_plan_id(pid: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", pid).strip("-._")
    return value or "plan"


def default_manifest_path(root: Path, pid: str) -> Path:
    return root / "docs_agent" / "evidence" / f"{safe_plan_id(pid)}-evidence.json"


def expected_plan_command(plan: Path, vid: str) -> str | None:
    row = verification_rows(plan).get(vid)
    if not row: return None
    if acceptance_enabled(plan):
        try:
            if verification_meta(plan, vid)["evidence_action"] == "REUSE_EVIDENCE":
                return None
        except ValueError:
            pass
    raw = strip_md(row.get("Entry Point / Command", ""))
    if not raw: return None
    try: return shlex.join(shlex.split(raw))
    except ValueError: return raw


def _freshness(plan: Path, rec: dict) -> bool:
    ws = workspace_inspect(plan)
    return (
        ws["pass"]
        and rec.get("scope_fingerprint") == ws["scope_fingerprint"]
        and rec.get("ambient_fingerprint") == ws["ambient_fingerprint"]
    )


def current_status(plan: Path, vid: str, expected_command: str | None = None) -> tuple[str, dict | None]:
    # @lat: [[plan-delivery#Evidence Freshness]]
    root = find_repo_root(plan); pid = plan_id(plan)
    records = [r for r in read_jsonl(ledger_path(root, pid)) if r.get("verification_id") == vid]
    if not records: return "MISSING", None
    latest = records[-1]
    if not _freshness(plan, latest): return "STALE", latest
    if acceptance_enabled(plan):
        try:
            meta = verification_meta(plan, vid)
        except ValueError:
            return "STALE", latest
        if meta["evidence_action"] == "REUSE_EVIDENCE":
            if not latest.get("inherited"):
                return "STALE", latest
        else:
            expected_command = expected_command or expected_plan_command(plan, vid)
            if expected_command and latest.get("command") != expected_command:
                return "STALE", latest
        for cid in meta["claim_ids"]:
            if str((latest.get("claim_results") or {}).get(cid, "")).upper() != "PASS":
                return "FAILED", latest
    else:
        expected_command = expected_command or expected_plan_command(plan, vid)
        if expected_command and latest.get("command") != expected_command: return "STALE", latest
    if int(latest.get("exit_code", 1)) != 0 or latest.get("result") != "PASS": return "FAILED", latest
    return "FRESH", latest


def _acceptance_claim_results(log: Path, claim_ids: list[str]) -> tuple[bool, dict[str, str], str | None]:
    prefix = "SMC_ACCEPTANCE_RESULT "
    payloads = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(prefix):
            try:
                payloads.append(json.loads(line[len(prefix):]))
            except json.JSONDecodeError:
                return False, {}, "ACCEPTANCE_RESULT_INVALID_JSON"
    if len(payloads) != 1:
        return False, {}, "ACCEPTANCE_RESULT_MISSING_OR_DUPLICATE"
    claims = payloads[0].get("claims")
    if not isinstance(claims, dict):
        return False, {}, "ACCEPTANCE_RESULT_CLAIMS_INVALID"
    results: dict[str, str] = {}
    for cid in claim_ids:
        value = claims.get(cid)
        result = value.get("result") if isinstance(value, dict) else value
        results[cid] = str(result or "").upper()
    return all(results.get(cid) == "PASS" for cid in claim_ids), results, None


def run_cmd(plan: Path, vid: str, command: list[str]) -> int:
    root = find_repo_root(plan); pid = plan_id(plan); rows = verification_rows(plan)
    if vid not in rows:
        print(f"PLAN_VERIFICATION_UNKNOWN: {vid}", file=sys.stderr); return 2
    row = rows[vid]
    policy = strip_md(row.get("Evidence Policy", "LOCAL_TRANSIENT")).upper() or "LOCAL_TRANSIENT"
    if policy not in VALID_POLICIES:
        print(f"PLAN_EVIDENCE_POLICY_INVALID: {vid}={policy}", file=sys.stderr); return 2

    meta = None
    preflight = None
    if acceptance_enabled(plan):
        try:
            meta = verification_meta(plan, vid)
        except ValueError as exc:
            print(str(exc), file=sys.stderr); return 2
        if meta["evidence_action"] == "REUSE_EVIDENCE":
            print(f"EVIDENCE_REUSE_REQUIRES_INHERIT: {vid}", file=sys.stderr); return 2
        preflight = preflight_verification(plan, vid)
        if not preflight.get("pass"):
            print("VERIFICATION_PRECHECK_BLOCKED: " + json.dumps(preflight, ensure_ascii=False), file=sys.stderr)
            return 2

    if not command:
        print("EVIDENCE_COMMAND_MISSING", file=sys.stderr); return 2
    rendered = shlex.join(command); expected = expected_plan_command(plan, vid)
    if expected and rendered != expected:
        print(f"EVIDENCE_COMMAND_MISMATCH: {vid}: expected={expected!r} actual={rendered!r}", file=sys.stderr); return 2
    ws = workspace_inspect(plan)
    if not ws["pass"]:
        print("EVIDENCE_WORKSPACE_UNSTABLE", file=sys.stderr); return 2
    ts = utc_now(); safe_ts = ts.replace(":", "").replace("-", "")
    logs = root / ".smc" / "evidence" / pid / "logs"; logs.mkdir(parents=True, exist_ok=True)
    log = logs / f"{safe_ts}-{vid}.log"
    with log.open("w", encoding="utf-8", newline="\n") as out:
        os.chmod(log, 0o600)
        out.write(f"# command: {rendered}\n# scope_fingerprint: {ws['scope_fingerprint']}\n# ambient_fingerprint: {ws['ambient_fingerprint']}\n# timestamp: {ts}\n\n")
        proc = subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line); out.write(line)
        proc.stdout.close(); command_rc = proc.wait()

    effective_rc = command_rc
    claim_results: dict[str, str] = {}
    acceptance_error = None
    if meta:
        claim_ids = [str(x) for x in meta["claim_ids"]]
        mode = str(meta["acceptance_mode"])
        if mode in {"LIVE", "FAULT_INJECTION", "EXTERNAL"}:
            claim_pass, claim_results, acceptance_error = _acceptance_claim_results(log, claim_ids)
            if not claim_pass:
                effective_rc = 1
        else:
            claim_results = {cid: ("PASS" if command_rc == 0 else "FAIL") for cid in claim_ids}

    record = {
        "schema": "smc.evidence.v3",
        "plan_id": pid,
        "verification_id": vid,
        "command": rendered,
        "command_exit_code": command_rc,
        "exit_code": effective_rc,
        "result": "PASS" if effective_rc == 0 else "FAIL",
        "scope_fingerprint": ws["scope_fingerprint"],
        "ambient_fingerprint": ws["ambient_fingerprint"],
        "timestamp": ts,
        "log_path": repo_relative_path(log, root),
        "policy": policy,
        "claim_ids": list(meta["claim_ids"]) if meta else [],
        "claim_results": claim_results,
        "acceptance_mode": meta["acceptance_mode"] if meta else "LOCAL",
        "evidence_action": meta["evidence_action"] if meta else "NEW_EVIDENCE",
        "inherited": False,
        "candidate_id": (preflight or {}).get("candidate_id"),
        "acceptance_error": acceptance_error,
    }
    append_jsonl(ledger_path(root, pid), record)
    print(f"EVIDENCE {vid} {'PASS' if effective_rc == 0 else 'FAIL'} scope={ws['scope_fingerprint']} log={record['log_path']}")
    if acceptance_error:
        print(f"{acceptance_error}: {vid}", file=sys.stderr)
    return effective_rc


def file_sha256(path: Path | None) -> str | None:
    if path is None or not path.is_file(): return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""): h.update(chunk)
    return "sha256:" + h.hexdigest()


def payload_sha256(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def build_manifest(plan: Path, output: Path | None = None) -> tuple[Path, dict]:
    from completion_audit import check as audit_check
    from review_record import latest_status as review_status

    root = find_repo_root(plan); pid = plan_id(plan); ws = workspace_inspect(plan)
    if not ws["pass"]:
        raise ValueError("EVIDENCE_MANIFEST_WORKSPACE_UNSTABLE")
    pstatus, plan_review = review_status(plan, "plan")
    if pstatus != "FRESH_PASS": raise ValueError(f"EVIDENCE_MANIFEST_PLAN_REVIEW_{pstatus}")
    astatus, audit = audit_check(plan)
    if astatus != "FRESH_PASS": raise ValueError(f"EVIDENCE_MANIFEST_COMPLETION_AUDIT_{astatus}")
    rstatus, implementation_review = review_status(plan, "implementation")
    if rstatus != "FRESH_PASS": raise ValueError(f"EVIDENCE_MANIFEST_IMPLEMENTATION_REVIEW_{rstatus}")

    verification_records: list[dict] = []
    vids = blocking_verifications(plan)
    if not vids: raise ValueError("EVIDENCE_MANIFEST_BLOCKING_VERIFICATION_MISSING")
    for vid in vids:
        status, rec = current_status(plan, vid)
        if status != "FRESH" or rec is None: raise ValueError(f"EVIDENCE_MANIFEST_VERIFICATION_{status}: {vid}")
        log_rel = str(rec.get("log_path") or ""); log_path = root / log_rel if log_rel else None
        verification_records.append({
            "verification_id": vid, "command": rec.get("command"), "exit_code": rec.get("exit_code"),
            "result": rec.get("result"), "timestamp": rec.get("timestamp"), "policy": rec.get("policy"),
            "raw_log_ref": log_rel or None, "raw_log_sha256": file_sha256(log_path),
            "claim_ids": rec.get("claim_ids") or [], "claim_results": rec.get("claim_results") or {},
            "acceptance_mode": rec.get("acceptance_mode"), "evidence_action": rec.get("evidence_action"),
            "candidate_id": rec.get("candidate_id"), "inherited": bool(rec.get("inherited")),
            "source_manifest": rec.get("source_manifest"), "source_manifest_sha256": rec.get("source_manifest_sha256"),
            "source_verification_id": rec.get("source_verification_id"),
        })

    blocking_claim_records = []
    acceptance_contract = "smc.acceptance.v1" if acceptance_enabled(plan) else None
    if acceptance_contract:
        for cid, claim in blocking_claims(plan).items():
            claim_vids = [x.upper() for x in split_values(claim.get("Verification IDs", ""))]
            claim_ok = bool(claim_vids)
            for claim_vid in claim_vids:
                status, rec = current_status(plan, claim_vid)
                if status != "FRESH" or rec is None:
                    claim_ok = False
                    break
                if str((rec.get("claim_results") or {}).get(cid, "")).upper() != "PASS":
                    claim_ok = False
                    break
            if not claim_ok:
                raise ValueError(f"EVIDENCE_MANIFEST_BLOCKING_CLAIM_NOT_PASS: {cid}")
            blocking_claim_records.append({
                "claim_id": cid,
                "requirement": strip_md(claim.get("Requirement", "")),
                "result": "PASS",
                "verification_ids": claim_vids,
                "evidence_action": strip_md(claim.get("Evidence Action", "")).upper(),
                "prior_evidence": strip_md(claim.get("Prior Evidence", "")) or None,
            })

    candidate_state, candidate = candidate_status(plan) if acceptance_contract else ("MISSING", None)
    payload = {
        "schema": MANIFEST_SCHEMA,
        "plan_id": pid,
        "plan": repo_relative_path(plan, root),
        "scope_fingerprint": ws["scope_fingerprint"],
        "ambient_fingerprint": ws["ambient_fingerprint"],
        "workspace_base_commit": ws["base_commit"],
        "generated_at": utc_now(),
        "plan_review": {"reviewer": (plan_review or {}).get("reviewer"), "verdict": (plan_review or {}).get("verdict"), "plan_sha256": (plan_review or {}).get("plan_sha256"), "timestamp": (plan_review or {}).get("timestamp")},
        "completion_audit": {k: (audit or {}).get(k) for k in ("verdict", "total_items", "done", "changed", "deferred", "unverifiable", "scope_drift", "timestamp")},
        "implementation_review": {"reviewer": (implementation_review or {}).get("reviewer"), "verdict": (implementation_review or {}).get("verdict"), "scope_fingerprint": (implementation_review or {}).get("scope_fingerprint"), "timestamp": (implementation_review or {}).get("timestamp")},
        "blocking_verifications": verification_records,
        "acceptance_contract": acceptance_contract,
        "blocking_claims": blocking_claim_records,
        "verification_candidate": candidate if candidate_state == "FRESH" else None,
    }
    payload["payload_sha256"] = payload_sha256(payload)
    out = output.resolve() if output else default_manifest_path(root, pid)
    try: repo_relative_path(out, root)
    except ValueError as exc: raise ValueError(f"EVIDENCE_MANIFEST_OUTSIDE_REPO: {out}") from exc
    atomic_write(out, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return out, payload


def manifest_status(plan: Path, expected_fingerprint: str | None = None, require_current: bool = True) -> tuple[str, dict | None, Path]:
    root = find_repo_root(plan); pid = plan_id(plan); path = default_manifest_path(root, pid)
    if not path.is_file(): return "MISSING", None, path
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError: return "INVALID", None, path
    if data.get("schema") not in {"smc.evidence.manifest.v2", MANIFEST_SCHEMA} or data.get("plan_id") != pid: return "INVALID", data, path
    stored_digest = data.get("payload_sha256"); check_payload = dict(data); check_payload.pop("payload_sha256", None)
    if stored_digest != payload_sha256(check_payload): return "INVALID", data, path
    ws = workspace_inspect(plan)
    target = expected_fingerprint or (ws["scope_fingerprint"] if require_current else data.get("scope_fingerprint"))
    if not target or data.get("scope_fingerprint") != target: return "STALE", data, path
    if require_current:
        if data.get("scope_fingerprint") != ws["scope_fingerprint"]: return "STALE", data, path
        if data.get("ambient_fingerprint") != ws["ambient_fingerprint"]: return "STALE", data, path
        if not ws["pass"]: return "STALE", data, path
    return "FRESH", data, path


def main() -> int:
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--verification", required=True); p.add_argument("command", nargs=argparse.REMAINDER)
    p = sub.add_parser("check"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--verification"); p.add_argument("--expect-command"); p.add_argument("--all-blocking", action="store_true"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("manifest"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--output", type=Path)
    p = sub.add_parser("manifest-check"); p.add_argument("--plan", required=True, type=Path); p.add_argument("--fingerprint"); p.add_argument("--json", action="store_true")
    args = ap.parse_args(); plan = args.plan.resolve()
    if not plan.is_file(): print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr); return 2
    if args.cmd == "run":
        cmd = args.command[1:] if args.command and args.command[0] == "--" else args.command
        return run_cmd(plan, args.verification.upper(), cmd)
    if args.cmd == "manifest":
        try: path, payload = build_manifest(plan, args.output)
        except (ValueError, RuntimeError) as exc: print(str(exc), file=sys.stderr); return 1
        print(json.dumps({"status": "WRITTEN", "manifest": repo_relative_path(path, find_repo_root(plan)), "plan_id": payload["plan_id"], "scope_fingerprint": payload["scope_fingerprint"], "payload_sha256": payload["payload_sha256"]}, ensure_ascii=False, indent=2)); return 0
    if args.cmd == "manifest-check":
        status, data, path = manifest_status(plan, args.fingerprint, require_current=not bool(args.fingerprint))
        result = {"status": status, "manifest": str(path), "record": data}
        if args.json: print(json.dumps(result, ensure_ascii=False, indent=2))
        else: print(f"EVIDENCE_MANIFEST {status} path={path} scope={(data or {}).get('scope_fingerprint','-')}")
        return 0 if status == "FRESH" else 1
    rows = verification_rows(plan)
    if args.all_blocking: vids = [vid for vid, row in rows.items() if strip_md(row.get("Blocking", "")).lower() == "yes"]
    elif args.verification: vids = [args.verification.upper()]
    else: print("EVIDENCE_CHECK_TARGET_MISSING", file=sys.stderr); return 2
    result = []; rc = 0
    for vid in vids:
        expected = args.expect_command if len(vids) == 1 and args.expect_command else None
        status, rec = current_status(plan, vid, expected); result.append({"verification_id": vid, "status": status, "record": rec})
        if status != "FRESH": rc = 1
    if args.json: print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result:
            rec = item["record"] or {}; print(f"{item['verification_id']} {item['status']} exit={rec.get('exit_code','-')} scope={rec.get('scope_fingerprint','-')} log={rec.get('log_path','-')}")
    return rc


if __name__ == "__main__": raise SystemExit(main())
