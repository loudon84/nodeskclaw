import pytest

from app.core.exceptions import BadRequestError
from app.services.genehub_bundle_service import build_bundle_from_manifest, sanitize_bundle_paths


def _sample_manifest(with_scripts: bool = False) -> dict:
    manifest = {
        "schema_version": "genehub.gene.v1",
        "slug": "contact-to-order",
        "version": "1.0.0",
        "name": "Contact To Order",
        "compatibility": [{"runtime": "hermes", "target": "desktop", "min_version": "0.9.0"}],
        "skill": {
            "name": "contact-to-order",
            "content": "---\nname: contact-to-order\n---\n\n# Skill",
        },
        "install": {
            "hermes_desktop": {
                "skill_dir": "~/.hermes/skills",
                "scripts_dir": "~/.hermes/scripts",
                "restart_required": True,
            }
        },
    }
    if with_scripts:
        manifest["scripts"] = {"parse_order.py": "print('ok')"}
    return manifest


def test_bundle_returns_files_and_scripts_arrays(monkeypatch):
    monkeypatch.setattr("app.services.genehub_bundle_service.settings.GENEHUB_BUNDLE_SIGNATURE_ENABLED", False)
    bundle = build_bundle_from_manifest(_sample_manifest(with_scripts=True))

    assert bundle["schema_version"] == "genehub.bundle.v1"
    assert isinstance(bundle["files"], list)
    assert isinstance(bundle["scripts"], list)
    assert bundle["files"][0]["relative_path"] == "skills/contact-to-order/SKILL.md"
    assert bundle["files"][0]["encoding"] == "utf-8"
    assert bundle["scripts"][0]["relative_path"] == "scripts/parse_order.py"
    assert bundle["manifest"]["gene_slug"] == "contact-to-order"
    assert bundle["manifest"]["gene_version"] == "1.0.0"
    assert bundle["manifest"]["skill_name"] == "contact-to-order"
    assert bundle["manifest"]["manifest_hash"]
    assert bundle["manifest"]["bundle_hash"]


def test_bundle_rejects_illegal_paths():
    with pytest.raises(BadRequestError):
        sanitize_bundle_paths({"../etc/passwd": "x"})

    with pytest.raises(BadRequestError):
        sanitize_bundle_paths({"C:/Windows/System32/config": "x"})

    with pytest.raises(BadRequestError):
        sanitize_bundle_paths({"//server/share/file.txt": "x"})
