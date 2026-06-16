import json
from pathlib import Path

from app.services.hermes_skill.output_manifest_parser import (
    parse_manifest_file,
    resolve_artifact_title,
    guess_artifact_type,
    extract_markdown_title,
)


def test_parse_manifest_file(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "artifacts": [
            {
                "file_name": "article.md",
                "title": "Manifest Title",
                "artifact_type": "markdown",
                "description": "desc",
            }
        ]
    }), encoding="utf-8")
    entries = parse_manifest_file(manifest)
    assert "article.md" in entries
    assert entries["article.md"].title == "Manifest Title"
    assert entries["article.md"].artifact_type == "markdown"


def test_resolve_artifact_title_priority(tmp_path: Path):
    md = tmp_path / "article.md"
    md.write_text("# Heading Title\nbody", encoding="utf-8")
    title = resolve_artifact_title(md, None, "request summary", "skill title")
    assert title == "Heading Title"


def test_guess_artifact_type():
    assert guess_artifact_type(Path("a.json")) == "json"
    assert guess_artifact_type(Path("a.pdf")) == "pdf"


def test_extract_markdown_frontmatter_title(tmp_path: Path):
    md = tmp_path / "x.md"
    md.write_text("---\ntitle: Front Title\n---\n# H1\n", encoding="utf-8")
    assert extract_markdown_title(md) == "Front Title"
