#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("validate_plan.py")
spec = importlib.util.spec_from_file_location("validate_plan", SCRIPT)
validator = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


PRD = """---
work_item_id: WI-TEST
version: 1.0.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-28T12:00:00+08:00
source_revision: AD-001@1.0.0/RM-01
grounded_commit: abcdef1234567
---

## Evidence Baseline
- Source: test fixture

## Current Capability Inventory
x

## Target End-State Inventory
y

## Change Classification
| Change ID | Capability | Action |
|---|---|---|
| C01 | Normalize | MODIFY |

## Acceptance Criteria
1. Normalized state is observable through the public API.

## State and Concurrency Invariants
1. A terminal run state is written by one owner.

## Definition of Done
1. The integration suite passes.
"""


def plan_text(*, conflict: bool = False, cycle: bool = False, parallel_second: bool = False) -> str:
    second_target = "src/a.py#normalize" if conflict else "src/b.py#use"
    t1_dep = "T2" if cycle else "-"
    t2_dep = "T1"
    parallel = "yes" if parallel_second else "no"
    return f"""---
plan_contract: smc.plan.v3.2
commit_policy: post_review
source_revision: WI-TEST@1.0.0
grounded_commit: abcdef1234567
---

# Test Implementation Plan

## Approved PRD

[Approved PRD](approved-prd.md)

## Scope

- In: normalize and consume
- Out: unrelated behavior

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | Normalized state is observable through the public API. | LIFECYCLE | C01<br>C02 | T1<br>T2 | V01 | INTEGRATION | yes |
| DOD-01 | DOD | The integration suite passes. | EVIDENCE | - | - | V02 | INTEGRATION | yes |

## Lifecycle Closure Matrix

| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |
|---|---|---|---|---|---|---|
| Run | AC-01 | submit | RUNNING | RunStateMachine | RunStateMachine | V01 |

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Output | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | INTEGRATION | python -m unittest tests.test_task | public state is normalized | invalid state rejected | reports/task.txt | LOCAL | yes |
| V02 | INTEGRATION | python -m unittest tests.test_task | suite passes | failure returns nonzero | reports/task.txt | LOCAL | yes |

## Immediate Read

- `src/a.py#normalize`

## Triggered Read

- If contract changes: `src/contract.py#Task`

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `src/a.py#normalize` | PROD | MODIFY | TaskNormalizer | T1 | normalize once | Normalize | no |
| C02 | `{second_target}` | PROD | MODIFY | TaskConsumer | T2 | consume normalized state | Normalize | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | `src/a.py#normalize` owns normalization | shared owner can fix behavior once |
| C02 | REUSE_EXISTING | `src/a.py#normalize` is the shared result | consumer only needs existing normalized result |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `src/a.py#normalize` | - | {t1_dep} | no |
| T2 | C02 | `{second_target}` | `src/a.py#normalize` | {t2_dep} | {parallel} |

## Integration Hotspots

None

## Todo T1 — normalize at owner

**Owns Changes**
- C01

**Goal**

Normalize state at the shared owner.

**Immediate anchors**
- `src/a.py#normalize`

**Changes**
- Update normalization logic once.

**Stop conditions**
- [ ] focused normalizer regression passes

**Triggered reads**
- None

## Todo T2 — consume normalized state

**Owns Changes**
- C02

**Goal**

Consume normalized state without another normalizer.

**Immediate anchors**
- `{second_target}`

**Changes**
- Reuse shared result.

**Stop conditions**
- [ ] focused consumer regression passes

**Triggered reads**
- None

## Verification

```bash
python -m unittest tests.test_task
```

- AC mapping: normalized state is produced once and consumed downstream.
- Expected: focused test passes.
- Negative/regression case: invalid state follows existing error path.

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all Coverage Ledger verification ids pass | V01,V02 reports exist |
| IMPLEMENTED_NOT_PROVEN | any blocking evidence is pending | pending output is recorded |
| BLOCKED | environment or dependency prevents proof | blocker is recorded |
| RETURN_PRD | owner or boundary conflicts with PRD | revision is requested |
"""


