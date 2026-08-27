from __future__ import annotations

import os
import re
from pathlib import Path

from app.config import settings


def _env_key_for_ref(ref_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", ref_id).strip("_").upper()
    return f"SKILL_AGENT_SECRET_{cleaned}"


class SecretStore:
    """Resolve SecretRef plaintext from local files or test env fallback.

    Plaintext must never be logged.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root if root is not None else settings.SKILL_AGENT_SECRET_STORE)

    def resolve(self, ref_id: str) -> str | None:
        if not ref_id:
            return None
        for candidate in (self.root / ref_id, self.root / f"{ref_id}.txt"):
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8").strip()
        env_value = os.environ.get(_env_key_for_ref(ref_id))
        if env_value is not None and env_value.strip():
            return env_value.strip()
        return None
