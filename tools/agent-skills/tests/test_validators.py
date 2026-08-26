from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PRD_VALIDATOR = ROOT / "tools" / "agent-skills" / "validate_prd.py"
PLAN_VALIDATOR = ROOT / "tools" / "agent-skills" / "validate_plan.py"


VALID_PRD = """---
work_item_id: TEST-1
version: v1
status: APPROVED
target_branch: work/prd-3.0
review_verdict: PASS
approved_at: 2026-08-24T14:00:00+08:00
---
# Test

## Current Capability Inventory
| Capability | Existing Owner | Current Behaviour |
|---|---|---|
| config | owner | current |

## Target End-State Inventory
| Capability | Production Owner | Allowed Implementations |
|---|---|---:|
| config | owner | 1 |

## Change Classification
| Item | Action | Target State |
|---|---|---|
| config | MODIFY | final |

## Acceptance Criteria
- [ ] works
"""


def valid_plan(prd_link: str = "PRD-test.md", row: str | None = None) -> str:
    change_row = row or "| a.ts#symbol | MODIFY | owner | final | config | no |"
    return f"""# Plan

## Approved PRD
[PRD]({prd_link})

## Scope
Implement config.

## Immediate Read
- `a.ts#symbol`

## Triggered Read
- None.

## Change Matrix
| File / Symbol | Action | Existing Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|
{change_row}

## Implementation Decisions
- Reuse current owner.

## Verification
- focused tests
"""


class ValidatorsTest(unittest.TestCase):
    def run_script(
        self, script: Path, target: Path, *extra: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), str(target), *extra],
            text=True,
            capture_output=True,
        )

    def test_prd_replace_requires_removal_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "PRD-test.md"
            path.write_text(VALID_PRD.replace("MODIFY", "REPLACE"), encoding="utf-8")
            result = self.run_script(PRD_VALIDATOR, path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PRD_REPLACEMENT_WITHOUT_REMOVAL", result.stderr)

    def test_prd_keywords_do_not_imply_compatibility_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "PRD-test.md"
            text = VALID_PRD + "\nNo fallback, legacy adapter, compat alias is introduced.\n"
            path.write_text(text, encoding="utf-8")
            result = self.run_script(PRD_VALIDATOR, path)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_approved_prd_cannot_keep_draft_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "PRD-test-DRAFT.md"
            path.write_text(VALID_PRD, encoding="utf-8")
            result = self.run_script(PRD_VALIDATOR, path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PRD_APPROVED_FILENAME_HAS_DRAFT", result.stderr)

    def test_approved_prd_requires_pass_and_approved_at(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "PRD-test.md"
            text = VALID_PRD.replace("review_verdict: PASS", "review_verdict:")
            path.write_text(text, encoding="utf-8")
            result = self.run_script(PRD_VALIDATOR, path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("APPROVED review_verdict must be PASS", result.stderr)

    def test_review_required_prd_cannot_carry_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "PRD-test.md"
            text = (
                VALID_PRD
                .replace("status: APPROVED", "status: REVIEW_REQUIRED")
                .replace("approved_at: 2026-08-24T14:00:00+08:00", "approved_at:")
            )
            path.write_text(text, encoding="utf-8")
            result = self.run_script(PRD_VALIDATOR, path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REVIEW_REQUIRED review_verdict must be empty", result.stderr)

    def test_plan_add_in_existing_file_needs_no_new_file_justification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            prd = base / "PRD-test.md"
            plan = base / "test.plan.md"
            prd.write_text(VALID_PRD, encoding="utf-8")
            plan.write_text(
                valid_plan(
                    row="| a.ts#newMethod | ADD | owner | new method in owner | config | no |"
                ),
                encoding="utf-8",
            )
            result = self.run_script(PLAN_VALIDATOR, plan)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_plan_new_file_requires_justification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            prd = base / "PRD-test.md"
            plan = base / "test.plan.md"
            prd.write_text(VALID_PRD, encoding="utf-8")
            plan.write_text(
                valid_plan(
                    row="| new.ts | ADD | none | new owner support | config | yes |"
                ),
                encoding="utf-8",
            )
            result = self.run_script(PLAN_VALIDATOR, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PLAN_NEW_FILE_WITHOUT_JUSTIFICATION", result.stderr)


    def test_plan_modify_can_add_new_file_with_justification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            prd = base / "PRD-test.md"
            plan = base / "test.plan.md"
            prd.write_text(VALID_PRD, encoding="utf-8")
            text = valid_plan(
                row="| support.ts | MODIFY | owner | split support under same owner | config | yes |"
            ) + "\n## New File Justification\n- `support.ts`: existing owner remains authoritative; file split is required by implementation boundary.\n"
            plan.write_text(text, encoding="utf-8")
            result = self.run_script(PLAN_VALIDATOR, plan)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_plan_replace_requires_remove_row(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            prd = base / "PRD-test.md"
            plan = base / "test.plan.md"
            prd.write_text(VALID_PRD, encoding="utf-8")
            plan.write_text(
                valid_plan(
                    row="| a.ts#old | REPLACE | owner | replaced | config | no |"
                ),
                encoding="utf-8",
            )
            result = self.run_script(PLAN_VALIDATOR, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PLAN_REPLACEMENT_WITHOUT_REMOVAL", result.stderr)


if __name__ == "__main__":
    unittest.main()
