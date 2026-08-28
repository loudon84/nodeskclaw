#!/usr/bin/env python3
"""Canonical wrapper for smc-plan-validator."""
from __future__ import annotations
import runpy
from pathlib import Path
TARGET=Path(__file__).resolve().parents[2]/'.agents/skills/smc-plan-validator/scripts/validate_plan.py'
if not TARGET.is_file(): raise SystemExit(f'PLAN_VALIDATOR_NOT_FOUND: {TARGET}')
runpy.run_path(str(TARGET),run_name='__main__')
