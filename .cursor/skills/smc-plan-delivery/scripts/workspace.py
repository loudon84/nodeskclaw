#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

from common import (
    atomic_write,
    find_repo_root,
    git,
    parse_first_table,
    plan_id,
    repo_relative_path,
    section,
    semantic_plan_sha256,
    strip_md,
    utc_now,
)

SCHEMA = "smc.delivery.workspace.v1"
STATUS_SCHEMA = "smc.delivery.workspace.status.v1"
DEFAULT_EXCLUDES = (".smc/", "docs_agent/evidence/")
TOOLING_PREFIXES = (".agents/skills/", ".cursor/skills/", "tools/agent-skills/")


def _norm(rel: str) -> str:
    value = rel.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def _excluded(rel: str) -> bool:
    rel = _norm(rel)
    return any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in DEFAULT_EXCLUDES)


def planned_files(plan: Path) -> set[str]:
    _, rows = parse_first_table(section(plan.read_text(encoding="utf-8"), "Change Matrix"))
    out: set[str] = set()
    for row in rows:
        ref = strip_md(row.get("File / Symbol", "")).replace("\\", "/")
        if not ref or ref.lower() in {"-", "none", "n/a", "na"}:
            continue
        rel = _norm(ref.split("#", 1)[0].strip())
        if rel:
            out.add(rel)
    return out


def _name_set(root: Path, *args: str) -> set[str]:
    proc = git(root, *args)
    return {
        _norm(raw.strip())
        for raw in proc.stdout.splitlines()
        if raw.strip() and not _excluded(raw.strip())
    }


def dirty_classes(root: Path) -> dict[str, set[str]]:
    """Return deterministic dirty classes without parsing `git status` rename text."""
    worktree = _name_set(root, "diff", "--name-only", "--")
    index = _name_set(root, "diff", "--cached", "--name-only", "--")
    untracked = _name_set(root, "ls-files", "--others", "--exclude-standard")
    return {"worktree": worktree, "index": index, "untracked": untracked}


def dirty_paths(root: Path) -> set[str]:
    classes = dirty_classes(root)
    return set().union(*classes.values())


def _path_state(root: Path, rel: str) -> str:
    """Hash path identity + bytes + type + executable bit; deletions are explicit."""
    rel = _norm(rel)
    path = root / rel
    h = hashlib.sha256()
    h.update(rel.encode("utf-8", "surrogateescape")); h.update(b"\0")
    if not path.exists() and not path.is_symlink():
        h.update(b"<DELETED>")
        return "sha256:" + h.hexdigest()
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode):
        h.update(b"L\0"); h.update(os.readlink(path).encode("utf-8", "surrogateescape"))
    elif stat.S_ISREG(st.st_mode):
        h.update(b"F+x\0" if (st.st_mode & stat.S_IXUSR) else b"F\0")
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
    else:
        h.update(b"O\0")
    return "sha256:" + h.hexdigest()


def _dirty_membership(rel: str, classes: dict[str, set[str]]) -> dict[str, bool]:
    return {name: rel in values for name, values in classes.items()}


def _path_snapshot(root: Path, rel: str, classes: dict[str, set[str]]) -> dict[str, object]:
    return {
        "content_state": _path_state(root, rel),
        "dirty": _dirty_membership(rel, classes),
    }


def _snapshot_map(root: Path, paths: set[str] | list[str], classes: dict[str, set[str]]) -> dict[str, dict[str, object]]:
    return {rel: _path_snapshot(root, rel, classes) for rel in sorted({_norm(x) for x in paths if x})}


def _snapshot_fingerprint(mapping: dict[str, dict[str, object]]) -> str:
    raw = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def baseline_path(plan: Path) -> Path:
    root = find_repo_root(plan)
    return root / ".smc" / "runs" / plan_id(plan) / "workspace-baseline.json"


def load(plan: Path) -> dict | None:
    path = baseline_path(plan)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("DELIVERY_WORKSPACE_BASELINE_INVALID") from exc
    if data.get("schema") != SCHEMA or data.get("plan_id") != plan_id(plan):
        raise ValueError("DELIVERY_WORKSPACE_BASELINE_IDENTITY_INVALID")
    return data


