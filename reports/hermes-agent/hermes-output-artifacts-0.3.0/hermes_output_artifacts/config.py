"""Plugin configuration loaded from the Hermes plugin context."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

_OBJECT_KEY_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


class PluginConfigContext(Protocol):
    def get_config(self, key: str, default: Any = None) -> Any: ...


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expected an integer setting, got {value!r}") from exc
    if parsed <= 0:
        raise ValueError("integer settings must be positive")
    return parsed


def _as_strings(value: Any, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    if value is None:
        return default
    values = value.split(",") if isinstance(value, str) else value
    if not isinstance(values, (list, tuple)):
        raise TypeError("list settings must be a list or a comma-separated string")
    return tuple(str(item).strip() for item in values if str(item).strip())


def _normalise_extensions(value: Any) -> tuple[str, ...]:
    return tuple(
        item.lower() if item.startswith(".") else f".{item.lower()}"
        for item in _as_strings(value)
    )


def _environment_value(environment: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = environment.get(name, "").strip()
        if value:
            return value
    return ""


@dataclass(frozen=True)
class ArtifactSettings:
    enabled: bool
    endpoint: str
    bucket: str
    region: str
    prefix: str
    instance_id: str
    addressing_style: str
    presign_expires_seconds: int
    access_key: str
    secret_key: str
    ext_allow: tuple[str, ...]
    exclude_patterns: tuple[str, ...]
    max_single_bytes: int
    max_total_bytes: int
    max_files: int
    required_default: bool
    upload_mode: str = "s3"
    presign: bool = True
    public_base_url: str = ""
    upload_url: str = ""
    upload_token: str = ""

    @classmethod
    def from_context(
        cls,
        context: PluginConfigContext,
        environment: Mapping[str, str] | None = None,
    ) -> ArtifactSettings:
        getter = getattr(context, "get_config", None)
        if not callable(getter):
            raise TypeError("Hermes PluginContext.get_config() is required")

        env = os.environ if environment is None else environment
        enabled = _as_bool(getter("enabled", None), False) or _as_bool(
            _environment_value(env, "HERMES_OUTPUT_ARTIFACTS_ENABLED"), False
        )
        endpoint = str(getter("s3_endpoint", "") or "").strip().rstrip("/")
        if not endpoint:
            endpoint = _environment_value(
                env, "HERMES_ARTIFACT_S3_ENDPOINT", "MINIO_ENDPOINT_URL"
            ).rstrip("/")
        bucket = str(getter("s3_bucket", "") or "").strip()
        if not bucket:
            bucket = _environment_value(
                env, "HERMES_ARTIFACT_S3_BUCKET", "MINIO_BUCKET"
            ) or "agent-runtime-export"
        region = str(getter("s3_region", "") or "").strip() or _environment_value(
            env, "HERMES_ARTIFACT_S3_REGION", "MINIO_REGION"
        ) or "us-east-1"
        prefix = str(getter("s3_prefix", "") or "").strip().strip("/")
        if not prefix:
            prefix = _environment_value(env, "HERMES_ARTIFACT_S3_PREFIX") or "artifacts"
        instance_id = str(getter("instance_id", "default") or "").strip()
        addressing_style = (
            str(getter("s3_addressing", "") or "").strip().lower()
            or _environment_value(env, "HERMES_ARTIFACT_S3_ADDRESSING")
            or "path"
        )
        access_key = _environment_value(
            env, "HERMES_ARTIFACT_S3_ACCESS_KEY", "MINIO_ACCESS_KEY"
        )
        secret_key = _environment_value(
            env, "HERMES_ARTIFACT_S3_SECRET_KEY", "MINIO_SECRET_KEY"
        )
        upload_mode = (
            str(getter("upload_mode", "") or "").strip().lower()
            or _environment_value(env, "HERMES_ARTIFACT_UPLOAD_MODE")
            or "s3"
        )
        if upload_mode == "minio":
            upload_mode = "s3"
        presign = _as_bool(
            getter("s3_presign", None),
            _as_bool(_environment_value(env, "HERMES_ARTIFACT_S3_PRESIGN"), True),
        )
        public_base_url = str(getter("public_base_url", "") or "").strip().rstrip(
            "/"
        ) or _environment_value(env, "HERMES_ARTIFACT_PUBLIC_BASE_URL")
        upload_url = str(getter("upload_url", "") or "").strip() or _environment_value(
            env, "HERMES_ARTIFACT_UPLOAD_URL"
        )
        upload_token = _environment_value(env, "HERMES_ARTIFACT_UPLOAD_TOKEN")
        settings = cls(
            enabled=enabled,
            endpoint=endpoint,
            bucket=bucket,
            region=region,
            prefix=prefix,
            instance_id=instance_id,
            addressing_style=addressing_style,
            presign_expires_seconds=_as_int(
                getter("s3_presign_expires", None)
                or _environment_value(env, "HERMES_ARTIFACT_S3_PRESIGN_EXPIRES")
                or 3600,
                3600,
            ),
            access_key=access_key,
            secret_key=secret_key,
            ext_allow=_normalise_extensions(
                getter("ext_allow", None)
                or _environment_value(env, "HERMES_ARTIFACT_EXT_ALLOW")
                or ()
            ),
            exclude_patterns=_as_strings(getter("exclude_patterns", ())),
            max_single_bytes=_as_int(
                getter("max_single_bytes", None)
                or _environment_value(env, "HERMES_ARTIFACT_MAX_BYTES")
                or 10_485_760,
                10_485_760,
            ),
            max_total_bytes=_as_int(getter("max_total_bytes", 52_428_800), 52_428_800),
            max_files=_as_int(getter("max_files", 20), 20),
            required_default=_as_bool(
                getter("required_default", None),
                _as_bool(
                    _environment_value(env, "HERMES_ARTIFACT_REQUIRED_DEFAULT"), True
                ),
            ),
            upload_mode=upload_mode,
            presign=presign,
            public_base_url=public_base_url,
            upload_url=upload_url,
            upload_token=upload_token,
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.enabled:
            return
        if self.upload_mode not in {"s3", "http"}:
            raise ValueError("upload_mode must be s3 or http")
        if not _OBJECT_KEY_SEGMENT.fullmatch(self.instance_id):
            raise ValueError("instance_id must be a single safe object-key segment")
        if self.max_total_bytes < self.max_single_bytes:
            raise ValueError("max_total_bytes must be at least max_single_bytes")
        if self.upload_mode == "http":
            parsed = urlparse(self.upload_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("upload_url must be an absolute http(s) URL")
            return
        parsed = urlparse(self.endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("s3_endpoint must be an absolute http(s) URL")
        if not self.bucket or "/" in self.bucket:
            raise ValueError("s3_bucket must be a non-empty bucket name")
        if self.addressing_style not in {"path", "virtual"}:
            raise ValueError("s3_addressing must be path or virtual")
        if not self.access_key:
            raise ValueError("HERMES_ARTIFACT_S3_ACCESS_KEY is required")
        if not self.secret_key:
            raise ValueError("HERMES_ARTIFACT_S3_SECRET_KEY is required")
