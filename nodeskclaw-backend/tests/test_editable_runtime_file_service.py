from types import SimpleNamespace
import posixpath

import pytest

from app.api.portal import instance_files
from app.core.exceptions import AppException
from app.models.instance_member import InstanceRole
from app.services import editable_runtime_file_service as service


class FakeFS:
    def __init__(self, files: dict[str, str] | None = None):
        self.files = files or {}

    async def file_stat(self, path: str) -> dict | None:
        if path not in self.files:
            return None
        return {
            "size": len(self.files[path].encode("utf-8")),
            "modified_at": 0,
            "mime_type": "text/markdown",
        }

    async def read_text(self, path: str) -> str | None:
        return self.files.get(path)

    async def write_text(self, path: str, content: str) -> None:
        self.files[path] = content

    async def list_dir(self, path: str) -> list[dict] | None:
        prefix = path.rstrip("/") + "/"
        entries: dict[str, dict] = {}
        for file_path, content in self.files.items():
            if not file_path.startswith(prefix):
                continue
            rest = file_path[len(prefix):]
            if not rest:
                continue
            name = rest.split("/", 1)[0]
            if name not in entries:
                entries[name] = {
                    "name": name,
                    "is_dir": "/" in rest,
                    "size": len(content.encode("utf-8")) if "/" not in rest else 0,
                    "modified_at": 0,
                }
            elif "/" in rest:
                entries[name]["is_dir"] = True
        if not entries and not any(posixpath.dirname(p) == path for p in self.files):
            return None
        return sorted(entries.values(), key=lambda item: (not item["is_dir"], item["name"].lower()))


