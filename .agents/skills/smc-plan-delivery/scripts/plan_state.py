#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import atomic_write, frontmatter_end_index, parse_top_level_frontmatter

VALID = {"pending", "in_progress", "completed", "blocked"}


def cursor_todos(text: str) -> list[dict[str, object]]:
    """Parse Cursor todo metadata while preserving unknown per-item fields.

    SMC owns id/content at planning time and status at delivery runtime.  This
    parser intentionally records line locations only for those governed fields;
    unknown Cursor fields remain untouched by set/sync operations.
    """
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
        item: dict[str, object] = {
            "id": m.group(2).strip(),
            "content": None,
            "status": None,
            "id_line": i,
            "content_line": None,
            "status_line": None,
            "indent": indent,
        }
        j = i + 1
        while j < end:
            nxt = lines[j]
            if re.match(rf"^\s{{{indent}}}-\s+id\s*:", nxt):
                break
            if nxt and not nxt[0].isspace() and re.match(r"^[A-Za-z0-9_.-]+\s*:", nxt):
                break
            cm = re.match(r"^(\s*)content\s*:\s*(.*?)\s*$", nxt)
            if cm:
                raw = cm.group(2).strip()
                if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
                    try:
                        item["content"] = json.loads(raw) if raw[0] == '"' else raw[1:-1].replace("''", "'")
                    except json.JSONDecodeError:
                        item["content"] = raw[1:-1]
                else:
                    item["content"] = raw.split(" #", 1)[0].strip()
                item["content_line"] = j
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


def markdown_todo_specs(text: str) -> dict[str, dict[str, object]]:
    """Return stable Markdown Todo heading and owned Change IDs."""
    matches = list(re.finditer(r"^##\s+Todo\s+(T\d+)\s*[—-]\s*(.+?)\s*$", text, re.M))
    out: dict[str, dict[str, object]] = {}
    for idx, match in enumerate(matches):
        tid = match.group(1).upper()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end]
        owns: list[str] = []
        owns_match = re.search(r"^\*\*Owns Changes\*\*\s*$\n(.*?)(?=^\*\*|^##\s+|\Z)", body, re.M | re.S)
        if owns_match:
            owns = [m.group(1).upper() for m in re.finditer(r"^\s*[-*]\s+(C\d{2,}(?:\.\d+)?)\b", owns_match.group(1), re.M | re.I)]
        out[tid] = {"title": re.sub(r"\s+", " ", match.group(2).strip()), "changes": owns}
    return out


def expected_content(tid: str, title: str, changes: list[str] | tuple[str, ...]) -> str:
    base = f"{tid.upper()} — {re.sub(r'\s+', ' ', title).strip()}"
    normalized = [str(x).upper() for x in changes if str(x).strip()]
    return base + (f" [{', '.join(normalized)}]" if normalized else "")


def expected_contents(text: str) -> dict[str, str]:
    return {
        tid: expected_content(tid, str(spec["title"]), list(spec["changes"]))
        for tid, spec in markdown_todo_specs(text).items()
    }


def validate(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    fm = parse_top_level_frontmatter(text)
    contract = fm.get("plan_contract", "").strip()
    require_content = contract == "smc.plan.v3.4"
    expected = expected_contents(text)
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
        if require_content:
            content = str(item.get("content") or "").strip()
            if not content:
                errors.append(f"PLAN_CURSOR_TODO_CONTENT_MISSING: {tid} / {item['id']}")
            else:
                exp = expected.get(tid)
                if exp is None:
                    errors.append(f"PLAN_CURSOR_TODO_CONTENT_ID_MISMATCH: {tid} has no Markdown Todo")
                elif content != exp:
                    errors.append(f"PLAN_CURSOR_TODO_CONTENT_DRIFT: {tid}: expected={exp!r} actual={content!r}")
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


def legacy_content_warnings(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    fm = parse_top_level_frontmatter(text)
    if fm.get("plan_contract") != "smc.plan.v3.3":
        return []
    out = []
    for item in cursor_todos(text):
        tid = smc_todo_id(str(item["id"])) or str(item["id"])
        if not str(item.get("content") or "").strip():
            out.append(f"PLAN_CURSOR_TODO_CONTENT_LEGACY_WARNING: {tid}")
    return out


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
        if item.get("content_line") is not None:
            insert = int(item["content_line"]) + 1
        lines.insert(insert, " " * (int(item["indent"]) + 2) + f"status: {status}")
    atomic_write(path, "\n".join(lines).rstrip() + "\n")


def sync_content(path: Path) -> int:
    """Synchronize Cursor display projections without changing runtime status."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    expected = expected_contents(text)
    items = cursor_todos(text)
    changed = 0
    # Work bottom-up so line insertions do not invalidate earlier locations.
    for item in reversed(items):
        tid = smc_todo_id(str(item["id"]))
        if not tid or tid not in expected:
            continue
        rendered = json.dumps(expected[tid], ensure_ascii=False)
        line_no = item.get("content_line")
        if line_no is not None:
            idx = int(line_no)
            indent = re.match(r"^(\s*)", lines[idx]).group(1)
            desired = f"{indent}content: {rendered}"
            if lines[idx] != desired:
                lines[idx] = desired
                changed += 1
        else:
            insert = int(item["id_line"]) + 1
            lines.insert(insert, " " * (int(item["indent"]) + 2) + f"content: {rendered}")
            changed += 1
    if changed:
        atomic_write(path, "\n".join(lines).rstrip() + "\n")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("plan", type=Path); p.add_argument("--json", action="store_true")
    p = sub.add_parser("validate"); p.add_argument("plan", type=Path)
    p = sub.add_parser("set"); p.add_argument("plan", type=Path); p.add_argument("todo"); p.add_argument("status")
    p = sub.add_parser("sync-content"); p.add_argument("plan", type=Path)
    args = ap.parse_args()
    path = args.plan.resolve()
    if not path.is_file():
        print(f"PLAN_NOT_FOUND: {path}", file=sys.stderr); return 2
    if args.cmd == "validate":
        errors = validate(path)
        if errors: print("\n".join(errors), file=sys.stderr); return 1
        for warning in legacy_content_warnings(path): print(warning, file=sys.stderr)
        print("Cursor todo state valid"); return 0
    if args.cmd == "set":
        try: set_status(path, args.todo, args.status)
        except ValueError as exc: print(str(exc), file=sys.stderr); return 1
        errors = validate(path)
        if errors: print("\n".join(errors), file=sys.stderr); return 1
        print(f"{args.todo.upper()} -> {args.status}"); return 0
    if args.cmd == "sync-content":
        changed = sync_content(path)
        errors = validate(path)
        if errors: print("\n".join(errors), file=sys.stderr); return 1
        print(f"CURSOR_TODO_CONTENT_SYNCED count={changed}"); return 0
    data = [{"id": i["id"], "smc_todo": smc_todo_id(str(i["id"])), "content": i.get("content"), "status": i["status"]} for i in cursor_todos(path.read_text(encoding="utf-8"))]
    if args.json: print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        for item in data: print(f"{item['smc_todo'] or '?'}\t{item['status']}\t{item['id']}\t{item.get('content') or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
