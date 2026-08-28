#!/usr/bin/env python3
from __future__ import annotations
import runpy
from pathlib import Path
TARGET=Path(__file__).resolve().parents[2]/'.agents/skills/smc-architecture-decision/scripts/validate_architecture.py'
if not TARGET.is_file(): raise SystemExit(f'ARCH_VALIDATOR_NOT_FOUND: {TARGET}')
runpy.run_path(str(TARGET),run_name='__main__')
