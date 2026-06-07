import pytest

from app.core.security import get_current_user
from app.main import app
from app.services.hermes_expert.expert_template_service import ExpertTemplateService


class _User:
    id = "user-1"
    current_org_id = "org-1"


@pytest.mark.asyncio
async def test_list_templates_api(client):
    app.dependency_overrides[get_current_user] = lambda: _User()
    try:
        response = await client.get("/api/v1/hermes-experts/templates")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()["data"]
    slugs = {item["slug"] for item in payload}
    assert slugs == {"writer", "finance"}


def test_template_service_matches_api_contract():
    templates = ExpertTemplateService().list_templates()
    assert all(item.version == "0.1.0" for item in templates)
    assert all(item.files for item in templates)
