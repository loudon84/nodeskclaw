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

    def test_extracts_numbered_acceptance_criteria_and_definition_of_done(self) -> None:
        text = """## Acceptance Criteria

1. Create one run for a stable idempotency key.
2. Reject a conflicting request.

## Definition of Done

1. The integration suite passes.
2. Release evidence is recorded.
"""
        self.assertEqual(
            module.extract_requirements(text),
            [
                ("AC-01", "AC", "Create one run for a stable idempotency key."),
                ("AC-02", "AC", "Reject a conflicting request."),
                ("DOD-01", "DOD", "The integration suite passes."),
                ("DOD-02", "DOD", "Release evidence is recorded."),
            ],
        )

    def test_normalizes_inline_markdown_and_whitespace_in_requirements(self) -> None:
        text = """## Acceptance Criteria

1. **Create**  one `run`.

## Definition of Done

1. The suite passes.
"""
        self.assertEqual(
            module.extract_requirements(text)[0],
            ("AC-01", "AC", "Create one run."),
        )


if __name__ == "__main__":
    unittest.main()
