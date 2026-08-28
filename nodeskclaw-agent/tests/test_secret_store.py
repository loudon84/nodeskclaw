from __future__ import annotations

from pathlib import Path

from app.services.secret_store import SecretStore


def test_resolve_from_temp_dir_file(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.secret_store.settings.SKILL_AGENT_SECRET_STORE", str(tmp_path))
    secret_file = tmp_path / "ref-crm-token"
    secret_file.write_text("  plain-secret-value  \n", encoding="utf-8")

    store = SecretStore(root=tmp_path)
    assert store.resolve("ref-crm-token") == "plain-secret-value"


def test_resolve_from_txt_suffix_and_env_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("app.services.secret_store.settings.SKILL_AGENT_SECRET_STORE", str(tmp_path))
    (tmp_path / "abc.txt").write_text("from-file\n", encoding="utf-8")
    store = SecretStore(root=tmp_path)
    assert store.resolve("abc") == "from-file"

    monkeypatch.setenv("SKILL_AGENT_SECRET_ENV_ONLY_REF", "env-secret")
    assert SecretStore(root=tmp_path).resolve("env-only-ref") == "env-secret"


def test_resolve_fail_closed_raises(tmp_path: Path):
    store = SecretStore(root=tmp_path)
    import pytest
    with pytest.raises(RuntimeError, match="fail-closed"):
        store.resolve("non-existent-secret-ref", fail_closed=True)
    assert store.resolve("non-existent-secret-ref", fail_closed=False) is None


def test_secret_store_does_not_mint_leases_and_strictly_resolves_refs(tmp_path: Path):
    store = SecretStore(root=tmp_path)
    # SecretStore only has resolve method, does not own lease minting or backend token generation
    assert hasattr(store, "resolve")
    assert not hasattr(store, "mint_lease")
    assert not hasattr(store, "create_lease")
    import pytest
    with pytest.raises(RuntimeError, match="empty secret ref_id"):
        store.resolve("", fail_closed=True)
