from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import test_assets
import contract_resolver


def plan_text(action: str, change_rows: str) -> str:
    return f'''---
name: RM-20
overview: test asset reuse
todos:
  - id: t1-live
    content: "T1 — verify live approval [C01]"
    status: pending
isProject: false
plan_contract: smc.plan.v3.6
plan_id: RM-20
commit_policy: post_review
acceptance_contract: smc.acceptance.v1
---

# RM-20

## Verification Ledger

| Verification ID | Claim IDs | Level | Acceptance Mode | Entry Point / Command | Oracle | Negative / Regression | Evidence Policy | Environment | Evidence Action | Blocking |
|---|---|---|---|---|---|---|---|---|---|---|
| V01 | CLM-01 | INTEGRATION | LIVE | `python tests/live/approval.py` | claim PASS | negative | LOCAL_TRANSIENT | ENV-01 | TARGETED_RERUN | yes |

## Live Scenario Matrix

| Scenario ID | Claim IDs | Verification IDs | Subject / Fixture | Required Capabilities | Preconditions | Stimulus | Oracle | Environment ID |
|---|---|---|---|---|---|---|---|---|
| SCN-01 | CLM-01 | V01 | TA-APPROVAL-LIVE | waiting_approval;approve | ready | approve | PASS | ENV-01 |

## Test Asset Ledger

| Verification ID | Asset ID | Kind | Path / Entrypoint | Required Capabilities | Action | Impact | Reason |
|---|---|---|---|---|---|---|---|
| V01 | TA-APPROVAL-LIVE | TEST | `tests/live/approval.py` | waiting_approval;approve | {action} | provider path changed | reusable approval acceptance |

## Change Matrix

| Change ID | File / Symbol | Kind | Action | Existing Owner | Todo Owner | Target State | PRD Capability | New File? |
|---|---|---|---|---|---|---|---|---|
{change_rows}
'''


class TestAssetContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".agents").mkdir()
        self.asset = self.root / "tests/live/approval.py"
        self.asset.parent.mkdir(parents=True)
        self.asset.write_text("print('approval')\n", encoding="utf-8")
        self.manifest = self.root / "docs_agent/test-assets/TA-APPROVAL-LIVE.json"
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text(json.dumps({
            "schema": test_assets.SCHEMA,
            "asset_id": "TA-APPROVAL-LIVE",
            "status": "ACTIVE",
            "kind": "TEST",
            "path": "tests/live/approval.py",
            "capabilities": ["waiting_approval", "approve"],
            "content_sha256": test_assets.file_sha256(self.asset),
        }), encoding="utf-8")
        self.plan = self.root / ".cursor/plans/RM-20.plan.md"
        self.plan.parent.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    # @lat: [[ges-tests#GES Tests#Test Asset Catalog#Resolves the v3.6 contract]]
    def test_resolves_v36_without_legacy_fallback(self):
        self.assertEqual("validate_plan_v36.py", contract_resolver.validator_name("smc.plan.v3.6"))
        self.assertIsNone(contract_resolver.validator_name("smc.plan.v9.9"))

    # @lat: [[ges-tests#GES Tests#Test Asset Catalog#Reuses an unchanged live asset]]
    def test_reuses_an_unchanged_live_asset(self):
        self.plan.write_text(plan_text("REUSE", "| C01 | `src/provider.py#approve` | PROD | MODIFY | provider | T1 | changed | approval | no |"), encoding="utf-8")
        self.assertEqual([], test_assets.validate_plan(self.plan))

    # @lat: [[ges-tests#GES Tests#Test Asset Catalog#Rejects stale reuse]]
    def test_rejects_stale_reuse(self):
        self.asset.write_text("print('changed')\n", encoding="utf-8")
        self.plan.write_text(plan_text("REUSE", "| C01 | `src/provider.py#approve` | PROD | MODIFY | provider | T1 | changed | approval | no |"), encoding="utf-8")
        codes = {error["code"] for error in test_assets.validate_plan(self.plan)}
        self.assertIn("TEST_ASSET_DIGEST_STALE", codes)

    # @lat: [[ges-tests#GES Tests#Test Asset Catalog#Synchronizes an extended asset]]
    def test_synchronizes_an_extended_asset(self):
        self.asset.write_text("print('extended')\n", encoding="utf-8")
        rows = "\n".join([
            "| C01 | `tests/live/approval.py` | TEST | MODIFY | approval test | T1 | extended | approval | no |",
            "| C02 | `docs_agent/test-assets/TA-APPROVAL-LIVE.json` | TEST | MODIFY | asset manifest | T1 | digest refreshed | approval | no |",
        ])
        self.plan.write_text(plan_text("EXTEND", rows), encoding="utf-8")
        self.assertEqual([], test_assets.validate_plan(self.plan))
        self.assertEqual([], test_assets.sync(self.plan))
        data = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(test_assets.file_sha256(self.asset), data["content_sha256"])


if __name__ == "__main__":
    unittest.main()
