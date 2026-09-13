#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from common import append_jsonl, atomic_write, find_repo_root, git, plan_id, read_jsonl, section, semantic_plan_sha256, utc_now
from delivery_state import load as load_delivery_state
from plan_state import cursor_todos, markdown_todo_specs, smc_todo_id
from workspace import inspect as workspace_inspect

EVENTS = {
    "TODO_STARTED", "DISCOVERY", "PROGRESS", "ERROR", "RETRY",
    "LOCAL_CHECK_PASS", "TODO_DONE", "BLOCKED", "NOTE",
}


def run_dir(plan: Path) -> Path:
    return find_repo_root(plan) / ".smc" / "runs" / plan_id(plan)


def resume_path(plan: Path) -> Path:
    return run_dir(plan) / "resume.json"


def _safe_agent(agent: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", agent).strip("-") or "main"


def ledger_path(plan: Path, agent: str) -> Path:
    return run_dir(plan) / f"ledger-{_safe_agent(agent)}.jsonl"


def errors_path(plan: Path) -> Path:
    return run_dir(plan) / "errors.jsonl"


def gate_path(plan: Path) -> Path:
    return run_dir(plan) / "continuation-gate.json"


def _normalize_todo(todo: str) -> str:
    value = todo.strip().upper()
    if not re.fullmatch(r"T\d+", value):
        raise ValueError(f"EXECUTION_TODO_ID_INVALID: {todo}")
    return value


def brief_path(plan: Path, todo: str) -> Path:
    return run_dir(plan) / "briefs" / f"{_normalize_todo(todo)}.md"


def report_path(plan: Path, todo: str) -> Path:
    return run_dir(plan) / "reports" / f"{_normalize_todo(todo)}.md"


def review_package_path(plan: Path, todo: str) -> Path:
    return run_dir(plan) / "reviews" / f"{_normalize_todo(todo)}-package.md"


def _todo_block(text: str, todo: str) -> str:
    tid = _normalize_todo(todo)
    matches = list(re.finditer(r"^##\s+Todo\s+(T\d+)\s*[—-]\s*(.+?)\s*$", text, re.M))
    for idx, match in enumerate(matches):
        if match.group(1).upper() != tid:
            continue
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        return text[match.start():end].rstrip() + "\n"
    raise ValueError(f"EXECUTION_TODO_NOT_FOUND: {tid}")


def _write_targets(todo_block: str) -> list[str]:
    """Extract repo paths from the current Todo's **Writes** contract.

    SMC v4.x plans use path#symbol write ownership. Review packages strip the
    symbol suffix and ask Git only for those owned files, which keeps prior
    Todo changes out of a task-scoped review without introducing Todo commits.
    """
    raw: list[str] = []
    inline = re.search(r"^\*\*Writes\*\*\s*:\s*(.+?)\s*$", todo_block, re.M | re.I)
    if inline:
        raw.extend(re.split(r"[,;]", inline.group(1)))
    block = re.search(
        r"^\*\*Writes\*\*\s*:?[ \t]*$\n(.*?)(?=^\*\*|^##\s+|\Z)",
        todo_block,
        re.M | re.S | re.I,
    )
    if block:
        for line in block.group(1).splitlines():
            m = re.match(r"^\s*[-*+]\s+(.+?)\s*$", line)
            if m:
                raw.append(m.group(1))
    paths: list[str] = []
    for value in raw:
        value = value.strip().strip("`").strip()
        value = re.sub(r"^(CREATE|MODIFY|UPDATE|DELETE|REMOVE)\s+", "", value, flags=re.I)
        value = value.split("#", 1)[0].strip().strip("`")
        value = value.replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        if value and value not in {"-", "none", "n/a"} and value not in paths:
            paths.append(value)
    return paths


# @lat: [[runtime-cost#GES Runtime Cost Optimization#Task Context Artifacts]]
def create_task_brief(plan: Path, todo: str) -> Path:
    tid = _normalize_todo(todo)
    text = plan.read_text(encoding="utf-8")
    specs = markdown_todo_specs(text)
    if tid not in specs:
        raise ValueError(f"EXECUTION_TODO_NOT_FOUND: {tid}")
    constraints = section(text, "Global Constraints") or "(none declared)"
    block = _todo_block(text, tid)
    body = (
        "# SMC Task Brief\n\n"
        f"- Plan ID: `{plan_id(plan)}`\n"
        f"- Todo: `{tid}`\n"
        f"- Plan semantic hash: `{semantic_plan_sha256(plan)}`\n"
        f"- Canonical Plan: `{plan}`\n\n"
        "This file is a derived execution brief, not a second Plan SOT. "
        "Implement only this Todo and its declared write ownership.\n\n"
        "## Global Constraints\n\n"
        f"{constraints}\n\n"
        f"{block}"
    )
    path = brief_path(plan, tid)
    atomic_write(path, body.rstrip() + "\n")
    return path


def ensure_report_path(plan: Path, todo: str) -> Path:
    path = report_path(plan, todo)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


# @lat: [[runtime-cost#GES Runtime Cost Optimization#Task Context Artifacts]]
def build_task_review_package(plan: Path, todo: str) -> Path:
    tid = _normalize_todo(todo)
    block = _todo_block(plan.read_text(encoding="utf-8"), tid)
    writes = _write_targets(block)
    if not writes:
        raise ValueError(f"EXECUTION_TODO_WRITE_SET_MISSING: {tid}")
    root = find_repo_root(plan)
    stat = git(root, "diff", "--stat", "--", *writes, check=False).stdout
    diff = git(root, "diff", "--no-ext-diff", "--unified=10", "--", *writes, check=False).stdout
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "--", *writes, check=False).stdout.splitlines()
    extra: list[str] = []
    for rel in untracked:
        target = root / rel
        if not target.is_file():
            continue
        data = target.read_bytes()
        if b"\0" in data:
            extra.append(f"### Untracked binary file `{rel}`\n\n(binary content omitted)\n")
            continue
        text = data.decode("utf-8", "replace")
        extra.append(f"### Untracked file `{rel}`\n\n```text\n{text}\n```\n")
    package = (
        "# SMC Task Review Package\n\n"
        f"- Plan ID: `{plan_id(plan)}`\n"
        f"- Todo: `{tid}`\n"
        f"- Plan semantic hash: `{semantic_plan_sha256(plan)}`\n"
        f"- Owned write paths: {', '.join(f'`{x}`' for x in writes)}\n\n"
        "The package is scoped to this Todo's declared Writes. It is derived review input, not evidence or Plan state.\n\n"
        "## Diff Stat\n\n```text\n"
        + (stat or "(no tracked diff)\n")
        + "```\n\n## Tracked Diff\n\n```diff\n"
        + (diff or "(no tracked diff)\n")
        + "```\n\n"
        + "\n".join(extra)
    )
    path = review_package_path(plan, tid)
    atomic_write(path, package.rstrip() + "\n")
    return path


