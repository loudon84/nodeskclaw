"""S3-compatible connector (MinIO / AWS S3) using boto3."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.connectors.base import ConnectorCapabilities
from app.connectors.models import DiscoveryPage, FetchedSource, SourceDescriptor
from app.connectors.registry import register
from app.core.exceptions import BadRequestError, ValidationError

# @lat: [[knowledge-objects#Connector Domain]]


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    return None


@register("s3_compatible")
class S3CompatibleConnector:
    capabilities = ConnectorCapabilities(
        incremental_cursor=False,
        stable_external_id=True,
        delete_events=False,
        folders=True,
        source_metadata=True,
        authentication=True,
    )

    def __init__(
        self,
        config: dict[str, Any],
        *,
        credentials: dict[str, Any] | None = None,
        client: Any = None,
        **_kwargs: Any,
    ) -> None:
        self.config = dict(config or {})
        self.credentials = dict(credentials or {})
        self.bucket = str(self.config.get("bucket") or "").strip()
        if not self.bucket:
            raise BadRequestError(
                message="s3_compatible 需要 bucket",
                message_key="errors.knowledge.connector_config_invalid",
            )
        self.prefix = str(self.config.get("prefix") or "").lstrip("/")
        self.endpoint_url = self.config.get("endpoint_url") or self.credentials.get("endpoint_url")
        self.region = str(self.config.get("region") or self.credentials.get("region") or "us-east-1")
        self.page_size = int(self.config.get("page_size") or 1000)
        self._client = client
        self._owns_client = client is None

    def _build_client(self) -> Any:
        access_key = self.credentials.get("access_key_id") or self.credentials.get("access_key")
        secret_key = self.credentials.get("secret_access_key") or self.credentials.get("secret_key")
        if not access_key or not secret_key:
            raise BadRequestError(
                message="缺少 S3 凭证",
                message_key="errors.knowledge.connector_credential_invalid",
            )
        session = boto3.session.Session()
        return session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            region_name=self.region,
            aws_access_key_id=str(access_key),
            aws_secret_access_key=str(secret_key),
            config=Config(signature_version="s3v4"),
        )

    def _client_or_create(self) -> Any:
        if self._client is None:
            self._client = self._build_client()
            self._owns_client = True
        return self._client

    async def test_connection(self) -> dict[str, Any]:
        client = self._client_or_create()
        try:
            client.head_bucket(Bucket=self.bucket)
        except (ClientError, BotoCoreError) as exc:
            raise BadRequestError(
                message="S3 bucket 不可用",
                message_key="errors.knowledge.connector_s3_unavailable",
            ) from exc
        return {"ok": True, "bucket": self.bucket}

    def _object_id(self, key: str) -> str:
        return f"{self.bucket}/{key}"

    def _canonical_uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{quote(key, safe='/')}"

    async def discover(self, *, cursor: dict[str, Any] | None = None) -> DiscoveryPage:
        client = self._client_or_create()
        token = (cursor or {}).get("continuation_token")
        kwargs: dict[str, Any] = {
            "Bucket": self.bucket,
            "MaxKeys": self.page_size,
        }
        if self.prefix:
            kwargs["Prefix"] = self.prefix
        if token:
            kwargs["ContinuationToken"] = token
        try:
            resp = client.list_objects_v2(**kwargs)
        except (ClientError, BotoCoreError) as exc:
            raise BadRequestError(
                message="S3 list 失败",
                message_key="errors.knowledge.connector_s3_list_failed",
            ) from exc

        objects: list[SourceDescriptor] = []
        for item in resp.get("Contents") or []:
            key = item.get("Key")
            if not key or str(key).endswith("/"):
                continue
            etag = str(item.get("ETag") or "").strip('"')
            version_id = item.get("VersionId")
            revision = str(version_id) if version_id else (etag or None)
            objects.append(
                SourceDescriptor(
                    external_object_id=self._object_id(str(key)),
                    name=str(key).rsplit("/", 1)[-1],
                    path=str(key),
                    canonical_uri=self._canonical_uri(str(key)),
                    size=int(item.get("Size") or 0),
                    external_revision=revision,
                    etag=etag or None,
                    modified_at=_parse_dt(item.get("LastModified")),
                    source_metadata={
                        "bucket": self.bucket,
                        "key": key,
                        "storage_class": item.get("StorageClass"),
                    },
                )
            )
        next_token = resp.get("NextContinuationToken")
        has_more = bool(resp.get("IsTruncated")) and bool(next_token)
        return DiscoveryPage(
            objects=objects,
            next_cursor={"continuation_token": next_token} if has_more else None,
            has_more=has_more,
        )

    async def fetch(self, descriptor: SourceDescriptor) -> FetchedSource:
        client = self._client_or_create()
        key = descriptor.path or descriptor.source_metadata.get("key")
        if not key:
            # external_object_id = bucket/key
            parts = descriptor.external_object_id.split("/", 1)
            if len(parts) != 2:
                raise ValidationError(
                    message="无效 S3 object id",
                    message_key="errors.knowledge.connector_s3_object_invalid",
                )
            key = parts[1]
        try:
            kwargs: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
            if descriptor.external_revision and descriptor.external_revision != descriptor.etag:
                kwargs["VersionId"] = descriptor.external_revision
            resp = client.get_object(**kwargs)
            body = resp["Body"].read()
        except (ClientError, BotoCoreError) as exc:
            raise BadRequestError(
                message="S3 get_object 失败",
                message_key="errors.knowledge.connector_s3_fetch_failed",
            ) from exc
        digest = hashlib.sha256(body).hexdigest()
        return FetchedSource(
            file_name=descriptor.name,
            mime_type=descriptor.mime_type or resp.get("ContentType"),
            stream=io.BytesIO(body),
            size=len(body),
            sha256=digest,
        )

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
