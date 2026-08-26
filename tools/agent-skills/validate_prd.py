#!/usr/bin/env python3
"""Validate deterministic structure/state rules for an SMC PRD."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


STATUSES = {"DRAFT", "REVIEW_REQUIRED", "APPROVED", "SUPERSEDED"}
REQUIRED_FIELDS = {
    "work_item_id",
    "version",
    "status",
    "target_branch",
    "review_verdict",
    "approved_at",
}
REQUIRED_SECTIONS = {
    "Current Capability Inventory",
    "Target End-State Inventory",
    "Change Classification",
    "Acceptance Criteria",
}
ACTIONS = {"KEEP", "MODIFY", "ADD", "REPLACE", "REMOVE"}
COMPAT_FIELDS = (
    "Current Consumer",
    "Reason",
    "Removal Condition",
    "Removal Version",
)
PROCESS_ONLY_APPROVED_SECTIONS = {
    "Grounding Closure Table",
    "Review History",
    "Required Revisions",
}


def frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("frontmatter missing")
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as error:
        raise ValueError("frontmatter is not closed") from error

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def section(text: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$\n?(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def section_exists(text: str, heading: str) -> bool:
    return re.search(rf"^##\s+{re.escape(heading)}\s*$", text, re.MULTILINE) is not None


def section_nonempty(text: str, heading: str) -> bool:
    body = section(text, heading)
    return body is not None and bool(body.strip())


def actions_in(body: str | None) -> list[str]:
    if not body:
        return []
    return [
        value
        for value in re.findall(
            r"\|\s*(KEEP|MODIFY|ADD|REPLACE|REMOVE)\s*\|",
            body,
        )
        if value in ACTIONS
    ]


def valid_iso8601(value: str) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_state(fields: dict[str, str], errors: list[str]) -> None:
    status = fields.get("status", "")
    verdict = fields.get("review_verdict", "")
    approved_at = fields.get("approved_at", "")

    if status not in STATUSES:
        errors.append(
            "PRD_INVALID: status must be DRAFT, REVIEW_REQUIRED, APPROVED, or SUPERSEDED"
        )
        return

    if status in {"DRAFT", "REVIEW_REQUIRED"}:
        if verdict:
            errors.append(f"PRD_STATE_INVALID: {status} review_verdict must be empty")
        if approved_at:
            errors.append(f"PRD_STATE_INVALID: {status} approved_at must be empty")
        return

    if status == "APPROVED":
        if verdict != "PASS":
            errors.append("PRD_STATE_INVALID: APPROVED review_verdict must be PASS")
        if not valid_iso8601(approved_at):
            errors.append("PRD_STATE_INVALID: APPROVED approved_at must be ISO-8601")
        return

    # SUPERSEDED may represent either an abandoned draft or a previously approved PRD.
    if verdict not in {"", "PASS"}:
        errors.append("PRD_STATE_INVALID: SUPERSEDED review_verdict must be empty or PASS")
    if verdict == "PASS" and not valid_iso8601(approved_at):
        errors.append(
            "PRD_STATE_INVALID: SUPERSEDED with PASS must retain ISO-8601 approved_at"
        )
    if not verdict and approved_at:
        errors.append(
            "PRD_STATE_INVALID: SUPERSEDED approved_at requires review_verdict PASS"
        )


def validate_prd(path: Path, require_approved: bool = False) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []

    try:
        fields = frontmatter(text)
    except ValueError as error:
        return [f"PRD_INVALID: {error}"]

    for field in sorted(REQUIRED_FIELDS - set(fields)):
        errors.append(f"PRD_INVALID: missing {field}")

    for field in ("work_item_id", "version", "target_branch"):
        if field in fields and not fields[field]:
            errors.append(f"PRD_INVALID: {field} must not be empty")

    validate_state(fields, errors)

    if require_approved and fields.get("status") != "APPROVED":
        errors.append("PRD_NOT_APPROVED")

    if fields.get("status") == "APPROVED" and path.name.endswith("-DRAFT.md"):
        errors.append(
            "PRD_APPROVED_FILENAME_HAS_DRAFT: APPROVED PRD filename must drop the -DRAFT suffix"
        )

    for heading in REQUIRED_SECTIONS:
        if not section_exists(text, heading):
            errors.append(f"PRD_INVALID: missing section {heading}")
        elif not section_nonempty(text, heading):
            errors.append(f"PRD_INVALID: empty section {heading}")

    change_section = section(text, "Change Classification")
    classifications = actions_in(change_section)
    if not classifications:
        errors.append("PRD_INVALID: Change Classification has no classified action")

    if "REPLACE" in classifications:
        replacement = section(text, "Replacement / Removal Matrix")
        if not replacement:
            errors.append("PRD_REPLACEMENT_WITHOUT_REMOVAL")
        else:
            # The matrix must explicitly name REMOVE/removal, but we do not infer
            # file-level mechanics here; that belongs to Plan.
            if not re.search(r"\bREMOVE\b|removal", replacement, re.IGNORECASE):
                errors.append("PRD_REPLACEMENT_WITHOUT_REMOVAL")

    compatibility = section(text, "Compatibility Contract")
    if compatibility is not None:
        for field in COMPAT_FIELDS:
            if field not in compatibility:
                errors.append(
                    f"PRD_COMPATIBILITY_WITHOUT_{field.upper().replace(' ', '_')}"
                )

    if fields.get("status") == "APPROVED":
        for heading in PROCESS_ONLY_APPROVED_SECTIONS:
            if section_exists(text, heading):
                errors.append(f"PRD_APPROVED_CONTAINS_PROCESS_SECTION: {heading}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prd", type=Path)
    parser.add_argument("--require-approved", action="store_true")
    args = parser.parse_args()

    errors = validate_prd(args.prd, require_approved=args.require_approved)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    print("PRD validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
