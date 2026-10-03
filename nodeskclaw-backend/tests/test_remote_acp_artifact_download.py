from unittest.mock import AsyncMock, patch

import pytest
from starlette.responses import Response

from app.api.remote_acp_ws import download_acp_artifact
from app.services.remote_acp.errors import ARTIFACT_DENIED


@pytest.mark.asyncio
async def test_artifact_download_maps_forbidden():
    user = AsyncMock()
    user.id = "u"
    org = AsyncMock()
    org.id = "o"

    class FakeResp:
        status_code = 403
        content = b""
        headers = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResp()

    with patch("app.api.remote_acp_ws.ExpertPermissionService.require", AsyncMock()):
        with patch("app.api.remote_acp_ws.httpx.AsyncClient", return_value=FakeClient()):
            result = await download_acp_artifact(
                "sales-expert",
                "run-1",
                "art-1",
                user_org=(user, org),
                db=AsyncMock(),
            )
    assert result.status_code == 403
    assert b"ARTIFACT_ACCESS_DENIED" in result.body
