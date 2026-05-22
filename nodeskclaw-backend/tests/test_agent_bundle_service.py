from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.exceptions import BadRequestError
from app.models.gene import ContentVisibility, Gene, GeneSource
from app.services.agent_bundle_service import (
    build_bundle_env_vars,
    parse_agent_bundle_dir,
    summarize_agent_bundle_manifest,
)
from app.services.deploy_service import _collect_secret_env_refs
from app.services.instance_template_service import (
    _next_agent_bundle_placeholder_name,
    _suggest_agent_bundle_display_name,
    import_agent_bundle_manifest,
)
from app.services.k8s.resource_builder import build_configmap, build_deployment, build_labels

FIXTURES = Path(__file__).parent / "fixtures" / "agent_bundles"
TEST_DATABASE_URL = "postgresql+asyncpg://nodeskclaw:nodeskclaw@localhost:5432/nodeskclaw_test"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def require_test_db():
    try:
        async with engine.connect():
            yield
    except Exception:
        pytest.skip("PostgreSQL test database is not available")


@pytest.mark.parametrize(
    "name",
    [
        "p0_echo_agent",
        "p1_template_import_agent",
        "p2_stateful_local_agent",
        "p3_resource_profile_agent",
        "p4_oauth_probe_agent",
        "p5_video_clone_mock_agent",
        "p5_video_clone_real_sanitized",
    ],
)
def test_parse_valid_agent_bundle_fixtures(name: str) -> None:
    manifest = parse_agent_bundle_dir(FIXTURES / name)

    assert manifest["schema_version"] == 1
    assert manifest["slug"]
    assert manifest["files"]["AGENT.md"]
    assert manifest["files"]["SOUL.md"]
    assert len(manifest["skills"]) >= 1
    assert manifest["skills"][0]["description"]


@pytest.mark.parametrize(
    "name, message",
    [
        ("invalid_missing_soul", "SOUL.md"),
        ("invalid_secret_in_config", "明文密钥"),
        ("invalid_script_path", "非法脚本路径"),
        ("invalid_bad_skill_frontmatter", "缺少 description"),
    ],
)
def test_parse_invalid_agent_bundle_fixtures(name: str, message: str) -> None:
    with pytest.raises(BadRequestError) as exc:
        parse_agent_bundle_dir(FIXTURES / name)

    assert message in exc.value.message


def test_agent_bundle_summary_hides_file_content() -> None:
    manifest = parse_agent_bundle_dir(FIXTURES / "p2_stateful_local_agent")
    summary = summarize_agent_bundle_manifest(manifest)

    assert summary is not None
    assert "files" in summary
    assert "skills/stateful/scripts/run_stateful.py" in summary["files"]
    assert "print(os.environ" not in str(summary)


def test_bundle_env_vars_filter_secret_values_and_keep_refs() -> None:
    manifest = parse_agent_bundle_dir(FIXTURES / "p4_oauth_probe_agent")
    env = build_bundle_env_vars(manifest, manifest["slug"], instance_id="inst-1")

    assert env["NODESKCLAW_AGENT_BUNDLE_DIR"] == "/root/.openclaw/agent-bundles/p4-oauth-probe-agent"
    assert env["NODESKCLAW_AGENT_STATE_DIR"] == "/root/.openclaw/agent-state/inst-1"
    assert env["OAUTH_TOKEN_REF"] == "mock-oauth-token/access_token"
    assert "OAUTH_ACCESS_TOKEN" not in env
    assert "NODESKCLAW_SECRET_REFS" in env


def test_secret_env_refs_are_injected_as_k8s_secret_refs_not_configmap_data() -> None:
    manifest = parse_agent_bundle_dir(FIXTURES / "p4_oauth_probe_agent")
    refs = _collect_secret_env_refs(manifest)
    labels = build_labels("agent", "inst-1", "v1")

    configmap = build_configmap("agent-config", "ns", {"VISIBLE": "1"}, labels)
    deployment = build_deployment(
        name="agent",
        namespace="ns",
        image="example/agent:v1",
        replicas=1,
        labels=labels,
        configmap_name="agent-config",
        env_vars={"VISIBLE": "1"},
        advanced_config={"secret_env_refs": refs},
    )

    env_by_name = {item.name: item for item in deployment.spec.template.spec.containers[0].env}
    assert configmap.data == {"VISIBLE": "1"}
    assert "OAUTH_ACCESS_TOKEN" not in configmap.data
    assert env_by_name["OAUTH_ACCESS_TOKEN"].value_from.secret_key_ref.name == "mock-oauth-token"
    assert env_by_name["OAUTH_ACCESS_TOKEN"].value_from.secret_key_ref.key == "access_token"


def test_agent_bundle_display_name_uses_only_explicit_display_name() -> None:
    video_manifest = parse_agent_bundle_dir(FIXTURES / "p5_video_clone_mock_agent")
    explicit_manifest = {
        "name": "plain-text-skills-agent",
        "slug": "plain-text-skills-agent",
        "description": "",
        "config": {"display_name": "文本编辑助理"},
    }

    assert _suggest_agent_bundle_display_name(video_manifest) is None
    assert _suggest_agent_bundle_display_name(explicit_manifest) == "文本编辑助理"


def test_agent_bundle_placeholder_name_uses_next_expert_index() -> None:
    assert _next_agent_bundle_placeholder_name([]) == "专家1"
    assert _next_agent_bundle_placeholder_name(["专家1", "数字人视频复刻专家"]) == "专家2"
    assert _next_agent_bundle_placeholder_name(["专家1", "专家2", "专家4"]) == "专家3"


@pytest.mark.asyncio
async def test_import_agent_bundle_creates_private_template_and_genes(require_test_db) -> None:
    manifest = parse_agent_bundle_dir(FIXTURES / "p1_template_import_agent")

    async with TestSessionLocal() as db:
        template = await import_agent_bundle_manifest(
            db,
            manifest,
            user_id="user-agent-bundle",
            org_id="org-agent-bundle",
        )

        assert template.template_type == "agent_bundle"
        assert template.name == "专家1"
        assert template.slug == "p1-template-import-agent"
        assert template.agent_bundle is not None
        assert template.agent_bundle["name"] == "Template Import Agent"
        assert template.agent_bundle["files"] == ["AGENT.md", "SOUL.md", "config.json", "skills/importer/SKILL.md"]
        assert template.gene_slugs

        result = await db.execute(select(Gene).where(Gene.slug.in_(template.gene_slugs)))
        genes = list(result.scalars().all())

        assert len(genes) == len(template.gene_slugs)
        assert all(g.source == GeneSource.agent for g in genes)
        assert all(g.visibility == ContentVisibility.org_private for g in genes)
        assert all(g.is_published is False for g in genes)
