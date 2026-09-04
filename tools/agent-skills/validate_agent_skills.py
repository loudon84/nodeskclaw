#!/usr/bin/env python3
"""Validate SMC Agent Skills structure, lock state, mirrors, and cross-skill references."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / ".agents" / "skills"
REFERENCES = ROOT / ".agents" / "references"
CURSOR_SKILLS = ROOT / ".cursor" / "skills"
CURSOR_REFERENCES = ROOT / ".cursor" / "references"
LOCK = ROOT / "tools" / "agent-skills" / "upstream.lock.yaml"
BANNED_ACTIVE_SKILLS = {"writing-plans", "smc-plan-from-approved-prd"}
GOVERNED_SKILLS = {
    "brainstorming",
    "executing-plans",
    "smc-plan-delivery",
    "smc-architecture-decision",
    "smc-architecture-review",
    "smc-plan-from-approved-prd-ponytail",
    "smc-plan-review",
    "smc-plan-validator",
    "smc-prd-converge",
    "smc-prd-grounding",
    "smc-prd-review",
    "smc-roadmap",
    "subagent-driven-development",
    "using-superpowers",
}
DEPRECATION_WORDS = (
    "deprecated", "deprecation", "removed", "remove", "legacy", "migration", "forbidden", "used to exist",
    "废弃", "已删除", "删除", "迁移", "不依赖", "不再依赖", "不调用", "禁止", "不再使用", "替代",
)
SUPERPOWER_REF = re.compile(r"superpowers:([a-z0-9][a-z0-9-]*)", re.I)
BACKTICK_SMC_REF = re.compile(r"`(smc-[a-z0-9-]+)`", re.I)
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def tree(path: Path) -> dict[str, bytes]:
    if not path.is_dir():
        return {}
    return {
        p.relative_to(path).as_posix(): p.read_bytes()
        for p in path.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing frontmatter")
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise ValueError("unterminated frontmatter") from exc
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"\'')
    return values


def parse_lock(path: Path) -> tuple[list[str], dict[str, str]]:
    if not path.is_file():
        return [], {}
    selected: list[str] = []
    replacements: dict[str, str] = {}
    section = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if stripped == "skills:":
            section = "skills"
            continue
        if stripped == "replacements:":
            section = "replacements"
            continue
        if not stripped or stripped.startswith("#"):
            continue
        if section == "skills" and stripped.startswith("- "):
            selected.append(stripped[2:].strip())
        elif section == "replacements" and not stripped.startswith("-") and ":" in stripped:
            key, value = stripped.split(":", 1)
            if key.strip() and value.strip():
                replacements[key.strip()] = value.strip()
    return selected, replacements


def deprecation_context(line: str, heading: str = "") -> bool:
    lowered = (line + " " + heading).lower()
    return any(word.lower() in lowered for word in DEPRECATION_WORDS)


def resolve_local_link(source: Path, target: str) -> Path | None:
    target = target.strip().split("#", 1)[0]
    if "<" in target or ">" in target:
        return None
    if not target or target.startswith(("#", "/")) or re.match(r"^[a-z]+://", target, re.I):
        return None
    return (source.parent / target).resolve()


def should_validate_local_links(markdown: Path) -> bool:
    if markdown.is_relative_to(REFERENCES):
        return True
    try:
        return markdown.relative_to(SKILLS).parts[0] in GOVERNED_SKILLS
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-mirror", action="store_true", help="skip .agents <-> .cursor mirror check")
    args = parser.parse_args()
    errors: list[str] = []

    if not SKILLS.is_dir():
        errors.append("SKILL-000 .agents/skills missing")
        print("\n".join(errors), file=sys.stderr)
        return 1

    skill_names = {p.name for p in SKILLS.iterdir() if p.is_dir()}

    # Structure/frontmatter and all relative markdown links.
    for directory in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        skill = directory / "SKILL.md"
        if not skill.is_file():
            errors.append(f"SKILL-001 {directory.relative_to(ROOT)}: SKILL.md missing")
            continue
        try:
            fm = frontmatter(skill)
        except ValueError as exc:
            errors.append(f"SKILL-002 {skill.relative_to(ROOT)}: {exc}")
            continue
        if fm.get("name") != directory.name:
            errors.append(f"SKILL-002 {skill.relative_to(ROOT)}: name must equal directory")
        if not fm.get("description"):
            errors.append(f"SKILL-002 {skill.relative_to(ROOT)}: description missing")

    for markdown in sorted(list(SKILLS.rglob("*.md")) + list(REFERENCES.rglob("*.md"))):
        if not should_validate_local_links(markdown):
            continue
        text = markdown.read_text(encoding="utf-8")
        for target in MARKDOWN_LINK.findall(text):
            resolved = resolve_local_link(markdown, target)
            if resolved is not None and not resolved.exists():
                errors.append(
                    f"SKILL-003 {markdown.relative_to(ROOT)}: missing local reference {target}"
                )

    # Upstream lock must describe a set that actually exists. Replacements must resolve.
    selected, replacements = parse_lock(LOCK)
    if not selected:
        errors.append("SKILL-005 upstream.lock.yaml has no selected skills")
    if len(selected) != len(set(selected)):
        errors.append("SKILL-005 upstream.lock.yaml contains duplicate selected skills")
    for name in selected:
        if name not in skill_names:
            errors.append(f"SKILL-005 LOCK_SELECTED_SKILL_MISSING: {name}")
    for old, new in replacements.items():
        if new not in skill_names:
            errors.append(f"SKILL-005 LOCK_REPLACEMENT_TARGET_MISSING: {old} -> {new}")
        if old == new:
            errors.append(f"SKILL-005 LOCK_REPLACEMENT_SELF_REFERENCE: {old}")
        if old in skill_names:
            errors.append(f"SKILL-005 LOCK_REPLACED_SKILL_STILL_PRESENT: {old} -> {new}")

    # Governed planning has exactly one canonical planner and validator.
    for retired in BANNED_ACTIVE_SKILLS:
        if (SKILLS / retired).exists():
            errors.append(f"SKILL-007 RETIRED_SKILL_STILL_PRESENT: {retired}")
    for required in ("smc-plan-from-approved-prd-ponytail", "smc-plan-validator"):
        if required not in skill_names:
            errors.append(f"SKILL-007 GOVERNED_SKILL_MISSING: {required}")
    retired_rule = ROOT / ".cursor" / "rules" / "plan-codegen-minimal.mdc"
    if retired_rule.exists():
        errors.append("SKILL-007 RETIRED_CURSOR_RULE_STILL_PRESENT: .cursor/rules/plan-codegen-minimal.mdc")
    wrapper = ROOT / "tools" / "agent-skills" / "validate_plan.py"
    if wrapper.is_file() and "smc-plan-validator/scripts/validate_plan.py" not in wrapper.read_text(encoding="utf-8").replace("\\", "/"):
        errors.append("SKILL-007 PLAN_VALIDATOR_WRAPPER_DRIFT")

    # Explicit cross-skill references must resolve. Deprecated names may only appear in deprecation context.
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        current_heading = ""
        for line_no, line in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                current_heading = line.strip()
            refs = {m.group(1) for m in SUPERPOWER_REF.finditer(line)}
            refs.update(m.group(1) for m in BACKTICK_SMC_REF.finditer(line))
            for ref in sorted(refs):
                if ref in BANNED_ACTIVE_SKILLS:
                    if not deprecation_context(line, current_heading):
                        errors.append(
                            f"SKILL-006 ACTIVE_DEPRECATED_SKILL_REFERENCE: {skill_md.relative_to(ROOT)}:{line_no} -> {ref}"
                        )
                    continue
                if ref.startswith("smc-") and ref not in skill_names:
                    errors.append(
                        f"SKILL-006 CROSS_SKILL_REFERENCE_MISSING: {skill_md.relative_to(ROOT)}:{line_no} -> {ref}"
                    )

            # Catch plain/backticked legacy planner without matching the canonical -ponytail name.
            legacy = re.search(r"(?<![a-z0-9-])smc-plan-from-approved-prd(?!-ponytail)(?![a-z0-9-])", line, re.I)
            if legacy and not deprecation_context(line, current_heading):
                errors.append(
                    f"SKILL-006 ACTIVE_DEPRECATED_SKILL_REFERENCE: {skill_md.relative_to(ROOT)}:{line_no} -> smc-plan-from-approved-prd"
                )
            if re.search(r"(?<![a-z0-9-])writing-plans(?![a-z0-9-])", line, re.I) and not deprecation_context(line, current_heading):
                errors.append(
                    f"SKILL-006 ACTIVE_DEPRECATED_SKILL_REFERENCE: {skill_md.relative_to(ROOT)}:{line_no} -> writing-plans"
                )

    if not args.no_mirror:
        if tree(SKILLS) != tree(CURSOR_SKILLS) or tree(REFERENCES) != tree(CURSOR_REFERENCES):
            errors.append("SKILL-004 CURSOR_SKILL_MIRROR_DRIFT")

    if errors:
        print("\n".join(dict.fromkeys(errors)), file=sys.stderr)
        return 1
    print("Agent Skills validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
