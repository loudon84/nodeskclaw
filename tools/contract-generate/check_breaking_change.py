#!/usr/bin/env python3
"""OpenAPI breaking-change check against PR base (or CONTRACT_BASE_REF / origin/main).

PRD v1.1 §19: compare with PR Base, not only current HEAD tip of the same commit.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "contracts" / "runtime-api" / "openapi.yaml"
REL = OPENAPI.relative_to(ROOT).as_posix()


def _load_yaml(text: str) -> dict:
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("openapi root must be an object")
    return data


def _ops(doc: dict) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for path, item in (doc.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in item:
            if method.startswith("x-") or not isinstance(item.get(method), dict):
                continue
            out.add((method.lower(), path))
    return out


def _resolve_base_ref() -> str:
    explicit = (os.environ.get("CONTRACT_BASE_REF") or "").strip()
    if explicit:
        return explicit
    github_base = (os.environ.get("GITHUB_BASE_REF") or "").strip()
    if github_base:
        return f"origin/{github_base}"
    return "origin/main"


def _show_at(ref: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{REL}"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def main() -> int:
    if not OPENAPI.exists():
        print("openapi.yaml missing; run contracts:generate first", file=sys.stderr)
        return 1

    current = _load_yaml(OPENAPI.read_text(encoding="utf-8"))
    base_ref = _resolve_base_ref()
    prev_text = _show_at(base_ref)
    if prev_text is None:
        prev_text = _show_at("HEAD")
        if prev_text is None:
            print(f"[breaking_change_check] no previous openapi at {base_ref} or HEAD — skip")
            return 0
        print(f"[breaking_change_check] base {base_ref} unavailable; falling back to HEAD")

    previous = _load_yaml(prev_text)
    removed = _ops(previous) - _ops(current)
    if removed:
        print("BREAKING: removed endpoints:", file=sys.stderr)
        for method, path in sorted(removed):
            print(f"  {method.upper()} {path}", file=sys.stderr)
        print("Bump contracts/version.json major and add ADR.", file=sys.stderr)
        return 1

    print(f"[breaking_change_check] no removed endpoints (base={base_ref})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
