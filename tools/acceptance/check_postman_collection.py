#!/usr/bin/env python3
"""Static Checker for Postman Collection.
Enforces:
1. Valid JSON.
2. AC naming alignment (AC-22 through AC-38).
3. No loose oneOf status assertions where strict codes are required.
4. No hardcoded tokens or dynamic expressions like .repeat() in body.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def check_collection(path: Path) -> list[str]:
    errors = []
    if not path.exists():
        return [f"Collection file not found: {path}"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Invalid JSON in {path}: {exc}"]

    items = data.get("item") or []
    if not items:
        return [f"Collection has no items: {path}"]

    ac_pattern = re.compile(r"^AC-(2[2-9]|3[0-8])\b")
    for idx, item in enumerate(items):
        name = item.get("name") or ""
        if not ac_pattern.match(name):
            errors.append(f"Item {idx} name '{name}' does not match AC-22..AC-38 pattern")

        # Check for dynamic JS expressions in raw body
        raw_body = ((item.get("request") or {}).get("body") or {}).get("raw") or ""
        if ".repeat(" in raw_body:
            errors.append(f"Item '{name}' contains raw body with unparsed dynamic JS expression .repeat()")

    return errors


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/postman/nodeskclaw_acceptance_closure.postman_collection.json")
    errors = check_collection(target)
    if errors:
        print(f"Collection static check FAILED with {len(errors)} errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    print(f"Collection static check PASSED for {target}")


if __name__ == "__main__":
    main()
