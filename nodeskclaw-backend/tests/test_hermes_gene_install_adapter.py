import pytest

from app.services.runtime.hermes_gene_install_adapter import HermesGeneInstallAdapter
from app.services.runtime.registries.runtime_registry import RUNTIME_REGISTRY


class FakeFS:
    def __init__(self):
        self.files = {}
        self.dirs = set()
        self.removed = []

    async def mkdir(self, path: str) -> None:
        self.dirs.add(path)

    async def write_text(self, path: str, content: str) -> None:
        self.files[path] = content

    async def remove(self, path: str) -> None:
        self.removed.append(path)
        self.files.pop(path, None)


@pytest.mark.asyncio
async def test_hermes_gene_adapter_writes_runtime_paths_and_cleans_legacy_path():
    fs = FakeFS()
    adapter = HermesGeneInstallAdapter()

    await adapter.deploy_skill(
        fs,
        "team-culture-concise",
        "\n".join([
            "Use ~/.deskclaw/tools/example.py",
            "Run /root/.deskclaw/tools/absolute.py",
            "Keep .deskclaw/tools/relative.py",
        ]),
        "Concise culture",
    )
    await adapter.deploy_scripts(fs, {"tool.py": "print('ok')"})
    await adapter.invalidate_cache(fs, "team-culture-concise")

    assert ".hermes/skills/team-culture-concise" in fs.dirs
    assert ".hermes/scripts" in fs.dirs
    assert ".deskclaw/skills/team-culture-concise" in fs.removed
    assert ".hermes/.skills_prompt_snapshot.json" in fs.removed
    assert fs.files[".hermes/skills/team-culture-concise/SKILL.md"].startswith("---\n")
    skill_content = fs.files[".hermes/skills/team-culture-concise/SKILL.md"]
    assert "~/.hermes/scripts/example.py" in skill_content
    assert "~/.hermes/scripts/absolute.py" in skill_content
    assert ".hermes/scripts/relative.py" in skill_content
    assert ".deskclaw/tools" not in skill_content
    assert fs.files[".hermes/scripts/tool.py"] == "print('ok')"


@pytest.mark.asyncio
async def test_hermes_gene_adapter_remove_skill_cleans_active_and_legacy_paths():
    fs = FakeFS()
    adapter = HermesGeneInstallAdapter()

    await adapter.remove_skill(fs, "team-culture-concise")
    await adapter.post_remove_cleanup(fs, "team-culture-concise")

    assert ".hermes/skills/team-culture-concise" in fs.removed
    assert ".deskclaw/skills/team-culture-concise" in fs.removed
    assert ".hermes/.skills_prompt_snapshot.json" in fs.removed


def test_runtime_registry_uses_hermes_gene_adapter():
    spec = RUNTIME_REGISTRY.get("hermes")

    assert isinstance(spec.gene_install_adapter, HermesGeneInstallAdapter)
