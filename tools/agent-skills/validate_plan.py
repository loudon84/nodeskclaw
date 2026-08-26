#!/usr/bin/env python3
"""Validate an SMC Cursor implementation plan against its approved PRD."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_SECTIONS = {
    "Approved PRD",
    "Scope",
    "Immediate Read",
    "Triggered Read",
    "Change Matrix",
    "Implementation Decisions",
    "Verification",
}
REQUIRED_CHANGE_COLUMNS = {
    "File / Symbol",
    "Action",
    "Existing Owner",
    "Target State",
    "PRD Capability",
    "New File?",
}
ACTIONS = {"KEEP", "MODIFY", "ADD", "REPLACE", "REMOVE"}


def section(text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


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


def resolve_prd(plan: Path, link: str) -> Path | None:
    raw = Path(link)
    if raw.is_absolute():
        return raw.resolve() if raw.is_file() else None

    # Support both plan-relative links and repository-relative links.
    for candidate in ((plan.parent / raw).resolve(), (ROOT / raw).resolve()):
        if candidate.is_file():
            return candidate
    return None


def run_prd_validator(prd: Path) -> tuple[int, str]:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "agent-skills" / "validate_prd.py"),
            str(prd),
            "--require-approved",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def parse_markdown_table(body: str | None) -> tuple[list[str], list[dict[str, str]]]:
    if not body:
        return [], []

    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return [], []

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    for index in range(len(lines) - 1):
        header = cells(lines[index])
        separator = cells(lines[index + 1])
        if len(header) != len(separator):
            continue
        if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in separator):
            continue

        rows: list[dict[str, str]] = []
        for line in lines[index + 2 :]:
            row_cells = cells(line)
            if len(row_cells) != len(header):
                break
            rows.append(dict(zip(header, row_cells)))
        return header, rows

    return [], []


def validate_plan(path: Path) -> list[str]:
    plan = path.resolve()
    text = plan.read_text(encoding="utf-8")
    errors: list[str] = []

    for heading in REQUIRED_SECTIONS:
        body = section(text, heading)
        if body is None:
            errors.append(f"PLAN_INVALID: missing section {heading}")
        elif not body.strip():
            errors.append(f"PLAN_INVALID: empty section {heading}")

    approved_body = section(text, "Approved PRD")
    link = local_markdown_link(approved_body)
    prd = resolve_prd(plan, link) if link else None
    if prd is None:
        errors.append("PLAN_INVALID: missing resolvable Approved PRD link")
    else:
        code, output = run_prd_validator(prd)
        if code:
            errors.append(f"PLAN_PRD_INVALID: {output.strip()}")

    matrix = section(text, "Change Matrix")
    header, rows = parse_markdown_table(matrix)
    if not header:
        errors.append("PLAN_INVALID: Change Matrix must contain a markdown table")
        return errors

    missing_columns = REQUIRED_CHANGE_COLUMNS - set(header)
    for column in sorted(missing_columns):
        errors.append(f"PLAN_INVALID: Change Matrix missing column {column}")

    if missing_columns:
        return errors

    actions: list[str] = []
    new_files: list[str] = []

    for row_no, row in enumerate(rows, 1):
        action = row["Action"].strip().upper()
        new_file = row["New File?"].strip().lower()

        if action not in ACTIONS:
            errors.append(f"PLAN_INVALID: row {row_no} invalid Action {row['Action']}")
            continue
        actions.append(action)

        if not row["File / Symbol"].strip():
            errors.append(f"PLAN_INVALID: row {row_no} File / Symbol is empty")
        if not row["PRD Capability"].strip():
            errors.append(f"PLAN_INVALID: row {row_no} PRD Capability is empty")

        if new_file not in {"yes", "no"}:
            errors.append(f"PLAN_INVALID: row {row_no} New File? must be yes or no")
        elif new_file == "yes":
            new_files.append(row["File / Symbol"].strip())

    if "REPLACE" in actions and "REMOVE" not in actions:
        errors.append("PLAN_REPLACEMENT_WITHOUT_REMOVAL")

    justification = section(text, "New File Justification")
    if new_files and not justification:
        errors.append("PLAN_NEW_FILE_WITHOUT_JUSTIFICATION")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()

    errors = validate_plan(args.plan)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print("Plan validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
