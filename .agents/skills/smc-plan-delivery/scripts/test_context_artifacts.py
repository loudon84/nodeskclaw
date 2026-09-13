#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from execution_context import build_task_review_package, create_task_brief, ensure_report_path


PLAN = """---
plan_id: context-artifact-test
plan_contract: smc.plan.v3.5
todos:
  - id: t1-change-a
    content: "T1 — change a [C01]"
    status: pending
  - id: t2-change-b
    content: "T2 — change b [C02]"
    status: pending
---
# Context artifact test

## Global Constraints

- Do not touch files outside the current Todo Writes.

## Todo T1 — change a

**Owns Changes**
- C01

**Writes**
- `src/a.py#run`

**Reads**
- `src/shared.py`

## Todo T2 — change b

**Owns Changes**
- C02

**Writes**
- `src/b.py#run`
"""


class ContextArtifactTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "SMC Test"], check=True)
        (self.root / "src").mkdir()
        (self.root / "src/a.py").write_text("def run():\n    return 1\n", encoding="utf-8")
        (self.root / "src/b.py").write_text("def run():\n    return 2\n", encoding="utf-8")
        (self.root / "src/shared.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.plan = self.root / "demo.plan.md"
        self.plan.write_text(PLAN, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "base"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    # @lat: [[ges-tests#GES Tests#Runtime Cost Optimization#Creates a todo-scoped brief]]
    def test_brief_contains_current_todo_only(self):
        path = create_task_brief(self.plan, "T1")
        text = path.read_text(encoding="utf-8")
        self.assertIn("## Todo T1", text)
        self.assertNotIn("## Todo T2", text)
        self.assertIn("Global Constraints", text)

    # @lat: [[ges-tests#GES Tests#Runtime Cost Optimization#Creates a plan-scoped report path]]
    def test_report_path_is_plan_scoped(self):
        path = ensure_report_path(self.plan, "T1")
        self.assertEqual(path.name, "T1.md")
        self.assertIn(".smc/runs/context-artifact-test/reports", path.as_posix())

    # @lat: [[ges-tests#GES Tests#Runtime Cost Optimization#Scopes task review to declared writes]]
    def test_review_package_is_write_scoped(self):
        (self.root / "src/a.py").write_text("def run():\n    return 10\n", encoding="utf-8")
        (self.root / "src/b.py").write_text("def run():\n    return 20\n", encoding="utf-8")
        path = build_task_review_package(self.plan, "T1")
        text = path.read_text(encoding="utf-8")
        self.assertIn("src/a.py", text)
        self.assertIn("return 10", text)
        self.assertNotIn("return 20", text)


if __name__ == "__main__":
    unittest.main()
