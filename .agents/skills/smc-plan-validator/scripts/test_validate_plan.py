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
---

## Current Capability Inventory
x

## Target End-State Inventory
y

## Change Classification
| Capability | Action |
|---|---|
| Normalize | MODIFY |

## Acceptance Criteria
- works
"""


def plan_text(*, conflict: bool = False, cycle: bool = False, parallel_second: bool = False) -> str:
    second_target = "src/a.py#normalize" if conflict else "src/b.py#use"
    t1_dep = "T2" if cycle else "-"
    t2_dep = "T1"
    parallel = "yes" if parallel_second else "no"
    return f"""# Test Implementation Plan

## Approved PRD

[Approved PRD](approved-prd.md)

## Scope

- In: normalize and consume
- Out: unrelated behavior

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


if __name__ == "__main__":
    unittest.main()
