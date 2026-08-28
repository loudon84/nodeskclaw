#!/usr/bin/env python3
"""Deterministic validator for SMC Cursor Plan Contract v3."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

REQUIRED_SECTIONS = (
    "Approved PRD",
    "Scope",
    "Immediate Read",
    "Triggered Read",
    "Change Matrix",
    "Implementation Decisions",
    "Write Ownership Ledger",
    "Integration Hotspots",
    "Verification",
)

MATRIX_COLUMNS = (
    "Change ID",
    "File / Symbol",
    "Kind",
    "Action",
    "Existing Owner",
    "Todo Owner",
    "Target State",
    "PRD Capability",
    "New File?",
)

DECISION_COLUMNS = (
    "Change ID",
    "Strategy",
    "Root-Cause / Reuse Evidence",
    "Why This Is Minimum",
)

LEDGER_COLUMNS = (
    "Todo",
    "Owns Changes",
    "Writes",
    "Reads",
    "Depends On",
    "Parallel Safe",
)

HOTSPOT_COLUMNS = ("File", "Owner Todo", "Reason")
NEW_FILE_COLUMNS = ("Change ID", "File", "Necessity", "Owner Impact")
NEW_DEP_COLUMNS = (
    "Change ID",
    "Dependency",
    "Necessity",
    "Why Existing / Stdlib / Native / Installed Fails",
)

ACTIONS = {"KEEP", "MODIFY", "ADD", "REPLACE", "REMOVE"}
KINDS = {"PROD", "TEST", "CONFIG", "DOC", "BUILD"}
STRATEGIES = {
    "REUSE_EXISTING",
    "STDLIB",
    "NATIVE",
    "INSTALLED_DEP",
    "MODIFY_EXISTING",
    "MINIMAL_NEW",
    "NEW_DEPENDENCY",
    "REMOVE_ONLY",
    "GENERATED_ENTRYPOINT",
}
TODO_LABELS = (
    "Owns Changes",
    "Goal",
    "Immediate anchors",
    "Changes",
    "Stop conditions",
    "Triggered reads",
)
PLACEHOLDER_RE = re.compile(
    r"<\s*(?:GROUND|DECIDE|VERIFY|TBD|TODO|TARGET|PRD CAPABILITY)\s*>|\?\?\?|\bTBD\b",
    re.IGNORECASE,
)
CHANGE_ID_RE = re.compile(r"^C\d{2,}(?:\.\d+)?$")
TODO_ID_RE = re.compile(r"^T\d+$")
EMPTY_VALUES = {"", "-", "none", "n/a", "na"}


@dataclass(frozen=True)
class ValidationError:
    code: str
    detail: str

    def line(self) -> str:
        return f"{self.code}: {self.detail}" if self.detail else self.code


def add(errors: list[ValidationError], code: str, detail: str) -> None:
    errors.append(ValidationError(code, detail))


def section(text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def strip_md(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^[-*+]\s+", "", value)
    if value.startswith("`") and value.endswith("`") and len(value) >= 2:
        value = value[1:-1]
    return value.strip()


def normalized_empty(value: str) -> bool:
    return strip_md(value).lower() in EMPTY_VALUES


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_first_table(body: str | None) -> tuple[list[str], list[dict[str, str]]]:
    if not body:
        return [], []
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    for idx in range(len(lines) - 1):
        header = table_cells(lines[idx])
        sep = table_cells(lines[idx + 1])
        if len(header) != len(sep):
            continue
        if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in sep):
            continue
        rows: list[dict[str, str]] = []
        for raw in lines[idx + 2 :]:
            vals = table_cells(raw)
            if len(vals) != len(header):
                break
            rows.append(dict(zip(header, vals)))
        return header, rows
    return [], []


def check_table(
    body: str | None,
    section_name: str,
    required_columns: Iterable[str],
    errors: list[ValidationError],
) -> tuple[list[str], list[dict[str, str]]]:
    header, rows = parse_first_table(body)
    if not header:
        add(errors, "PLAN_TABLE_MISSING", f"{section_name} must contain a markdown table")
        return [], []
    for col in required_columns:
        if col not in header:
            add(errors, "PLAN_TABLE_MISSING_COLUMN", f"{section_name} missing column {col}")
    return header, rows


def split_values(cell: str) -> list[str]:
    raw = cell.strip()
    if normalized_empty(raw):
        return []
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    parts = re.split(r"[\n;,]+", raw)
    out: list[str] = []
    for part in parts:
        value = strip_md(part)
        if value and value.lower() not in EMPTY_VALUES:
            out.append(value)
    return out


def normalize_ref(value: str) -> str:
    return re.sub(r"\s+", "", strip_md(value).replace("\\", "/"))


def ref_file(ref: str) -> str:
    return normalize_ref(ref).split("#", 1)[0]


def ref_has_symbol(ref: str) -> bool:
    return "#" in normalize_ref(ref)


def refs_overlap(a: str, b: str, hotspot_files: set[str] | None = None) -> bool:
    a_n, b_n = normalize_ref(a), normalize_ref(b)
    if a_n == b_n:
        return True
    a_file, b_file = ref_file(a_n), ref_file(b_n)
    if a_file != b_file:
        return False
    if hotspot_files and a_file in hotspot_files:
        return True
    return not ref_has_symbol(a_n) or not ref_has_symbol(b_n)


def same_physical_file(a: str, b: str) -> bool:
    return ref_file(a) == ref_file(b)


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return {}
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"\'')
    return fields


def local_markdown_link(body: str | None) -> str | None:
    if not body:
        return None
    match = re.search(r"\[[^\]]+\]\(([^)]+)\)", body)
    if not match:
        return None
    target = match.group(1).strip().split("#", 1)[0]
    if not target or re.match(r"^[a-z]+://", target, re.IGNORECASE):
        return None
    return target


def find_repo_root(path: Path) -> Path | None:
    start = path.resolve()
    if start.is_file():
        start = start.parent
    for candidate in (start, *start.parents):
        if (candidate / ".agents").is_dir() or (candidate / ".git").exists():
            return candidate
    return None


def resolve_prd(plan: Path, link: str | None) -> Path | None:
    if not link:
        return None
    raw = Path(link)
    if raw.is_absolute():
        return raw.resolve() if raw.is_file() else None
    candidates = [(plan.parent / raw).resolve()]
    root = find_repo_root(plan)
    if root:
        candidates.append((root / raw).resolve())
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def validate_approved_prd(plan: Path, text: str, errors: list[ValidationError]) -> Path | None:
    link = local_markdown_link(section(text, "Approved PRD"))
    prd = resolve_prd(plan, link)
    if prd is None:
        add(errors, "PLAN_APPROVED_PRD_UNRESOLVED", "Approved PRD link is missing or cannot be resolved")
        return None

    prd_text = prd.read_text(encoding="utf-8")
    fm = parse_frontmatter(prd_text)
    if fm.get("status") != "APPROVED":
        add(errors, "PLAN_PRD_NOT_APPROVED", f"{prd}: status={fm.get('status', '')!r}")
    if fm.get("review_verdict") != "PASS":
        add(errors, "PLAN_PRD_REVIEW_NOT_PASS", f"{prd}: review_verdict={fm.get('review_verdict', '')!r}")
    if not fm.get("approved_at"):
        add(errors, "PLAN_PRD_APPROVED_AT_MISSING", str(prd))
    if prd.name.endswith("-DRAFT.md"):
        add(errors, "PLAN_PRD_APPROVED_FILENAME_HAS_DRAFT", str(prd))

    root = find_repo_root(plan)
    project_validator = root / "tools/agent-skills/validate_prd.py" if root else None
    if project_validator and project_validator.is_file():
        result = subprocess.run(
            [sys.executable, str(project_validator), str(prd), "--require-approved"],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            detail = (result.stdout + result.stderr).strip().replace("\n", " | ")
            add(errors, "PLAN_PROJECT_PRD_VALIDATOR_FAILED", detail)
    return prd


def todo_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+Todo\s+(T\d+)\b.*$", text, re.MULTILINE))
    out: dict[str, str] = {}
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        # Do not absorb final normal section (usually Verification) into last Todo.
        tail = text[start:end]
        normal = re.search(r"^##\s+(?!Todo\b).+$", tail, re.MULTILINE)
        if normal:
            tail = tail[: normal.start()]
        out[match.group(1)] = tail.strip()
    return out


def todo_owned_changes(body: str) -> set[str]:
    match = re.search(
        r"\*\*Owns Changes\*\*\s*(.*?)(?=\n\*\*[^\n]+\*\*|\Z)",
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return set()
    return {v for v in split_values(match.group(1).replace("- ", "\n")) if CHANGE_ID_RE.fullmatch(v)}


def validate_placeholders(text: str, errors: list[ValidationError]) -> None:
    # Ignore HTML comments so the template can document conditional placeholders,
    # but a final plan must not contain active placeholder tokens.
    active = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    matches = sorted(set(m.group(0) for m in PLACEHOLDER_RE.finditer(active)))
    if matches:
        add(errors, "PLAN_UNRESOLVED_PLACEHOLDER", ", ".join(matches))


def dependency_closure(deps: dict[str, set[str]], start: str) -> set[str]:
    seen: set[str] = set()
    stack = list(deps.get(start, set()))
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(deps.get(node, set()) - seen)
    return seen


def detect_cycles(deps: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    state: dict[str, int] = {node: 0 for node in deps}
    stack: list[str] = []

    def dfs(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for dep in deps.get(node, set()):
            if dep not in state:
                continue
            if state[dep] == 0:
                dfs(dep)
            elif state[dep] == 1:
                try:
                    idx = stack.index(dep)
                    cycle = stack[idx:] + [dep]
                except ValueError:
                    cycle = [node, dep, node]
                if cycle not in cycles:
                    cycles.append(cycle)
        stack.pop()
        state[node] = 2

    for node in deps:
        if state[node] == 0:
            dfs(node)
    return cycles


def validate_plan(path: Path) -> list[ValidationError]:
    plan = path.resolve()
    text = plan.read_text(encoding="utf-8")
    errors: list[ValidationError] = []

    # V1/V2: required sections + PRD state + placeholders.
    for heading in REQUIRED_SECTIONS:
        body = section(text, heading)
        if body is None:
            add(errors, "PLAN_REQUIRED_SECTION_MISSING", heading)
        elif not body.strip():
            add(errors, "PLAN_REQUIRED_SECTION_EMPTY", heading)

    validate_approved_prd(plan, text, errors)
    validate_placeholders(text, errors)

    # V3: Change Matrix.
    _, matrix_rows = check_table(section(text, "Change Matrix"), "Change Matrix", MATRIX_COLUMNS, errors)
    change_owners: dict[str, set[str]] = {}
    change_actions: dict[str, set[str]] = {}
    matrix_targets_by_todo: dict[str, set[str]] = {}
    matrix_change_ids: set[str] = set()
    non_keep_ids: set[str] = set()
    new_files: set[tuple[str, str]] = set()

    for idx, row in enumerate(matrix_rows, 1):
        if not all(col in row for col in MATRIX_COLUMNS):
            continue
        cid = strip_md(row["Change ID"]).upper()
        kind = strip_md(row["Kind"]).upper()
        action = strip_md(row["Action"]).upper()
        todo = strip_md(row["Todo Owner"]).upper()
        new_file = strip_md(row["New File?"]).lower()
        target = normalize_ref(row["File / Symbol"])

        if not CHANGE_ID_RE.fullmatch(cid):
            add(errors, "PLAN_CHANGE_ID_INVALID", f"row {idx}: {row['Change ID']}")
            continue
        matrix_change_ids.add(cid)
        change_actions.setdefault(cid, set()).add(action)

        if kind not in KINDS:
            add(errors, "PLAN_KIND_INVALID", f"{cid}: {row['Kind']}")
        if action not in ACTIONS:
            add(errors, "PLAN_ACTION_INVALID", f"{cid}: {row['Action']}")
            continue
        if new_file not in {"yes", "no"}:
            add(errors, "PLAN_NEW_FILE_FLAG_INVALID", f"{cid}: {row['New File?']}")

        if action == "KEEP":
            if todo not in {"", "-"} or new_file == "yes":
                add(errors, "PLAN_KEEP_HAS_IMPLEMENTATION", f"{cid} row {idx}")
            continue

        non_keep_ids.add(cid)
        if not TODO_ID_RE.fullmatch(todo):
            add(errors, "PLAN_CHANGE_WITHOUT_TODO_OWNER", f"{cid} row {idx}: {row['Todo Owner']}")
        else:
            change_owners.setdefault(cid, set()).add(todo)
            matrix_targets_by_todo.setdefault(todo, set()).add(target)

        if new_file == "yes" and target:
            new_files.add((cid, ref_file(target)))

    for cid, owners in sorted(change_owners.items()):
        if len(owners) > 1:
            add(errors, "PLAN_CHANGE_MULTIPLE_TODO_OWNERS", f"{cid}: {', '.join(sorted(owners))}")
    for cid, actions in sorted(change_actions.items()):
        if "REPLACE" in actions and "REMOVE" not in actions:
            add(errors, "PLAN_REPLACEMENT_WITHOUT_REMOVAL", f"{cid}: REPLACE must include a REMOVE row under the same Change ID")

    # V4: Implementation Decisions.
    _, decision_rows = check_table(
        section(text, "Implementation Decisions"),
        "Implementation Decisions",
        DECISION_COLUMNS,
        errors,
    )
    decisions: dict[str, list[dict[str, str]]] = {}
    new_dep_ids: set[str] = set()
    for idx, row in enumerate(decision_rows, 1):
        if not all(col in row for col in DECISION_COLUMNS):
            continue
        cid = strip_md(row["Change ID"]).upper()
        strategy = strip_md(row["Strategy"]).upper()
        evidence = strip_md(row["Root-Cause / Reuse Evidence"])
        reason = strip_md(row["Why This Is Minimum"])
        if not CHANGE_ID_RE.fullmatch(cid):
            add(errors, "PLAN_CHANGE_ID_INVALID", f"Implementation Decisions row {idx}: {row['Change ID']}")
            continue
        decisions.setdefault(cid, []).append(row)
        if strategy not in STRATEGIES:
            add(errors, "PLAN_STRATEGY_INVALID", f"{cid}: {row['Strategy']}")
        if normalized_empty(evidence):
            add(errors, "PLAN_MINIMALITY_EVIDENCE_MISSING", cid)
        if normalized_empty(reason):
            add(errors, "PLAN_MINIMALITY_REASON_MISSING", cid)
        if strategy == "NEW_DEPENDENCY":
            new_dep_ids.add(cid)

    for cid in sorted(non_keep_ids):
        count = len(decisions.get(cid, []))
        if count == 0:
            add(errors, "PLAN_IMPLEMENTATION_DECISION_MISSING", cid)
        elif count > 1:
            add(errors, "PLAN_IMPLEMENTATION_DECISION_DUPLICATE", f"{cid}: {count} rows")

    # Conditional justification tables.
    if new_files:
        _, jf_rows = check_table(
            section(text, "New File Justification"),
            "New File Justification",
            NEW_FILE_COLUMNS,
            errors,
        )
        justified: set[tuple[str, str]] = set()
        for row in jf_rows:
            if not all(col in row for col in NEW_FILE_COLUMNS):
                continue
            cid = strip_md(row["Change ID"]).upper()
            file = ref_file(row["File"])
            if not normalized_empty(row["Necessity"]) and not normalized_empty(row["Owner Impact"]):
                justified.add((cid, file))
        for item in sorted(new_files - justified):
            add(errors, "PLAN_NEW_FILE_WITHOUT_JUSTIFICATION", f"{item[0]}: {item[1]}")

    if new_dep_ids:
        _, jd_rows = check_table(
            section(text, "New Dependency Justification"),
            "New Dependency Justification",
            NEW_DEP_COLUMNS,
            errors,
        )
        justified_ids: set[str] = set()
        for row in jd_rows:
            if not all(col in row for col in NEW_DEP_COLUMNS):
                continue
            cid = strip_md(row["Change ID"]).upper()
            if (
                not normalized_empty(row["Dependency"])
                and not normalized_empty(row["Necessity"])
                and not normalized_empty(row["Why Existing / Stdlib / Native / Installed Fails"])
            ):
                justified_ids.add(cid)
        for cid in sorted(new_dep_ids - justified_ids):
            add(errors, "PLAN_NEW_DEPENDENCY_WITHOUT_JUSTIFICATION", cid)

    # V5/V6: Ledger and Todo sections.
    _, ledger_rows = check_table(
        section(text, "Write Ownership Ledger"),
        "Write Ownership Ledger",
        LEDGER_COLUMNS,
        errors,
    )
    ledger: dict[str, dict[str, object]] = {}
    for idx, row in enumerate(ledger_rows, 1):
        if not all(col in row for col in LEDGER_COLUMNS):
            continue
        tid = strip_md(row["Todo"]).upper()
        if not TODO_ID_RE.fullmatch(tid):
            add(errors, "PLAN_LEDGER_TODO_UNKNOWN", f"row {idx}: {row['Todo']}")
            continue
        if tid in ledger:
            add(errors, "PLAN_LEDGER_TODO_DUPLICATE", tid)
            continue
        parallel = strip_md(row["Parallel Safe"]).lower()
        if parallel not in {"yes", "no"}:
            add(errors, "PLAN_PARALLEL_SAFE_INVALID", f"{tid}: expected yes/no, got {row['Parallel Safe']}")
            parallel = "no"
        ledger[tid] = {
            "changes": {v.upper() for v in split_values(row["Owns Changes"])},
            "writes": {normalize_ref(v) for v in split_values(row["Writes"])},
            "reads": {normalize_ref(v) for v in split_values(row["Reads"])},
            "deps": {v.upper() for v in split_values(row["Depends On"])},
            "parallel": parallel,
        }

    for cid, owners in sorted(change_owners.items()):
        if len(owners) != 1:
            continue
        owner = next(iter(owners))
        if owner not in ledger:
            add(errors, "PLAN_LEDGER_TODO_UNKNOWN", f"{cid} owner {owner} missing from ledger")
            continue
        if cid not in ledger[owner]["changes"]:
            add(errors, "PLAN_LEDGER_CHANGE_OWNER_MISMATCH", f"{cid} matrix owner={owner}, ledger does not own it")

    for tid, info in sorted(ledger.items()):
        for cid in sorted(info["changes"]):
            owners = change_owners.get(cid, set())
            if owners != {tid}:
                add(errors, "PLAN_LEDGER_CHANGE_OWNER_MISMATCH", f"{tid} claims {cid}, matrix owners={sorted(owners)}")

        matrix_targets = matrix_targets_by_todo.get(tid, set())
        writes = info["writes"]
        for target in sorted(matrix_targets):
            if target and target not in writes:
                add(errors, "PLAN_MATRIX_TARGET_NOT_OWNED", f"{tid}: {target}")
        for write in sorted(writes):
            if write not in matrix_targets:
                add(errors, "PLAN_ORPHAN_TODO_WRITE", f"{tid}: {write}")

    sections = todo_sections(text)
    for tid in sorted(ledger):
        if tid not in sections:
            add(errors, "PLAN_TODO_SECTION_MISSING", tid)
    for tid in sorted(set(sections) - set(ledger)):
        add(errors, "PLAN_TODO_SECTION_UNKNOWN", tid)

    for tid, body in sorted(sections.items()):
        for label in TODO_LABELS:
            if not re.search(rf"\*\*{re.escape(label)}\*\*", body, re.IGNORECASE):
                add(errors, "PLAN_TODO_FIELD_MISSING", f"{tid}: {label}")
        if tid in ledger:
            section_changes = todo_owned_changes(body)
            if section_changes != ledger[tid]["changes"]:
                add(
                    errors,
                    "PLAN_LEDGER_CHANGE_OWNER_MISMATCH",
                    f"{tid}: Todo section owns {sorted(section_changes)}, ledger owns {sorted(ledger[tid]['changes'])}",
                )

    # Integration hotspots.
    hotspot_body = section(text, "Integration Hotspots")
    hotspot_files: set[str] = set()
    hotspot_owners: dict[str, str] = {}
    if hotspot_body and strip_md(hotspot_body).lower() != "none":
        _, hotspot_rows = check_table(hotspot_body, "Integration Hotspots", HOTSPOT_COLUMNS, errors)
        for row in hotspot_rows:
            if not all(col in row for col in HOTSPOT_COLUMNS):
                continue
            file = ref_file(row["File"])
            owner = strip_md(row["Owner Todo"]).upper()
            if file:
                if file in hotspot_owners and hotspot_owners[file] != owner:
                    add(errors, "PLAN_INTEGRATION_HOTSPOT_CONFLICT", f"{file}: owners {hotspot_owners[file]} and {owner}")
                hotspot_files.add(file)
                hotspot_owners[file] = owner
            if owner and owner not in ledger:
                add(errors, "PLAN_LEDGER_TODO_UNKNOWN", f"hotspot {file}: owner {owner}")

    # Write conflicts.
    tids = sorted(ledger)
    for i, left in enumerate(tids):
        for right in tids[i + 1 :]:
            for lw in ledger[left]["writes"]:
                for rw in ledger[right]["writes"]:
                    if refs_overlap(lw, rw, hotspot_files):
                        code = (
                            "PLAN_INTEGRATION_HOTSPOT_CONFLICT"
                            if ref_file(lw) in hotspot_files
                            else "PLAN_WRITE_CONFLICT"
                        )
                        add(errors, code, f"{left} and {right}: {lw} <-> {rw}")

    for file, owner in sorted(hotspot_owners.items()):
        for tid, info in ledger.items():
            if tid == owner:
                continue
            for write in info["writes"]:
                if ref_file(write) == file:
                    add(errors, "PLAN_INTEGRATION_HOTSPOT_CONFLICT", f"{file} owner={owner}, also written by {tid}")

    # V7: dependency graph.
    deps: dict[str, set[str]] = {tid: set(info["deps"]) for tid, info in ledger.items()}
    for tid, values in deps.items():
        for dep in sorted(values):
            if dep == tid:
                add(errors, "PLAN_DEPENDENCY_SELF", tid)
            elif dep not in ledger:
                add(errors, "PLAN_DEPENDENCY_UNKNOWN", f"{tid} -> {dep}")
    for cycle in detect_cycles(deps):
        add(errors, "PLAN_DEPENDENCY_CYCLE", " -> ".join(cycle))

    # V8: read/write ordering. Either direction is accepted as an explicit order;
    # the planner decides which Todo is semantically upstream.
    closures = {tid: dependency_closure(deps, tid) for tid in ledger}
    hazard_pairs: set[tuple[str, str, str]] = set()
    for writer, winfo in ledger.items():
        for reader, rinfo in ledger.items():
            if writer == reader:
                continue
            for write in winfo["writes"]:
                for read in rinfo["reads"]:
                    if refs_overlap(write, read, hotspot_files):
                        ordered = writer in closures.get(reader, set()) or reader in closures.get(writer, set())
                        if not ordered:
                            key = (writer, reader, f"{write} <-> {read}")
                            if key not in hazard_pairs:
                                hazard_pairs.add(key)
                                add(
                                    errors,
                                    "PLAN_READ_AFTER_WRITE_WITHOUT_DEPENDENCY",
                                    f"writer={writer}, reader={reader}: {write} <-> {read}",
                                )

    # V9: Parallel Safe is deliberately conservative.
    incoming: dict[str, set[str]] = {tid: set() for tid in ledger}
    for tid, values in deps.items():
        for dep in values:
            if dep in incoming:
                incoming[dep].add(tid)

    for tid, info in ledger.items():
        if info["parallel"] != "yes":
            continue
        reasons: list[str] = []
        if deps.get(tid):
            reasons.append(f"depends_on={sorted(deps[tid])}")
        if incoming.get(tid):
            reasons.append(f"depended_by={sorted(incoming[tid])}")

        for other, oinfo in ledger.items():
            if other == tid:
                continue
            if any(same_physical_file(a, b) for a in info["writes"] for b in oinfo["writes"]):
                reasons.append(f"same-file write hazard with {other}")
            if any(refs_overlap(a, b, hotspot_files) for a in info["writes"] for b in oinfo["reads"]):
                reasons.append(f"write/read hazard with {other}")
            if any(refs_overlap(a, b, hotspot_files) for a in info["reads"] for b in oinfo["writes"]):
                reasons.append(f"read/write hazard with {other}")

        if reasons:
            add(errors, "PLAN_PARALLEL_SAFE_INVALID", f"{tid}: {'; '.join(sorted(set(reasons)))}")

    # De-duplicate identical errors while preserving order.
    deduped: list[ValidationError] = []
    seen: set[tuple[str, str]] = set()
    for error in errors:
        key = (error.code, error.detail)
        if key not in seen:
            seen.add(key)
            deduped.append(error)
    return deduped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    plan = args.plan.resolve()
    if not plan.is_file():
        if args.as_json:
            print(json.dumps({"valid": False, "plan": str(plan), "errors": [{"code": "PLAN_NOT_FOUND", "detail": str(plan)}]}, ensure_ascii=False, indent=2))
        else:
            print(f"PLAN_NOT_FOUND: {plan}", file=sys.stderr)
        return 2

    errors = validate_plan(plan)
    if args.as_json:
        print(
            json.dumps(
                {"valid": not errors, "plan": str(plan), "errors": [asdict(e) for e in errors]},
                ensure_ascii=False,
                indent=2,
            )
        )
    elif errors:
        print("\n".join(error.line() for error in errors), file=sys.stderr)
    else:
        print("Plan validation passed")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