class FakeRemoteFSContext:
    def __init__(self, fs: FakeFS):
        self.fs = fs

    async def __aenter__(self) -> FakeFS:
        return self.fs

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def make_instance(runtime: str = "openclaw", env_vars: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(id="inst-1", runtime=runtime, env_vars=env_vars)


async def read_with_fake_fs(
    monkeypatch,
    fs: FakeFS,
    runtime: str = "openclaw",
    resource_key: str = service.ROLE_PROMPT_KEY,
    env_vars: str | None = None,
) -> dict:
    instance = make_instance(runtime, env_vars=env_vars)

    async def fake_get_running_instance(_instance_id, _db):
        return instance

    monkeypatch.setattr(service.enterprise_file_service, "_get_running_instance", fake_get_running_instance)
    monkeypatch.setattr(service, "remote_fs", lambda _instance, _db: FakeRemoteFSContext(fs))
    return await service.read_managed_file("inst-1", resource_key, db=None)


async def write_with_fake_fs(
    monkeypatch,
    fs: FakeFS,
    content: str,
    runtime: str = "openclaw",
) -> dict:
    instance = make_instance(runtime)

    async def fake_get_running_instance(_instance_id, _db):
        return instance

    monkeypatch.setattr(service.enterprise_file_service, "_get_running_instance", fake_get_running_instance)
    monkeypatch.setattr(service, "remote_fs", lambda _instance, _db: FakeRemoteFSContext(fs))
    return await service.write_managed_file("inst-1", service.ROLE_PROMPT_KEY, content, db=None)


async def test_hermes_role_prompt_resolves_to_soul_md(monkeypatch):
    fs = FakeFS({".hermes/SOUL.md": "# Hermes soul"})

    result = await read_with_fake_fs(monkeypatch, fs, runtime="hermes")

    assert result["rel_path"] == ".hermes/SOUL.md"
    assert result["display_path"] == "/root/.hermes/SOUL.md"
    assert result["content"] == "# Hermes soul"
    assert result["exists"] is True


async def test_openclaw_role_prompt_defaults_to_workspace_soul(monkeypatch):
    fs = FakeFS({".openclaw/workspace/SOUL.md": "# OpenClaw soul"})

    result = await read_with_fake_fs(monkeypatch, fs)

    assert result["rel_path"] == ".openclaw/workspace/SOUL.md"
    assert result["display_path"] == "/root/.openclaw/workspace/SOUL.md"
    assert result["content"] == "# OpenClaw soul"


async def test_openclaw_role_prompt_uses_configured_workspace(monkeypatch):
    fs = FakeFS({
        ".openclaw/openclaw.json": """
        {
          // JSONC comments are valid in openclaw.json
          "agents": {
            "defaults": { "workspace": "~/.openclaw/agents" },
            "list": [{ "id": "ops", "default": true, "workspace": "/root/.openclaw/ops" }]
          }
        }
        """,
        ".openclaw/ops/SOUL.md": "# Ops soul",
    })

    result = await read_with_fake_fs(monkeypatch, fs)

    assert result["rel_path"] == ".openclaw/ops/SOUL.md"
    assert result["content"] == "# Ops soul"


async def test_openclaw_role_prompt_rejects_workspace_outside_allowed_root(monkeypatch):
    fs = FakeFS({
        ".openclaw/openclaw.json": '{"agents":{"defaults":{"workspace":"/tmp/workspace"}}}',
    })

    with pytest.raises(AppException) as exc:
        await read_with_fake_fs(monkeypatch, fs)

    assert exc.value.message_key == "errors.managed_files.path_outside_allowed_root"


async def test_openclaw_role_prompt_rejects_unparseable_config(monkeypatch):
    fs = FakeFS({".openclaw/openclaw.json": "{invalid"})

    with pytest.raises(AppException) as exc:
        await read_with_fake_fs(monkeypatch, fs)

    assert exc.value.message_key == "errors.managed_files.config_parse_failed"


async def test_missing_soul_md_returns_empty_content(monkeypatch):
    fs = FakeFS()

    result = await read_with_fake_fs(monkeypatch, fs)

    assert result["rel_path"] == ".openclaw/workspace/SOUL.md"
    assert result["content"] == ""
    assert result["exists"] is False


async def test_agent_bundle_docs_reads_top_level_text_docs(monkeypatch):
    fs = FakeFS({
        ".openclaw/agent-bundles/editor/AGENT.md": "# Agent",
        ".openclaw/agent-bundles/editor/rules.md": "- Rule",
        ".openclaw/agent-bundles/editor/notes.txt": "Notes",
        ".openclaw/agent-bundles/editor/SOUL.md": "# Soul",
        ".openclaw/agent-bundles/editor/config.json": "{}",
        ".openclaw/agent-bundles/editor/skills/writer/SKILL.md": "# Writer",
    })

    result = await read_with_fake_fs(
        monkeypatch,
        fs,
        resource_key=service.AGENT_BUNDLE_DOCS_KEY,
        env_vars='{"NODESKCLAW_AGENT_BUNDLE_DIR": "/root/.openclaw/agent-bundles/editor"}',
    )

    assert result["rel_path"] == ".openclaw/agent-bundles/editor"
    assert [item["key"] for item in result["items"]] == ["AGENT.md", "rules.md", "notes.txt"]
    assert result["items"][0]["display_path"] == "/root/.openclaw/agent-bundles/editor/AGENT.md"
    assert result["items"][0]["content"] == "# Agent"
    assert result["exists"] is True


async def test_agent_bundle_docs_falls_back_to_first_bundle_dir(monkeypatch):
    fs = FakeFS({
        ".openclaw/agent-bundles/beta/AGENT.md": "# Beta",
        ".openclaw/agent-bundles/alpha/README.md": "# Alpha",
    })

    result = await read_with_fake_fs(
        monkeypatch,
        fs,
        resource_key=service.AGENT_BUNDLE_DOCS_KEY,
    )

    assert result["rel_path"] == ".openclaw/agent-bundles/alpha"
    assert [item["key"] for item in result["items"]] == ["README.md"]


async def test_write_managed_file_creates_role_prompt(monkeypatch):
    fs = FakeFS()

    result = await write_with_fake_fs(monkeypatch, fs, "# New soul")

    assert result["rel_path"] == ".openclaw/workspace/SOUL.md"
    assert result["content"] == "# New soul"
    assert fs.files[".openclaw/workspace/SOUL.md"] == "# New soul"


async def test_unknown_managed_file_resource_returns_not_found(monkeypatch):
    instance = make_instance("openclaw")

    async def fake_get_running_instance(_instance_id, _db):
        return instance

    monkeypatch.setattr(service.enterprise_file_service, "_get_running_instance", fake_get_running_instance)

    with pytest.raises(AppException) as exc:
        await service.read_managed_file("inst-1", "unknown", db=None)

    assert exc.value.message_key == "errors.managed_files.resource_not_found"


async def test_managed_file_route_requires_instance_admin(monkeypatch):
    seen = {}

    async def fake_check_instance_access(instance_id, current_user, role, db):
        seen["instance_id"] = instance_id
        seen["role"] = role

    async def fake_read_managed_file(instance_id, resource_key, db):
        return {"key": resource_key, "instance_id": instance_id}

    monkeypatch.setattr(
        instance_files.instance_member_service,
        "check_instance_access",
        fake_check_instance_access,
    )
    monkeypatch.setattr(
        instance_files.editable_runtime_file_service,
        "read_managed_file",
        fake_read_managed_file,
    )

    response = await instance_files.read_managed_file_content(
        "inst-1",
        service.ROLE_PROMPT_KEY,
        db=None,
        current_user=SimpleNamespace(id="user-1"),
    )

    assert seen == {"instance_id": "inst-1", "role": InstanceRole.admin}
    assert response.data == {"key": service.ROLE_PROMPT_KEY, "instance_id": "inst-1"}
