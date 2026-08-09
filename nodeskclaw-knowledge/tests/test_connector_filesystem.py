"""Filesystem connector tests."""

from pathlib import Path

import pytest

from app.connectors.filesystem.connector import FilesystemConnector, resolve_fs_path
from app.connectors.registry import get_connector_class
from app.core.exceptions import ValidationError


def test_filesystem_registered():
    assert get_connector_class("filesystem") is FilesystemConnector


def test_resolve_rejects_traversal(tmp_path: Path):
    roots = {"docs": str(tmp_path)}
    with pytest.raises(ValidationError) as exc:
        resolve_fs_path(root_alias="docs", sub_path="../../etc/passwd", roots=roots)
    assert exc.value.message_key == "errors.knowledge.connector_fs_path_escape"


def test_resolve_rejects_unknown_alias(tmp_path: Path):
    with pytest.raises(ValidationError):
        resolve_fs_path(root_alias="missing", sub_path="", roots={"docs": str(tmp_path)})


@pytest.mark.asyncio
async def test_discover_and_fetch_with_globs(tmp_path: Path):
    (tmp_path / "a.md").write_text("hello", encoding="utf-8")
    (tmp_path / "b.txt").write_text("world", encoding="utf-8")
    (tmp_path / "skip.bin").write_bytes(b"\x00\x01")

    connector = FilesystemConnector(
        {"root_alias": "docs", "include_globs": ["*.md", "*.txt"], "exclude_globs": ["skip.*"]},
        roots={"docs": str(tmp_path)},
    )
    assert await connector.test_connection() == {"ok": True, "root": str(tmp_path.resolve())}
    page = await connector.discover()
    ids = {o.external_object_id for o in page.objects}
    assert ids == {"a.md", "b.txt"}
    assert page.has_more is False

    fetched = await connector.fetch(page.objects[0])
    assert fetched.size == 5
    assert fetched.sha256
    assert fetched.file_name in {"a.md", "b.txt"}
    await connector.close()


@pytest.mark.asyncio
async def test_symlink_escape_rejected(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "secret.txt"
    target.write_text("secret", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    link = root / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink not permitted")

    connector = FilesystemConnector({"root_alias": "docs"}, roots={"docs": str(root)})
    page = await connector.discover()
    assert page.objects == []
