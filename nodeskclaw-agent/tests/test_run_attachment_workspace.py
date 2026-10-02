from pathlib import Path

import pytest

from app.services.run_attachment_workspace import (
    resolve_existing_run_workspace,
    safe_basename,
    stage_run_attachments,
)


def test_safe_basename_strips_directories_and_falls_back_to_ref():
    assert safe_basename("folder/report.pdf", "att_a") == "report.pdf"
    assert safe_basename("C:\\docs\\memo.txt", "att_a") == "memo.txt"
    assert safe_basename("../", "att_a") == "att_a"
    assert safe_basename("", "att_a") == "att_a"


def test_instance_attachment_dir_is_not_a_run_workspace(tmp_path: Path):
    attachments = tmp_path / "attachments"
    attachments.mkdir()
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    assert resolve_existing_run_workspace(
        {"hermes_run_workspace": str(attachments)},
        run_id="run-1",
    ) is None
    assert resolve_existing_run_workspace(
        {"hermes_run_workspace": str(run_dir)},
        run_id="run-1",
    ) == run_dir
    assert resolve_existing_run_workspace({}, run_id="run-1") is None


def test_stage_exposes_files_only_after_every_write(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    paths = stage_run_attachments(
        run_dir,
        [
            {"attachment_ref": "att_b", "original_name": "b/note.txt", "content": b"b"},
            {"attachment_ref": "att_a", "original_name": "a.txt", "content": b"a"},
        ],
    )
    assert paths == [
        "attachments/att_b/note.txt",
        "attachments/att_a/a.txt",
    ]
    assert (run_dir / "attachments/att_a/a.txt").read_bytes() == b"a"
    assert not (run_dir / ".attachment-staging").exists()


def test_stage_failure_leaves_visible_dir_empty(tmp_path: Path):
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    with pytest.raises(TypeError):
        stage_run_attachments(
            run_dir,
            [
                {"attachment_ref": "att_a", "original_name": "a.txt", "content": b"a"},
                {"attachment_ref": "att_b", "original_name": "b.txt", "content": None},
            ],
        )
    assert not (run_dir / "attachments").exists() or not any((run_dir / "attachments").iterdir())
    assert not (run_dir / ".attachment-staging").exists()