def _all_ledgers(plan: Path) -> list[dict]:
    """Merge per-agent append-only ledgers into deterministic event-time order.

    File-name order is not execution order: an older event in ``ledger-z`` must
    not become the resume capsule's ``last_event`` merely because ``z`` sorts
    after ``a``.  ISO-8601 UTC timestamps are the primary ordering key; the
    remaining fields provide a deterministic tie-break without introducing a
    shared mutable sequence allocator between workers.
    """
    rows: list[dict] = []
    directory = run_dir(plan)
    if not directory.is_dir():
        return rows
    for path in sorted(directory.glob("ledger-*.jsonl")):
        rows.extend(read_jsonl(path))
    rows.sort(key=lambda row: (
        str(row.get("at") or ""),
        str(row.get("agent") or ""),
        str(row.get("event") or ""),
        str(row.get("todo") or ""),
        str(row.get("summary") or ""),
    ))
    return rows


def _ledger_progress(plan: Path) -> int:
    # Count is monotonic across per-agent append-only ledgers and does not depend
    # on a racy cross-agent global sequence allocator.
    return len(_all_ledgers(plan))


def _failure_signature(summary: str) -> str:
    normalized = re.sub(r"\s+", " ", summary.strip().lower())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def append_event(
    plan: Path,
    event: str,
    *,
    agent: str = "main",
    todo: str = "",
    summary: str = "",
    files: list[str] | None = None,
) -> dict:
    event = event.upper()
    if event not in EVENTS:
        raise ValueError(f"EXECUTION_EVENT_INVALID: {event}")
    agent = _safe_agent(agent)
    # Workspace check makes execution memory itself fail closed on scope drift.
    ws = workspace_inspect(plan)
    if not ws["pass"]:
        raise ValueError("EXECUTION_CONTEXT_WORKSPACE_UNSTABLE")
    rec = {
        "schema": "smc.execution.event.v1",
        "at": utc_now(),
        "plan_id": plan_id(plan),
        "agent": agent,
        "todo": todo.upper() if todo else None,
        "event": event,
        "summary": re.sub(r"\s+", " ", summary.strip())[:500],
        "files": [x.replace("\\", "/") for x in (files or [])],
        "scope_fingerprint": ws["scope_fingerprint"],
    }
    append_jsonl(ledger_path(plan, agent), rec)
    if event == "ERROR":
        sig = _failure_signature(rec["summary"])
        existing = [r for r in read_jsonl(errors_path(plan)) if r.get("failure_signature") == sig]
        err = {
            "schema": "smc.execution.error.v1",
            "at": rec["at"],
            "plan_id": rec["plan_id"],
            "agent": agent,
            "todo": rec["todo"],
            "failure_signature": sig,
            "attempt": len(existing) + 1,
            "summary": rec["summary"],
        }
        append_jsonl(errors_path(plan), err)
        rec["failure_signature"] = sig
        rec["attempt"] = err["attempt"]
    refresh(plan)
    return rec