class ValidatorTests(unittest.TestCase):
    def write_case(self, td: str, content: str) -> Path:
        root = Path(td)
        (root / "approved-prd.md").write_text(PRD, encoding="utf-8")
        plan = root / "feature.plan.md"
        plan.write_text(content, encoding="utf-8")
        return plan

    def codes(self, errors) -> set[str]:
        return {e.code for e in errors}

    def test_valid_plan_passes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            plan = self.write_case(td, plan_text())
            errors = validator.validate_plan(plan)
            self.assertEqual(errors, [], "\n".join(e.line() for e in errors))

    def test_detects_duplicate_symbol_writer(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            plan = self.write_case(td, plan_text(conflict=True))
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_WRITE_CONFLICT", codes)

    def test_detects_dependency_cycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            plan = self.write_case(td, plan_text(cycle=True))
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_DEPENDENCY_CYCLE", codes)

    def test_parallel_safe_rejected_when_dependency_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            plan = self.write_case(td, plan_text(parallel_second=True))
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_PARALLEL_SAFE_INVALID", codes)

    def test_new_file_requires_justification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            text = plan_text().replace(
                "| C02 | `src/b.py#use` | PROD | MODIFY | TaskConsumer | T2 | consume normalized state | Normalize | no |",
                "| C02 | `src/b.py#use` | PROD | ADD | TaskConsumer | T2 | consume normalized state | Normalize | yes |",
            )
            plan = self.write_case(td, text)
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_NEW_FILE_WITHOUT_JUSTIFICATION", codes)

    def test_placeholder_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            text = plan_text().replace("Normalize state at the shared owner.", "<GROUND>")
            plan = self.write_case(td, text)
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_UNRESOLVED_PLACEHOLDER", codes)

    def test_rejects_missing_requirement_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            text = plan_text().replace(
                "| DOD-01 | DOD | The integration suite passes. | EVIDENCE | - | - | V02 | INTEGRATION | yes |\n",
                "",
            )
            plan = self.write_case(td, text)
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_REQUIREMENT_COVERAGE_MISSING", codes)

    def test_rejects_missing_lifecycle_closure_for_stateful_prd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            text = plan_text().replace(
                "## Lifecycle Closure Matrix\n\n| Journey | Requirements | Trigger | Nonterminal State | Success Writer | Failure / Cancel Writer | Evidence IDs |\n|---|---|---|---|---|---|---|\n| Run | AC-01 | submit | RUNNING | RunStateMachine | RunStateMachine | V01 |\n\n## Verification Ledger",
                "## Lifecycle Closure Matrix\n\nNone\n\n## Verification Ledger",
            )
            plan = self.write_case(td, text)
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_LIFECYCLE_CLOSURE_MISSING", codes)

    def test_rejects_non_blocking_verification_for_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            text = plan_text().replace(
                "| V02 | INTEGRATION | python -m unittest tests.test_task | suite passes | failure returns nonzero | reports/task.txt | LOCAL | yes |",
                "| V02 | INTEGRATION | python -m unittest tests.test_task | suite passes | failure returns nonzero | reports/task.txt | LOCAL | no |",
            )
            plan = self.write_case(td, text)
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_BLOCKING_VERIFICATION_REQUIRED", codes)

    def test_allows_inline_markdown_in_prd_obligation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            prd = PRD.replace(
                "Normalized state is observable through the public API.",
                "**Normalized** state is observable through the `public` API.",
            )
            root = Path(td)
            (root / "approved-prd.md").write_text(prd, encoding="utf-8")
            plan = root / "feature.plan.md"
            plan.write_text(plan_text(), encoding="utf-8")
            errors = validator.validate_plan(plan)
            self.assertEqual(errors, [], "\n".join(e.line() for e in errors))

    def test_allows_explicit_id_bullet_requirements_in_prd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            prd = PRD.replace(
                "## Acceptance Criteria\n1. Normalized state is observable through the public API.",
                "## Acceptance Criteria\n\n- **AC-01 / C01**：Normalized state is observable through the public API.",
            ).replace(
                "## Definition of Done\n1. The integration suite passes.",
                "## Definition of Done\n\n- **DOD-01**：The integration suite passes.",
            )
            root = Path(td)
            (root / "approved-prd.md").write_text(prd, encoding="utf-8")
            plan = root / "feature.plan.md"
            plan.write_text(plan_text(), encoding="utf-8")
            errors = validator.validate_plan(plan)
            self.assertEqual(errors, [], "\n".join(e.line() for e in errors))

    def test_explicit_id_bullet_extraction_uses_declared_ids(self) -> None:
        errors: list = []
        requirements = validator.extract_prd_requirements(
            "## Acceptance Criteria\n\n"
            "- **AC-01 / C01**：First obligation.\n"
            "- **AC-02 / C02**：Second obligation.\n\n"
            "## Definition of Done\n\n"
            "- **DOD-01**：Done obligation.\n",
            errors,
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            requirements,
            {
                "AC-01": "First obligation.",
                "AC-02": "Second obligation.",
                "DOD-01": "Done obligation.",
            },
        )

    def test_rejects_lifecycle_requirement_without_closure_row(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            text = plan_text().replace("| Run | AC-01 |", "| Run | DOD-01 |")
            plan = self.write_case(td, text)
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_LIFECYCLE_REQUIREMENT_UNCLOSED", codes)

    def test_rejects_completion_gate_missing_required_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            text = plan_text().replace("V01,V02 reports exist", "V01 reports exist")
            plan = self.write_case(td, text)
            codes = self.codes(validator.validate_plan(plan))
            self.assertIn("PLAN_COMPLETION_EVIDENCE_MISSING", codes)


if __name__ == "__main__":
    unittest.main()
