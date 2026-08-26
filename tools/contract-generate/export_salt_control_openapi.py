#!/usr/bin/env python3
"""Export Salt Control FastAPI OpenAPI document to contracts/salt-control-api/openapi.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SALT_SRC = ROOT / "services" / "salt-control" / "src"
OUT = ROOT / "contracts" / "salt-control-api" / "openapi.yaml"


def _sort_dict(value: object) -> object:
    if isinstance(value, dict):
        return {k: _sort_dict(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [_sort_dict(item) for item in value]
    return value


def main() -> int:
    sys.path.insert(0, str(SALT_SRC))
    from app import create_app  # noqa: WPS433

    schema = create_app().openapi()
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
    print(f"[export_salt_control_openapi] wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
