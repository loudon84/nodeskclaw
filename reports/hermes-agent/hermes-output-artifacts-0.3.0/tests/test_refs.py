from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hermes_output_artifacts.config import ArtifactSettings
from hermes_output_artifacts.contracts import NativeRunFinalizeRequest
from hermes_output_artifacts.refs import ArtifactRegistry
from hermes_output_artifacts.upload import UploadResult


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
        exclude_patterns=(),
        max_single_bytes=1024,
        max_total_bytes=2048,
        max_files=4,
        required_default=True,
    )


class SuccessfulUploader:
    def upload(self, run_id: str, path: Path, required: bool) -> UploadResult:
        return UploadResult(
            name=path.name,
            content_type="text/csv",
            object_key=f"artifacts/instances/instance-a/runs/{run_id}/digest-{path.name}",
            url="https://minio.smc.lan:9000/agent-runtime-export/signed.csv",
            size_bytes=path.stat().st_size,
            checksum_sha256="a" * 64,
            expires_at="2026-09-12T00:00:00+00:00",
            required=required,
            ok=True,
        )


class FailingUploader:
    def upload(self, run_id: str, path: Path, required: bool) -> UploadResult:
        return UploadResult(
            name=path.name,
            content_type="text/csv",
            object_key="",
            url="",
            size_bytes=path.stat().st_size,
            checksum_sha256="",
            expires_at="",
            required=required,
            ok=False,
            error="MinIO unavailable",
        )


class InvalidSuccessUploader:
    def upload(self, run_id: str, path: Path, required: bool) -> UploadResult:
        return UploadResult(
            name=path.name,
            content_type="text/csv",
            object_key="artifacts/invalid",
            url="not-an-absolute-url",
            size_bytes=path.stat().st_size,
            checksum_sha256="a" * 64,
            expires_at="2026-09-12T00:00:00+00:00",
            required=required,
            ok=True,
        )


class ArtifactRegistryTests(unittest.TestCase):
    def test_finalizer_returns_uploaded_refs_with_integrity_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            report = workspace / "report.csv"
            report.write_text("value\n1\n", encoding="utf-8")
            registry = ArtifactRegistry(make_settings(), uploader=SuccessfulUploader())
            registry.track_path("run-42", report, workspace)

            result = registry.finalize(
                NativeRunFinalizeRequest(
                    schema_version=1,
                    run_id="run-42",
                    session_id="session-1",
                    proposed_status="completed",
                    workspace_root=workspace,
                )
            )

        self.assertEqual(result.outcome, "ready")
        self.assertEqual(len(result.output_refs), 1)
        self.assertEqual(result.output_refs[0].checksum_sha256, "a" * 64)

    def test_finalizer_fails_when_a_required_upload_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            report = workspace / "report.csv"
            report.write_text("value\n1\n", encoding="utf-8")
            registry = ArtifactRegistry(make_settings(), uploader=FailingUploader())
            registry.track_path("run-42", report, workspace)

            result = registry.finalize(
                NativeRunFinalizeRequest(
                    schema_version=1,
                    run_id="run-42",
                    session_id="session-1",
                    proposed_status="completed",
                    workspace_root=workspace,
                )
            )

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.error_code, "artifact_upload_failed")

    def test_finalizer_returns_failure_when_uploaded_reference_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            report = workspace / "report.csv"
            report.write_text("value\n1\n", encoding="utf-8")
            registry = ArtifactRegistry(
                make_settings(), uploader=InvalidSuccessUploader()
            )
            registry.track_path("run-42", report, workspace)

            result = registry.finalize(
                NativeRunFinalizeRequest(
                    schema_version=1,
                    run_id="run-42",
                    session_id="session-1",
                    proposed_status="completed",
                    workspace_root=workspace,
                )
            )

        self.assertEqual(result.outcome, "failed")
        self.assertEqual(result.error_code, "artifact_finalize_failed")


if __name__ == "__main__":
    unittest.main()
