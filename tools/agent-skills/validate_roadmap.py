#!/usr/bin/env python3
from __future__ import annotations
import runpy
from pathlib import Path
TARGET=Path(__file__).resolve().parents[2]/'.agents/skills/smc-roadmap/scripts/validate_roadmap.py'
if not TARGET.is_file(): raise SystemExit(f'ROADMAP_VALIDATOR_NOT_FOUND: {TARGET}')
runpy.run_path(str(TARGET),run_name='__main__')
