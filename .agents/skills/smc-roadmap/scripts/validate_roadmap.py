#!/usr/bin/env python3
"""Compatibility entrypoint: current Roadmap validator is v1.1-compatible."""
from __future__ import annotations
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from validate_roadmap_v11 import *  # noqa: F401,F403
if __name__ == "__main__":
    raise SystemExit(main())
