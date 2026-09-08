#!/usr/bin/env python3
from __future__ import annotations
import subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
raise SystemExit(subprocess.call([sys.executable,"-m","unittest","discover","-s",str(HERE/"tests"),"-p","test_*.py","-v"]))
