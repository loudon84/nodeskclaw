from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from hermes_output_artifacts.collector import ArtifactCollector
from hermes_output_artifacts.config import ArtifactSettings


def make_settings() -> ArtifactSettings:
    return ArtifactSettings(
        enabled=True,
        endpoint="https://minio.smc.lan:9000",
        bucket="agent-runtime-export",
        region="us-east-1",
        prefix="artifacts",
        instance_id="instance-a",
        addressing_style="path",
        presign_expires_seconds=3600,
        access_key="access",
        secret_key="secret",
        ext_allow=(".csv",),
        exclude_patterns=("private/*",),
        max_single_bytes=1024,
        max_total_bytes=2048,
        max_files=4,
        required_default=True,
    )


class ArtifactCollectorTests(unittest.TestCase):
    def test_accepts_only_files_under_workspace_and_applies_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "workspace"
            workspace.mkdir()
            accepted = workspace / "report.csv"
            accepted.write_text("value\n1\n", encoding="utf-8")
            private = workspace / "private"
            private.mkdir()
            (private / "secret.csv").write_text("secret", encoding="utf-8")
            outside = Path(temporary_directory) / "outside.csv"
            outside.write_text("outside", encoding="utf-8")

            result = ArtifactCollector(make_settings()).collect(
                workspace_root=workspace,
                paths=[accepted, private / "secret.csv", outside],
            )

        self.assertEqual(
            [candidate.name for candidate in result.candidates], ["report.csv"]
        )
        self.assertEqual(len(result.rejected), 1)
        self.assertIn("outside workspace", result.rejected[0].reason)

    def test_rejects_a_path_that_traverses_a_workspace_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "workspace"
            workspace.mkdir()
            target = workspace / "generated"
            target.mkdir()
            (target / "report.csv").write_text("value\n1\n", encoding="utf-8")
            linked = workspace / "linked"
            try:
                os.symlink(target, linked, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks are unavailable: {exc}")

            result = ArtifactCollector(make_settings()).collect(
                workspace_root=workspace,
                paths=[linked / "report.csv"],
            )

        self.assertEqual(result.candidates, ())
        self.assertEqual(len(result.rejected), 1)
        self.assertIn("symbolic links", result.rejected[0].reason)


if __name__ == "__main__":
    unittest.main()
