#!/usr/bin/env python3
"""Acceptance Claim Governance for governed delivery.

This module is intentionally orthogonal to smc.plan.v3.4.  A Plan opts in by
declaring:

    acceptance_contract: smc.acceptance.v1

Legacy LOCAL-only plans remain readable.  LIVE / FAULT_INJECTION / EXTERNAL
verification must use the acceptance contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from common import (
    append_jsonl,
    atomic_write,
    find_repo_root,
    parse_first_table,
    parse_top_level_frontmatter,
    plan_id,
    repo_relative_path,
    section,
    split_values,
    strip_md,
    utc_now,
)
from workspace import inspect as workspace_inspect

ACCEPTANCE_CONTRACT = "smc.acceptance.v1"
LIVE_MODES = {"LIVE", "FAULT_INJECTION", "EXTERNAL"}
ALL_MODES = {"LOCAL", *LIVE_MODES}
ACTIONS = {"NEW_EVIDENCE", "TARGETED_RERUN", "REUSE_EVIDENCE"}
CANDIDATE_MODES = {"LOCAL_WORKTREE", "ENV_TOKEN", "COMMAND", "RECEIPT"}

CLAIM_HEADERS = (
    "Claim ID",
    "Requirement",
    "Observable Fact",
    "Blocking",
    "Prior Evidence",
    "Prior Result",
    "Evidence Action",
    "Invalidation Reason",
    "Verification IDs",
)
SCENARIO_HEADERS = (
    "Scenario ID",
    "Claim IDs",
    "Verification IDs",
    "Subject / Fixture",
    "Required Capabilities",
    "Preconditions",
    "Stimulus",
    "Oracle",
    "Environment ID",
)
ENV_HEADERS = (
    "Environment ID",
    "Required Env Vars",
    "Preflight Command",
    "Fault Driver Env",
    "Candidate Mode",
    "Candidate Probe",
)
VERIFICATION_ACCEPTANCE_HEADERS = (
    "Claim IDs",
    "Acceptance Mode",
    "Evidence Action",
)

EMPTY = {"", "-", "none", "n/a", "na"}


def _empty(value: str | None) -> bool:
    return strip_md(value or "").lower() in EMPTY


def _table(plan: Path, heading: str) -> tuple[list[str], list[dict[str, str]]]:
    return parse_first_table(section(plan.read_text(encoding="utf-8"), heading))


def verification_rows(plan: Path) -> dict[str, dict[str, str]]:
    _, rows = _table(plan, "Verification Ledger")
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        vid = strip_md(row.get("Verification ID", "")).upper()
        if vid:
            out[vid] = row
    return out


def claim_rows(plan: Path) -> dict[str, dict[str, str]]:
    _, rows = _table(plan, "Acceptance Claim Ledger")
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        cid = strip_md(row.get("Claim ID", "")).upper()
        if cid:
            out[cid] = row
    return out


def scenario_rows(plan: Path) -> dict[str, dict[str, str]]:
    _, rows = _table(plan, "Live Scenario Matrix")
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        sid = strip_md(row.get("Scenario ID", "")).upper()
        if sid:
            out[sid] = row
    return out


def environment_rows(plan: Path) -> dict[str, dict[str, str]]:
    _, rows = _table(plan, "Live Environment Matrix")
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        eid = strip_md(row.get("Environment ID", "")).upper()
        if eid:
            out[eid] = row
    return out


def acceptance_enabled(plan: Path) -> bool:
    fm = parse_top_level_frontmatter(plan.read_text(encoding="utf-8"))
    return fm.get("acceptance_contract", "").strip() == ACCEPTANCE_CONTRACT


def _looks_live_without_contract(plan: Path) -> bool:
    text = plan.read_text(encoding="utf-8")
    # Compatibility guard for historical Plans that already use live-language
    # before the acceptance contract existed.
    return bool(
        re.search(
            r"\b(REAL_PROCESS|REAL_RUNTIME|FAULT_INJECTION|LIVE_SUT|LIVE_ENV|LIVE_FIXTURE)\b",
            text,
            re.I,
        )
        or re.search(r"\|\s*(LIVE|FAULT_INJECTION|EXTERNAL)\s*\|", text, re.I)
    )


def verification_meta(plan: Path, vid: str) -> dict[str, object]:
    row = verification_rows(plan).get(vid.upper())
    if row is None:
        raise ValueError(f"PLAN_VERIFICATION_UNKNOWN: {vid}")
    return {
        "verification_id": vid.upper(),
        "claim_ids": [x.upper() for x in split_values(row.get("Claim IDs", ""))],
        "acceptance_mode": strip_md(row.get("Acceptance Mode", "LOCAL")).upper() or "LOCAL",
        "evidence_action": strip_md(row.get("Evidence Action", "NEW_EVIDENCE")).upper() or "NEW_EVIDENCE",
        "blocking": strip_md(row.get("Blocking", "")).lower() == "yes",
        "policy": strip_md(row.get("Evidence Policy", "LOCAL_TRANSIENT")).upper() or "LOCAL_TRANSIENT",
        "row": row,
    }


def _header_errors(header: list[str], expected: tuple[str, ...], section_name: str) -> list[str]:
    return [
        f"PLAN_ACCEPTANCE_TABLE_MISSING_COLUMN: {section_name}: {column}"
        for column in expected
        if column not in header
    ]


def validate_contract(plan: Path) -> list[dict[str, str]]:
    # @lat: [[acceptance#Five Gates]]
    """Deterministic acceptance-structure validation.

    Semantic suitability (e.g. whether a fixture truly invokes a tool) stays
    with smc-plan-review.  This function guarantees that the semantic reviewer
    receives an explicit binding instead of an unstructured mega-runner.
    """
    errors: list[dict[str, str]] = []

    def add(code: str, detail: str) -> None:
        errors.append({"code": code, "detail": detail})

    enabled = acceptance_enabled(plan)
    if not enabled:
        if _looks_live_without_contract(plan):
            add(
                "PLAN_ACCEPTANCE_CONTRACT_REQUIRED",
                "live/fault/external verification requires acceptance_contract: smc.acceptance.v1",
            )
        return errors

    claim_header, claim_list = _table(plan, "Acceptance Claim Ledger")
    scenario_header, scenario_list = _table(plan, "Live Scenario Matrix")
    env_header, env_list = _table(plan, "Live Environment Matrix")
    ver_header, ver_list = _table(plan, "Verification Ledger")

    for code in _header_errors(claim_header, CLAIM_HEADERS, "Acceptance Claim Ledger"):
        add(*code.split(": ", 1))
    for code in _header_errors(scenario_header, SCENARIO_HEADERS, "Live Scenario Matrix"):
        add(*code.split(": ", 1))
    for code in _header_errors(env_header, ENV_HEADERS, "Live Environment Matrix"):
        add(*code.split(": ", 1))
    for code in _header_errors(ver_header, VERIFICATION_ACCEPTANCE_HEADERS, "Verification Ledger"):
        add(*code.split(": ", 1))
    if errors:
        return errors

    claims: dict[str, dict[str, str]] = {}
    for row in claim_list:
        cid = strip_md(row.get("Claim ID", "")).upper()
        if not re.fullmatch(r"CLM-\d{2,}", cid):
            add("PLAN_ACCEPTANCE_CLAIM_ID_INVALID", cid or "<empty>")
            continue
        if cid in claims:
            add("PLAN_ACCEPTANCE_CLAIM_DUPLICATE", cid)
            continue
        claims[cid] = row
        requirement = strip_md(row.get("Requirement", ""))
        if not requirement:
            add("PLAN_ACCEPTANCE_CLAIM_REQUIREMENT_MISSING", cid)
        if _empty(row.get("Observable Fact")):
            add("PLAN_ACCEPTANCE_CLAIM_OBSERVABLE_MISSING", cid)
        blocking = strip_md(row.get("Blocking", "")).lower()
        if blocking not in {"yes", "no"}:
            add("PLAN_ACCEPTANCE_CLAIM_BLOCKING_INVALID", f"{cid}: {blocking}")
        action = strip_md(row.get("Evidence Action", "")).upper()
        prior = strip_md(row.get("Prior Result", "")).upper() or "UNKNOWN"
        prior_evidence = strip_md(row.get("Prior Evidence", ""))
        reason = strip_md(row.get("Invalidation Reason", ""))
        if action not in ACTIONS:
            add("PLAN_ACCEPTANCE_EVIDENCE_ACTION_INVALID", f"{cid}: {action}")
        if blocking == "yes" and prior == "FAIL" and action == "REUSE_EVIDENCE":
            add("PLAN_BLOCKING_FAILURE_REUSE_FORBIDDEN", cid)
        if action == "REUSE_EVIDENCE":
            if prior != "PASS":
                add("PLAN_EVIDENCE_REUSE_PRIOR_PASS_REQUIRED", f"{cid}: prior={prior}")
            if _empty(prior_evidence):
                add("PLAN_EVIDENCE_REUSE_SOURCE_REQUIRED", cid)
            if not _empty(reason):
                add("PLAN_EVIDENCE_REUSE_WITH_INVALIDATION_FORBIDDEN", cid)
        if action == "TARGETED_RERUN" and _empty(reason):
            add("PLAN_EVIDENCE_RERUN_REASON_REQUIRED", cid)
        vids = [x.upper() for x in split_values(row.get("Verification IDs", ""))]
        if not vids:
            add("PLAN_ACCEPTANCE_CLAIM_VERIFICATION_MISSING", cid)

    verifications: dict[str, dict[str, str]] = {}
    for row in ver_list:
        vid = strip_md(row.get("Verification ID", "")).upper()
        if not vid:
            continue
        verifications[vid] = row
        mode = strip_md(row.get("Acceptance Mode", "")).upper()
        action = strip_md(row.get("Evidence Action", "")).upper()
        claim_ids = [x.upper() for x in split_values(row.get("Claim IDs", ""))]
        if mode not in ALL_MODES:
            add("PLAN_ACCEPTANCE_MODE_INVALID", f"{vid}: {mode}")
        if action not in ACTIONS:
            add("PLAN_ACCEPTANCE_EVIDENCE_ACTION_INVALID", f"{vid}: {action}")
        if not claim_ids:
            add("PLAN_ACCEPTANCE_VERIFICATION_CLAIMS_MISSING", vid)
        for cid in claim_ids:
            if cid not in claims:
                add("PLAN_ACCEPTANCE_VERIFICATION_CLAIM_UNKNOWN", f"{vid}: {cid}")
        claim_actions = {
            strip_md(claims[cid].get("Evidence Action", "")).upper()
            for cid in claim_ids
            if cid in claims
        }
        if len(claim_actions) > 1:
            add("PLAN_ACCEPTANCE_MIXED_EVIDENCE_ACTIONS", f"{vid}: {sorted(claim_actions)}")
        elif claim_actions and action not in claim_actions:
            add(
                "PLAN_ACCEPTANCE_EVIDENCE_ACTION_MISMATCH",
                f"{vid}: verification={action} claim={next(iter(claim_actions))}",
            )

    for cid, row in claims.items():
        for vid in [x.upper() for x in split_values(row.get("Verification IDs", ""))]:
            if vid not in verifications:
                add("PLAN_ACCEPTANCE_CLAIM_VERIFICATION_UNKNOWN", f"{cid}: {vid}")
            else:
                if cid not in [x.upper() for x in split_values(verifications[vid].get("Claim IDs", ""))]:
                    add("PLAN_ACCEPTANCE_CLAIM_BACKREF_MISSING", f"{cid}: {vid}")
                if (
                    strip_md(row.get("Blocking", "")).lower() == "yes"
                    and strip_md(verifications[vid].get("Blocking", "")).lower() != "yes"
                ):
                    add("PLAN_BLOCKING_CLAIM_VERIFICATION_NOT_BLOCKING", f"{cid}: {vid}")

    # Every blocking PRD requirement must have an explicit blocking claim.
    _, coverage = _table(plan, "Requirement Coverage Ledger")
    blocking_requirements = {
        strip_md(row.get("Requirement", "")).upper()
        for row in coverage
        if strip_md(row.get("Blocking", "")).lower() == "yes"
    }
    covered_requirements = {
        strip_md(row.get("Requirement", "")).upper()
        for row in claims.values()
        if strip_md(row.get("Blocking", "")).lower() == "yes"
    }
    for requirement in sorted(x for x in blocking_requirements if x):
        if requirement not in covered_requirements:
            add("PLAN_BLOCKING_REQUIREMENT_CLAIM_MISSING", requirement)

    scenarios: dict[str, dict[str, str]] = {}
    scenario_for_vid: dict[str, list[str]] = {}
    for row in scenario_list:
        sid = strip_md(row.get("Scenario ID", "")).upper()
        if not re.fullmatch(r"SCN-\d{2,}", sid):
            add("PLAN_ACCEPTANCE_SCENARIO_ID_INVALID", sid or "<empty>")
            continue
        if sid in scenarios:
            add("PLAN_ACCEPTANCE_SCENARIO_DUPLICATE", sid)
            continue
        scenarios[sid] = row
        claim_ids = [x.upper() for x in split_values(row.get("Claim IDs", ""))]
        vids = [x.upper() for x in split_values(row.get("Verification IDs", ""))]
        if not claim_ids:
            add("PLAN_ACCEPTANCE_SCENARIO_CLAIMS_MISSING", sid)
        if not vids:
            add("PLAN_ACCEPTANCE_SCENARIO_VERIFICATION_MISSING", sid)
        if _empty(row.get("Required Capabilities")):
            add("PLAN_ACCEPTANCE_SCENARIO_CAPABILITIES_MISSING", sid)
        if _empty(row.get("Oracle")):
            add("PLAN_ACCEPTANCE_SCENARIO_ORACLE_MISSING", sid)
        if _empty(row.get("Environment ID")):
            add("PLAN_ACCEPTANCE_SCENARIO_ENVIRONMENT_MISSING", sid)
        for cid in claim_ids:
            if cid not in claims:
                add("PLAN_ACCEPTANCE_SCENARIO_CLAIM_UNKNOWN", f"{sid}: {cid}")
        for vid in vids:
            if vid not in verifications:
                add("PLAN_ACCEPTANCE_SCENARIO_VERIFICATION_UNKNOWN", f"{sid}: {vid}")
            scenario_for_vid.setdefault(vid, []).append(sid)

    environments: dict[str, dict[str, str]] = {}
    for row in env_list:
        eid = strip_md(row.get("Environment ID", "")).upper()
        if not re.fullmatch(r"ENV-\d{2,}", eid):
            add("PLAN_ACCEPTANCE_ENVIRONMENT_ID_INVALID", eid or "<empty>")
            continue
        if eid in environments:
            add("PLAN_ACCEPTANCE_ENVIRONMENT_DUPLICATE", eid)
            continue
        environments[eid] = row

    for sid, row in scenarios.items():
        eid = strip_md(row.get("Environment ID", "")).upper()
        if eid not in environments:
            add("PLAN_ACCEPTANCE_SCENARIO_ENVIRONMENT_UNKNOWN", f"{sid}: {eid}")

    for vid, row in verifications.items():
        mode = strip_md(row.get("Acceptance Mode", "")).upper()
        action = strip_md(row.get("Evidence Action", "")).upper()
        if mode in LIVE_MODES and action != "REUSE_EVIDENCE":
            bound = scenario_for_vid.get(vid, [])
            if len(bound) != 1:
                add(
                    "PLAN_LIVE_SCENARIO_BINDING_INVALID",
                    f"{vid}: expected exactly one scenario, got {bound or 'none'}",
                )
                continue
            scenario = scenarios.get(bound[0], {})
            eid = strip_md(scenario.get("Environment ID", "")).upper()
            env = environments.get(eid)
            if env is None:
                continue
            candidate_mode = strip_md(env.get("Candidate Mode", "")).upper()
            if candidate_mode not in CANDIDATE_MODES:
                add("PLAN_LIVE_CANDIDATE_MODE_INVALID", f"{vid}: {candidate_mode or '<empty>'}")
            if candidate_mode != "LOCAL_WORKTREE" and _empty(env.get("Candidate Probe")):
                add("PLAN_LIVE_CANDIDATE_PROBE_MISSING", f"{vid}: {eid}")
            subject = strip_md(scenario.get("Subject / Fixture", ""))
            if subject.lower() not in EMPTY and subject.lower() != "none" and _empty(env.get("Preflight Command")):
                add("PLAN_LIVE_FIXTURE_PREFLIGHT_MISSING", f"{vid}: {sid}/{eid}")
            if mode == "FAULT_INJECTION" and _empty(env.get("Fault Driver Env")):
                add("PLAN_LIVE_FAULT_DRIVER_MISSING", f"{vid}: {eid}")

    return errors


def _candidate_path(plan: Path) -> Path:
    root = find_repo_root(plan)
    return root / ".smc" / "runs" / plan_id(plan) / "verification-candidate.json"


def _candidate_id(pid: str, scope_fingerprint: str) -> str:
    raw = f"{pid}\n{scope_fingerprint}\n".encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def capture_candidate(plan: Path) -> dict:
    ws = workspace_inspect(plan)
    if not ws["pass"]:
        raise ValueError("VERIFICATION_CANDIDATE_WORKSPACE_UNSTABLE")
    payload = {
        "schema": "smc.verification.candidate.v1",
        "plan_id": plan_id(plan),
        "scope_fingerprint": ws["scope_fingerprint"],
        "candidate_id": _candidate_id(plan_id(plan), ws["scope_fingerprint"]),
        "captured_at": utc_now(),
    }
    atomic_write(_candidate_path(plan), json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return payload


def candidate_status(plan: Path) -> tuple[str, dict | None]:
    path = _candidate_path(plan)
    if not path.is_file():
        return "MISSING", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "INVALID", None
    ws = workspace_inspect(plan)
    if (
        data.get("schema") != "smc.verification.candidate.v1"
        or data.get("plan_id") != plan_id(plan)
        or data.get("scope_fingerprint") != ws["scope_fingerprint"]
        or data.get("candidate_id") != _candidate_id(plan_id(plan), ws["scope_fingerprint"])
    ):
        return "STALE", data
    return "FRESH", data


def _run_shell(command: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=root,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _scenario_for_verification(plan: Path, vid: str) -> tuple[str, dict[str, str]] | None:
    matches: list[tuple[str, dict[str, str]]] = []
    for sid, row in scenario_rows(plan).items():
        if vid.upper() in [x.upper() for x in split_values(row.get("Verification IDs", ""))]:
            matches.append((sid, row))
    if len(matches) != 1:
        return None
    return matches[0]


def preflight_verification(plan: Path, vid: str, execute_commands: bool = True) -> dict:
    errors = validate_contract(plan)
    if errors:
        return {"pass": False, "code": "PLAN_ACCEPTANCE_INVALID", "errors": errors}

    meta = verification_meta(plan, vid)
    action = str(meta["evidence_action"])
    mode = str(meta["acceptance_mode"])
    if action == "REUSE_EVIDENCE":
        return {"pass": True, "verification_id": vid.upper(), "mode": mode, "action": action, "reuse": True}
    if mode == "LOCAL":
        return {"pass": True, "verification_id": vid.upper(), "mode": mode, "action": action}

    bound = _scenario_for_verification(plan, vid)
    if bound is None:
        return {"pass": False, "code": "LIVE_SCENARIO_BINDING_INVALID", "verification_id": vid.upper()}
    sid, scenario = bound
    eid = strip_md(scenario.get("Environment ID", "")).upper()
    env = environment_rows(plan).get(eid)
    if env is None:
        return {"pass": False, "code": "LIVE_ENVIRONMENT_UNKNOWN", "environment_id": eid}

    missing_env = [name for name in split_values(env.get("Required Env Vars", "")) if not os.environ.get(name)]
    if mode == "FAULT_INJECTION":
        missing_env.extend(
            name for name in split_values(env.get("Fault Driver Env", "")) if not os.environ.get(name)
        )
    missing_env = sorted(set(missing_env))
    if missing_env:
        return {
            "pass": False,
            "code": "LIVE_ENV_NOT_READY",
            "verification_id": vid.upper(),
            "environment_id": eid,
            "missing_env": missing_env,
        }

    root = find_repo_root(plan)
    preflight_command = strip_md(env.get("Preflight Command", ""))
    if execute_commands and not _empty(preflight_command):
        result = _run_shell(preflight_command, root)
        if result.returncode != 0:
            return {
                "pass": False,
                "code": "LIVE_ENV_PREFLIGHT_FAILED",
                "verification_id": vid.upper(),
                "environment_id": eid,
                "exit_code": result.returncode,
                "stdout": result.stdout[-2000:],
                "stderr": result.stderr[-2000:],
            }

    candidate_state, candidate = candidate_status(plan)
    if candidate_state != "FRESH" or candidate is None:
        return {
            "pass": False,
            "code": "VERIFICATION_CANDIDATE_" + candidate_state,
            "verification_id": vid.upper(),
        }
    expected = str(candidate["candidate_id"])
    candidate_mode = strip_md(env.get("Candidate Mode", "")).upper()
    probe = strip_md(env.get("Candidate Probe", ""))

    actual: str | None = None
    if candidate_mode == "LOCAL_WORKTREE":
        actual = expected
    elif candidate_mode == "ENV_TOKEN":
        actual = os.environ.get(probe)
    elif candidate_mode == "COMMAND":
        if not execute_commands:
            actual = expected
        else:
            result = _run_shell(probe, root)
            if result.returncode == 0:
                actual = result.stdout.strip()
    elif candidate_mode == "RECEIPT":
        receipt = Path(probe)
        if not receipt.is_absolute():
            receipt = root / receipt
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
            actual = str(data.get("candidate_id") or "")
        except (OSError, json.JSONDecodeError):
            actual = None

    if actual != expected:
        return {
            "pass": False,
            "code": "LIVE_SUT_MISMATCH",
            "verification_id": vid.upper(),
            "environment_id": eid,
            "candidate_mode": candidate_mode,
            "expected_candidate_id": expected,
            "actual_candidate_id": actual,
        }

    return {
        "pass": True,
        "verification_id": vid.upper(),
        "mode": mode,
        "action": action,
        "scenario_id": sid,
        "environment_id": eid,
        "candidate_id": expected,
    }


def _manifest_digest(path: Path) -> tuple[dict, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    stored = data.get("payload_sha256")
    check = dict(data)
    check.pop("payload_sha256", None)
    raw = json.dumps(check, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if stored and stored != digest:
        raise ValueError("EVIDENCE_INHERIT_SOURCE_MANIFEST_DIGEST_INVALID")
    file_digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return data, file_digest


def inherit_evidence(plan: Path, vid: str, source_manifest: Path, source_verification: str) -> dict:
    """Materialize an approved prior proof as current-scope evidence.

    The semantic decision to reuse belongs to PRD Grounding + Plan Review.
    This function only enforces that the current Plan declares REUSE_EVIDENCE
    and that the referenced source verification was a successful durable proof.
    """
    meta = verification_meta(plan, vid)
    if meta["evidence_action"] != "REUSE_EVIDENCE":
        raise ValueError(f"EVIDENCE_REUSE_NOT_DECLARED: {vid}")
    claims = claim_rows(plan)
    claim_ids = [str(x) for x in meta["claim_ids"]]
    for cid in claim_ids:
        row = claims.get(cid)
        if row is None:
            raise ValueError(f"EVIDENCE_REUSE_CLAIM_UNKNOWN: {cid}")
        if strip_md(row.get("Evidence Action", "")).upper() != "REUSE_EVIDENCE":
            raise ValueError(f"EVIDENCE_REUSE_CLAIM_ACTION_MISMATCH: {cid}")
        if strip_md(row.get("Prior Result", "")).upper() != "PASS":
            raise ValueError(f"EVIDENCE_REUSE_PRIOR_PASS_REQUIRED: {cid}")

    source_manifest = source_manifest.resolve()
    if not source_manifest.is_file():
        raise ValueError(f"EVIDENCE_REUSE_SOURCE_MANIFEST_MISSING: {source_manifest}")
    source, source_sha = _manifest_digest(source_manifest)
    rows = source.get("blocking_verifications") or []
    match = next(
        (
            row
            for row in rows
            if isinstance(row, dict)
            and str(row.get("verification_id", "")).upper() == source_verification.upper()
        ),
        None,
    )
    if not match or match.get("result") != "PASS" or int(match.get("exit_code", 1)) != 0:
        raise ValueError(
            f"EVIDENCE_REUSE_SOURCE_VERIFICATION_NOT_PASS: {source_verification}"
        )

    ws = workspace_inspect(plan)
    if not ws["pass"]:
        raise ValueError("EVIDENCE_REUSE_WORKSPACE_UNSTABLE")
    root = find_repo_root(plan)
    policy = str(meta["policy"])
    record = {
        "schema": "smc.evidence.v3",
        "plan_id": plan_id(plan),
        "verification_id": vid.upper(),
        "command": f"INHERIT:{repo_relative_path(source_manifest, root)}#{source_verification.upper()}",
        "exit_code": 0,
        "command_exit_code": 0,
        "result": "PASS",
        "scope_fingerprint": ws["scope_fingerprint"],
        "ambient_fingerprint": ws["ambient_fingerprint"],
        "timestamp": utc_now(),
        "log_path": None,
        "policy": policy,
        "claim_ids": claim_ids,
        "claim_results": {cid: "PASS" for cid in claim_ids},
        "acceptance_mode": str(meta["acceptance_mode"]),
        "evidence_action": "REUSE_EVIDENCE",
        "inherited": True,
        "source_manifest": repo_relative_path(source_manifest, root),
        "source_manifest_sha256": source_sha,
        "source_verification_id": source_verification.upper(),
        "candidate_id": None,
    }
    ledger = root / ".smc" / "evidence" / plan_id(plan) / "ledger.jsonl"
    append_jsonl(ledger, record)
    return record


def blocking_claims(plan: Path) -> dict[str, dict[str, str]]:
    return {
        cid: row
        for cid, row in claim_rows(plan).items()
        if strip_md(row.get("Blocking", "")).lower() == "yes"
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("validate")
    p.add_argument("--plan", required=True, type=Path)

    p = sub.add_parser("capture")
    p.add_argument("--plan", required=True, type=Path)

    p = sub.add_parser("status")
    p.add_argument("--plan", required=True, type=Path)

    p = sub.add_parser("preflight")
    p.add_argument("--plan", required=True, type=Path)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--verification")
    group.add_argument("--all-blocking", action="store_true")
    p.add_argument("--no-exec", action="store_true")

    p = sub.add_parser("inherit")
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--verification", required=True)
    p.add_argument("--from-manifest", required=True, type=Path)
    p.add_argument("--from-verification", required=True)

    args = ap.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file():
        print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr)
        return 2

    if args.cmd == "validate":
        errors = validate_contract(plan)
        payload = {"valid": not errors, "errors": errors}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1 if errors else 0

    if args.cmd == "capture":
        try:
            payload = capture_candidate(plan)
        except (ValueError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "status":
        state, payload = candidate_status(plan)
        print(json.dumps({"status": state, "candidate": payload}, ensure_ascii=False, indent=2))
        return 0 if state == "FRESH" else 1

    if args.cmd == "inherit":
        try:
            payload = inherit_evidence(
                plan,
                args.verification.upper(),
                args.from_manifest,
                args.from_verification.upper(),
            )
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    rows = verification_rows(plan)
    if args.all_blocking:
        vids = [
            vid
            for vid, row in rows.items()
            if strip_md(row.get("Blocking", "")).lower() == "yes"
        ]
    else:
        vids = [args.verification.upper()]
    results = [
        preflight_verification(plan, vid, execute_commands=not args.no_exec)
        for vid in vids
    ]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(x.get("pass") for x in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
