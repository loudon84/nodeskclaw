import json
from pathlib import Path

import pytest

from app.core.exceptions import BadRequestError
from app.models.instance import Instance
from app.services.hermes_external import model_config_service, skill_service
from app.services.hermes_external.binding_type import get_instance_binding_type
from app.services.hermes_external.path_resolver import HermesExternalPaths


def _external_instance(tmp_path: Path, slug: str = "writer") -> Instance:
    host_data_dir = tmp_path / slug / "data" / "hermes"
    host_data_dir.mkdir(parents=True)
    cfg = {
        "attach_mode": "external",
        "profile": slug,
        "paths": {"host_data_dir": str(host_data_dir)},
    }
    return Instance(
        id="inst-ext-1",
        name="External Writer",
        slug=slug,
        runtime="openclaw",
        cluster_id="cluster-1",
        namespace=f"docker-{slug}",
        org_id="org-1",
        advanced_config=json.dumps(cfg),
    )


def _platform_instance() -> Instance:
    return Instance(
        id="inst-platform-1",
        name="Platform",
        slug="platform-1",
        runtime="openclaw",
        cluster_id="cluster-1",
        namespace="ns-1",
        org_id="org-1",
        advanced_config=None,
    )


@pytest.fixture
def patch_paths(monkeypatch, tmp_path):
    def resolve_paths(instance: Instance) -> HermesExternalPaths:
        host_data_dir = tmp_path / instance.slug / "data" / "hermes"
        host_data_dir.mkdir(parents=True, exist_ok=True)
        return HermesExternalPaths(
            profile=instance.slug,
            container_name=f"hermes-{instance.slug}",
            docker_env_file=tmp_path / instance.slug / ".env",
            host_data_dir=host_data_dir,
            container_data_dir="/data/hermes",
            config_file=host_data_dir / "config.yaml",
            workspace_dir=host_data_dir / "workspace",
            profiles_dir=host_data_dir / "profiles",
            skills_dir=host_data_dir / "skills",
            skill_inbox_dir=host_data_dir / "skill-inbox",
            tools_dir=host_data_dir / "tools",
            plugins_dir=host_data_dir / "plugins",
            attachments_dir=host_data_dir / "attachments",
            logs_dir=host_data_dir / "logs",
            sessions_dir=host_data_dir / "sessions",
            backups_dir=host_data_dir / "backups",
        )

    monkeypatch.setattr("app.services.hermes_external._common.resolve_paths", resolve_paths)
    return tmp_path


@pytest.mark.asyncio
async def test_validate_model_config_valid():
    result = model_config_service.validate_model_config("default_model:\n  provider: custom:deepseek\n")
    assert result.valid is True
    assert result.parsed_preview is not None


def test_validate_model_config_invalid():
    result = model_config_service.validate_model_config("default_model:\n provider: custom\n  bad: true\n")
    assert result.valid is False


@pytest.mark.asyncio
async def test_update_model_config_saves_and_backups(patch_paths, tmp_path):
    instance = _external_instance(tmp_path)
    original = "default_model:\n  provider: custom:old\n"
    config_file = tmp_path / instance.slug / "data" / "hermes" / "config.yaml"
    config_file.write_text(original, encoding="utf-8")

    result = await model_config_service.update_model_config(
        instance,
        "default_model:\n  provider: custom:deepseek\n  default: DeepSeek-V4-pro\n",
    )
    assert result.success is True
    assert result.requires_restart is True
    assert config_file.read_text(encoding="utf-8").startswith("default_model:")
    backup_dir = tmp_path / instance.slug / "data" / "hermes" / "backups" / "config"
    assert backup_dir.is_dir()
    assert any(backup_dir.glob("config-*.yaml"))


@pytest.mark.asyncio
async def test_update_model_config_rejects_invalid_yaml(patch_paths, tmp_path):
    instance = _external_instance(tmp_path)
    config_file = tmp_path / instance.slug / "data" / "hermes" / "config.yaml"
    config_file.write_text("default_model:\n  provider: ok\n", encoding="utf-8")

    with pytest.raises(BadRequestError):
        await model_config_service.update_model_config(instance, "default_model:\n provider: bad\n  x: 1\n")

    assert config_file.read_text(encoding="utf-8") == "default_model:\n  provider: ok\n"


def test_install_builtin_bundle_and_rescan(patch_paths, tmp_path):
    instance = _external_instance(tmp_path)
    result = skill_service.install_builtin_bundle(instance, "writer")
    assert result.success is True
    assert result.requires_restart is True
    assert result.item is not None
    assert result.item.slug == "writer-outline"

    index_path = tmp_path / instance.slug / "data" / "hermes" / "skills" / ".index.json"
    assert index_path.is_file()


def test_disable_skill_sets_status(patch_paths, tmp_path):
    instance = _external_instance(tmp_path)
    skill_service.install_builtin_bundle(instance, "writer")
    result = skill_service.disable_skill(instance, "writer-outline")
    assert result.item is not None
    assert result.item.enabled is False
    assert result.requires_restart is True


def test_delete_skill_creates_backup(patch_paths, tmp_path):
    instance = _external_instance(tmp_path)
    skill_service.install_builtin_bundle(instance, "writer")
    skill_dir = tmp_path / instance.slug / "data" / "hermes" / "skills" / "writer-outline"
    assert skill_dir.is_dir()

    result = skill_service.delete_skill(instance, "writer-outline")
    assert result.success is True
    assert not skill_dir.exists()
    backup_root = tmp_path / instance.slug / "data" / "hermes" / "backups" / "skills"
    assert any(backup_root.glob("writer-outline-*"))


@pytest.mark.asyncio
async def test_install_from_git_rejects_invalid_url(patch_paths, tmp_path):
    instance = _external_instance(tmp_path)
    with pytest.raises(BadRequestError):
        await skill_service.install_from_git(instance, repo="file:///tmp/evil.git")


def test_binding_type_external_vs_platform(tmp_path):
    external = _external_instance(tmp_path)
    platform = _platform_instance()
    assert get_instance_binding_type(external) == "external_docker"
    assert get_instance_binding_type(platform) == "platform_managed"
