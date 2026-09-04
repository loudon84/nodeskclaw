#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

EMPTY = {"", "-", "none", "n/a", "na"}


def find_repo_root(path: Path | str) -> Path:
    p = Path(path).resolve()
    if p.is_file():
        p = p.parent
    result = subprocess.run(
        ["git", "-C", str(p), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()
    for candidate in (p, *p.parents):
        if (candidate / ".agents").is_dir():
            return candidate
    raise RuntimeError(f"REPO_ROOT_NOT_FOUND: {p}")


def paths_same(left: Path | str, right: Path | str) -> bool:
    """Return filesystem identity equality, not lexical path equality.

    Windows may expose the same directory through an 8.3 short name, a long
    user-profile name, a junction, or a subst/symlink alias.  ``Path`` lexical
    comparisons cannot safely decide identity in those cases.
    """
    try:
        return os.path.samefile(os.fspath(left), os.fspath(right))
    except (FileNotFoundError, NotADirectoryError, OSError):
        # Fallback is intentionally conservative and only covers normal lexical
        # aliases when filesystem identity cannot be queried.
        l = os.path.normcase(os.path.abspath(os.fspath(left)))
        r = os.path.normcase(os.path.abspath(os.fspath(right)))
        return l == r


def repo_relative_path(path: Path | str, root: Path | str) -> str:
    """Return a POSIX repo-relative path across filesystem aliases.

    First use the normal lexical fast path.  If that fails, walk the supplied
    path's existing ancestors and compare each ancestor to the Git root using
    filesystem identity.  This makes Windows 8.3/long-path aliases, junctions
    and symlinks equivalent without weakening the outside-repository guard.
    """
    p = Path(path).absolute()
    r = Path(root).absolute()
    try:
        return p.relative_to(r).as_posix()
    except ValueError:
        pass

    for ancestor in (p, *p.parents):
        if paths_same(ancestor, r):
            return p.relative_to(ancestor).as_posix()
    raise ValueError(f"PATH_OUTSIDE_REPO: path={p} root={r}")


def git(root: Path, *args: str, check: bool = True, text: bool = True):
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )
    if check and result.returncode:
        stderr = result.stderr.strip() if text else result.stderr.decode("utf-8", "replace")
        raise RuntimeError(f"GIT_COMMAND_FAILED: git {' '.join(args)}: {stderr}")
    return result


def split_frontmatter(text: str) -> tuple[list[str], list[str]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return [], lines
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        raise ValueError("PLAN_FRONTMATTER_UNCLOSED")
    return lines[1:end], lines[end + 1 :]


def parse_top_level_frontmatter(text: str) -> dict[str, str]:
    fm_lines, _ = split_frontmatter(text)
    out: dict[str, str] = {}
    for line in fm_lines:
        if not line or line[0].isspace() or line.lstrip().startswith("-") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"\'')
    return out


def frontmatter_end_index(lines: list[str]) -> int:
    if not lines or lines[0].strip() != "---":
        return -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i
    return -1


def set_top_level_frontmatter(text: str, updates: dict[str, str]) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        prefix = ["---"] + [f"{k}: {v}" for k, v in updates.items()] + ["---", ""]
        return "\n".join(prefix + lines).rstrip() + "\n"
    end = frontmatter_end_index(lines)
    if end < 0:
        raise ValueError("PLAN_FRONTMATTER_UNCLOSED")
    found: set[str] = set()
    for i in range(1, end):
        line = lines[i]
        if not line or line[0].isspace() or line.lstrip().startswith("-") or ":" not in line:
            continue
        key, _ = line.split(":", 1)
        key = key.strip()
        if key in updates:
            lines[i] = f"{key}: {updates[key]}"
            found.add(key)
    insert_at = end
    missing = [f"{key}: {value}" for key, value in updates.items() if key not in found]
    lines[insert_at:insert_at] = missing
    return "\n".join(lines).rstrip() + "\n"


def section(text: str, heading: str) -> str | None:
    m = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return m.group(1).strip() if m else None


def table_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_first_table(body: str | None) -> tuple[list[str], list[dict[str, str]]]:
    if not body:
        return [], []
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    for idx in range(len(lines) - 1):
        header, sep = table_cells(lines[idx]), table_cells(lines[idx + 1])
        if len(header) != len(sep):
            continue
        if not all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in sep):
            continue
        rows: list[dict[str, str]] = []
        for raw in lines[idx + 2 :]:
            vals = table_cells(raw)
            if len(vals) != len(header):
                break
            rows.append(dict(zip(header, vals)))
        return header, rows
    return [], []


def strip_md(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^[-*+]\s+", "", value)
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        value = value[1:-1]
    return value.strip()


def split_values(cell: str) -> list[str]:
    raw = cell.strip()
    if strip_md(raw).lower() in EMPTY:
        return []
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    return [strip_md(v) for v in re.split(r"[\n;,]+", raw) if strip_md(v).lower() not in EMPTY]


def plan_id_from_text(path: Path, text: str) -> str:
    fm = parse_top_level_frontmatter(text)
    value = fm.get("plan_id", "").strip()
    if value:
        return value
    source = fm.get("source_revision", "").strip()
    if source:
        return source.split("@", 1)[0].strip() or path.stem
    return re.sub(r"\.plan$", "", path.stem, flags=re.I)


def plan_id(path: Path) -> str:
    return plan_id_from_text(path, path.read_text(encoding="utf-8"))


def semantic_plan_sha256(path: Path) -> str:
    """Hash Plan semantics while excluding derived/runtime Cursor todo fields.

    `status` is runtime state and is normalized. `content` is a deterministic UI
    projection of the Markdown Todo specification and is removed entirely so a
    v3.3 -> v3.4 content backfill does not create semantic drift by itself.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    end = frontmatter_end_index(lines)
    if end > 0:
        in_todos = False
        drop: set[int] = set()
        for i in range(1, end):
            line = lines[i]
            if re.match(r"^todos\s*:\s*$", line):
                in_todos = True
                continue
            if in_todos:
                if line and not line[0].isspace() and re.match(r"^[A-Za-z0-9_.-]+\s*:", line):
                    in_todos = False
                elif re.match(r"^\s+status\s*:\s*.*$", line):
                    indent = re.match(r"^(\s*)", line).group(1)
                    lines[i] = f"{indent}status: <runtime>"
                elif re.match(r"^\s+content\s*:\s*.*$", line):
                    drop.add(i)
        if drop:
            lines = [line for i, line in enumerate(lines) if i not in drop]
    normalized = "\n".join(lines).rstrip() + "\n"
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    original_mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.chmod(tmp, original_mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    if new_file:
        os.chmod(path, 0o600)


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
