#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import atomic_write, frontmatter_end_index

VALID = {"pending", "in_progress", "completed", "blocked"}


def cursor_todos(text: str) -> list[dict[str, object]]:
    lines = text.splitlines()
    end = frontmatter_end_index(lines)
    if end < 0:
        return []
    todos_start = None
    for i in range(1, end):
        if re.match(r"^todos\s*:\s*$", lines[i]):
            todos_start = i
            break
    if todos_start is None:
        return []
    items: list[dict[str, object]] = []
    i = todos_start + 1
    while i < end:
        line = lines[i]
        if line and not line[0].isspace() and re.match(r"^[A-Za-z0-9_.-]+\s*:", line):
            break
        m = re.match(r"^(\s*)-\s+id\s*:\s*['\"]?([^'\"#]+?)['\"]?\s*$", line)
        if not m:
            i += 1
            continue
        indent = len(m.group(1))
        item = {"id": m.group(2).strip(), "status": None, "id_line": i, "status_line": None, "indent": indent}
        j = i + 1
        while j < end:
            nxt = lines[j]
            if re.match(rf"^\s{{{indent}}}-\s+id\s*:", nxt):
                break
            if nxt and not nxt[0].isspace() and re.match(r"^[A-Za-z0-9_.-]+\s*:", nxt):
                break
            sm = re.match(r"^(\s*)status\s*:\s*['\"]?([^'\"#]+?)['\"]?\s*$", nxt)
            if sm:
                item["status"] = sm.group(2).strip()
                item["status_line"] = j
            j += 1
        items.append(item)
        i = j
    return items


def smc_todo_id(cursor_id: str) -> str | None:
    m = re.match(r"^t(\d+)(?:-|$)", cursor_id.strip(), re.I)
    return f"T{int(m.group(1))}" if m else None


def markdown_todos(text: str) -> list[str]:
    return [m.group(1).upper() for m in re.finditer(r"^##\s+Todo\s+(T\d+)\b", text, re.M)]


def validate(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    curs = cursor_todos(text)
    md = markdown_todos(text)
    errors: list[str] = []
    mapping: dict[str, list[dict[str, object]]] = {}
    for item in curs:
        tid = smc_todo_id(str(item["id"]))
        if tid is None:
            errors.append(f"PLAN_CURSOR_TODO_ID_INVALID: {item['id']}")
            continue
        mapping.setdefault(tid, []).append(item)
        if item["status"] not in VALID:
            errors.append(f"PLAN_CURSOR_TODO_STATE_INVALID: {item['id']}={item['status']}")
    for tid in md:
        if tid not in mapping:
            errors.append(f"PLAN_CURSOR_TODO_MISSING: {tid}")
        elif len(mapping[tid]) > 1:
            errors.append(f"PLAN_CURSOR_TODO_DUPLICATE: {tid}")
    for tid in mapping:
        if tid not in md:
            errors.append(f"PLAN_CURSOR_TODO_ORPHAN: {tid}")
    if len(md) != len(set(md)):
        errors.append("PLAN_MARKDOWN_TODO_DUPLICATE")
    return errors


def set_status(path: Path, tid: str, status: str) -> None:
    if status not in VALID:
        raise ValueError(f"PLAN_CURSOR_TODO_STATE_INVALID: {status}")
    tid = tid.upper()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    items = [i for i in cursor_todos(text) if smc_todo_id(str(i["id"])) == tid]
    if len(items) != 1:
        raise ValueError(f"PLAN_CURSOR_TODO_MAPPING_INVALID: {tid} matches={len(items)}")
    item = items[0]
    if item["status_line"] is not None:
        line_no = int(item["status_line"])
        indent = re.match(r"^(\s*)", lines[line_no]).group(1)
        lines[line_no] = f"{indent}status: {status}"
    else:
        insert = int(item["id_line"]) + 1
        lines.insert(insert, " " * (int(item["indent"]) + 2) + f"status: {status}")
    atomic_write(path, "\n".join(lines).rstrip() + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("plan", type=Path); p.add_argument("--json", action="store_true")
    p = sub.add_parser("validate"); p.add_argument("plan", type=Path)
    p = sub.add_parser("set"); p.add_argument("plan", type=Path); p.add_argument("todo"); p.add_argument("status")
    args = ap.parse_args()
    path = args.plan.resolve()
    if not path.is_file():
        print(f"PLAN_NOT_FOUND: {path}", file=sys.stderr); return 2
    if args.cmd == "validate":
        errors = validate(path)
        if errors: print("\n".join(errors), file=sys.stderr); return 1
        print("Cursor todo state valid"); return 0
    if args.cmd == "set":
        try: set_status(path, args.todo, args.status)
        except ValueError as exc: print(str(exc), file=sys.stderr); return 1
        errors = validate(path)
        if errors: print("\n".join(errors), file=sys.stderr); return 1
        print(f"{args.todo.upper()} -> {args.status}"); return 0
    data = [{"id": i["id"], "smc_todo": smc_todo_id(str(i["id"])), "status": i["status"]} for i in cursor_todos(path.read_text(encoding="utf-8"))]
    if args.json: print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for item in data: print(f"{item['smc_todo'] or '?'}\t{item['status']}\t{item['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
