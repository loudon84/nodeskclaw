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

from common import (
    append_jsonl,
    atomic_write,
    find_repo_root,
    parse_first_table,
    plan_id,
    read_jsonl,
    repo_relative_path,
    section,
    strip_md,
    utc_now,
)
from working_tree_fingerprint import fingerprint

VALID_POLICIES = {"LOCAL_TRANSIENT", "LOCAL_DURABLE", "CI_ARTIFACT", "EXTERNAL_ARTIFACT", "REPO_SUMMARY"}
MANIFEST_SCHEMA = "smc.evidence.manifest.v1"


def verification_rows(plan: Path) -> dict[str, dict[str, str]]:
    body = section(plan.read_text(encoding="utf-8"), "Verification Ledger")
    _, rows = parse_first_table(body)
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        vid = strip_md(row.get("Verification ID", "")).upper()
        if vid:
            result[vid] = row
    return result


def blocking_verifications(plan: Path) -> list[str]:
    return [
        vid
        for vid, row in verification_rows(plan).items()
        if strip_md(row.get("Blocking", "")).lower() == "yes"
    ]


def ledger_path(root: Path, pid: str) -> Path:
    return root / ".smc" / "evidence" / pid / "ledger.jsonl"


def safe_plan_id(pid: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", pid).strip("-._")
    return value or "plan"


def default_manifest_path(root: Path, pid: str) -> Path:
    return root / "docs_agent" / "evidence" / f"{safe_plan_id(pid)}-evidence.json"


def expected_plan_command(plan: Path, vid: str) -> str | None:
    row = verification_rows(plan).get(vid)
    if not row:
        return None
    raw = strip_md(row.get("Entry Point / Command", ""))
    if not raw:
        return None
    try:
        return shlex.join(shlex.split(raw))
    except ValueError:
        return raw


def current_status(plan: Path, vid: str, expected_command: str | None = None) -> tuple[str, dict | None]:
    root = find_repo_root(plan)
    pid = plan_id(plan)
    records = [r for r in read_jsonl(ledger_path(root, pid)) if r.get("verification_id") == vid]
    if not records:
        return "MISSING", None
    current = fingerprint(root)
    latest = records[-1]
    if latest.get("wtree_fingerprint") != current:
        return "STALE", latest
    expected_command = expected_command or expected_plan_command(plan, vid)
    if expected_command and latest.get("command") != expected_command:
        return "STALE", latest
    if int(latest.get("exit_code", 1)) != 0 or latest.get("result") != "PASS":
        return "FAILED", latest
    return "FRESH", latest


def run_cmd(plan: Path, vid: str, command: list[str]) -> int:
    root = find_repo_root(plan)
    pid = plan_id(plan)
    rows = verification_rows(plan)
    if vid not in rows:
        print(f"PLAN_VERIFICATION_UNKNOWN: {vid}", file=sys.stderr)
        return 2
    row = rows[vid]
    policy = strip_md(row.get("Evidence Policy", "LOCAL_TRANSIENT")).upper() or "LOCAL_TRANSIENT"
    if policy not in VALID_POLICIES:
        print(f"PLAN_EVIDENCE_POLICY_INVALID: {vid}={policy}", file=sys.stderr)
        return 2
    if not command:
        print("EVIDENCE_COMMAND_MISSING", file=sys.stderr)
        return 2
    fp = fingerprint(root)
    ts = utc_now()
    safe_ts = ts.replace(":", "").replace("-", "")
    logs = root / ".smc" / "evidence" / pid / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log = logs / f"{safe_ts}-{vid}.log"
    rendered = shlex.join(command)
    expected = expected_plan_command(plan, vid)
    if expected and rendered != expected:
        print(f"EVIDENCE_COMMAND_MISMATCH: {vid}: expected={expected!r} actual={rendered!r}", file=sys.stderr)
        return 2
    with log.open("w", encoding="utf-8", newline="\n") as out:
        os.chmod(log, 0o600)
        out.write(f"# command: {rendered}\n# fingerprint: {fp}\n# timestamp: {ts}\n\n")
        proc = subprocess.Popen(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            out.write(line)
        proc.stdout.close()
        rc = proc.wait()
    record = {
        "schema": "smc.evidence.v1",
        "plan_id": pid,
        "verification_id": vid,
        "command": rendered,
        "exit_code": rc,
        "result": "PASS" if rc == 0 else "FAIL",
        "wtree_fingerprint": fp,
        "timestamp": ts,
        "log_path": repo_relative_path(log, root),
        "policy": policy,
    }
    append_jsonl(ledger_path(root, pid), record)
    print(f"EVIDENCE {vid} {'PASS' if rc == 0 else 'FAIL'} fingerprint={fp} log={record['log_path']}")
    return rc


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def payload_sha256(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def build_manifest(plan: Path, output: Path | None = None) -> tuple[Path, dict]:
    """Write durable compact proof metadata; raw logs remain local/CI.

    The manifest directory is excluded from working-tree fingerprints so writing
    proof metadata cannot invalidate the implementation proof it summarizes.
    """
    from completion_audit import check as audit_check
    from review_record import latest_status as review_status

    root = find_repo_root(plan)
    pid = plan_id(plan)
    fp = fingerprint(root)

    pstatus, plan_review = review_status(plan, "plan")
    if pstatus != "FRESH_PASS":
        raise ValueError(f"EVIDENCE_MANIFEST_PLAN_REVIEW_{pstatus}")
    astatus, audit = audit_check(plan)
    if astatus != "FRESH_PASS":
        raise ValueError(f"EVIDENCE_MANIFEST_COMPLETION_AUDIT_{astatus}")
    rstatus, implementation_review = review_status(plan, "implementation")
    if rstatus != "FRESH_PASS":
        raise ValueError(f"EVIDENCE_MANIFEST_IMPLEMENTATION_REVIEW_{rstatus}")

    verification_records: list[dict] = []
    vids = blocking_verifications(plan)
    if not vids:
        raise ValueError("EVIDENCE_MANIFEST_BLOCKING_VERIFICATION_MISSING")
    for vid in vids:
        status, rec = current_status(plan, vid)
        if status != "FRESH" or rec is None:
            raise ValueError(f"EVIDENCE_MANIFEST_VERIFICATION_{status}: {vid}")
        log_rel = str(rec.get("log_path") or "")
        log_path = root / log_rel if log_rel else None
        verification_records.append(
            {
                "verification_id": vid,
                "command": rec.get("command"),
                "exit_code": rec.get("exit_code"),
                "result": rec.get("result"),
                "timestamp": rec.get("timestamp"),
                "policy": rec.get("policy"),
                "raw_log_ref": log_rel or None,
                "raw_log_sha256": file_sha256(log_path) if log_path else None,
            }
        )

    rel_plan = repo_relative_path(plan, root)
    payload = {
        "schema": MANIFEST_SCHEMA,
        "plan_id": pid,
        "plan": rel_plan,
        "wtree_fingerprint": fp,
        "generated_at": utc_now(),
        "plan_review": {
            "reviewer": (plan_review or {}).get("reviewer"),
            "verdict": (plan_review or {}).get("verdict"),
            "plan_sha256": (plan_review or {}).get("plan_sha256"),
            "timestamp": (plan_review or {}).get("timestamp"),
        },
        "completion_audit": {
            "verdict": (audit or {}).get("verdict"),
            "total_items": (audit or {}).get("total_items"),
            "done": (audit or {}).get("done"),
            "changed": (audit or {}).get("changed"),
            "deferred": (audit or {}).get("deferred"),
            "unverifiable": (audit or {}).get("unverifiable"),
            "scope_drift": (audit or {}).get("scope_drift"),
            "timestamp": (audit or {}).get("timestamp"),
        },
        "implementation_review": {
            "reviewer": (implementation_review or {}).get("reviewer"),
            "verdict": (implementation_review or {}).get("verdict"),
            "wtree_fingerprint": (implementation_review or {}).get("wtree_fingerprint"),
            "timestamp": (implementation_review or {}).get("timestamp"),
        },
        "blocking_verifications": verification_records,
    }
    payload["payload_sha256"] = payload_sha256(payload)
    out = (output.resolve() if output else default_manifest_path(root, pid))
    try:
        repo_relative_path(out, root)
    except ValueError as exc:
        raise ValueError(f"EVIDENCE_MANIFEST_OUTSIDE_REPO: {out}") from exc
    atomic_write(out, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return out, payload


def manifest_status(plan: Path, expected_fingerprint: str | None = None, require_current: bool = True) -> tuple[str, dict | None, Path]:
    root = find_repo_root(plan)
    pid = plan_id(plan)
    path = default_manifest_path(root, pid)
    if not path.is_file():
        return "MISSING", None, path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "INVALID", None, path
    if data.get("schema") != MANIFEST_SCHEMA or data.get("plan_id") != pid:
        return "INVALID", data, path
    stored_digest = data.get("payload_sha256")
    check_payload = dict(data)
    check_payload.pop("payload_sha256", None)
    if stored_digest != payload_sha256(check_payload):
        return "INVALID", data, path
    target = expected_fingerprint or (fingerprint(root) if require_current else data.get("wtree_fingerprint"))
    if not target or data.get("wtree_fingerprint") != target:
        return "STALE", data, path
    if require_current and data.get("wtree_fingerprint") != fingerprint(root):
        return "STALE", data, path
    return "FRESH", data, path


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--verification", required=True)
    p.add_argument("command", nargs=argparse.REMAINDER)

    p = sub.add_parser("check")
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--verification")
    p.add_argument("--expect-command")
    p.add_argument("--all-blocking", action="store_true")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("manifest")
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--output", type=Path)

    p = sub.add_parser("manifest-check")
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--fingerprint")
    p.add_argument("--json", action="store_true")

    args = ap.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file():
        print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr)
        return 2

    if args.cmd == "run":
        cmd = args.command[1:] if args.command and args.command[0] == "--" else args.command
        return run_cmd(plan, args.verification.upper(), cmd)

    if args.cmd == "manifest":
        try:
            path, payload = build_manifest(plan, args.output)
        except (ValueError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        root = find_repo_root(plan)
        print(
            json.dumps(
                {
                    "status": "WRITTEN",
                    "manifest": repo_relative_path(path, root),
                    "plan_id": payload["plan_id"],
                    "wtree_fingerprint": payload["wtree_fingerprint"],
                    "payload_sha256": payload["payload_sha256"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.cmd == "manifest-check":
        status, data, path = manifest_status(plan, args.fingerprint, require_current=not bool(args.fingerprint))
        result = {
            "status": status,
            "manifest": str(path),
            "record": data,
        }
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"EVIDENCE_MANIFEST {status} path={path} fp={(data or {}).get('wtree_fingerprint','-')}")
        return 0 if status == "FRESH" else 1

    rows = verification_rows(plan)
    vids: list[str]
    if args.all_blocking:
        vids = [vid for vid, row in rows.items() if strip_md(row.get("Blocking", "")).lower() == "yes"]
    elif args.verification:
        vids = [args.verification.upper()]
    else:
        print("EVIDENCE_CHECK_TARGET_MISSING", file=sys.stderr)
        return 2
    result = []
    rc = 0
    for vid in vids:
        expected = args.expect_command if len(vids) == 1 and args.expect_command else None
        status, rec = current_status(plan, vid, expected)
        result.append({"verification_id": vid, "status": status, "record": rec})
        if status != "FRESH":
            rc = 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result:
            rec = item["record"] or {}
            print(
                f"{item['verification_id']} {item['status']} exit={rec.get('exit_code','-')} "
                f"fp={rec.get('wtree_fingerprint','-')} log={rec.get('log_path','-')}"
            )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
