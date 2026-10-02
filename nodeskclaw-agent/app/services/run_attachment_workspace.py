from __future__ import annotations

import shutil
from pathlib import Path

_REJECTED_DIR_NAMES = frozenset({"attachments", "skills", "skill-inbox"})


def safe_basename(original_name: str, attachment_ref: str) -> str:
    normalized = str(original_name or "").replace("\\", "/")
    base = normalized.split("/")[-1].strip()
    if base in {"", ".", ".."}:
        return attachment_ref
    return base


def resolve_existing_run_workspace(route_snapshot: dict, *, run_id: str | None) -> Path | None:
    raw = route_snapshot.get("hermes_run_workspace")
    if not isinstance(raw, str) or not raw.strip() or not run_id:
        return None
    path = Path(raw)
    if path.name in _REJECTED_DIR_NAMES or path.name != run_id:
        return None
    if not path.is_dir():
        return None
    return path


def stage_run_attachments(run_dir: Path, files: list[dict]) -> list[str]:
    staging = run_dir / ".attachment-staging"
    visible = run_dir / "attachments"
    if staging.exists():
        shutil.rmtree(staging)
    relative_paths: list[str] = []
    refs: list[str] = []
    try:
        for item in files:
            ref = str(item["attachment_ref"])
            base = safe_basename(str(item.get("original_name") or ""), ref)
            destination = staging / ref / base
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(item["content"])
            refs.append(ref)
            relative_paths.append(f"attachments/{ref}/{base}")
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    try:
        visible.mkdir(parents=True, exist_ok=True)
        for ref in refs:
            target = visible / ref
            if target.exists():
                shutil.rmtree(target)
            shutil.move(str(staging / ref), str(target))
    except Exception:
        for ref in refs:
            shutil.rmtree(visible / ref, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
        raise
    shutil.rmtree(staging, ignore_errors=True)
    return relative_paths
