import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.models.conversation import Conversation
from app.models.corridor import HexConnection
from app.models.node_card import NodeCard
from app.models.organization import Organization
from app.models.user import User
from app.models.workspace import Workspace
from app.services import conversation_service

TEST_DATABASE_URL = "postgresql+asyncpg://nodeskclaw:nodeskclaw@localhost:5432/nodeskclaw_test"
engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def require_test_db():
    try:
        async with engine.connect():
            yield
    except Exception:
        pytest.skip("PostgreSQL test database is not available")


async def _create_workspace(db: AsyncSession, workspace_id: str) -> None:
    org = Organization(id=f"org-{workspace_id}", name="Org", slug=f"org-{workspace_id}")
    user = User(id=f"user-{workspace_id}", name="Tester", username=f"tester-{workspace_id}")
    workspace = Workspace(
        id=workspace_id,
        org_id=org.id,
        name="Workspace",
        description="",
        color="#111111",
        icon="bot",
        created_by=user.id,
    )
    db.add_all([org, user])
    await db.flush()
    db.add(workspace)
    await db.flush()


def _node(
    workspace_id: str,
    node_id: str,
    node_type: str,
    q: int,
    r: int,
    name: str,
) -> NodeCard:
    return NodeCard(
        id=f"card-{node_id}",
        workspace_id=workspace_id,
        node_id=node_id,
        node_type=node_type,
        hex_q=q,
        hex_r=r,
        name=name,
    )


def _connection(workspace_id: str, conn_id: str, aq: int, ar: int, bq: int, br: int) -> HexConnection:
    return HexConnection(
        id=f"conn-{conn_id}",
        workspace_id=workspace_id,
        hex_a_q=aq,
        hex_a_r=ar,
        hex_b_q=bq,
        hex_b_r=br,
        direction="both",
    )


async def _conversation_rows(db: AsyncSession, workspace_id: str) -> list[Conversation]:
    return await conversation_service.list_conversations(workspace_id, db)


@pytest.mark.asyncio
async def test_blackboard_conversation_exists_without_agents():
    async with TestSessionLocal() as db:
        workspace_id = "ws-conv-empty-bb"
        await _create_workspace(db, workspace_id)
        db.add(_node(workspace_id, "blackboard-1", "blackboard", 0, 0, "Blackboard"))
        await db.flush()

        conversations = await conversation_service.sync_conversations_from_topology(workspace_id, db)
        await db.commit()

        assert len(conversations) == 1
        blackboard = conversations[0]
        assert blackboard.is_blackboard_group is True
        assert blackboard.member_node_ids == []


@pytest.mark.asyncio
async def test_corridor_conversation_exists_with_one_agent():
    async with TestSessionLocal() as db:
        workspace_id = "ws-conv-one-corridor"
        await _create_workspace(db, workspace_id)
        db.add_all([
            _node(workspace_id, "blackboard-1", "blackboard", 0, 0, "Blackboard"),
            _node(workspace_id, "corridor-1", "corridor", 2, 0, "Corridor"),
            _node(workspace_id, "agent-1", "agent", 3, 0, "Agent One"),
            _connection(workspace_id, "corridor-agent", 2, 0, 3, 0),
        ])
        await db.flush()

        await conversation_service.sync_conversations_from_topology(workspace_id, db)
        await db.commit()

        conversations = await _conversation_rows(db, workspace_id)
        blackboard = next(c for c in conversations if c.is_blackboard_group)
        corridor = next(c for c in conversations if not c.is_blackboard_group)
        assert blackboard.member_node_ids == []
        assert corridor.member_node_ids == ["agent-1"]


@pytest.mark.asyncio
async def test_single_agent_can_have_blackboard_and_corridor_conversations():
    async with TestSessionLocal() as db:
        workspace_id = "ws-conv-two-groups"
        await _create_workspace(db, workspace_id)
        db.add_all([
            _node(workspace_id, "blackboard-1", "blackboard", 0, 0, "Blackboard"),
            _node(workspace_id, "agent-1", "agent", 1, 0, "Agent One"),
            _node(workspace_id, "corridor-1", "corridor", 2, 0, "Corridor"),
            _connection(workspace_id, "blackboard-agent", 0, 0, 1, 0),
            _connection(workspace_id, "agent-corridor", 1, 0, 2, 0),
        ])
        await db.flush()

        await conversation_service.sync_conversations_from_topology(workspace_id, db)
        await db.commit()

        conversations = await _conversation_rows(db, workspace_id)
        blackboard = next(c for c in conversations if c.is_blackboard_group)
        corridor = next(c for c in conversations if not c.is_blackboard_group)
        assert blackboard.member_node_ids == ["agent-1"]
        assert corridor.member_node_ids == ["agent-1"]
        assert blackboard.member_hash != corridor.member_hash
