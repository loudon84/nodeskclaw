#!/usr/bin/env python3
"""Export OPSI Control FastAPI OpenAPI document to contracts/opsi/openapi.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OPSI_SRC = ROOT / "services" / "opsi-control" / "src"
OUT = ROOT / "contracts" / "opsi" / "openapi.yaml"


def _sort_dict(value: object) -> object:
    if isinstance(value, dict):
        return {k: _sort_dict(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_sort_dict(item) for item in value]
    return value


def main() -> int:
    sys.path.insert(0, str(OPSI_SRC))
    from app import build_test_state, create_app

    schema = create_app(build_test_state()).openapi()
    schema = _sort_dict(schema)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        schema,
        sort_keys=True,
        allow_unicode=True,
        default_flow_style=False,
        width=120,
    )
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"[export_opsi_control_openapi] wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