def init(plan: Path, *, refresh: bool = False) -> dict:
    """Freeze the execution baseline before the first implementation mutation.

    Unrelated pre-existing dirty paths are allowed and protected as ambient state.
    Any pre-existing dirty path in the Plan Change Matrix is ambiguous ownership
    and therefore a hard conflict. Governance tooling dirty outside this Plan is
    also a hard block: a business delivery cannot rewrite its own proof machinery.
    """
    root = find_repo_root(plan)
    existing = load(plan)
    if existing and not refresh:
        return existing
    if existing and refresh:
        # Refresh is only a pre-implementation rebind after an intentional Plan
        # revision.  It must never be usable to bless implementation/ambient
        # mutations that already happened under the previous baseline.
        prior = inspect(plan)
        refresh_blockers = []
        if prior.get("scope_changed_files"):
            refresh_blockers.append("implementation delta exists")
        if prior.get("ambient_mutated"):
            refresh_blockers.append("ambient mutated")
        if prior.get("unexpected_dirty"):
            refresh_blockers.append("scope drift exists")
        if not prior.get("head_stable", False):
            refresh_blockers.append("HEAD drifted")
        if refresh_blockers:
            raise ValueError("DELIVERY_WORKSPACE_REFRESH_AFTER_MUTATION: " + "; ".join(refresh_blockers))

    pid = plan_id(plan)
    rel_plan = repo_relative_path(plan, root)
    planned = planned_files(plan)
    if not planned:
        raise ValueError("DELIVERY_PLAN_WRITE_SET_EMPTY")

    classes = dirty_classes(root)
    dirty = set().union(*classes.values())
    target_conflicts = sorted(dirty & planned)
    if target_conflicts:
        raise ValueError("DELIVERY_TARGET_CONFLICT: " + ", ".join(target_conflicts))

    owned_control = {rel_plan, f"docs_agent/evidence/{pid}-evidence.json"}
    tooling_conflicts = sorted(
        rel for rel in dirty - planned - owned_control
        if any(rel.startswith(prefix) for prefix in TOOLING_PREFIXES)
    )
    if tooling_conflicts:
        raise ValueError("DELIVERY_TOOLING_BLOCKED: " + ", ".join(tooling_conflicts))

    ambient = sorted(dirty - planned - owned_control)
    ambient_snapshots = _snapshot_map(root, ambient, classes)
    planned_snapshots = _snapshot_map(root, planned, classes)
    data = {
        "schema": SCHEMA,
        "plan_id": pid,
        "plan": rel_plan,
        "base_commit": git(root, "rev-parse", "HEAD").stdout.strip(),
        "created_at": utc_now(),
        "planned_files": sorted(planned),
        "owned_control_paths": sorted(owned_control),
        "planned_baseline": planned_snapshots,
        "ambient_preexisting": ambient_snapshots,
        "ambient_baseline_fingerprint": _snapshot_fingerprint(ambient_snapshots),
        "plan_semantic_sha256": semantic_plan_sha256(plan),
    }
    path = baseline_path(plan)
    atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return data


def ensure(plan: Path) -> dict:
    data = load(plan)
    if data is None:
        raise ValueError("DELIVERY_WORKSPACE_BASELINE_MISSING: run workspace.py init before implementation")
    return data


def scope_fingerprint(plan: Path, baseline: dict | None = None) -> str:
    root = find_repo_root(plan)
    data = baseline or ensure(plan)
    h = hashlib.sha256()
    h.update(semantic_plan_sha256(plan).encode("ascii")); h.update(b"\0")
    for rel in sorted(data.get("planned_files", [])):
        h.update(rel.encode("utf-8", "surrogateescape")); h.update(b"\0")
        h.update(_path_state(root, rel).encode("ascii")); h.update(b"\0")
    return "sha256:" + h.hexdigest()


