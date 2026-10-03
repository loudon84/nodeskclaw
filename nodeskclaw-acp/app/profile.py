from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.errors import profile_invalid

SECRET_KEYS = frozenset({
    "access_token",
    "refresh_token",
    "password",
    "oauth_token",
    "composio_key",
    "connector_credential",
    "token",
})


class Profile:
    def __init__(self, data: dict[str, Any], path: str):
        self.path = path
        self.profile_version = int(data.get("profile_version") or 1)
        self.name = str(data.get("name") or "").strip()
        self.agent_ref = str(data.get("agent_ref") or "").strip()
        self.knowledge_refs = list(data.get("knowledge_refs") or [])
        self.connector_binding_refs = list(data.get("connector_binding_refs") or [])
        self.integration_account_refs = list(data.get("integration_account_refs") or [])
        extra = set(data) - {
            "profile_version",
            "name",
            "agent_ref",
            "knowledge_refs",
            "connector_binding_refs",
            "integration_account_refs",
        }
        if extra & SECRET_KEYS:
            raise profile_invalid("profile 不得包含密钥字段")
        if "attachment_refs" in extra:
            raise profile_invalid("profile 不得包含 attachment_refs")
        if self.profile_version != 1 or not self.name or not self.agent_ref:
            raise profile_invalid("profile 无效")


def load_profile(path: str | Path) -> Profile:
    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise profile_invalid("profile 必须是对象")
    return Profile(data, str(path))
