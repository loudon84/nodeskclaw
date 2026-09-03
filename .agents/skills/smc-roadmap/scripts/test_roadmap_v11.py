from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_roadmap_v11 as vr


def digest(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class RoadmapV11Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Test"], check=True)
        (self.root / "docs_agent/architecture").mkdir(parents=True)
        (self.root / "docs_agent/architecture/AD-001.md").write_text(
            "---\nstatus: APPROVED\nreview_verdict: PASS\napproved_at: 2026-09-03T00:00:00Z\n---\n# AD\n",
            encoding="utf-8",
        )
        (self.root / ".cursor/plans").mkdir(parents=True)
        (self.root / ".cursor/plans/rm-01.plan.md").write_text(
            "---\nplan_contract: smc.plan.v3.3\nplan_id: RM-01\n---\n# Plan\n",
            encoding="utf-8",
        )
        (self.root / "docs_agent/prd").mkdir(parents=True)
        (self.root / "docs_agent/prd/RM-01.md").write_text("# PRD\n", encoding="utf-8")
        self.fp = "sha256:" + "a" * 64
        payload = {
            "schema": "smc.evidence.manifest.v1",
            "plan_id": "RM-01",
            "plan": ".cursor/plans/rm-01.plan.md",
            "wtree_fingerprint": self.fp,
            "generated_at": "2026-09-03T00:00:00Z",
            "plan_review": {"reviewer": "x", "verdict": "PASS", "plan_sha256": "sha256:" + "b" * 64, "timestamp": "2026-09-03T00:00:00Z"},
            "completion_audit": {"verdict": "PASS", "total_items": 1, "done": 1, "changed": 0, "deferred": 0, "unverifiable": 0, "scope_drift": 0, "timestamp": "2026-09-03T00:00:00Z"},
            "implementation_review": {"reviewer": "x", "verdict": "PASS", "wtree_fingerprint": self.fp, "timestamp": "2026-09-03T00:00:00Z"},
            "blocking_verifications": [{"verification_id": "V01", "command": "pytest", "exit_code": 0, "result": "PASS", "timestamp": "2026-09-03T00:00:00Z", "policy": "LOCAL_TRANSIENT", "raw_log_ref": ".smc/evidence/RM-01/logs/x.log", "raw_log_sha256": "sha256:" + "c" * 64}],
        }
        payload["payload_sha256"] = digest(payload)
        manifest = self.root / "docs_agent/evidence/RM-01-evidence.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "implementation"], check=True)
        self.commit = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        self.roadmap = self.root / "docs_agent/roadmap.md"
        self.write_roadmap(self.fp)

    def tearDown(self):
        self.tmp.cleanup()

    def write_roadmap(self, fp: str) -> None:
        self.roadmap.write_text(
            f'''---\nroadmap_id: ROADMAP-001\nversion: 1.1.0\nstatus: ACTIVE\narchitecture_decision: docs_agent/architecture/AD-001.md\nsource_revision: AD-001@1.0.0\nupdated_at: 2026-09-03T00:00:00Z\n---\n\n## Roadmap Items\n\n| Item ID | Outcome | Depends On | Status | Exit Criteria | PRD | Plan | Implementation Commit | Verification Evidence |\n|---|---|---|---|---|---|---|---|---|\n| RM-01 | deliver | - | DONE | pass | docs_agent/prd/RM-01.md | .cursor/plans/rm-01.plan.md | {self.commit} | smc-evidence:RM-01@{fp} |\n''',
            encoding="utf-8",
        )

    def test_valid_durable_smc_evidence(self):
        self.assertEqual([], vr.validate(self.roadmap))

    def test_fingerprint_mismatch_is_rejected(self):
        self.write_roadmap("sha256:" + "d" * 64)
        errors = vr.validate(self.roadmap)
        self.assertTrue(any("FINGERPRINT_MISMATCH" in x for x in errors), errors)

    def test_v11_requires_supported_evidence_scheme(self):
        text = self.roadmap.read_text(encoding="utf-8").replace(f"smc-evidence:RM-01@{self.fp}", "artifacts/v01.xml")
        self.roadmap.write_text(text, encoding="utf-8")
        errors = vr.validate(self.roadmap)
        self.assertTrue(any("EVIDENCE_REF_SCHEME_REQUIRED" in x for x in errors), errors)


if __name__ == "__main__":
    unittest.main()
