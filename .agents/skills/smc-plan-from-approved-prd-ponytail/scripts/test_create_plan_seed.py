#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("create_plan_seed.py")
spec = importlib.util.spec_from_file_location("create_plan_seed", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class CreatePlanSeedTests(unittest.TestCase):
    def test_extracts_non_keep_changes_and_stable_ids(self) -> None:
        text = """---
work_item_id: WI-1
status: APPROVED
review_verdict: PASS
approved_at: 2026-08-28T12:00:00+08:00
---
## Change Classification

| Capability | Action | Owner |
|---|---|---|
| Existing thing | KEEP | A |
| Add health | ADD | A |
| Replace parser | REPLACE | B |
"""
        changes = module.extract_changes(text)
        self.assertEqual(changes, [("C01", "ADD", "Add health"), ("C02", "REPLACE", "Replace parser")])

    def test_rejects_non_approved_prd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "x.md"
            p.write_text("""---
status: DRAFT
review_verdict:
approved_at:
---
## Change Classification
| Capability | Action |
|---|---|
| X | ADD |
""", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PRD_NOT_APPROVED"):
                module.validate_prd_state(p, p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
