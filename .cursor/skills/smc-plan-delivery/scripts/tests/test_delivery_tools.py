from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import common
import completion_audit
import evidence
import plan_state
import review_record
from working_tree_fingerprint import fingerprint

PLAN='''---
name: RM-01 Test
overview: test plan
todos:
  - id: t1-change-app
    status: pending
isProject: false
plan_contract: smc.plan.v3.3
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

- app.py#main

## Triggered Read

- None

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
| C01 | app.py#main | PROD | MODIFY | main | T1 | changed | test | no |

## Implementation Decisions

| Change ID | Strategy | Root-Cause / Reuse Evidence | Why This Is Minimum |
|---|---|---|---|
| C01 | MODIFY_EXISTING | existing main | one edit |

## Write Ownership Ledger

| Todo | Owns Changes | Writes | Reads | Depends On | Parallel Safe |
|---|---|---|---|---|---|
| T1 | C01 | app.py#main | - | - | no |

## Integration Hotspots

None

## Generated Outputs Ledger

None

## Todo T1 — change app

**Owns Changes**
- C01

**Goal**
change app

**Immediate anchors**
- app.py#main

**Changes**
- edit

**Stop conditions**
- [ ] focused test pass

**Triggered reads**
- None

## Verification

run V01

## Completion Gate

| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | proof gates pass | V01 via SMC evidence ledger |
| IMPLEMENTED_NOT_PROVEN | implementation only | pending V01 |
| BLOCKED | blocker | blocker record |
| RETURN_PRD | contract conflict | PRD revision |
'''

class DeliveryToolsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        subprocess.run(["git","init","-q",str(self.root)],check=True)
        subprocess.run(["git","-C",str(self.root),"config","user.email","test@example.com"],check=True)
        subprocess.run(["git","-C",str(self.root),"config","user.name","Test"],check=True)
        (self.root/".gitignore").write_text(".smc/\n",encoding="utf-8")
        (self.root/"app.py").write_text("def main():\n    return 1\n",encoding="utf-8")
        (self.root/".cursor/plans").mkdir(parents=True)
        self.plan=self.root/".cursor/plans/rm-01.plan.md";self.plan.write_text(PLAN,encoding="utf-8")
        (self.root/".cursor/prd.md").write_text("---\nstatus: APPROVED\nreview_verdict: PASS\napproved_at: now\n---\n",encoding="utf-8")
        subprocess.run(["git","-C",str(self.root),"add","."],check=True);subprocess.run(["git","-C",str(self.root),"commit","-qm","base"],check=True)
    def tearDown(self):self.tmp.cleanup()

    def _prepare_full_proof(self):
        plan_state.set_status(self.plan,"T1","completed")
        (self.root/"app.py").write_text("def main():\n    return 2\n",encoding="utf-8")
        review_record.record("plan",self.plan,"PASS","test-plan")
        base=subprocess.run(["git","-C",str(self.root),"rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
        pre=completion_audit.precheck(self.plan,base)
        self.assertTrue(pre["pass"],pre)
        result=self.root/"audit.json"
        result.write_text(json.dumps({"total_items":1,"done":1,"changed":0,"deferred":0,"unverifiable":0,"scope_drift":0,"verdict":"PASS","summary":"ok"}),encoding="utf-8")
        completion_audit.record(self.plan,result)
        review_record.record("implementation",self.plan,"PASS","test-implementation")
        rc=evidence.run_cmd(self.plan,"V01",["python","-c","print('ok')"])
        self.assertEqual(0,rc)

    def test_legacy_plan_migration_to_v33(self):
        legacy=PLAN
        # Strip Cursor metadata and v3.3 plan id, then restore v3.2 evidence shape.
        legacy=re.sub(r"name:.*?working_tree_fingerprint: clean\n", "plan_contract: smc.plan.v3.2\ncommit_policy: post_review\nsource_revision: RM-01@1.0\ngrounded_commit: deadbeef\ngrounding_source: committed_baseline\nworking_tree_fingerprint: clean\n", legacy, count=1, flags=re.S)
        legacy=legacy.replace("Evidence Policy", "Evidence Output").replace("LOCAL_TRANSIENT", "artifacts/v01.xml")
        self.plan.write_text(legacy,encoding="utf-8")
        script=HERE/"migrate_legacy_plan.py"
        r=subprocess.run([sys.executable,str(script),str(self.plan),"--in-place"],capture_output=True,text=True)
        self.assertEqual(0,r.returncode,r.stdout+r.stderr)
        migrated=self.plan.read_text(encoding="utf-8")
        self.assertIn("plan_contract: smc.plan.v3.3",migrated)
        self.assertIn("plan_id: RM-01",migrated)
        self.assertIn("Evidence Policy",migrated)
        self.assertIn("LOCAL_TRANSIENT",migrated)
        self.assertEqual([],plan_state.validate(self.plan))


    def test_durable_manifest_is_fingerprint_neutral_and_fresh(self):
        self._prepare_full_proof()
        before=fingerprint(self.root)
        path,payload=evidence.build_manifest(self.plan)
        self.assertTrue(path.is_file())
        self.assertEqual(before,fingerprint(self.root))
        self.assertEqual("FRESH",evidence.manifest_status(self.plan)[0])
        self.assertEqual("RM-01",payload["plan_id"])
        self.assertEqual(before,payload["wtree_fingerprint"])
        (self.root/"app.py").write_text("def main():\n    return 9\n",encoding="utf-8")
        self.assertEqual("STALE",evidence.manifest_status(self.plan)[0])

    def test_docs_agent_evidence_is_excluded_from_content_fingerprint(self):
        before=fingerprint(self.root)
        p=self.root/"docs_agent/evidence/manual.json"
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text("{}\n",encoding="utf-8")
        self.assertEqual(before,fingerprint(self.root))

    def test_repo_relative_path_accepts_filesystem_alias(self):
        # Simulate Windows 8.3/long-name identity mismatch deterministically.
        # The alias root is lexically different from the Git root, but the
        # filesystem identity layer says they are the same directory.
        alias_root = self.root.parent / (self.root.name + "-SHORT")
        alias_plan = alias_root / ".cursor" / "plans" / "rm-01.plan.md"
        original_same = common.paths_same

        def fake_same(left, right):
            if Path(left) == alias_root and Path(right) == self.root:
                return True
            return original_same(left, right)

        with mock.patch.object(common, "paths_same", side_effect=fake_same):
            self.assertEqual(".cursor/plans/rm-01.plan.md", common.repo_relative_path(alias_plan, self.root))

    def test_completion_precheck_accepts_repo_root_path_alias(self):
        # Reproduce the production failure shape: plan keeps one spelling while
        # git root is returned through an equivalent, lexically different path.
        plan_state.set_status(self.plan,"T1","completed")
        (self.root/"app.py").write_text("def main():\n    return 2\n",encoding="utf-8")
        base=subprocess.run(["git","-C",str(self.root),"rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
        alias_root = self.root.parent / (self.root.name + "-LONG")
        original_find = completion_audit.find_repo_root
        original_same = common.paths_same

        def fake_same(left, right):
            if Path(left) == self.root and Path(right) == alias_root:
                return True
            return original_same(left, right)

        with mock.patch.object(completion_audit, "find_repo_root", return_value=alias_root), \
             mock.patch.object(common, "paths_same", side_effect=fake_same), \
             mock.patch.object(completion_audit, "git", side_effect=lambda _root,*args,**kwargs: common.git(self.root,*args,**kwargs)), \
             mock.patch.object(completion_audit, "fingerprint", side_effect=lambda _root: fingerprint(self.root)):
            pre=completion_audit.precheck(self.plan,base)
        self.assertTrue(pre["pass"],pre)

    def test_todo_mapping_and_state(self):
        self.assertEqual([],plan_state.validate(self.plan));plan_state.set_status(self.plan,"T1","completed")
        self.assertEqual("completed",plan_state.cursor_todos(self.plan.read_text(encoding="utf-8"))[0]["status"])
    def test_fingerprint_content_changes_but_smc_does_not(self):
        a=fingerprint(self.root);(self.root/".smc/x").mkdir(parents=True);(self.root/".smc/x/a").write_text("x")
        self.assertEqual(a,fingerprint(self.root));(self.root/"app.py").write_text("def main():\n    return 2\n")
        self.assertNotEqual(a,fingerprint(self.root))
    def test_plan_review_todo_status_is_not_semantic_drift(self):
        review_record.record("plan",self.plan,"PASS","test")
        self.assertEqual("FRESH_PASS",review_record.latest_status(self.plan,"plan")[0])
        plan_state.set_status(self.plan,"T1","completed")
        self.assertEqual("FRESH_PASS",review_record.latest_status(self.plan,"plan")[0])
        text=self.plan.read_text(encoding="utf-8").replace("- In: x","- In: x\n- In: y")
        self.plan.write_text(text,encoding="utf-8")
        self.assertEqual("STALE",review_record.latest_status(self.plan,"plan")[0])

    def test_review_freshness(self):
        review_record.record("implementation",self.plan,"PASS","test")
        self.assertEqual("FRESH_PASS",review_record.latest_status(self.plan,"implementation")[0])
        (self.root/"app.py").write_text("def main():\n    return 2\n")
        self.assertEqual("STALE",review_record.latest_status(self.plan,"implementation")[0])
    def test_evidence_command_must_match_plan(self):
        rc=evidence.run_cmd(self.plan,"V01",["python","-c","print('wrong')"])
        self.assertEqual(2,rc)
        self.assertEqual("MISSING",evidence.current_status(self.plan,"V01")[0])

    def test_evidence_freshness(self):
        rc=evidence.run_cmd(self.plan,"V01",["python","-c","print('ok')"]);self.assertEqual(0,rc)
        self.assertEqual("FRESH",evidence.current_status(self.plan,"V01")[0])
        (self.root/"app.py").write_text("def main():\n    return 3\n")
        self.assertEqual("STALE",evidence.current_status(self.plan,"V01")[0])
    def test_completion_precheck_rejects_unplanned_untracked_file(self):
        plan_state.set_status(self.plan,"T1","completed")
        (self.root/"app.py").write_text("def main():\n    return 2\n")
        (self.root/"surprise.py").write_text("x=1\n")
        base=subprocess.run(["git","-C",str(self.root),"rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
        pre=completion_audit.precheck(self.plan,base)
        self.assertFalse(pre["pass"])
        self.assertIn("surprise.py",pre["unexpected_changed_files"])

    def test_completion_audit_record_freshness(self):
        plan_state.set_status(self.plan,"T1","completed");(self.root/"app.py").write_text("def main():\n    return 2\n")
        base=subprocess.run(["git","-C",str(self.root),"rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
        pre=completion_audit.precheck(self.plan,base);self.assertTrue(pre["pass"])
        result=self.root/"audit.json";result.write_text(json.dumps({"total_items":1,"done":1,"changed":0,"deferred":0,"unverifiable":0,"scope_drift":0,"verdict":"PASS","summary":"ok"}),encoding="utf-8")
        completion_audit.record(self.plan,result);self.assertEqual("FRESH_PASS",completion_audit.check(self.plan)[0])
        (self.root/"app.py").write_text("def main():\n    return 4\n");self.assertEqual("STALE",completion_audit.check(self.plan)[0])

if __name__=="__main__":unittest.main()
