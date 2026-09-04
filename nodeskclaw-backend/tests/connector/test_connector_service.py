"""Connector Center service unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BadRequestError, ConflictError
from app.models.connector.edge_node import EdgeNode
from app.models.hermes_skill.skill_release import SkillReleaseStatus
from app.schemas.connector import EdgeNodeRead, SecretRefRead
from app.services.connector.connector_service import ConnectorService
from app.services.connector.edge_node_service import EdgeNodeService, hash_edge_bootstrap, hash_edge_token


@pytest.mark.asyncio
async def test_create_definition_rejects_duplicate_name():
    db = AsyncMock()
    service = ConnectorService(db)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = "existing-id"
    db.execute = AsyncMock(return_value=result_mock)

    with pytest.raises(ConflictError):
        await service.create_definition(
            org_id="org-1",
            name="crm_http",
            kind="rest",
        )


@pytest.mark.asyncio
async def test_soft_deleted_definition_name_can_be_recreated():
    db = AsyncMock()
    service = ConnectorService(db)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)
    db.add = MagicMock()
    db.flush = AsyncMock()

    definition = await service.create_definition(
        org_id="org-1",
        name="crm_http",
        kind="rest",
        operator_user_id="user-1",
    )
    assert definition.name == "crm_http"
    assert definition.org_id == "org-1"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_instance_rejects_plaintext_connector_credentials():
    service = ConnectorService(AsyncMock())
    service._get_definition = AsyncMock()
    service._assert_instance_name_available = AsyncMock()
    service._validate_instance_placement = AsyncMock()

    with pytest.raises(BadRequestError) as exc_info:
        await service.create_instance(
            org_id="org-1",
            definition_id="def-1",
            name="crm",
            config={"headers": {"Authorization": "Bearer plaintext-token"}},
        )

    assert exc_info.value.message_key == "errors.connector.plaintext_credentials_forbidden"


@pytest.mark.asyncio
async def test_create_instance_rejects_plaintext_x_api_key_header():
    service = ConnectorService(AsyncMock())
    service._get_definition = AsyncMock()
    service._assert_instance_name_available = AsyncMock()
    service._validate_instance_placement = AsyncMock()

    with pytest.raises(BadRequestError) as exc_info:
        await service.create_instance(
            org_id="org-1",
            definition_id="def-1",
            name="crm",
            config={"headers": {"X-Api-Key": "plaintext-token"}},
        )

    assert exc_info.value.message_key == "errors.connector.plaintext_credentials_forbidden"


@pytest.mark.asyncio
async def test_update_instance_rejects_url_with_embedded_credentials():
    db = AsyncMock()
    service = ConnectorService(db)
    instance = MagicMock(
        id="inst-1",
        org_id="org-1",
        definition_id="def-1",
        name="crm",
        placement="central",
        edge_node_id=None,
        secret_ref_id=None,
        config={"url": "https://api.example.com"},
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = instance
    db.execute = AsyncMock(return_value=result)
    service.is_instance_bound_to_published_release = AsyncMock(return_value=False)
    service._validate_instance_placement = AsyncMock()

    with pytest.raises(BadRequestError) as exc_info:
        await service.update_instance(
            org_id="org-1",
            instance_id="inst-1",
            updates={"config": {"url": "https://user:password@example.com"}},
        )

    assert exc_info.value.message_key == "errors.connector.plaintext_credentials_forbidden"


def test_secret_ref_read_excludes_plaintext_fields():
    data = SecretRefRead.model_validate(
        {
            "id": "ref-1",
            "org_id": "org-1",
            "name": "crm-token",
            "edge_node_id": None,
            "description": "edge secret",
            "created_by": "user-1",
            "created_at": None,
        }
    ).model_dump()
    assert "token" not in data
    assert "password" not in data
    assert "plaintext" not in data
    assert data["name"] == "crm-token"


def test_edge_node_read_excludes_token_hash():
    node = EdgeNode(
        id="node-1",
        org_id="org-1",
        name="edge-1",
        status="pending",
        token_hash=hash_edge_token("secret-token"),
    )
    data = EdgeNodeRead.model_validate(node).model_dump()
    assert "token_hash" not in data
    assert "token" not in data


@pytest.mark.asyncio
async def test_update_instance_rejects_connection_params_when_published_bound():
    db = AsyncMock()
    service = ConnectorService(db)
    instance = MagicMock()
    instance.id = "inst-1"
    instance.org_id = "org-1"
    instance.definition_id = "def-1"
    instance.name = "prod"
    instance.placement = "central"
    instance.edge_node_id = None
    instance.secret_ref_id = None
    instance.config = {"url": "https://example.com"}

    instance_result = MagicMock()
    instance_result.scalar_one_or_none.return_value = instance

    bound_result = MagicMock()
    bound_result.scalar_one_or_none.return_value = "binding-1"

    db.execute = AsyncMock(side_effect=[instance_result, bound_result])

    with pytest.raises(BadRequestError) as exc_info:
        await service.update_instance(
            org_id="org-1",
            instance_id="inst-1",
            updates={"config": {"url": "https://other.example.com"}},
        )
    assert exc_info.value.message_key == "errors.connector.instance_locked_by_published_release"


@pytest.mark.asyncio
async def test_update_instance_allows_name_change_when_published_bound():
    db = AsyncMock()
    service = ConnectorService(db)
    instance = MagicMock()
    instance.id = "inst-1"
    instance.org_id = "org-1"
    instance.definition_id = "def-1"
    instance.name = "prod"
    instance.placement = "central"
    instance.edge_node_id = None
    instance.secret_ref_id = None
    instance.config = {"url": "https://example.com"}

    instance_result = MagicMock()
    instance_result.scalar_one_or_none.return_value = instance

    name_check = MagicMock()
    name_check.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(side_effect=[instance_result, name_check])
    db.flush = AsyncMock()

    updated = await service.update_instance(
        org_id="org-1",
        instance_id="inst-1",
        updates={"name": "prod-v2"},
    )
    assert updated.name == "prod-v2"


@pytest.mark.asyncio
async def test_register_edge_node_returns_plain_token_once():
    db = AsyncMock()
    service = EdgeNodeService(db)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)
    db.add = MagicMock()
    db.flush = AsyncMock()

    node, bootstrap, expires_at = await service.register(org_id="org-1", name="edge-1", operator_user_id="user-1")
    assert bootstrap
    assert expires_at
    assert node.token_hash == hash_edge_bootstrap(bootstrap)
    assert node.token_hash != bootstrap


@pytest.mark.asyncio
async def test_is_instance_bound_to_published_release():
    db = AsyncMock()
    service = ConnectorService(db)
    bound_result = MagicMock()
    bound_result.scalar_one_or_none.return_value = "binding-1"
    db.execute = AsyncMock(return_value=bound_result)

    assert await service.is_instance_bound_to_published_release("inst-1") is True

    bound_result.scalar_one_or_none.return_value = None
    assert await service.is_instance_bound_to_published_release("inst-1") is False


def test_skill_release_status_published_constant():
    assert SkillReleaseStatus.PUBLISHED.value == "published"


@pytest.mark.asyncio
async def test_enqueue_edge_job_idempotency():
    db = AsyncMock()
    service = EdgeNodeService(db)

    # 1. Existing job found
    existing_job = MagicMock()
    existing_job.id = "job-1"
    res1 = MagicMock()
    res1.scalar_one_or_none.return_value = existing_job
    db.execute = AsyncMock(return_value=res1)

    job = await service.enqueue_edge_job(
        org_id="org-1",
        edge_node_id="node-1",
        run_id="run-1",
        tool_name="tool-1",
    )
    assert job.id == "job-1"

    # 2. No existing job -> create
    res2 = MagicMock()
    res2.scalar_one_or_none.return_value = None
    node_mock = MagicMock()
    node_mock.id = "node-1"
    node_res = MagicMock()
    node_res.scalar_one_or_none.return_value = node_mock
    db.execute = AsyncMock(side_effect=[res2, node_res])
    db.add = MagicMock()
    db.flush = AsyncMock()

    new_job = await service.enqueue_edge_job(
        org_id="org-1",
        edge_node_id="node-1",
        run_id="run-2",
        tool_name="tool-1",
        arguments={"x": 1},
    )
    assert new_job.run_id == "run-2"
    db.add.assert_called_once()

