#!/usr/bin/env python3
"""Validate canonical skills, references, and the generated Cursor mirror."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents" / "skills"
REFERENCES = ROOT / ".agents" / "references"
CURSOR_SKILLS = ROOT / ".cursor" / "skills"
CURSOR_REFERENCES = ROOT / ".cursor" / "references"


def tree(path: Path) -> dict[str, bytes]:
    return {
        item.relative_to(path).as_posix(): item.read_bytes()
        for item in path.rglob("*")
        if item.is_file()
    }


def frontmatter(skill: Path) -> dict[str, str]:
    lines = skill.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise ValueError("unterminated frontmatter") from error
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    errors: list[str] = []
    for directory in sorted(item for item in SKILLS.iterdir() if item.is_dir()):
        skill = directory / "SKILL.md"
        if not skill.is_file():
            errors.append(f"SKILL-001 {directory}: SKILL.md missing")
            continue
        try:
            values = frontmatter(skill)
        except ValueError as error:
            errors.append(f"SKILL-002 {skill}: {error}")
            continue
        if values.get("name") != directory.name:
            errors.append(f"SKILL-002 {skill}: name must equal directory")
        if not values.get("description"):
            errors.append(f"SKILL-002 {skill}: description missing")
        content = skill.read_text(encoding="utf-8")
        for target in re.findall(r"\]\((?:\.\./)+references/([^)]+)\)", content):
            if not (REFERENCES / target).is_file() and not (REFERENCES / "upstream" / target).is_file():
                errors.append(f"SKILL-003 {skill}: missing reference {target}")
    if tree(SKILLS) != tree(CURSOR_SKILLS) or tree(REFERENCES) != tree(CURSOR_REFERENCES):
        errors.append("SKILL-004 CURSOR_SKILL_MIRROR_DRIFT")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Agent Skills validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
