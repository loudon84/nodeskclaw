import pytest
from pathlib import Path

from app.services.hermes_expert.expert_template_service import ExpertTemplateService


@pytest.fixture
def template_service() -> ExpertTemplateService:
    return ExpertTemplateService()


def test_list_templates_includes_writer_and_finance(template_service: ExpertTemplateService):
    slugs = {item.slug for item in template_service.list_templates()}
    assert slugs == {"writer", "finance"}


def test_inject_template_replaces_placeholders(tmp_path, monkeypatch, template_service: ExpertTemplateService):
    from app.services.hermes_expert import expert_filesystem as fs

    monkeypatch.setattr(fs, "DOCKER_DATA_DIR", tmp_path)
    data_dir = template_service.inject_template(
        instance_slug="writer-demo",
        profile="writer",
        expert_template="writer",
        instance_id="inst-001",
        instance_name="Writer Demo",
        hindsight_api_url="http://hindsight.example.com",
        hindsight_bank_id="hermes-writer",
        init_obsidian_vault=True,
    )
    config_text = (data_dir / "config.yaml").read_text(encoding="utf-8")
    soul_text = (data_dir / "SOUL.md").read_text(encoding="utf-8")

    assert "profile: writer" in config_text
    assert "inst-001" in config_text
    assert "hermes-writer" in config_text
    assert "Writer Demo" in soul_text
    assert (data_dir / "obsidian-vault" / "00-Inbox").is_dir()
    assert (data_dir / "skills").is_dir()
    assert (data_dir / ".inject-record.json").is_file()


def test_inject_template_backups_existing_directory(tmp_path, monkeypatch, template_service: ExpertTemplateService):
    from app.services.hermes_expert import expert_filesystem as fs

    monkeypatch.setattr(fs, "DOCKER_DATA_DIR", tmp_path)
    template_service.inject_template(
        instance_slug="writer-demo",
        profile="writer",
        expert_template="writer",
        instance_id="inst-001",
        instance_name="Writer Demo",
        hindsight_api_url="http://hindsight.example.com",
        hindsight_bank_id="hermes-writer",
    )
    data_dir = tmp_path / "writer-demo" / "data" / "hermes"
    marker = data_dir / "marker.txt"
    marker.write_text("old", encoding="utf-8")

    template_service.inject_template(
        instance_slug="writer-demo",
        profile="writer",
        expert_template="writer",
        instance_id="inst-002",
        instance_name="Writer Demo 2",
        hindsight_api_url="http://hindsight.example.com",
        hindsight_bank_id="hermes-writer",
    )

    backups = list(data_dir.parent.glob("hermes.backup.*"))
    assert backups
