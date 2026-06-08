import json

import pytest

from app.core.exceptions import BadRequestError
from app.services.genehub_bundle_service import (
    build_bundle_from_manifest,
    sanitize_bundle_paths,
    validate_manifest,
    validate_skill_name,
)


def _sample_manifest() -> dict:
    return {
        "schema_version": "genehub.gene.v1",
        "slug": "contact-to-order",
        "version": "1.0.0",
        "name": "Contact To Order",
        "compatibility": [{"runtime": "hermes", "target": "desktop", "min_version": "0.9.0"}],
        "skill": {
            "name": "contact-to-order",
            "content": "---\nname: contact-to-order\n---\n",
        },
        "install": {
            "hermes_desktop": {
                "skill_dir": "~/.hermes/skills",
                "scripts_dir": "~/.hermes/scripts",
                "restart_required": True,
            }
        },
    }


def test_validate_skill_name_rejects_hidden():
    with pytest.raises(BadRequestError):
        validate_skill_name(".hidden")


def test_validate_skill_name_rejects_path_separator():
    with pytest.raises(BadRequestError):
        validate_skill_name("bad/name")


def test_sanitize_bundle_paths_rejects_absolute_path():
    with pytest.raises(BadRequestError):
        sanitize_bundle_paths({"/etc/passwd": "x"})


def test_sanitize_bundle_paths_rejects_traversal():
    with pytest.raises(BadRequestError):
        sanitize_bundle_paths({"../secret.txt": "x"})


def test_validate_manifest_requires_hermes_desktop_install():
    manifest = _sample_manifest()
    del manifest["install"]["hermes_desktop"]
    with pytest.raises(BadRequestError):
        validate_manifest(manifest)


def test_build_bundle_from_manifest_without_signing_secret(monkeypatch):
    monkeypatch.setattr("app.services.genehub_bundle_service.settings.GENEHUB_BUNDLE_SIGNATURE_ENABLED", True)
    monkeypatch.setattr("app.services.genehub_bundle_service.settings.GENEHUB_BUNDLE_SIGNING_SECRET", "")
    with pytest.raises(BadRequestError):
        build_bundle_from_manifest(_sample_manifest())


def test_build_bundle_from_manifest_with_signing(monkeypatch):
    monkeypatch.setattr("app.services.genehub_bundle_service.settings.GENEHUB_BUNDLE_SIGNATURE_ENABLED", True)
    monkeypatch.setattr("app.services.genehub_bundle_service.settings.GENEHUB_BUNDLE_SIGNING_SECRET", "test-secret")
    bundle = build_bundle_from_manifest(_sample_manifest())
    assert bundle["schema_version"] == "genehub.bundle.v1"
    assert "skills/contact-to-order/SKILL.md" in bundle["files"]
    assert bundle["hashes"]["manifest_sha256"]
    assert bundle["hashes"]["bundle_sha256"]
    assert bundle["signature"]["algorithm"] == "hmac-sha256"
    assert bundle["signature"]["value"]
