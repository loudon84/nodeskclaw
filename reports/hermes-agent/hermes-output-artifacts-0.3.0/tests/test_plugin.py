from __future__ import annotations

import unittest

from hermes_output_artifacts.plugin import register


class FakeContext:
    def __init__(self, finalizer: bool = True) -> None:
        self.values = {
            "enabled": True,
            "s3_endpoint": "https://minio.smc.lan:9000",
            "s3_bucket": "agent-runtime-export",
        }
        self.hooks: dict[str, object] = {}
        self.finalizer = None
        if finalizer:
            self.register_native_run_finalizer = self._register_finalizer

    def get_config(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def register_hook(self, hook_name: str, callback: object) -> None:
        self.hooks[hook_name] = callback

    def _register_finalizer(self, callback: object) -> None:
        self.finalizer = callback


class PluginTests(unittest.TestCase):
    def test_registers_only_formal_post_tool_hook_and_native_finalizer(self) -> None:
        context = FakeContext()

        register(
            context,
            environment={
                "HERMES_ARTIFACT_S3_ACCESS_KEY": "access",
                "HERMES_ARTIFACT_S3_SECRET_KEY": "secret",
            },
        )

        self.assertEqual(set(context.hooks), {"post_tool_call"})
        self.assertIsNotNone(context.finalizer)
        self.assertFalse(hasattr(context, "output_artifacts_registry"))

    def test_refuses_to_enable_without_native_finalizer_contract(self) -> None:
        context = FakeContext(finalizer=False)

        with self.assertRaisesRegex(TypeError, "register_native_run_finalizer"):
            register(
                context,
                environment={
                    "HERMES_ARTIFACT_S3_ACCESS_KEY": "access",
                    "HERMES_ARTIFACT_S3_SECRET_KEY": "secret",
                },
            )


if __name__ == "__main__":
    unittest.main()