def build_resume(plan: Path) -> dict:
    text = plan.read_text(encoding="utf-8")
    todos = []
    for item in cursor_todos(text):
        tid = smc_todo_id(str(item["id"]))
        if tid:
            todos.append({
                "id": tid,
                "cursor_id": item["id"],
                "content": item.get("content"),
                "status": item.get("status"),
            })
    active = next((x for x in todos if x["status"] == "in_progress"), None)
    if active is None:
        active = next((x for x in todos if x["status"] == "pending"), None)
    delivery = load_delivery_state(plan) or {}
    ws = workspace_inspect(plan)
    events = _all_ledgers(plan)
    last = events[-1] if events else None
    errors = read_jsonl(errors_path(plan))
    return {
        "schema": "smc.execution.resume.v1",
        "plan_id": plan_id(plan),
        "plan_semantic_sha256": semantic_plan_sha256(plan),
        "delivery_state": delivery.get("state", "UNINITIALIZED"),
        "last_valid_state": delivery.get("last_valid_state", "UNINITIALIZED"),
        "active_todo": active,
        "next_step": (active or {}).get("content") or (
            "Run governed completion gates"
            if todos and all(x["status"] == "completed" for x in todos)
            else "Resolve next governed action"
        ),
        "completed_todos": [x["id"] for x in todos if x["status"] == "completed"],
        "blocked_todos": [x["id"] for x in todos if x["status"] == "blocked"],
        "last_event": last,
        "last_error": errors[-1] if errors else None,
        "ledger_progress": len(events),
        "workspace": {
            "scope_fingerprint": ws["scope_fingerprint"],
            "ambient_fingerprint": ws["ambient_fingerprint"],
            "ambient_stable": ws["ambient_stable"],
            "head_stable": ws["head_stable"],
            "unexpected_dirty": ws["unexpected_dirty"],
        },
        "updated_at": utc_now(),
    }


