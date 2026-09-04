from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import common
import commit_guard
import completion_audit
import delivery_state
import evidence
import execution_context
import plan_state
import review_record
import workspace


PLAN = r'''---
name: RM-01
 overview: invalid-indent-ignored
'''.replace(" overview", "overview") + r'''todos:
  - id: t1-change-app
    content: "T1 — change app [C01]"
    status: pending
isProject: false
plan_contract: smc.plan.v3.4
plan_id: RM-01
commit_policy: post_review
source_revision: RM-01@1.0
grounded_commit: deadbeef
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# RM-01 Test

## Approved PRD

[Approved PRD](../prd.md)

## Scope

- In: x

## Grounding Evidence Ledger

| Change ID | Target | Baseline State | Symbol / Entry Resolution | Caller / Callee Evidence | Existing Reuse Search | Result |
|---|---|---|---|---|---|---|
| C01 | app.py#main | exists | ok | ok | ok | ok |

## Requirement Coverage Ledger

| Requirement | Source | Obligation | Classification | Change IDs | Todo | Verification IDs | Evidence Class | Blocking |
|---|---|---|---|---|---|---|---|---|
| AC-01 | AC | works | BEHAVIOR | C01 | T1 | V01 | UNIT | yes |

## Lifecycle Closure Matrix

None

## Contract / Data Flow Closure Matrix

None

## Verification Ledger

| Verification ID | Level | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Blocking |
|---|---|---|---|---|---|---|---|
| V01 | UNIT | `python -c "print('ok')"` | exit 0 | regression | LOCAL_TRANSIENT | local | yes |

## Immediate Read

- `app.py#main`

## Triggered Read

- None

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | `app.py#main` | PROD | MODIFY | app.py#main | T1 | return 2 | app | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | app.py#main | minimal |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | `app.py#main` | - | - | yes |

## Integration Hotspots

None

## Generated Outputs Ledger

None

## Todo T1 — change app

**Owns Changes**
- C01

**Goal**
return 2

**Immediate anchors**
- `app.py#main`

**Changes**
- modify return

**Stop conditions**
- [ ] return is 2

**Triggered reads**
- None

## Verification

Run V01.

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | all proof fresh | V01 |
| IMPLEMENTED_NOT_PROVEN | proof pending | pending |
| BLOCKED | blocked | blocker |
| RETURN_PRD | conflict | PRD revision |
'''


class DeliveryToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)
        (self.root / ".gitignore").write_text(".smc/\n", encoding="utf-8")
        (self.root / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
        (self.root / ".cursor/plans").mkdir(parents=True)
        self.plan = self.root / ".cursor/plans/rm-01.plan.md"
        self.plan.write_text(PLAN, encoding="utf-8")
        (self.root / ".cursor/prd.md").write_text("---\nstatus: APPROVED\nreview_verdict: PASS\napproved_at: now\n---\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "base"], check=True)
        delivery_state.init(self.plan)

    def tearDown(self):
        self.tmp.cleanup()

    def init_workspace(self):
        return workspace.init(self.plan)

    def implement(self):
        plan_state.set_status(self.plan, "T1", "completed")
        (self.root / "app.py").write_text("def main():\n    return 2\n", encoding="utf-8")

    def prepare_full_proof(self):
        self.init_workspace()
        review_record.record("plan", self.plan, "PASS", "test-plan")
        self.implement()
        pre = completion_audit.precheck(self.plan)
        self.assertTrue(pre["pass"], pre)
        result = self.root / ".smc" / "audit.json"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(json.dumps({
            "total_items": 1, "done": 1, "changed": 0, "deferred": 0,
            "unverifiable": 0, "scope_drift": 0, "verdict": "PASS", "summary": "ok",
        }), encoding="utf-8")
        completion_audit.record(self.plan, result)
        review_record.record("implementation", self.plan, "PASS", "test-implementation")
        rc = evidence.run_cmd(self.plan, "V01", ["python", "-c", "print('ok')"])
        self.assertEqual(0, rc)

    def test_cursor_projection_valid(self):
        self.assertEqual([], plan_state.validate(self.plan))
        item = plan_state.cursor_todos(self.plan.read_text(encoding="utf-8"))[0]
        self.assertEqual("T1 — change app [C01]", item["content"])

    def test_cursor_projection_missing_fails_v34(self):
        self.plan.write_text(self.plan.read_text().replace('    content: "T1 — change app [C01]"\n', ""), encoding="utf-8")
        self.assertTrue(any(x.startswith("PLAN_CURSOR_TODO_CONTENT_MISSING") for x in plan_state.validate(self.plan)))

    def test_cursor_projection_drift_fails_v34(self):
        self.plan.write_text(self.plan.read_text().replace("change app [C01]", "old title [C01]"), encoding="utf-8")
        self.assertTrue(any(x.startswith("PLAN_CURSOR_TODO_CONTENT_DRIFT") for x in plan_state.validate(self.plan)))

    def test_set_status_preserves_content(self):
        before = plan_state.cursor_todos(self.plan.read_text())[0]["content"]
        plan_state.set_status(self.plan, "T1", "completed")
        item = plan_state.cursor_todos(self.plan.read_text())[0]
        self.assertEqual(before, item["content"])
        self.assertEqual("completed", item["status"])

    def test_semantic_hash_ignores_status_and_projection_only(self):
        a = common.semantic_plan_sha256(self.plan)
        plan_state.set_status(self.plan, "T1", "completed")
        b = common.semantic_plan_sha256(self.plan)
        self.assertEqual(a, b)
        text = self.plan.read_text().replace('content: "T1 — change app [C01]"', 'content: "display-only"')
        self.plan.write_text(text, encoding="utf-8")
        self.assertEqual(a, common.semantic_plan_sha256(self.plan))
        self.plan.write_text(self.plan.read_text().replace("## Todo T1 — change app", "## Todo T1 — changed semantics"), encoding="utf-8")
        self.assertNotEqual(a, common.semantic_plan_sha256(self.plan))

    def test_plan_review_survives_runtime_status(self):
        review_record.record("plan", self.plan, "PASS", "test")
        self.assertEqual("FRESH_PASS", review_record.latest_status(self.plan, "plan")[0])
        plan_state.set_status(self.plan, "T1", "completed")
        self.assertEqual("FRESH_PASS", review_record.latest_status(self.plan, "plan")[0])

    def test_workspace_refresh_cannot_hide_implementation_delta(self):
        workspace.init(self.plan)
        (self.root / "app.py").write_text("print('changed')\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DELIVERY_WORKSPACE_REFRESH_AFTER_MUTATION"):
            workspace.init(self.plan, refresh=True)

    def test_workspace_requires_explicit_init(self):
        with self.assertRaisesRegex(ValueError, "DELIVERY_WORKSPACE_BASELINE_MISSING"):
            workspace.inspect(self.plan)

    def test_workspace_allows_ambient_preexisting(self):
        (self.root / "notes.md").write_text("other task\n", encoding="utf-8")
        data = self.init_workspace()
        self.assertIn("notes.md", data["ambient_preexisting"])
        status = workspace.inspect(self.plan)
        self.assertTrue(status["pass"], status)

    def test_workspace_target_conflict_blocks(self):
        (self.root / "app.py").write_text("dirty before delivery\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DELIVERY_TARGET_CONFLICT"):
            self.init_workspace()

    def test_workspace_tooling_conflict_blocks(self):
        path = self.root / ".agents/skills/smc-plan-validator/SKILL.md"
        path.parent.mkdir(parents=True); path.write_text("dirty tooling\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DELIVERY_TOOLING_BLOCKED"):
            self.init_workspace()

    def test_workspace_ambient_mutation_blocks(self):
        (self.root / "notes.md").write_text("other task\n", encoding="utf-8")
        self.init_workspace()
        (self.root / "notes.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DELIVERY_AMBIENT_MUTATED"):
            workspace.assert_stable(self.plan)

    def test_workspace_scope_drift_blocks(self):
        self.init_workspace()
        (self.root / "surprise.py").write_text("x=1\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DELIVERY_SCOPE_DRIFT"):
            workspace.assert_stable(self.plan)

    def test_workspace_head_drift_blocks(self):
        self.init_workspace()
        # Commit an unrelated file from a clean state to move HEAD.
        (self.root / "other.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "other.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "other"], check=True)
        with self.assertRaisesRegex(ValueError, "DELIVERY_HEAD_DRIFT"):
            workspace.assert_stable(self.plan)

    def test_workspace_plan_semantic_drift_blocks(self):
        self.init_workspace()
        self.plan.write_text(self.plan.read_text().replace("- In: x", "- In: changed"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "DELIVERY_PLAN_SEMANTIC_DRIFT"):
            workspace.assert_stable(self.plan)

    def test_completion_precheck_with_ambient_dirty(self):
        (self.root / "notes.md").write_text("other task\n", encoding="utf-8")
        self.init_workspace(); self.implement()
        pre = completion_audit.precheck(self.plan)
        self.assertTrue(pre["pass"], pre)
        self.assertEqual(["app.py"], pre["changed_files"])

    def test_completion_precheck_rejects_unplanned_file(self):
        self.init_workspace(); self.implement()
        (self.root / "surprise.py").write_text("x=1\n", encoding="utf-8")
        pre = completion_audit.precheck(self.plan)
        self.assertFalse(pre["pass"])
        self.assertIn("surprise.py", pre["unexpected_changed_files"])

    def test_completion_audit_freshness_is_scope_bound(self):
        self.init_workspace(); self.implement()
        result = self.root / ".smc" / "audit.json"
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text(json.dumps({"total_items":1,"done":1,"changed":0,"deferred":0,"unverifiable":0,"scope_drift":0,"verdict":"PASS","summary":"ok"}), encoding="utf-8")
        completion_audit.record(self.plan, result)
        self.assertEqual("FRESH_PASS", completion_audit.check(self.plan)[0])
        (self.root / "app.py").write_text("def main():\n    return 9\n", encoding="utf-8")
        self.assertEqual("STALE", completion_audit.check(self.plan)[0])

    def test_implementation_review_scope_freshness(self):
        self.init_workspace(); self.implement()
        review_record.record("implementation", self.plan, "PASS", "test")
        self.assertEqual("FRESH_PASS", review_record.latest_status(self.plan, "implementation")[0])
        (self.root / "app.py").write_text("def main():\n    return 3\n", encoding="utf-8")
        self.assertEqual("STALE", review_record.latest_status(self.plan, "implementation")[0])

    def test_evidence_command_must_match_plan(self):
        self.init_workspace()
        rc = evidence.run_cmd(self.plan, "V01", ["python", "-c", "print('wrong')"])
        self.assertEqual(2, rc)
        self.assertEqual("MISSING", evidence.current_status(self.plan, "V01")[0])

    def test_evidence_scope_freshness(self):
        self.init_workspace(); self.implement()
        rc = evidence.run_cmd(self.plan, "V01", ["python", "-c", "print('ok')"])
        self.assertEqual(0, rc)
        self.assertEqual("FRESH", evidence.current_status(self.plan, "V01")[0])
        (self.root / "app.py").write_text("def main():\n    return 3\n", encoding="utf-8")
        self.assertEqual("STALE", evidence.current_status(self.plan, "V01")[0])

    def test_durable_manifest_is_scope_neutral_and_fresh(self):
        self.prepare_full_proof()
        before = workspace.scope_fingerprint(self.plan)
        path, payload = evidence.build_manifest(self.plan)
        self.assertTrue(path.is_file())
        self.assertEqual(before, workspace.scope_fingerprint(self.plan))
        self.assertEqual("FRESH", evidence.manifest_status(self.plan)[0])
        self.assertEqual(before, payload["scope_fingerprint"])

    def test_execution_context_resume_and_error_attempts(self):
        self.init_workspace()
        delivery_state.transition(self.plan, "PLAN_STATIC_VALID")
        delivery_state.transition(self.plan, "PLAN_REVIEW_CLEARED")
        delivery_state.transition(self.plan, "IMPLEMENTING")
        plan_state.set_status(self.plan, "T1", "in_progress")
        execution_context.append_event(self.plan, "TODO_STARTED", todo="T1", summary="begin")
        one = execution_context.append_event(self.plan, "ERROR", todo="T1", summary="same failure")
        two = execution_context.append_event(self.plan, "ERROR", todo="T1", summary="same   failure")
        self.assertEqual(1, one["attempt"]); self.assertEqual(2, two["attempt"])
        resume = execution_context.refresh(self.plan)
        self.assertEqual("T1", resume["active_todo"]["id"])
        self.assertIn("T1", resume["next_step"])

    def test_execution_context_last_event_is_chronological_across_agents(self):
        self.init_workspace()
        common.append_jsonl(execution_context.ledger_path(self.plan, "z-worker"), {
            "schema": "smc.execution.event.v1",
            "at": "2026-09-04T10:00:00.000001Z",
            "plan_id": "RM-01",
            "agent": "z-worker",
            "todo": "T1",
            "event": "PROGRESS",
            "summary": "older-z",
            "files": [],
            "scope_fingerprint": workspace.inspect(self.plan)["scope_fingerprint"],
        })
        common.append_jsonl(execution_context.ledger_path(self.plan, "a-worker"), {
            "schema": "smc.execution.event.v1",
            "at": "2026-09-04T10:00:00.000002Z",
            "plan_id": "RM-01",
            "agent": "a-worker",
            "todo": "T1",
            "event": "PROGRESS",
            "summary": "newer-a",
            "files": [],
            "scope_fingerprint": workspace.inspect(self.plan)["scope_fingerprint"],
        })
        resume = execution_context.refresh(self.plan)
        self.assertEqual("newer-a", resume["last_event"]["summary"])

    def test_continuation_gate_stall_guard(self):
        self.init_workspace(); plan_state.set_status(self.plan, "T1", "in_progress")
        execution_context.append_event(self.plan, "TODO_STARTED", todo="T1", summary="begin")
        first = execution_context.continuation_gate(self.plan, cap=3)
        self.assertEqual("CONTINUE", first["decision"])
        second = execution_context.continuation_gate(self.plan, cap=3)
        self.assertEqual("ALLOW_STOP", second["decision"])
        self.assertIn("no execution progress", second["reason"])

    def test_commit_guard_allows_stable_ambient_dirty(self):
        (self.root / "notes.md").write_text("other task\n", encoding="utf-8")
        self.prepare_full_proof()
        evidence.build_manifest(self.plan)
        with mock.patch.object(commit_guard, "validate", return_value=([], {
            "scope_fingerprint": workspace.inspect(self.plan)["scope_fingerprint"],
            "ambient_fingerprint": workspace.inspect(self.plan)["ambient_fingerprint"],
        })):
            self.assertEqual(0, commit_guard.capture(self.plan))
        # Stage only Plan-owned paths, never the ambient notes.md.
        subprocess.run(["git", "-C", str(self.root), "add", "app.py", ".cursor/plans/rm-01.plan.md", "docs_agent/evidence/RM-01-evidence.json"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "implement rm-01"], check=True)
        sha = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        self.assertEqual(0, commit_guard.verify(self.plan, sha))
        self.assertIn("notes.md", workspace.dirty_paths(self.root))

    def test_repo_relative_path_accepts_filesystem_alias(self):
        alias_root = self.root.parent / (self.root.name + "-SHORT")
        alias_plan = alias_root / ".cursor" / "plans" / "rm-01.plan.md"
        original_same = common.paths_same
        def fake_same(left, right):
            if Path(left) == alias_root and Path(right) == self.root:
                return True
            return original_same(left, right)
        with mock.patch.object(common, "paths_same", side_effect=fake_same):
            self.assertEqual(".cursor/plans/rm-01.plan.md", common.repo_relative_path(alias_plan, self.root))


if __name__ == "__main__":
    unittest.main()
