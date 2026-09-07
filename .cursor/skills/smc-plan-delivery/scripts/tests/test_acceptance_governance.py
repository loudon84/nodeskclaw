from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import acceptance
import delivery_state
import plan_state
import workspace


PLAN = r"""---
name: RM-AC
overview: acceptance governance
todos:
  - id: t1-change-app
    content: "T1 — change app [C01]"
    status: pending
isProject: false
plan_contract: smc.plan.v3.4
plan_id: RM-AC
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
source_revision: RM-AC@1.0
grounded_commit: deadbeef
grounding_source: committed_baseline
working_tree_fingerprint: clean
---

# RM-AC

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
| AC-01 | AC | approval accepted | BEHAVIOR | C01 | T1 | V01 | INTEGRATION | yes |

## Lifecycle Closure Matrix
None

## Contract / Data Flow Closure Matrix
None

## Acceptance Claim Ledger
| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason | Verification IDs |
|---|---|---|---|---|---|---|---|---|
| CLM-01 | AC-01 | runtime approval returns accepted | yes | RM-15/V13 | FAIL | TARGETED_RERUN | approval bearer changed | V01 |

## Live Scenario Matrix
| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
|---|---|---|---|---|---|---|---|---|
| SCN-01 | CLM-01 | V01 | approval-fixture | waiting_approval | runtime ready | approve | HTTP 200 and /approval observed | ENV-01 |

## Live Environment Matrix
| Environment ID | Required Env Vars | Preflight Command | Fault Driver Env | Candidate Mode | Candidate Probe |
|---|---|---|---|---|---|
| ENV-01 | TEST_TOKEN | `python -c "print('ok')"` | - | ENV_TOKEN | DEPLOYED_CANDIDATE |

## Verification Ledger
| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | CLM-01 | INTEGRATION | LIVE | `python -c "print('SMC_ACCEPTANCE_RESULT {\\"claims\\":{\\"CLM-01\\":{\\"result\\":\\"PASS\\"}}}')"` | approval accepted | 400 fails | LOCAL_TRANSIENT | ENV-01 | TARGETED_RERUN | yes |

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
change

**Immediate anchors**
- `app.py#main`

**Changes**
- change

**Stop conditions**
- [ ] works

**Triggered reads**
- None

## Verification
Run V01.

## Completion Gate
| Exit State | Allowed When | Blocking Evidence |
|---|---|---|
| IMPLEMENTED_AND_PROVEN | proof fresh | V01 |
| IMPLEMENTED_NOT_PROVEN | pending | pending |
| BLOCKED | blocked | blocker |
| RETURN_PRD | conflict | revision |
"""


class AcceptanceGovernanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)
        (self.root / ".gitignore").write_text(".smc/\n", encoding="utf-8")
        (self.root / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
        (self.root / ".cursor/plans").mkdir(parents=True)
        (self.root / ".cursor/prd.md").write_text(
            "---\nstatus: APPROVED\nreview_verdict: PASS\napproved_at: now\n---\n",
            encoding="utf-8",
        )
        self.plan = self.root / ".cursor/plans/rm-ac.plan.md"
        self.plan.write_text(PLAN, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "base"], check=True)
        delivery_state.init(self.plan)
        workspace.init(self.plan)

    def tearDown(self):
        self.tmp.cleanup()

    def test_contract_accepts_targeted_rerun(self):
        # @lat: [[ges-tests#GES Tests#Acceptance#Contract accepts targeted rerun]]
        self.assertEqual([], acceptance.validate_contract(self.plan))

    def test_blocking_prior_failure_cannot_be_reused(self):
        # @lat: [[ges-tests#GES Tests#Acceptance#Blocking prior failure cannot be reused]]
        text = self.plan.read_text(encoding="utf-8")
        text = text.replace(
            "| CLM-01 | AC-01 | runtime approval returns accepted | yes | RM-15/V13 | FAIL | TARGETED_RERUN | approval bearer changed | V01 |",
            "| CLM-01 | AC-01 | runtime approval returns accepted | yes | RM-15/V13 | FAIL | REUSE_EVIDENCE | - | V01 |",
        )
        text = text.replace("| ENV-01 | TARGETED_RERUN | yes |", "| ENV-01 | REUSE_EVIDENCE | yes |")
        self.plan.write_text(text, encoding="utf-8")
        codes = {x["code"] for x in acceptance.validate_contract(self.plan)}
        self.assertIn("PLAN_BLOCKING_FAILURE_REUSE_FORBIDDEN", codes)

    def test_live_preflight_blocks_missing_environment_before_execution(self):
        # @lat: [[ges-tests#GES Tests#Acceptance#Missing environment is precheck blocked]]
        acceptance.capture_candidate(self.plan)
        result = acceptance.preflight_verification(self.plan, "V01")
        self.assertFalse(result["pass"])
        self.assertEqual("LIVE_ENV_NOT_READY", result["code"])
        self.assertIn("TEST_TOKEN", result["missing_env"])

    def test_live_preflight_rejects_deployed_candidate_mismatch(self):
        # @lat: [[ges-tests#GES Tests#Acceptance#Candidate mismatch is LIVE_SUT_MISMATCH]]
        candidate = acceptance.capture_candidate(self.plan)
        with mock.patch.dict(
            os.environ,
            {"TEST_TOKEN": "set", "DEPLOYED_CANDIDATE": "sha256:not-the-current-candidate"},
            clear=False,
        ):
            result = acceptance.preflight_verification(self.plan, "V01")
        self.assertFalse(result["pass"])
        self.assertEqual("LIVE_SUT_MISMATCH", result["code"])
        self.assertEqual(candidate["candidate_id"], result["expected_candidate_id"])

    def test_live_preflight_accepts_matching_candidate(self):
        # @lat: [[ges-tests#GES Tests#Acceptance#Matching candidate passes preflight]]
        candidate = acceptance.capture_candidate(self.plan)
        with mock.patch.dict(
            os.environ,
            {"TEST_TOKEN": "set", "DEPLOYED_CANDIDATE": candidate["candidate_id"]},
            clear=False,
        ):
            result = acceptance.preflight_verification(self.plan, "V01")
        self.assertTrue(result["pass"], result)


if __name__ == "__main__":
    unittest.main()
