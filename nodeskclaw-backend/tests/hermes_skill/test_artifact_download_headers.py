from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote

import pytest

from app.api.file_downloads import content_disposition_attachment
from app.api.hermes_skill import artifacts_router


# @lat: [[architecture/backend#Download Content-Disposition]]
def test_content_disposition_attachment_is_latin1_safe_for_chinese_filename():
    header = content_disposition_attachment("会议纪要.md")
    header.encode("latin-1")
    encoded_name = quote("会议纪要.md", safe="")
    assert header == f"attachment; filename*=UTF-8''{encoded_name}"


def test_content_disposition_attachment_keeps_ascii_filename_in_rfc5987():
    header = content_disposition_attachment("report.txt")
    header.encode("latin-1")
    assert header == "attachment; filename*=UTF-8''report.txt"


@pytest.mark.asyncio
async def test_download_artifact_object_store_chinese_filename_headers_are_latin1():
    artifact = SimpleNamespace(
        file_name="会议纪要.md",
        content_type="text/markdown",
        task_id="task-1",
    )
    user = SimpleNamespace(id="user-1", name="tester")
    org = SimpleNamespace(id="org-1")
    service = MagicMock()
    service.get_artifact = AsyncMock(return_value=artifact)
    service.download = AsyncMock(return_value=(artifact, b"# notes\n"))

    with (
        patch.object(artifacts_router, "ArtifactService", return_value=service),
        patch.object(artifacts_router.PermissionChecker, "require_permission", AsyncMock()),
        patch.object(artifacts_router, "_assert_task_owner_for_artifact", AsyncMock()),
    ):
        response = await artifacts_router.download_artifact(
            "art-1",
            user_org=(user, org),
            db=MagicMock(),
        )

    header = response.headers["content-disposition"]
    header.encode("latin-1")
    assert "filename*=UTF-8''" in header
    assert quote("会议纪要.md", safe="") in header
    assert "会议" not in header
