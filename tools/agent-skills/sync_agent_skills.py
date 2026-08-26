#!/usr/bin/env python3
"""Sync the pinned upstream Agent Skills source into this repository."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / "tools" / "agent-skills" / "upstream.lock.yaml"
AGENT_SKILLS = ROOT / ".agents" / "skills"
AGENT_REFERENCES = ROOT / ".agents" / "references"
CURSOR_SKILLS = ROOT / ".cursor" / "skills"
CURSOR_REFERENCES = ROOT / ".cursor" / "references"
THIRD_PARTY = ROOT / "third_party" / "agent-skills"


def fail(message: str) -> None:
    raise ValueError(message)


def read_lock() -> tuple[str, list[str]]:
    lines = LOCK_PATH.read_text(encoding="utf-8").splitlines()
    commit = ""
    skills: list[str] = []
    in_skills = False
    for raw in lines:
        line = raw.strip()
        if line.startswith("commit:"):
            commit = line.split(":", 1)[1].strip()
        if line == "skills:":
            in_skills = True
            continue
        if in_skills and line.startswith("- "):
            skills.append(line[2:].strip())
    if len(commit) != 40 or not skills:
        fail(f"Invalid upstream lock: {LOCK_PATH}")
    return commit, skills


def git_commit(source_dir: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(source_dir), "rev-parse", "HEAD"], text=True
        ).strip()
    except subprocess.CalledProcessError as error:
        fail(f"Cannot resolve source Git commit: {error}")


def digest_tree(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        result[file.relative_to(path).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def expected_tree(source_dir: Path, skills: list[str], staging: Path) -> None:
    staged_skills = staging / "skills"
    staged_references = staging / "references"
    staged_third_party = staging / "third_party"
    staged_skills.mkdir(parents=True)
    staged_references.mkdir(parents=True)
    staged_third_party.mkdir(parents=True)

    for skill in skills:
        source = source_dir / "skills" / skill
        if not (source / "SKILL.md").is_file():
            fail(f"Pinned upstream source lacks skills/{skill}/SKILL.md")
        shutil.copytree(source, staged_skills / skill)
    shutil.copytree(source_dir / "references", staged_references / "upstream")
    shutil.copy2(source_dir / "LICENSE", staged_third_party / "LICENSE")
    (staged_third_party / "NOTICE.md").write_text(
        "This directory vendors selected content from addyosmani/agent-skills.\n"
        "Source: https://github.com/addyosmani/agent-skills\n"
        "Version: 0.6.7\n"
        "Commit: df1edb2e05487d0aa6d93c747141e0aed1187f25\n"
        "License: MIT; see LICENSE.\n",
        encoding="utf-8",
    )


def verify_expected(source_dir: Path, skills: list[str]) -> list[str]:
    differences: list[str] = []
    with tempfile.TemporaryDirectory(prefix="smc-agent-skills-") as temporary:
        staged = Path(temporary)
        expected_tree(source_dir, skills, staged)
        for source, destination, label in (
            (staged / "references" / "upstream", AGENT_REFERENCES / "upstream", ".agents/references/upstream"),
            (staged / "third_party", THIRD_PARTY, "third_party/agent-skills"),
        ):
            expected = digest_tree(source)
            actual = digest_tree(destination)
            for path in sorted(set(expected) | set(actual)):
                if expected.get(path) != actual.get(path):
                    differences.append(f"{label}: {path}")
        for skill in skills:
            expected = digest_tree(staged / "skills" / skill)
            actual = digest_tree(AGENT_SKILLS / skill)
            for path in sorted(set(expected) | set(actual)):
                if expected.get(path) != actual.get(path):
                    differences.append(f".agents/skills/{skill}: {path}")
        upstream_names = {item.name for item in (source_dir / "skills").iterdir() if item.is_dir()}
        for unexpected in sorted(upstream_names - set(skills)):
            if (AGENT_SKILLS / unexpected).exists():
                differences.append(f".agents/skills/{unexpected}: not selected by upstream lock")
    return differences


def apply(source_dir: Path, skills: list[str]) -> None:
    with tempfile.TemporaryDirectory(prefix="smc-agent-skills-") as temporary:
        staged = Path(temporary)
        expected_tree(source_dir, skills, staged)
        AGENT_SKILLS.mkdir(parents=True, exist_ok=True)
        for skill in skills:
            copy_tree(staged / "skills" / skill, AGENT_SKILLS / skill)
        upstream_names = {item.name for item in (source_dir / "skills").iterdir() if item.is_dir()}
        for stale in upstream_names - set(skills):
            target = AGENT_SKILLS / stale
            if target.exists():
                shutil.rmtree(target)
        copy_tree(staged / "references" / "upstream", AGENT_REFERENCES / "upstream")
        copy_tree(staged / "third_party", THIRD_PARTY)

    # .cursor is deliberately a generated projection of the canonical source.
    copy_tree(AGENT_SKILLS, CURSOR_SKILLS)
    copy_tree(AGENT_REFERENCES, CURSOR_REFERENCES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    commit, skills = read_lock()
    source_dir = args.source_dir.resolve()
    if git_commit(source_dir) != commit:
        fail(f"Source commit must be {commit}")

    if args.apply:
        apply(source_dir, skills)
        print("Agent Skills sync complete")
        return 0

    differences = verify_expected(source_dir, skills)
    if digest_tree(AGENT_SKILLS) != digest_tree(CURSOR_SKILLS):
        differences.append(".cursor/skills mirror drift")
    if digest_tree(AGENT_REFERENCES) != digest_tree(CURSOR_REFERENCES):
        differences.append(".cursor/references mirror drift")
    if differences:
        print("AGENT_SKILL_DRIFT", file=sys.stderr)
        print("\n".join(differences), file=sys.stderr)
        return 1
    print("Agent Skills sync check passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
