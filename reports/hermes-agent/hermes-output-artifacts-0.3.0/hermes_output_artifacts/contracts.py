"""Native run finalizer values shared with the Hermes Core contract."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

_CHECKSUM = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class NativeRunFinalizeRequest:
    schema_version: int
    run_id: str
    session_id: str | None
    proposed_status: str
    fields: Mapping[str, Any] = field(default_factory=dict)
    workspace_root: Path | None = None

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported native finalizer schema version")
        if not self.run_id.strip():
            raise ValueError("run_id is required")
        object.__setattr__(self, "fields", MappingProxyType(dict(self.fields)))
        if self.workspace_root is not None:
            object.__setattr__(self, "workspace_root", Path(self.workspace_root))


@dataclass(frozen=True)
class NativeOutputRef:
    name: str
    content_type: str
    url: str
    required: bool
    size_bytes: int
    checksum_sha256: str
    expires_at: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("output ref name is required")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("output ref URL must be absolute http(s)")
        if self.size_bytes < 0:
            raise ValueError("output ref size cannot be negative")
        if not _CHECKSUM.fullmatch(self.checksum_sha256):
            raise ValueError(
                "output ref checksum_sha256 must be a lowercase SHA-256 hex digest"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "content_type": self.content_type,
            "url": self.url,
            "required": self.required,
            "size_bytes": self.size_bytes,
            "checksum_sha256": self.checksum_sha256,
            "expires_at": self.expires_at,
        }


@dataclass(frozen=True)
class NativeRunFinalizeResult:
    outcome: Literal["ready", "failed"]
    output_refs: tuple[NativeOutputRef, ...] = ()
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def ready(
        cls, output_refs: tuple[NativeOutputRef, ...] = ()
    ) -> NativeRunFinalizeResult:
        return cls(outcome="ready", output_refs=output_refs)

    @classmethod
    def failed(
        cls,
        error_code: str,
        error_message: str,
        output_refs: tuple[NativeOutputRef, ...] = (),
    ) -> NativeRunFinalizeResult:
        return cls(
            outcome="failed",
            output_refs=output_refs,
            error_code=error_code,
            error_message=error_message,
        )
