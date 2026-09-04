from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import common
import plan_state


LEGACY = '''---
name: legacy
overview: legacy plan
todos:
  - id: t1-legacy
    status: completed
    customCursorField: keep-me
isProject: false
plan_contract: smc.plan.v3.3
plan_id: RM-LEGACY
commit_policy: post_review
source_revision: RM-LEGACY@1.0
grounded_commit: deadbeef
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# Legacy

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | UNIT | `python -c "print(1)"` | ok | no | LOCAL_TRANSIENT | local | yes |

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `a.py#x` | PROD | MODIFY | x | T1 | y | x | no |

## Todo T1 — legacy display

**Owns Changes**
- C01

**Goal**
change
'''


class PlanV34Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".cursor/plans").mkdir(parents=True)
        self.plan = self.root / ".cursor/plans/legacy.plan.md"
        self.plan.write_text(LEGACY, encoding="utf-8")

    def tearDown(self): self.tmp.cleanup()

    def test_v33_missing_content_is_warning_not_error(self):
        self.assertEqual([], plan_state.validate(self.plan))
        warnings = plan_state.legacy_content_warnings(self.plan)
        self.assertEqual(["PLAN_CURSOR_TODO_CONTENT_LEGACY_WARNING: T1"], warnings)

    def test_sync_content_backfills_without_status_change(self):
        before = common.semantic_plan_sha256(self.plan)
        changed = plan_state.sync_content(self.plan)
        self.assertEqual(1, changed)
        item = plan_state.cursor_todos(self.plan.read_text())[0]
        self.assertEqual("completed", item["status"])
        self.assertEqual("T1 — legacy display [C01]", item["content"])
        self.assertIn("customCursorField: keep-me", self.plan.read_text())
        self.assertEqual(before, common.semantic_plan_sha256(self.plan))

    def test_migration_v33_to_v34_preserves_status_unknown_fields(self):
        script = HERE / "migrate_legacy_plan.py"
        result = subprocess.run([sys.executable, str(script), str(self.plan), "--in-place"], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        text = self.plan.read_text()
        self.assertIn("plan_contract: smc.plan.v3.4", text)
        self.assertIn("content: \"T1 — legacy display [C01]\"", text)
        self.assertIn("status: completed", text)
        self.assertIn("customCursorField: keep-me", text)
        self.assertEqual([], plan_state.validate(self.plan))

    def test_seed_generator_emits_v34_content(self):
        prd = self.root / "prd.md"
        prd.write_text('''---
status: APPROVED
review_verdict: PASS
approved_at: now
work_item_id: RM-02
version: 1.0
source_revision: RM-02@1.0
grounded_commit: abcdef
---

## Change Classification

| Change ID | Capability | Action |
|---|---|---|
| C01 | Public routing | MODIFY |

## Acceptance Criteria

1. route works

## Definition of Done

1. tests pass
''', encoding="utf-8")
        out = self.root / ".cursor/plans/rm-02.plan.md"
        script = HERE.parents[1] / "smc-plan-from-approved-prd-ponytail" / "scripts" / "create_plan_seed.py"
        result = subprocess.run([sys.executable, str(script), str(prd), str(out), "--plan-id", "RM-02"], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        text = out.read_text()
        self.assertIn("plan_contract: smc.plan.v3.4", text)
        self.assertRegex(text, r'content: "T1 .+Public routing \[C01\]"')
        self.assertEqual([], plan_state.validate(out))

    def test_content_quoting_handles_yaml_sensitive_title(self):
        text = LEGACY.replace("plan_contract: smc.plan.v3.3", "plan_contract: smc.plan.v3.4")
        text = text.replace("## Todo T1 — legacy display", '## Todo T1 — route: #public "quoted"')
        self.plan.write_text(text, encoding="utf-8")
        plan_state.sync_content(self.plan)
        raw = self.plan.read_text()
        self.assertIn('content: "T1 — route: #public \\"quoted\\" [C01]"', raw)
        self.assertEqual([], plan_state.validate(self.plan))


if __name__ == "__main__": unittest.main()
