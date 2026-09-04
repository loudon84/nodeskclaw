#!/usr/bin/env python3
"""Canonical wrapper for SMC Plan validators (v3.2 legacy + v3.3 current)."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY_TARGET = ROOT / '.agents/skills/smc-plan-validator/scripts/validate_plan.py'
V33_TARGET = ROOT / '.agents/skills/smc-plan-validator/scripts/validate_plan_v33.py'


def plan_contract(path: Path) -> str:
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        return ''
    if not lines or lines[0].strip() != '---':
        return ''
    for line in lines[1:]:
        if line.strip() == '---':
            break
        if line.startswith('plan_contract:'):
            return line.split(':', 1)[1].strip().strip('"\'')
    return ''


def main() -> None:
    # Keep the legacy canonical path in this wrapper for repository governance compatibility:
    # .agents/skills/smc-plan-validator/scripts/validate_plan.py
    candidate = next((Path(a) for a in sys.argv[1:] if not a.startswith('-')), None)
    contract = plan_contract(candidate.resolve()) if candidate and candidate.is_file() else ''
    target = V33_TARGET if contract == 'smc.plan.v3.3' else LEGACY_TARGET
    if not target.is_file():
        raise SystemExit(f'PLAN_VALIDATOR_NOT_FOUND: {target}')
    runpy.run_path(str(target), run_name='__main__')


if __name__ == '__main__':
    main()
