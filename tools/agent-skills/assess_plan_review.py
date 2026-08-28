#!/usr/bin/env python3
from __future__ import annotations
import runpy
from pathlib import Path
TARGET=Path(__file__).resolve().parents[2]/'.agents/skills/smc-plan-review/scripts/assess_plan_review.py'
if not TARGET.is_file(): raise SystemExit(f'PLAN_REVIEW_ASSESSOR_NOT_FOUND: {TARGET}')
runpy.run_path(str(TARGET),run_name='__main__')
