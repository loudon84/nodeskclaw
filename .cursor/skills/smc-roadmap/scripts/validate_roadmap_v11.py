#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

STATUSES = {"BACKLOG", "READY", "IN_PRD", "PLANNED", "IMPLEMENTING", "REVIEW", "BLOCKED", "DONE", "SUPERSEDED"}
ROADMAP_STATUSES = {"ACTIVE", "SUPERSEDED"}
COLS = ("Item ID", "Outcome", "Depends On", "Status", "Exit Criteria", "PRD", "Plan", "Implementation Commit", "Verification Evidence")
ID = re.compile(r"^RM-\d{2,}$")
SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")
SMC_EVIDENCE = re.compile(r"^smc-evidence:([^@]+)@(sha256:[0-9a-fA-F]{64})$")
EMPTY = {"", "-", "none", "n/a", "na"}
FM_FIELDS = ("roadmap_id", "version", "status", "architecture_decision", "source_revision", "updated_at")


def frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i, x in enumerate(lines[1:], 1) if x.strip() == "---")
    except StopIteration:
        return {}
    out: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line and (not line or not line[0].isspace()):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"\'')
    return out


def iso(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def section(text: str, name: str) -> str | None:
    m = re.search(rf"^##\s+{re.escape(name)}\s*$\n?(.*?)(?=^##\s+|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def cells(line: str) -> list[str]:
    return [x.strip() for x in line.strip().strip("|").split("|")]


def table(body: str | None) -> tuple[list[str], list[dict[str, str]]]:
    if not body:
        return [], []
    lines = [x.strip() for x in body.splitlines() if x.strip().startswith("|")]
    for i in range(len(lines) - 1):
        header = cells(lines[i])
        sep = cells(lines[i + 1])
        if len(header) == len(sep) and all(re.fullmatch(r":?-{3,}:?", x.replace(" ", "")) for x in sep):
            rows = []
            for raw in lines[i + 2 :]:
                vals = cells(raw)
                if len(vals) != len(header):
                    break
                rows.append(dict(zip(header, vals)))
            return header, rows
    return [], []


def empty(value: str) -> bool:
    return value.strip().strip("`").lower() in EMPTY


def split(value: str) -> list[str]:
    if empty(value):
        return []
    return [
        x.strip().strip("`")
        for x in re.split(r"<br\s*/?>|[,;\n]+", value, flags=re.I)
        if x.strip() and not empty(x)
    ]


def cycle(deps: dict[str, set[str]]) -> list[str] | None:
    state = {k: 0 for k in deps}
    stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        state[node] = 1
        stack.append(node)
        for dep in deps.get(node, set()):
            if dep not in state:
                continue
            if state[dep] == 0:
                result = dfs(dep)
                if result:
                    return result
            elif state[dep] == 1:
                return stack[stack.index(dep) :] + [dep]
        stack.pop()
        state[node] = 2
        return None

    for node in deps:
        if state[node] == 0:
            result = dfs(node)
            if result:
                return result
    return None


def git_root(path: Path) -> Path | None:
    start = path.resolve().parent
    try:
        out = subprocess.check_output(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return Path(out)
    except Exception:
        return None


def commit_exists(root: Path | None, sha: str) -> bool:
    if root is None:
        return False
    return subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"{sha}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def resolve_repo_path(roadmap: Path, raw: str, root: Path | None) -> Path | None:
    value = raw.strip().strip("`")
    if not value:
        return None
    candidate = Path(value)
    options = [candidate] if candidate.is_absolute() else [roadmap.parent / candidate]
    if root and not candidate.is_absolute():
        options.append(root / candidate)
    for option in options:
        try:
            resolved = option.resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    return None


def architecture_is_approved(path: Path) -> bool:
    fm = frontmatter(path.read_text(encoding="utf-8"))
    return fm.get("status") == "APPROVED" and fm.get("review_verdict") == "PASS" and bool(fm.get("approved_at"))


def repo_rel(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def safe_plan_id(pid: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", pid).strip("-._")
    return value or "plan"


def git_show_bytes(root: Path, commit: str, rel: str) -> bytes | None:
    result = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{rel}"], capture_output=True)
    return result.stdout if result.returncode == 0 else None


def payload_sha256(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def validate_manifest_bytes(data: bytes, pid: str, expected_fp: str, expected_plan: str) -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(data.decode("utf-8"))
    except Exception as exc:
        return [f"ROADMAP_EVIDENCE_MANIFEST_INVALID_JSON: {exc}"]
    if manifest.get("schema") != "smc.evidence.manifest.v1":
        errors.append("ROADMAP_EVIDENCE_MANIFEST_SCHEMA_INVALID")
    if manifest.get("plan_id") != pid:
        errors.append(f"ROADMAP_EVIDENCE_MANIFEST_PLAN_ID_MISMATCH: expected={pid} actual={manifest.get('plan_id')}")
    if manifest.get("wtree_fingerprint") != expected_fp:
        errors.append("ROADMAP_EVIDENCE_MANIFEST_FINGERPRINT_MISMATCH")
    if str(manifest.get("plan", "")).replace("\\", "/") != expected_plan:
        errors.append(f"ROADMAP_EVIDENCE_MANIFEST_PLAN_PATH_MISMATCH: expected={expected_plan} actual={manifest.get('plan')}")
    stored = manifest.get("payload_sha256")
    check = dict(manifest)
    check.pop("payload_sha256", None)
    if stored != payload_sha256(check):
        errors.append("ROADMAP_EVIDENCE_MANIFEST_DIGEST_INVALID")
    impl = manifest.get("implementation_review") or {}
    if impl.get("verdict") != "PASS" or impl.get("wtree_fingerprint") != expected_fp:
        errors.append("ROADMAP_EVIDENCE_MANIFEST_IMPLEMENTATION_REVIEW_INVALID")
    audit = manifest.get("completion_audit") or {}
    if audit.get("verdict") != "PASS":
        errors.append("ROADMAP_EVIDENCE_MANIFEST_COMPLETION_AUDIT_INVALID")
    for key in ("deferred", "unverifiable", "scope_drift"):
        try:
            if int(audit.get(key, 0)) != 0:
                errors.append(f"ROADMAP_EVIDENCE_MANIFEST_COMPLETION_AUDIT_{key.upper()}")
        except Exception:
            errors.append(f"ROADMAP_EVIDENCE_MANIFEST_COMPLETION_AUDIT_{key.upper()}_INVALID")
    try:
        if int(audit.get("done", -1)) != int(audit.get("total_items", -2)):
            errors.append("ROADMAP_EVIDENCE_MANIFEST_COMPLETION_AUDIT_INCOMPLETE")
    except Exception:
        errors.append("ROADMAP_EVIDENCE_MANIFEST_COMPLETION_AUDIT_COUNTS_INVALID")
    verifications = manifest.get("blocking_verifications")
    if not isinstance(verifications, list) or not verifications:
        errors.append("ROADMAP_EVIDENCE_MANIFEST_BLOCKING_VERIFICATION_MISSING")
    else:
        for row in verifications:
            if not isinstance(row, dict) or row.get("result") != "PASS" or int(row.get("exit_code", 1)) != 0:
                errors.append("ROADMAP_EVIDENCE_MANIFEST_BLOCKING_VERIFICATION_FAILED")
                break
    return errors


def validate_evidence_ref(roadmap: Path, row: dict[str, str], root: Path | None, require_scheme: bool) -> list[str]:
    errors: list[str] = []
    iid = row["Item ID"].strip()
    raw = row["Verification Evidence"].strip().strip("`")
    match = SMC_EVIDENCE.fullmatch(raw)
    if match:
        if root is None:
            return [f"ROADMAP_EVIDENCE_REPO_ROOT_MISSING: {iid}"]
        pid, expected_fp = match.group(1), match.group(2)
        plan = resolve_repo_path(roadmap, row["Plan"], root)
        if plan is None:
            return [f"ROADMAP_EVIDENCE_PLAN_UNRESOLVED: {iid}: {row['Plan']}"]
        plan_fm = frontmatter(plan.read_text(encoding="utf-8"))
        actual_pid = plan_fm.get("plan_id", "").strip()
        if actual_pid != pid:
            errors.append(f"ROADMAP_EVIDENCE_PLAN_ID_MISMATCH: {iid}: ref={pid} plan={actual_pid}")
        manifest_rel = f"docs_agent/evidence/{safe_plan_id(pid)}-evidence.json"
        commit = row["Implementation Commit"].strip().strip("`")
        data = git_show_bytes(root, commit, manifest_rel)
        if data is None:
            errors.append(f"ROADMAP_EVIDENCE_MANIFEST_NOT_IN_IMPLEMENTATION_COMMIT: {iid}: {manifest_rel}@{commit}")
            return errors
        errors.extend(f"{iid}: {e}" for e in validate_manifest_bytes(data, pid, expected_fp, repo_rel(root, plan)))
        return errors
    if raw.startswith("ci-artifact:"):
        if not raw[len("ci-artifact:") :].strip():
            errors.append(f"ROADMAP_EVIDENCE_REF_INVALID: {iid}: {raw}")
        return errors
    if raw.startswith("external-artifact:"):
        if not raw[len("external-artifact:") :].strip():
            errors.append(f"ROADMAP_EVIDENCE_REF_INVALID: {iid}: {raw}")
        return errors
    if require_scheme:
        errors.append(f"ROADMAP_EVIDENCE_REF_SCHEME_REQUIRED: {iid}: {raw}")
    return errors


def validate(path: Path, check_git: bool = True, check_architecture: bool = True) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    fm = frontmatter(text)
    if not fm:
        errors.append("ROADMAP_FRONTMATTER_MISSING")
    else:
        for field in FM_FIELDS:
            if not fm.get(field):
                errors.append(f"ROADMAP_FRONTMATTER_FIELD_REQUIRED: {field}")
        if fm.get("status") and fm["status"].upper() not in ROADMAP_STATUSES:
            errors.append(f"ROADMAP_STATE_INVALID: {fm['status']}")
        if fm.get("updated_at") and not iso(fm["updated_at"]):
            errors.append("ROADMAP_UPDATED_AT_INVALID")
        if check_architecture and fm.get("architecture_decision"):
            root = git_root(path)
            arch = resolve_repo_path(path, fm["architecture_decision"], root)
            if arch is None:
                errors.append(f"ROADMAP_ARCHITECTURE_UNRESOLVED: {fm['architecture_decision']}")
            elif not architecture_is_approved(arch):
                errors.append(f"ROADMAP_ARCHITECTURE_NOT_APPROVED: {arch}")

    body = section(text, "Roadmap Items")
    header, rows = table(body)
    if not header:
        return errors + ["ROADMAP_TABLE_MISSING"]
    for column in COLS:
        if column not in header:
            errors.append(f"ROADMAP_COLUMN_MISSING: {column}")
    if any(column not in header for column in COLS):
        return errors

    seen: set[str] = set()
    statuses: dict[str, str] = {}
    deps: dict[str, set[str]] = {}
    prd_owner: dict[str, str] = {}
    plan_owner: dict[str, str] = {}
    root = git_root(path) if check_git else None
    version = fm.get("version", "1.0.0")
    require_evidence_scheme = version.startswith("1.1") or version.startswith("2.")

    for index, row in enumerate(rows, 1):
        iid = row["Item ID"].strip()
        status = row["Status"].strip().upper()
        row_deps = set(split(row["Depends On"]))
        if not ID.fullmatch(iid):
            errors.append(f"ROADMAP_ITEM_ID_INVALID: row {index}: {iid}")
        if iid in seen:
            errors.append(f"ROADMAP_ITEM_DUPLICATE: {iid}")
        seen.add(iid)
        statuses[iid] = status
        deps[iid] = row_deps
        if status not in STATUSES:
            errors.append(f"ROADMAP_STATUS_INVALID: {iid}: {status}")
        if empty(row["Outcome"]):
            errors.append(f"ROADMAP_OUTCOME_EMPTY: {iid}")
        if empty(row["Exit Criteria"]):
            errors.append(f"ROADMAP_EXIT_CRITERIA_EMPTY: {iid}")

        prd = row["PRD"].strip().strip("`")
        plan = row["Plan"].strip().strip("`")
        if not empty(prd):
            previous = prd_owner.setdefault(prd, iid)
            if previous != iid:
                errors.append(f"ROADMAP_STAGE_PRD_REUSED: {prd}: {previous},{iid}")
        if not empty(plan):
            previous = plan_owner.setdefault(plan, iid)
            if previous != iid:
                errors.append(f"ROADMAP_PLAN_REUSED: {plan}: {previous},{iid}")

        if status in {"IN_PRD", "PLANNED", "IMPLEMENTING", "REVIEW", "DONE"} and empty(row["PRD"]):
            errors.append(f"ROADMAP_PRD_REQUIRED: {iid}")
        if status in {"PLANNED", "IMPLEMENTING", "REVIEW", "DONE"} and empty(row["Plan"]):
            errors.append(f"ROADMAP_PLAN_REQUIRED: {iid}")
        if status == "DONE":
            sha = row["Implementation Commit"].strip().strip("`")
            if not SHA.fullmatch(sha):
                errors.append(f"ROADMAP_IMPLEMENTATION_COMMIT_REQUIRED: {iid}")
            elif check_git and not commit_exists(root, sha):
                errors.append(f"ROADMAP_IMPLEMENTATION_COMMIT_NOT_FOUND: {iid}: {sha}")
            if empty(row["Verification Evidence"]):
                errors.append(f"ROADMAP_VERIFICATION_REQUIRED: {iid}")
            elif check_git and SHA.fullmatch(sha) and commit_exists(root, sha):
                errors.extend(validate_evidence_ref(path, row, root, require_evidence_scheme))
            elif require_evidence_scheme and not SMC_EVIDENCE.fullmatch(row["Verification Evidence"].strip().strip("`")) and not row["Verification Evidence"].strip().startswith(("ci-artifact:", "external-artifact:")):
                errors.append(f"ROADMAP_EVIDENCE_REF_SCHEME_REQUIRED: {iid}: {row['Verification Evidence']}")

    for iid, row_deps in deps.items():
        for dep in row_deps:
            if dep not in seen:
                errors.append(f"ROADMAP_DEPENDENCY_UNKNOWN: {iid}->{dep}")
        if statuses.get(iid) == "READY":
            for dep in row_deps:
                if statuses.get(dep) != "DONE":
                    errors.append(f"ROADMAP_READY_DEPENDENCY_NOT_DONE: {iid}->{dep}")
    found_cycle = cycle(deps)
    if found_cycle:
        errors.append("ROADMAP_DEPENDENCY_CYCLE: " + " -> ".join(found_cycle))

    deduped: list[str] = []
    seen_error: set[str] = set()
    for error in errors:
        if error not in seen_error:
            seen_error.add(error)
            deduped.append(error)
    return deduped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roadmap", type=Path)
    ap.add_argument("--no-git-check", action="store_true", help="test/migration escape hatch")
    ap.add_argument("--no-architecture-check", action="store_true", help="test/migration escape hatch")
    args = ap.parse_args()
    path = args.roadmap.resolve()
    if not path.is_file():
        print(f"ROADMAP_NOT_FOUND: {path}", file=sys.stderr)
        return 2
    errors = validate(path, check_git=not args.no_git_check, check_architecture=not args.no_architecture_check)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Roadmap v1.1 validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
