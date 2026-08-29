#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("create_plan_seed.py")
spec = importlib.util.spec_from_file_location("create_plan_seed", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class CreatePlanSeedTests(unittest.TestCase):
    def test_worktree_fingerprint_is_clean_when_no_diff_exists(self) -> None:
        self.assertEqual(module.fingerprint_worktree(b"", b"", b""), "clean")

    def test_worktree_fingerprint_changes_with_diff(self) -> None:
        first = module.fingerprint_worktree(b" M a.py\0", b"diff-a", b"")
        second = module.fingerprint_worktree(b" M a.py\0", b"diff-b", b"")
        self.assertRegex(first, r"^sha256:[0-9a-f]{64}$")
        self.assertNotEqual(first, second)

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

    def test_extracts_explicit_id_bullet_requirements(self) -> None:
        text = """## Acceptance Criteria

- **AC-01 / C01**：Create one run for a stable idempotency key.
- **AC-02 / C01**：Reject a conflicting request.

## Definition of Done

- **DOD-01**：The integration suite passes.
"""
        self.assertEqual(
            module.extract_requirements(text),
            [
                ("AC-01", "AC", "Create one run for a stable idempotency key."),
                ("AC-02", "AC", "Reject a conflicting request."),
                ("DOD-01", "DOD", "The integration suite passes."),
            ],
        )

    def test_force_requires_explicit_revise_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prd = root / "approved.md"
            out = root / "existing.plan.md"
            prd.write_text(self._approved_prd(), encoding="utf-8")
            out.write_text("existing", encoding="utf-8")
            stderr = io.StringIO()
            with patch("sys.argv", [str(SCRIPT), str(prd), str(out), "--force"]), redirect_stderr(stderr):
                result = module.main()
            self.assertEqual(result, 2)
            self.assertIn("PLAN_REVISION_NOT_AUTHORIZED", stderr.getvalue())
            self.assertEqual(out.read_text(encoding="utf-8"), "existing")

    def test_revise_mode_requires_existing_output_and_force(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prd = root / "approved.md"
            out = root / "missing.plan.md"
            prd.write_text(self._approved_prd(), encoding="utf-8")
            stderr = io.StringIO()
            argv = [str(SCRIPT), str(prd), str(out), "--mode", "revise", "--force"]
            with patch("sys.argv", argv), redirect_stderr(stderr):
                result = module.main()
            self.assertEqual(result, 2)
            self.assertIn("PLAN_NOT_FOUND_FOR_REVISION", stderr.getvalue())

    def test_seed_contains_integrity_ledgers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prd = root / "approved.md"
            out = root / "seed.plan.md"
            prd.write_text(self._approved_prd(), encoding="utf-8")
            text = prd.read_text(encoding="utf-8")
            frontmatter = module.validate_prd_state(prd, text)
            rendered = module.render(
                prd,
                out,
                frontmatter,
                module.extract_changes(text),
                module.extract_requirements(text),
            )
            self.assertIn("## Grounding Evidence Ledger", rendered)
            self.assertIn("## Contract / Data Flow Closure Matrix", rendered)
            self.assertIn("## Generated Outputs Ledger", rendered)

    @staticmethod
    def _approved_prd() -> str:
        return """---
status: APPROVED
review_verdict: PASS
approved_at: 2026-08-29T12:00:00+08:00
---
## Change Classification
| Capability | Action |
|---|---|
| Add health | ADD |

## Acceptance Criteria
1. Health is observable.

## Definition of Done
1. Verification evidence is retained.
"""


if __name__ == "__main__":
    unittest.main()
