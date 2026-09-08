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
source_revision: TEST-0@1.0.0
grounded_commit: abcdef1234567
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
1. works

## Definition of Done
1. focused tests pass
"""


# @lat: [[decisions/agent-skills-governance#Plan Closure Contract#Wrapper Validator Fixtures]]
def valid_plan(
    prd_link: str = "PRD-test.md", row: str | None = None, target: str = "a.ts#symbol"
) -> str:
    change_row = row or "| C01 | `a.ts#symbol` | PROD | MODIFY | owner | T1 | final | config | no |"
    return f"""---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: TEST-1@1.0.0
grounded_commit: abcdef1234567
---
# Plan

## Approved PRD
[PRD]({prd_link})

## Scope
Implement config.

## Requirement Coverage Ledger
| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | works | BEHAVIOR | C01 | T1 | V01 | UNIT | yes |
| DOD-01 | DOD | focused tests pass | EVIDENCE | - | - | V01 | UNIT | yes |

## Lifecycle Closure Matrix
None

## Verification Ledger
| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | UNIT | python -m unittest tools.agent-skills.tests.test_validators | config owner is updated | missing justification is rejected | reports/validators.txt | LOCAL | yes |

## Immediate Read
- `a.ts#symbol`

## Triggered Read
- None.

## Change Matrix
| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
{change_row}

## Implementation Decisions
| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | `{target}` is the established owner | keep the existing owner and change only its behavior |

## Write Ownership Ledger
| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `{target}` | - | - | no |

## Integration Hotspots
None

## Todo T1 — update owner

**Owns Changes**
- C01

**Goal**

Update the existing owner.

**Immediate anchors**
- `{target}`

**Changes**
- Apply the scoped plan change.

**Stop conditions**
- [ ] focused test passes

**Triggered reads**
- None

## Verification
- focused tests

## Completion Gate
| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Coverage Ledger verification ids pass | V01 reports exist |
| IMPLEMENTED_NOT_PROVEN | any blocking evidence is pending | pending output is recorded |
| BLOCKED | environment or dependency prevents proof | blocker is recorded |
| RETURN_PRD | owner or boundary conflicts with PRD | revision is requested |
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
                    row="| C01 | `a.ts#newMethod` | PROD | ADD | owner | T1 | new method in owner | config | no |",
                    target="a.ts#newMethod",
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
                    row="| C01 | `new.ts` | PROD | ADD | none | T1 | new owner support | config | yes |",
                    target="new.ts",
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
                row="| C01 | `support.ts` | PROD | MODIFY | owner | T1 | split support under same owner | config | yes |",
                target="support.ts",
            ) + """
## New File Justification
| Change ID | File | Necessity | Owner Impact |
|---|---|---|---|
| C01 | `support.ts` | file split is required by the implementation boundary | existing owner remains authoritative |
"""
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
                    row="| C01 | `a.ts#old` | PROD | REPLACE | owner | T1 | replaced | config | no |",
                    target="a.ts#old",
                ),
                encoding="utf-8",
            )
            result = self.run_script(PLAN_VALIDATOR, plan)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PLAN_REPLACEMENT_WITHOUT_REMOVAL", result.stderr)


if __name__ == "__main__":
    unittest.main()
