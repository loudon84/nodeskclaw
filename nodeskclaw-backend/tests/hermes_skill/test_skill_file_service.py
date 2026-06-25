import sys

from app.services.hermes_agents.skill_file_service import atomic_write_text_file, remove_directory


def test_atomic_write_text_file_creates_and_overwrites(tmp_path):
    target = tmp_path / "nodeskclaw-skill-router" / "SKILL.md"
    atomic_write_text_file(target, "# v1\n", backup=True)
    assert target.read_text(encoding="utf-8") == "# v1\n"
    atomic_write_text_file(target, "# v2\n", backup=True)
    assert target.read_text(encoding="utf-8") == "# v2\n"
    backups = list(target.parent.glob("SKILL.md.bak.*"))
    assert len(backups) >= 1
    if sys.platform != "win32":
        assert (target.stat().st_mode & 0o777) == 0o644


def test_remove_directory(tmp_path):
    skill_dir = tmp_path / "nodeskclaw-skill-router"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")
    remove_directory(skill_dir)
    assert not skill_dir.exists()