def refresh(plan: Path) -> dict:
    data = build_resume(plan)
    atomic_write(resume_path(plan), json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return data


def latest(plan: Path) -> dict:
    path = resume_path(plan)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Never trust a stale capsule without re-grounding it to current state.
            if data.get("plan_semantic_sha256") == semantic_plan_sha256(plan):
                return refresh(plan)
        except json.JSONDecodeError:
            pass
    return refresh(plan)


def continuation_gate(plan: Path, cap: int = 20) -> dict:
    """Execution-only bounded continuation. It never certifies completion."""
    resume = refresh(plan)
    active = resume.get("active_todo")
    if active is None:
        decision = {"decision": "ALLOW_STOP", "reason": "no pending/in_progress Todo", "blocks": 0, "progress": _ledger_progress(plan)}
        atomic_write(gate_path(plan), json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        return decision

    path = gate_path(plan)
    state: dict = {}
    if path.is_file():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    blocks = int(state.get("blocks", 0) or 0)
    previous_progress = int(state.get("progress", 0) or 0)
    now_progress = _ledger_progress(plan)

    if blocks >= cap:
        decision = {"decision": "ALLOW_STOP", "reason": f"continuation cap reached ({blocks}/{cap})", "blocks": blocks, "progress": now_progress}
    elif blocks > 0 and now_progress <= previous_progress:
        decision = {"decision": "ALLOW_STOP", "reason": "no execution progress since last continuation", "blocks": blocks, "progress": now_progress}
    else:
        decision = {
            "decision": "CONTINUE",
            "reason": f"Todo {active['id']} remains {active['status']}: {active.get('content') or ''}",
            "blocks": blocks + 1,
            "progress": now_progress,
        }
    atomic_write(path, json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return decision


def main() -> int:
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("refresh"); p.add_argument("plan", type=Path); p.add_argument("--json", action="store_true")
    p = sub.add_parser("show"); p.add_argument("plan", type=Path); p.add_argument("--json", action="store_true")
    p = sub.add_parser("event"); p.add_argument("plan", type=Path); p.add_argument("--event", required=True); p.add_argument("--agent", default="main"); p.add_argument("--todo", default=""); p.add_argument("--summary", default=""); p.add_argument("--file", action="append", default=[])
    p = sub.add_parser("gate"); p.add_argument("plan", type=Path); p.add_argument("--cap", type=int, default=20); p.add_argument("--json", action="store_true")
    p = sub.add_parser("brief"); p.add_argument("plan", type=Path); p.add_argument("--todo", required=True); p.add_argument("--json", action="store_true")
    p = sub.add_parser("report-path"); p.add_argument("plan", type=Path); p.add_argument("--todo", required=True); p.add_argument("--json", action="store_true")
    p = sub.add_parser("review-package"); p.add_argument("plan", type=Path); p.add_argument("--todo", required=True); p.add_argument("--json", action="store_true")
    args = ap.parse_args(); plan = args.plan.resolve()
    if not plan.is_file():
        print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr); return 2
    try:
        if args.cmd == "refresh": data = refresh(plan)
        elif args.cmd == "show": data = latest(plan)
        elif args.cmd == "event": data = append_event(plan, args.event, agent=args.agent, todo=args.todo, summary=args.summary, files=args.file)
        elif args.cmd == "gate": data = continuation_gate(plan, max(1, args.cap))
        elif args.cmd == "brief": data = {"path": str(create_task_brief(plan, args.todo)), "todo": _normalize_todo(args.todo)}
        elif args.cmd == "report-path": data = {"path": str(ensure_report_path(plan, args.todo)), "todo": _normalize_todo(args.todo)}
        else: data = {"path": str(build_task_review_package(plan, args.todo)), "todo": _normalize_todo(args.todo)}
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr); return 1

    if args.cmd in {"brief", "report-path", "review-package"}:
        if getattr(args, "json", False):
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(data["path"])
        return 0

    if getattr(args, "json", False) or args.cmd == "event":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if args.cmd in {"refresh", "show"}:
            print(f"EXECUTION_CONTEXT plan={data['plan_id']} state={data['delivery_state']} next={data['next_step']}")
        else:
            print(f"EXECUTION_GATE {data['decision']}: {data['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
