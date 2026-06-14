import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.services.mcp_skill_gateway.hermes_instance_resolver import resolve_instance_ref


def _make_instance(instance_id: str, profile: str) -> MagicMock:
    instance = MagicMock()
    instance.id = instance_id
    instance.slug = profile
    instance.name = profile
    instance.advanced_config = (
        f'{{"profile": "{profile}", "external_container_name": "hermes-{profile}"}}'
    )
    return instance


@pytest.mark.asyncio
async def test_resolve_instance_ref_not_found():
    user = MagicMock()
    user.id = "user-1"
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.hermes_instance_resolver.list_external_docker_instances",
        return_value=[],
    ):
        with pytest.raises(NotFoundError):
            await resolve_instance_ref("missing", "org-1", user, db)


@pytest.mark.asyncio
async def test_resolve_instance_ref_ambiguous():
    user = MagicMock()
    user.id = "user-1"
    db = AsyncMock()
    instances = [_make_instance("inst-1", "dup"), _make_instance("inst-2", "dup")]

    with patch(
        "app.services.mcp_skill_gateway.hermes_instance_resolver.list_external_docker_instances",
        return_value=instances,
    ):
        with pytest.raises(BadRequestError) as exc_info:
            await resolve_instance_ref("dup", "org-1", user, db)

    assert exc_info.value.message_key == "errors.external_docker.instance_ambiguous"


@pytest.mark.asyncio
async def test_resolve_default_instance_single_accessible():
    user = MagicMock()
    user.id = "user-1"
    db = AsyncMock()
    instance = _make_instance("inst-1", "only-one")

    with patch(
        "app.services.mcp_skill_gateway.hermes_instance_resolver.list_external_docker_instances",
        return_value=[instance],
    ), patch(
        "app.services.mcp_skill_gateway.hermes_instance_resolver._filter_accessible_instances",
        return_value=[instance],
    ):
        resolved = await resolve_instance_ref(None, "org-1", user, db)

    assert resolved.id == "inst-1"


@pytest.mark.asyncio
async def test_resolve_instance_ref_forbidden():
    user = MagicMock()
    user.id = "user-1"
    db = AsyncMock()
    instance = _make_instance("inst-1", "locked")

    with patch(
        "app.services.mcp_skill_gateway.hermes_instance_resolver.list_external_docker_instances",
        return_value=[instance],
    ), patch(
        "app.services.mcp_skill_gateway.hermes_instance_resolver.instance_member_service.check_instance_access",
        side_effect=ForbiddenError("无权限", "errors.member.permission_denied"),
    ):
        with pytest.raises(ForbiddenError) as exc_info:
            await resolve_instance_ref("locked", "org-1", user, db)

    assert exc_info.value.message_key == "errors.external_docker.instance_forbidden"
