from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hermes_output_artifacts.config import ArtifactSettings
from hermes_output_artifacts.upload import MinioUploader


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
        ext_allow=(),
        exclude_patterns=(),
        max_single_bytes=1024,
        max_total_bytes=2048,
        max_files=4,
        required_default=True,
    )


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []

    def put_object(self, **kwargs: object) -> None:
        self.put_calls.append(kwargs)

    def generate_presigned_url(
        self,
        client_method: str,
        *,
        Params: dict[str, object],
        ExpiresIn: int,
    ) -> str:
        self.presign_call = (client_method, Params, ExpiresIn)
        return "https://minio.smc.lan:9000/agent-runtime-export/signed-report.csv"


class MinioUploaderTests(unittest.TestCase):
    def test_uploads_hashed_run_scoped_object_and_returns_integrity_metadata(
        self,
    ) -> None:
        client = FakeS3Client()
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "report.csv"
            path.write_bytes(b"amount\n10\n")

            result = MinioUploader(make_settings(), client=client).upload(
                "run-42", path, True
            )

        self.assertTrue(result.ok)
        self.assertEqual(
            result.checksum_sha256,
            "628fbbd099ed015d810b117afa7958d0761f97362a4a161039aa46b1c742d3f6",
        )
        self.assertIn("instances/instance-a/runs/run-42/", result.object_key)
        self.assertIn(result.checksum_sha256, result.object_key)
        self.assertEqual(
            client.put_calls[0]["Metadata"],
            {"sha256": result.checksum_sha256, "run_id": "run-42"},
        )
        self.assertEqual(client.presign_call[0], "get_object")
        self.assertIsNotNone(result.expires_at)


if __name__ == "__main__":
    unittest.main()
