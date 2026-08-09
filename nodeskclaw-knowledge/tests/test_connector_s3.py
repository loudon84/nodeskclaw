"""S3 compatible connector tests with mocked boto3."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.connectors.registry import get_connector_class
from app.connectors.s3.connector import S3CompatibleConnector
from app.connectors.models import SourceDescriptor


def test_s3_registered():
    assert get_connector_class("s3_compatible") is S3CompatibleConnector


@pytest.mark.asyncio
async def test_s3_discover_paginate_and_fetch():
    client = MagicMock()
    client.list_objects_v2.side_effect = [
        {
            "Contents": [
                {
                    "Key": "docs/a.pdf",
                    "Size": 3,
                    "ETag": '"etag-a"',
                    "LastModified": datetime(2026, 1, 1, tzinfo=UTC),
                }
            ],
            "IsTruncated": True,
            "NextContinuationToken": "tok-2",
        },
        {
            "Contents": [
                {
                    "Key": "docs/b.pdf",
                    "Size": 4,
                    "ETag": '"etag-b"',
                    "VersionId": "v-b",
                    "LastModified": datetime(2026, 1, 2, tzinfo=UTC),
                }
            ],
            "IsTruncated": False,
        },
    ]
    body = MagicMock()
    body.read.return_value = b"abc"
    client.get_object.return_value = {"Body": body, "ContentType": "application/pdf"}
    client.head_bucket.return_value = {}

    connector = S3CompatibleConnector(
        {"bucket": "kb-docs", "prefix": "docs/", "page_size": 1},
        credentials={"access_key_id": "AKIAEXAMPLE", "secret_access_key": "secret"},
        client=client,
    )
    assert await connector.test_connection() == {"ok": True, "bucket": "kb-docs"}

    page1 = await connector.discover()
    assert len(page1.objects) == 1
    assert page1.objects[0].external_object_id == "kb-docs/docs/a.pdf"
    assert page1.objects[0].external_revision == "etag-a"
    assert page1.has_more is True

    page2 = await connector.discover(cursor=page1.next_cursor)
    assert page2.objects[0].external_revision == "v-b"
    assert page2.has_more is False

    fetched = await connector.fetch(page1.objects[0])
    assert fetched.size == 3
    assert fetched.sha256
    assert fetched.file_name == "a.pdf"
    await connector.close()


@pytest.mark.asyncio
async def test_s3_identity_is_bucket_plus_key():
    client = MagicMock()
    client.list_objects_v2.return_value = {
        "Contents": [{"Key": "x/y.txt", "Size": 1, "ETag": '"e"', "LastModified": datetime.now(UTC)}],
        "IsTruncated": False,
    }
    connector = S3CompatibleConnector(
        {"bucket": "b1"},
        credentials={"access_key_id": "a", "secret_access_key": "s"},
        client=client,
    )
    page = await connector.discover()
    assert page.objects[0].external_object_id == "b1/x/y.txt"
    assert isinstance(page.objects[0], SourceDescriptor)
