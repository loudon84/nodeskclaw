import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class ManifestArtifactEntry:
    file_name: str
    title: str | None = None
    artifact_type: str | None = None
    description: str | None = None
    preview: bool | None = None
    tags: list[str] | None = None


def parse_manifest_file(manifest_path: Path) -> dict[str, ManifestArtifactEntry]:
    if not manifest_path.is_file():
        return {}
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("manifest parse failed %s: %s", manifest_path, exc)
        return {}

    entries: dict[str, ManifestArtifactEntry] = {}
    for item in raw.get("artifacts") or []:
        if not isinstance(item, dict):
            continue
        file_name = item.get("file_name")
        if not file_name:
            continue
        entries[file_name] = ManifestArtifactEntry(
            file_name=file_name,
            title=item.get("title"),
            artifact_type=item.get("artifact_type"),
            description=item.get("description"),
            preview=item.get("preview"),
            tags=item.get("tags"),
        )
    return entries


def extract_markdown_title(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _FRONTMATTER_RE.match(text)
    if match:
        for line in match.group(1).splitlines():
            if line.strip().lower().startswith("title:"):
                return line.split(":", 1)[1].strip().strip('"').strip("'")
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return None


def guess_artifact_type(path: Path) -> str:
    suffix_map = {
        ".md": "markdown",
        ".markdown": "markdown",
        ".txt": "txt",
        ".json": "json",
        ".csv": "csv",
        ".html": "html",
        ".htm": "html",
        ".pdf": "pdf",
        ".docx": "docx",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".zip": "archive",
    }
    return suffix_map.get(path.suffix.lower(), "file")


def resolve_artifact_title(
    file_path: Path,
    manifest_entry: ManifestArtifactEntry | None,
    request_summary: str | None,
    skill_title: str | None,
) -> str:
    if manifest_entry and manifest_entry.title:
        return manifest_entry.title
    if file_path.suffix.lower() in (".md", ".markdown"):
        md_title = extract_markdown_title(file_path)
        if md_title:
            return md_title
    stem = file_path.stem
    if stem:
        return stem
    if request_summary:
        return request_summary
    if skill_title:
        return skill_title
    return file_path.name
