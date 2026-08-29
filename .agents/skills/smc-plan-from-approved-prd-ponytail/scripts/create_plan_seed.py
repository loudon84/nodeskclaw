#!/usr/bin/env python3
"""Create an SMC Plan v3.2 seed from an APPROVED PRD.

This script is intentionally conservative: it creates stable Change IDs and the
required plan structure, but leaves implementation-grounding placeholders for
the agent to resolve. A seed is NOT executable until validation and conditional
semantic review gates pass.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ACTIONS = {"KEEP", "MODIFY", "ADD", "REPLACE", "REMOVE"}
PLACEHOLDER = "<GROUND>"
REQUIREMENT_SECTIONS = (("Acceptance Criteria", "AC"), ("Definition of Done", "DOD"))


def fingerprint_worktree(status: bytes, unstaged: bytes, staged: bytes) -> str:
    if not status and not unstaged and not staged:
        return "clean"
    digest = hashlib.sha256()
    for payload in (status, unstaged, staged):
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return f"sha256:{digest.hexdigest()}"


def detect_worktree_fingerprint(start: Path) -> str:
    root = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if root.returncode != 0:
        return "unavailable"
    repo = root.stdout.strip()
    commands = (
        ["git", "-C", repo, "status", "--porcelain=v1", "-z"],
        ["git", "-C", repo, "diff", "--binary"],
        ["git", "-C", repo, "diff", "--cached", "--binary"],
    )
    outputs: list[bytes] = []
    for command in commands:
        result = subprocess.run(command, capture_output=True, check=False)
        if result.returncode != 0:
            return "unavailable"
        outputs.append(result.stdout)
    return fingerprint_worktree(*outputs)


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("PRD frontmatter missing")
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError("PRD frontmatter is not closed") from exc
    out: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"\'')
    return out


def section(text: str, heading: str) -> str | None:
    match = re.search(
        rf"^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else None


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_first_table(body: str) -> tuple[list[str], list[dict[str, str]]]:
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    for idx in range(len(lines) - 1):
        header = cells(lines[idx])
        sep = cells(lines[idx + 1])
        if len(header) != len(sep):
            continue
        if not all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in sep):
            continue
        rows: list[dict[str, str]] = []
        for raw in lines[idx + 2 :]:
            vals = cells(raw)
            if len(vals) != len(header):
                break
            rows.append(dict(zip(header, vals)))
        return header, rows
    return [], []


def clean_md(value: str) -> str:
    return re.sub(r"[`*_]", "", value).strip()


def find_action(row: dict[str, str]) -> str | None:
    for key, value in row.items():
        cleaned = clean_md(value).upper()
        if cleaned in ACTIONS:
            return cleaned
        if "action" in key.lower() or "classification" in key.lower():
            for action in ACTIONS:
                if re.search(rf"\b{action}\b", cleaned):
                    return action
    for value in row.values():
        cleaned = clean_md(value).upper()
        for action in ACTIONS:
            if re.search(rf"\b{action}\b", cleaned):
                return action
    return None


def find_existing_id(row: dict[str, str]) -> str | None:
    for key, value in row.items():
        if key.strip().lower() in {"change id", "id", "change_id"}:
            candidate = clean_md(value).upper()
            if re.fullmatch(r"C\d{2,}(?:\.\d+)?", candidate):
                return candidate
    return None


def find_capability(row: dict[str, str], action: str) -> str:
    preferred = ("capability", "feature", "item", "scope", "change", "target")
    for token in preferred:
        for key, value in row.items():
            if token in key.lower() and clean_md(value).upper() != action and clean_md(value):
                return clean_md(value)
    for value in row.values():
        cleaned = clean_md(value)
        if cleaned and cleaned.upper() != action and not re.fullmatch(r"C\d+", cleaned.upper()):
            return cleaned
    return "<PRD CAPABILITY>"


def extract_changes(prd_text: str) -> list[tuple[str, str, str]]:
    body = section(prd_text, "Change Classification")
    if not body:
        raise ValueError("PRD missing Change Classification section")
    _, rows = parse_first_table(body)
    if not rows:
        raise ValueError("PRD Change Classification must contain a markdown table")

    changes: list[tuple[str, str, str]] = []
    next_id = 1
    used: set[str] = set()
    for row in rows:
        action = find_action(row)
        if not action or action == "KEEP":
            continue
        cid = find_existing_id(row)
        if cid is None or cid in used:
            while f"C{next_id:02d}" in used:
                next_id += 1
            cid = f"C{next_id:02d}"
            next_id += 1
        used.add(cid)
        changes.append((cid, action, find_capability(row, action)))
    if not changes:
        raise ValueError("PRD has no non-KEEP changes to plan")
    return changes


EXPLICIT_ID_BULLET = r"^\s*[-*]\s+\*\*([A-Za-z]+-\d+)(?:\s*/\s*[^*：:]+)?\*\*\s*[：:]\s*(.+?)\s*$"


def extract_requirements(prd_text: str) -> list[tuple[str, str, str]]:
    """Return stable requirement ids from the approved PRD's AC and DoD lists.

    Supports numbered items (positional ids) and explicit-id bullets
    such as ``- **AC-01 / C01**：obligation``.
    """
    requirements: list[tuple[str, str, str]] = []
    for heading, source in REQUIREMENT_SECTIONS:
        body = section(prd_text, heading)
        if not body:
            raise ValueError(f"PRD missing {heading}")
        explicit = [
            (match.group(1).upper(), re.sub(r"\s+", " ", clean_md(match.group(2))).strip())
            for match in re.finditer(EXPLICIT_ID_BULLET, body, flags=re.MULTILINE)
        ]
        if explicit:
            requirements.extend((req_id, source, item) for req_id, item in explicit)
            continue
        items = [
            re.sub(r"\s+", " ", clean_md(match.group(1))).strip()
            for match in re.finditer(r"^\s*\d+[.)]\s+(.+?)\s*$", body, flags=re.MULTILINE)
        ]
        if not items:
            raise ValueError(f"PRD {heading} must contain numbered or explicit-id requirements")
        requirements.extend(
            (f"{source}-{idx:02d}", source, item)
            for idx, item in enumerate(items, 1)
        )
    return requirements


def validate_prd_state(prd: Path, text: str) -> dict[str, str]:
    fm = parse_frontmatter(text)
    if fm.get("status") != "APPROVED":
        raise ValueError("PRD_NOT_APPROVED")
    if fm.get("review_verdict") != "PASS":
        raise ValueError("PRD_REVIEW_NOT_PASS")
    if not fm.get("approved_at"):
        raise ValueError("PRD_APPROVED_AT_MISSING")
    if prd.name.endswith("-DRAFT.md"):
        raise ValueError("PRD_APPROVED_FILENAME_HAS_DRAFT")
    return fm


def relative_link(from_path: Path, to_path: Path) -> str:
    try:
        return str(to_path.resolve().relative_to(from_path.parent.resolve())).replace("\\", "/")
    except ValueError:
        import os
        return os.path.relpath(to_path.resolve(), from_path.parent.resolve()).replace("\\", "/")


def render(
    prd: Path,
    out: Path,
    fm: dict[str, str],
    changes: list[tuple[str, str, str]],
    requirements: list[tuple[str, str, str]],
) -> str:
    title = fm.get("work_item_id") or prd.stem
    prd_link = relative_link(out, prd)

    matrix_rows: list[str] = []
    decision_rows: list[str] = []
    ledger_rows: list[str] = []
    todo_blocks: list[str] = []
    requirement_rows: list[str] = []

    for idx, (cid, action, capability) in enumerate(changes, 1):
        tid = f"T{idx}"
        matrix_rows.append(
            f"| {cid} | `{PLACEHOLDER}` | PROD | {action} | {PLACEHOLDER} | {tid} | <TARGET> | {capability} | no |"
        )
        decision_rows.append(
            f"| {cid} | <DECIDE> | {PLACEHOLDER} | <DECIDE> |"
        )
        ledger_rows.append(
            f"| {tid} | {cid} | `{PLACEHOLDER}` | - | - | no |"
        )
        todo_blocks.append(
            f"## Todo {tid} — {capability}\n\n"
            f"**Owns Changes**\n- {cid}\n\n"
            "**Goal**\n\n<DECIDE>\n\n"
            f"**Immediate anchors**\n- `{PLACEHOLDER}`\n\n"
            "**Changes**\n- <DECIDE>\n\n"
            "**Stop conditions**\n- [ ] <VERIFY>\n\n"
            "**Triggered reads**\n- None unless a listed trigger becomes true\n"
        )

    for requirement_id, source, obligation in requirements:
        requirement_rows.append(
            f"| {requirement_id} | {source} | {obligation} | <CLASSIFY> | - | - | <VERIFY> | <EVIDENCE_CLASS> | yes |"
        )

    source_revision = fm.get("source_revision") or f"{fm.get('work_item_id', prd.stem)}@{fm.get('version', 'unknown')}"
    grounded_commit = fm.get("grounded_commit") or "<GROUND>"
    worktree_fingerprint = detect_worktree_fingerprint(prd.parent)
    return (
        "---\n"
        "plan_contract: smc.plan.v3.2\n"
        "commit_policy: post_review\n"
        f"source_revision: {source_revision}\n"
        f"grounded_commit: {grounded_commit}\n"
        "grounding_source: committed_baseline\n"
        f"working_tree_fingerprint: {worktree_fingerprint}\n"
        "---\n\n"
        f"# {title} Implementation Plan\n\n"
        f"## Approved PRD\n\n[Approved PRD]({prd_link})\n\n"
        "## Scope\n\n- In: <DECIDE>\n- Out: <DECIDE>\n- Production Owner inherited from PRD: <GROUND>\n\n"
        "## Grounding Evidence Ledger\n\n"
        "| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |\n"
        "|---|---|---|---|---|---|---|\n"
        "| <DECIDE> | `<GROUND>` | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <GROUND> |\n\n"
        "## Requirement Coverage Ledger\n\n"
        "| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        + "\n".join(requirement_rows)
        + "\n\n## Lifecycle Closure Matrix\n\n"
        "Use `None` only when the PRD has no state/concurrency lifecycle requirements.\n\n"
        "| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |\n"
        "|---|---|---|---|---|---|---|\n"
        "| <DECIDE> | <DECIDE> | <DECIDE> | <DECIDE> | <DECIDE> | <DECIDE> | <VERIFY> |\n\n"
        "## Contract / Data Flow Closure Matrix\n\n"
        "Use `None` only when no data crosses an independent owner, process, network, persistence, queue, or generator boundary.\n\n"
        "| Flow | Requirements | Producer | Transport / Schema | Consumer | Required Fields | Validation Owner | Failure Mapping | Retry / Idempotency Identity | Evidence IDs |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        "| <DECIDE> | <DECIDE> | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <GROUND> | <VERIFY> |\n\n"
        "## Verification Ledger\n\n"
        "| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| V01 | <VERIFY_LEVEL> | <VERIFY> | <VERIFY> | <VERIFY> | <VERIFY> | <ENVIRONMENT> | yes |\n\n"
        "## Immediate Read\n\n- `<GROUND>`\n\n"
        "## Triggered Read\n\n- If <trigger>: `<GROUND>`\n- Otherwise: do not read\n\n"
        "## Change Matrix\n\n"
        "| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
        + "\n".join(matrix_rows)
        + "\n\n## Implementation Decisions\n\n"
        + "| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |\n"
        + "|---|---|---|---|\n"
        + "\n".join(decision_rows)
        + "\n\n## Write Ownership Ledger\n\n"
        + "| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |\n"
        + "|---|---|---|---|---|---|\n"
        + "\n".join(ledger_rows)
        + "\n\n## Integration Hotspots\n\nNone\n\n"
        "## Generated Outputs Ledger\n\nNone\n\n"
        + "\n\n".join(todo_blocks)
        + "\n\n## Verification\n\nUse the Verification Ledger as the only evidence SOT; this section orders the final commands.\n\n```bash\n<VERIFY>\n```\n\n"
        "## Completion Gate\n\n"
        "| Exit State | Allowed When | Blocking Evidence |\n"
        "|---|---|---|\n"
        "| IMPLEMENTED_AND_PROVEN | <VERIFY> | <VERIFY> |\n"
        "| IMPLEMENTED_NOT_PROVEN | <VERIFY> | <VERIFY> |\n"
        "| BLOCKED | <VERIFY> | <VERIFY> |\n"
        "| RETURN_PRD | <VERIFY> | <VERIFY> |\n"
    )

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prd", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("create", "revise"), default="create")
    parser.add_argument("--force", action="store_true", help="confirm overwrite in revise mode")
    args = parser.parse_args()

    prd = args.prd.resolve()
    out = args.output.resolve()
    if not prd.is_file():
        print(f"PRD_NOT_FOUND: {prd}", file=sys.stderr)
        return 2
    if args.force and args.mode != "revise":
        print("PLAN_REVISION_NOT_AUTHORIZED: --force requires --mode revise", file=sys.stderr)
        return 2
    if args.mode == "create" and out.exists():
        print(f"PLAN_ALREADY_EXISTS: {out}; explicit revise authorization is required", file=sys.stderr)
        return 2
    if args.mode == "revise" and not out.exists():
        print(f"PLAN_NOT_FOUND_FOR_REVISION: {out}", file=sys.stderr)
        return 2
    if args.mode == "revise" and not args.force:
        print("PLAN_REVISION_NOT_AUTHORIZED: revise mode requires --force", file=sys.stderr)
        return 2

    text = prd.read_text(encoding="utf-8")
    try:
        fm = validate_prd_state(prd, text)
        changes = extract_changes(text)
        requirements = extract_requirements(text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(prd, out, fm, changes, requirements), encoding="utf-8")
    print(f"Plan seed created: {out}")
    print(f"Non-KEEP changes: {len(changes)}")
    print(f"Requirements: {len(requirements)}")
    print("Seed contains grounding placeholders and MUST pass validation and review gates before execution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
