from __future__ import annotations

from typing import Any

from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation

DEFAULT_POLICIES: dict[str, dict[str, Any]] = {
    "customer-profiling": {
        "artifact_mode": "pull_only",
        "store_to_gateway": True,
        "format": "markdown",
        "suggested_workspace_dir": "drafts/customer",
        "filename_template": "{company}_客户画像_{date}.md",
        "kb_ingest": {
            "enabled": True,
            "mode": "pending_review",
            "knowledge_base": "general",
            "tags": ["customer", "sales"],
        },
    },
    "enterprise-risk-analysis": {
        "artifact_mode": "pull_only",
        "store_to_gateway": True,
        "format": "markdown",
        "suggested_workspace_dir": "drafts/risk",
        "filename_template": "{company}_风险评估_{date}.md",
        "kb_ingest": {
            "enabled": True,
            "mode": "pending_review",
            "knowledge_base": "general",
            "tags": ["risk", "credit"],
        },
    },
    "manufacturer-profiling": {
        "artifact_mode": "pull_only",
        "store_to_gateway": True,
        "format": "markdown",
        "suggested_workspace_dir": "drafts/manufacturer",
        "filename_template": "{company}_原厂画像_{date}.md",
        "kb_ingest": {
            "enabled": True,
            "mode": "pending_review",
            "knowledge_base": "general",
            "tags": ["manufacturer", "supplier"],
        },
    },
    "semiconductor-marketing-copy": {
        "artifact_mode": "pull_only",
        "store_to_gateway": True,
        "format": "markdown",
        "suggested_workspace_dir": "drafts/sale",
        "filename_template": "{topic}_推广文案_{date}.md",
        "kb_ingest": {
            "enabled": True,
            "mode": "pending_review",
            "knowledge_base": "general",
            "tags": ["marketing", "semiconductor"],
        },
    },
    "industry-search": {
        "artifact_mode": "pull_only",
        "store_to_gateway": True,
        "format": "markdown",
        "suggested_workspace_dir": "drafts/research",
        "filename_template": "{topic}_行业搜索报告_{date}.md",
        "kb_ingest": {
            "enabled": True,
            "mode": "pending_review",
            "knowledge_base": "general",
            "tags": ["research", "industry"],
        },
    },
    "b2b-contact-finder": {
        "artifact_mode": "pull_only",
        "store_to_gateway": True,
        "format": "markdown",
        "suggested_workspace_dir": "drafts/contact",
        "filename_template": "{company}_联系窗口清单_{date}.md",
        "kb_ingest": {
            "enabled": False,
            "mode": "manual",
            "knowledge_base": "general",
            "tags": ["contact", "sales"],
        },
    },
}

FALLBACK_POLICY: dict[str, Any] = {
    "artifact_mode": "pull_only",
    "store_to_gateway": True,
    "format": "markdown",
    "suggested_workspace_dir": "drafts/misc",
    "filename_template": "{topic}_报告_{date}.md",
    "kb_ingest": {
        "enabled": False,
        "mode": "manual",
        "knowledge_base": "general",
        "tags": [],
    },
}


def tool_short_name(tool_name: str) -> str:
    if "__" in tool_name:
        return tool_name.split("__", 1)[1]
    if tool_name.startswith("skill."):
        return tool_name.removeprefix("skill.")
    return tool_name


class OutputPolicyService:
    @staticmethod
    def resolve(
        *,
        skill: HermesSkill | None,
        installation: HermesSkillInstallation | None,
        tool_name: str,
    ) -> dict[str, Any]:
        policy: dict[str, Any] = {}

        if installation and installation.routing_metadata:
            inst_policy = installation.routing_metadata.get("output_policy")
            if isinstance(inst_policy, dict):
                policy = dict(inst_policy)

        if not policy and skill and skill.output_policy:
            policy = dict(skill.output_policy)

        if not policy:
            short = tool_short_name(tool_name)
            policy = dict(DEFAULT_POLICIES.get(short, FALLBACK_POLICY))

        policy["artifact_mode"] = "pull_only"
        if "store_to_gateway" not in policy:
            policy["store_to_gateway"] = True
        return policy
