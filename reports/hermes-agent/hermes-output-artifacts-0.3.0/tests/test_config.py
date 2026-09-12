from __future__ import annotations

import unittest

from hermes_output_artifacts.config import ArtifactSettings


class FakeContext:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values
        self.calls: list[str] = []

    def get_config(self, key: str, default: object = None) -> object:
        self.calls.append(key)
        return self.values.get(key, default)


class ArtifactSettingsTests(unittest.TestCase):
    def test_loads_non_secret_settings_from_formal_context(self) -> None:
        context = FakeContext(
            {
                "enabled": True,
                "s3_endpoint": "https://minio.smc.lan:9000",
                "s3_bucket": "agent-runtime-export",
                "s3_prefix": "artifacts",
                "instance_id": "instance-a",
                "ext_allow": [".csv", ".pdf"],
                "max_files": 12,
            }
        )
        environment = {
            "HERMES_ARTIFACT_S3_ACCESS_KEY": "access",
            "HERMES_ARTIFACT_S3_SECRET_KEY": "secret",
            "MINIO_ROOT_USER": "root-user-must-not-be-used",
            "MINIO_ROOT_PASSWORD": "root-password-must-not-be-used",
        }

        settings = ArtifactSettings.from_context(context, environment)

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.endpoint, "https://minio.smc.lan:9000")
        self.assertEqual(settings.bucket, "agent-runtime-export")
        self.assertEqual(settings.prefix, "artifacts")
        self.assertEqual(settings.instance_id, "instance-a")
        self.assertEqual(settings.ext_allow, (".csv", ".pdf"))
        self.assertEqual(settings.access_key, "access")
        self.assertEqual(settings.secret_key, "secret")
        self.assertIn("s3_endpoint", context.calls)
        self.assertNotIn("s3_access_key", context.calls)
        self.assertNotIn("s3_secret_key", context.calls)

    def test_does_not_accept_minio_root_credentials(self) -> None:
        context = FakeContext(
            {"enabled": True, "s3_endpoint": "https://minio.smc.lan:9000"}
        )
        environment = {
            "MINIO_ROOT_USER": "root",
            "MINIO_ROOT_PASSWORD": "root-password",
        }

        with self.assertRaisesRegex(ValueError, "HERMES_ARTIFACT_S3_ACCESS_KEY"):
            ArtifactSettings.from_context(context, environment)

    def test_rejects_instance_id_that_is_not_a_single_object_key_segment(self) -> None:
        context = FakeContext(
            {
                "enabled": True,
                "s3_endpoint": "https://minio.smc.lan:9000",
                "instance_id": "instance-a/other",
            }
        )

        with self.assertRaisesRegex(ValueError, "instance_id"):
            ArtifactSettings.from_context(
                context,
                {
                    "HERMES_ARTIFACT_S3_ACCESS_KEY": "access",
                    "HERMES_ARTIFACT_S3_SECRET_KEY": "secret",
                },
            )


if __name__ == "__main__":
    unittest.main()