def inspect(plan: Path, *, allow_head_change: bool = False) -> dict:
    root = find_repo_root(plan)
    data = ensure(plan)
    planned = set(data.get("planned_files", []))
    rel_plan = str(data.get("plan") or repo_relative_path(plan, root))
    control = set(data.get("owned_control_paths", [])) | {rel_plan}
    baseline_ambient = dict(data.get("ambient_preexisting", {}))
    classes = dirty_classes(root)
    current_dirty = set().union(*classes.values())

    current_ambient = _snapshot_map(root, set(baseline_ambient), classes)
    ambient_mutated = sorted(
        rel for rel, before in baseline_ambient.items()
        if current_ambient.get(rel) != before
    )
    # A new dirty path outside planned/control/ambient is delivery scope drift.
    unexpected = sorted(current_dirty - set(baseline_ambient) - planned - control)
    tooling_mutated = sorted(
        rel for rel in unexpected
        if any(rel.startswith(prefix) for prefix in TOOLING_PREFIXES)
    )

    baseline_planned = dict(data.get("planned_baseline", {}))
    current_planned = _snapshot_map(root, planned, classes)
    scope_changed = sorted(
        rel for rel in planned
        if current_planned.get(rel, {}).get("content_state")
        != baseline_planned.get(rel, {}).get("content_state")
    )

    current_plan_sha = semantic_plan_sha256(plan)
    plan_semantic_changed = current_plan_sha != data.get("plan_semantic_sha256")
    current_head = git(root, "rev-parse", "HEAD").stdout.strip()
    head_stable = current_head == data.get("base_commit")
    ambient_fp = _snapshot_fingerprint(current_ambient)
    ambient_stable = not ambient_mutated and ambient_fp == data.get("ambient_baseline_fingerprint")
    current_scope = scope_fingerprint(plan, data)

    passed = (
        ambient_stable
        and not unexpected
        and not plan_semantic_changed
        and (allow_head_change or head_stable)
    )
    return {
        "schema": STATUS_SCHEMA,
        "plan_id": plan_id(plan),
        "base_commit": data.get("base_commit"),
        "current_head": current_head,
        "head_stable": head_stable,
        "plan": rel_plan,
        "plan_semantic_sha256": current_plan_sha,
        "plan_semantic_changed": plan_semantic_changed,
        "planned_files": sorted(planned),
        "scope_changed_files": scope_changed,
        "ambient_preexisting": sorted(baseline_ambient),
        "ambient_mutated": ambient_mutated,
        "unexpected_dirty": unexpected,
        "tooling_mutated": tooling_mutated,
        "scope_fingerprint": current_scope,
        "ambient_fingerprint": ambient_fp,
        "ambient_baseline_fingerprint": data.get("ambient_baseline_fingerprint"),
        "ambient_stable": ambient_stable,
        "scope_clean": not unexpected,
        "pass": passed,
    }


def assert_stable(plan: Path, *, allow_head_change: bool = False) -> dict:
    status = inspect(plan, allow_head_change=allow_head_change)
    problems: list[str] = []
    if status["plan_semantic_changed"]:
        problems.append("DELIVERY_PLAN_SEMANTIC_DRIFT")
    if not allow_head_change and not status["head_stable"]:
        problems.append(
            f"DELIVERY_HEAD_DRIFT: base={status['base_commit']} current={status['current_head']}"
        )
    if status["ambient_mutated"]:
        problems.append("DELIVERY_AMBIENT_MUTATED: " + ", ".join(status["ambient_mutated"]))
    if status["tooling_mutated"]:
        problems.append("DELIVERY_TOOLING_MUTATION: " + ", ".join(status["tooling_mutated"]))
    elif status["unexpected_dirty"]:
        problems.append("DELIVERY_SCOPE_DRIFT: " + ", ".join(status["unexpected_dirty"]))
    if problems:
        raise ValueError("\n".join(problems))
    return status


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("plan", type=Path); p.add_argument("--refresh", action="store_true"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("inspect"); p.add_argument("plan", type=Path); p.add_argument("--allow-head-change", action="store_true"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("fingerprint"); p.add_argument("plan", type=Path)
    p = sub.add_parser("assert-stable"); p.add_argument("plan", type=Path); p.add_argument("--allow-head-change", action="store_true")
    args = ap.parse_args()
    plan = args.plan.resolve()
    if not plan.is_file():
        print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr)
        return 2
    try:
        if args.cmd == "init":
            result = init(plan, refresh=args.refresh)
        elif args.cmd == "inspect":
            result = inspect(plan, allow_head_change=args.allow_head_change)
        elif args.cmd == "fingerprint":
            print(scope_fingerprint(plan)); return 0
        else:
            result = assert_stable(plan, allow_head_change=args.allow_head_change)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr); return 1
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"WORKSPACE {'PASS' if result.get('pass', True) else 'BLOCKED'} plan={result.get('plan_id')} scope={result.get('scope_fingerprint', '-')}")
    return 0 if result.get("pass", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
