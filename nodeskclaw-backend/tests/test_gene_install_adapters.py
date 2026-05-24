import pytest

from app.core.exceptions import BadRequestError
from app.services.runtime.hermes_gene_install_adapter import HermesGeneInstallAdapter
from app.services.runtime.noop_gene_install_adapter import NoopGeneInstallAdapter
from app.services.runtime.openclaw_gene_install_adapter import OpenClawGeneInstallAdapter


class FakeFS:
    def __init__(self):
        self.files = {}
        self.dirs = set()
        self.removed = []

    async def mkdir(self, path: str) -> None:
        self.dirs.add(path)

    async def write_text(self, path: str, content: str) -> None:
        self.files[path] = content

    async def read_text(self, path: str) -> str | None:
        return self.files.get(path)

    async def remove(self, path: str) -> None:
        self.removed.append(path)
        self.files.pop(path, None)


@pytest.mark.parametrize(
    "adapter",
    [
        HermesGeneInstallAdapter(),
        OpenClawGeneInstallAdapter(),
        NoopGeneInstallAdapter(),
    ],
)
@pytest.mark.asyncio
async def test_gene_adapters_reject_unsafe_skill_name_before_deploy_writes(adapter) -> None:
    fs = FakeFS()

    with pytest.raises(BadRequestError) as exc:
        await adapter.deploy_skill(fs, "../../workspace/pwned", "content", "desc")

    assert "skill name" in exc.value.message
    assert fs.files == {}
    assert fs.dirs == set()
    assert fs.removed == []


@pytest.mark.parametrize(
    "adapter",
    [
        HermesGeneInstallAdapter(),
        OpenClawGeneInstallAdapter(),
        NoopGeneInstallAdapter(),
    ],
)
@pytest.mark.asyncio
async def test_gene_adapters_reject_unsafe_skill_name_before_remove_paths(adapter) -> None:
    fs = FakeFS()

    with pytest.raises(BadRequestError) as exc:
        await adapter.remove_skill(fs, "../../workspace/pwned")

    assert "skill name" in exc.value.message
    assert fs.removed == []


@pytest.mark.asyncio
async def test_openclaw_gene_adapter_writes_safe_skill_path() -> None:
    fs = FakeFS()
    adapter = OpenClawGeneInstallAdapter()

    await adapter.deploy_skill(fs, "team_culture.v1", "content", "Team culture")

    assert ".openclaw/skills/team_culture.v1" in fs.dirs
    assert ".openclaw/skills/team_culture.v1/SKILL.md" in fs.files
    assert "name: team_culture.v1" in fs.files[".openclaw/skills/team_culture.v1/SKILL.md"]


@pytest.mark.asyncio
async def test_noop_gene_adapter_writes_safe_skill_path() -> None:
    fs = FakeFS()
    adapter = NoopGeneInstallAdapter()

    await adapter.deploy_skill(fs, "team_culture.v1", "content")

    assert ".deskclaw/skills/team_culture.v1" in fs.dirs
    assert fs.files[".deskclaw/skills/team_culture.v1/SKILL.md"] == "content"
