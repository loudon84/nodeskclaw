import json
from pathlib import Path

import pytest

from app.models.instance import Instance
from app.services.hermes_expert.expert_skill_service import EXPERT_RUNTIME, ExpertSkillService


def _expert_instance(slug: str = "writer") -> Instance:
    return Instance(
        id="inst-1",
        name="Writer",
        slug=slug,
        runtime=EXPERT_RUNTIME,
        cluster_id="cluster-1",
        namespace=f"docker-{slug}",
        org_id="org-1",
    )


@pytest.fixture
def skill_service() -> ExpertSkillService:
    return ExpertSkillService()


def test_install_builtin_bundle_and_rescan(tmp_path, monkeypatch, skill_service: ExpertSkillService):
    from app.services.hermes_expert import expert_filesystem as fs

    monkeypatch.setattr(fs, "DOCKER_DATA_DIR", tmp_path)
    instance = _expert_instance()
    items = skill_service.install_builtin_bundle(instance, "writer")
    assert len(items) == 1
    assert items[0].slug == "writer-outline"
    assert items[0].enabled is True

    index_path = tmp_path / instance.slug / "data" / "hermes" / "skills" / ".index.json"
    assert index_path.is_file()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["skills"][0]["slug"] == "writer-outline"


def test_disable_skill_sets_status(tmp_path, monkeypatch, skill_service: ExpertSkillService):
    from app.services.hermes_expert import expert_filesystem as fs

    monkeypatch.setattr(fs, "DOCKER_DATA_DIR", tmp_path)
    instance = _expert_instance()
    skill_service.install_builtin_bundle(instance, "writer")
    info = skill_service.disable_skill(instance, "writer-outline")
    assert info.enabled is False
    assert info.status == "disabled"


def test_requires_restart_marks_pending(tmp_path, monkeypatch, skill_service: ExpertSkillService):
    from app.services.hermes_expert import expert_filesystem as fs

    monkeypatch.setattr(fs, "DOCKER_DATA_DIR", tmp_path)
    instance = _expert_instance("finance")
    items = skill_service.install_builtin_bundle(instance, "finance")
    assert items[0].slug == "finance-summary"
    assert items[0].status == "pending_restart"


def test_safe_zip_rejects_path_traversal(tmp_path, monkeypatch, skill_service: ExpertSkillService):
    import io
    import zipfile

    from app.core.exceptions import BadRequestError
    from app.services.hermes_expert.expert_filesystem import safe_extract_zip

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../evil/SKILL.md", "# evil")
    skills_dir = tmp_path / "writer" / "data" / "hermes" / "skills"
    skills_dir.mkdir(parents=True)
    with pytest.raises(BadRequestError):
        safe_extract_zip(buf.getvalue(), skills_dir)
