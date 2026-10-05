from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

from hermes_output_artifacts.plugin import register, track_workspace_file
from hermes_output_artifacts.refs import REGISTRY
from hermes_output_artifacts.upload import UploadResult


_ENV = {
    "HERMES_ARTIFACT_S3_ACCESS_KEY": "access",
    "HERMES_ARTIFACT_S3_SECRET_KEY": "secret",
}


class FakeUploader:
    def upload(self, run_id: str, path: Path, required: bool) -> UploadResult:
        return UploadResult(
            name=path.name,
            content_type="text/csv",
            object_key=f"artifacts/{run_id}/{path.name}",
            url=f"https://minio.smc.lan:9000/agent-runtime-export/{path.name}",
            size_bytes=path.stat().st_size,
            checksum_sha256="a" * 64,
            expires_at="2026-09-12T00:00:00+00:00",
            required=required,
            ok=True,
        )


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


def _install_fake_api_server() -> type:
    gateway = types.ModuleType("gateway")
    platforms = types.ModuleType("gateway.platforms")
    api_server = types.ModuleType("gateway.platforms.api_server")

    class APIServerAdapter:
        def _set_run_status(self, run_id, status, **fields):
            self.last = (run_id, status, fields)
            return self.last

    api_server.APIServerAdapter = APIServerAdapter
    sys.modules["gateway"] = gateway
    sys.modules["gateway.platforms"] = platforms
    sys.modules["gateway.platforms.api_server"] = api_server
    return APIServerAdapter


class PluginTests(unittest.TestCase):
    def tearDown(self) -> None:
        REGISTRY.bind(None)
        for name in (
            "gateway.platforms.api_server",
            "gateway.platforms",
            "gateway",
        ):
            sys.modules.pop(name, None)

    def test_registers_only_formal_post_tool_hook_and_native_finalizer(self) -> None:
        context = FakeContext()

        register(context, environment=_ENV, uploader=FakeUploader())

        self.assertEqual(set(context.hooks), {"post_tool_call"})
        self.assertIsNotNone(context.finalizer)
        self.assertFalse(hasattr(context, "output_artifacts_registry"))

    def test_refuses_to_enable_without_finalizer_or_api_server_gate(self) -> None:
        context = FakeContext(finalizer=False)

        with self.assertRaisesRegex(TypeError, "APIServerAdapter._set_run_status"):
            register(context, environment=_ENV, uploader=FakeUploader())

    def test_enables_on_v21_by_wrapping_set_run_status(self) -> None:
        adapter_cls = _install_fake_api_server()
        context = FakeContext(finalizer=False)

        register(context, environment=_ENV, uploader=FakeUploader())

        adapter = adapter_cls()
        adapter._set_run_status("run-1", "completed")
        self.assertEqual(adapter.last[1], "completed")
        self.assertIn("output_refs", adapter.last[2])

    def test_tracks_write_file_using_session_id_when_native_run_id_missing(
        self,
    ) -> None:
        context = FakeContext()
        register(context, environment=_ENV, uploader=FakeUploader())
        hook = context.hooks["post_tool_call"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            report = workspace / "report.csv"
            report.write_text("value\n1\n", encoding="utf-8")
            hook(
                tool_name="write_file",
                args={"path": str(report)},
                result={"written": str(report)},
                session_id="run-session",
                workspace_root=workspace,
            )
            refs = REGISTRY.merge_output_refs("run-session", None, force_flush=True)
        self.assertEqual(refs[0]["name"], "report.csv")

    def test_track_workspace_file_registers_path_for_run(self) -> None:
        context = FakeContext()
        register(context, environment=_ENV, uploader=FakeUploader())
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            report = workspace / "report.csv"
            report.write_text("value\n1\n", encoding="utf-8")
            track_workspace_file("run-42", str(report), workspace_root=workspace)
            refs = REGISTRY.merge_output_refs("run-42", None, force_flush=True)
        self.assertTrue(any(item.get("name") == "report.csv" for item in refs))


if __name__ == "__main__":
    unittest.main()
