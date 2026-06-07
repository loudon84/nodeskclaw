"""Expert template listing and injection."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import BadRequestError, NotFoundError
from app.services.hermes_expert.expert_filesystem import (
    RESOURCES_ROOT,
    backup_path,
    copy_tree_with_placeholders,
    ensure_default_layout,
    expert_host_data_dir,
    validate_profile_slug,
    write_json,
)
from app.services.hermes_expert.schemas import ExpertTemplateInfo

BUILTIN_TEMPLATES: dict[str, dict[str, str]] = {
    "base": {
        "name": "基础专家",
        "description": "通用 Hermes 专家目录结构与默认行为边界",
    },
    "writer": {
        "name": "写作专家",
        "description": "面向文章创作、PRD、方案文档、报告、资料摘要",
    },
    "finance": {
        "name": "财务专家",
        "description": "面向财务分析、资金日报、账龄分析、订单回款状态",
    },
}


class ExpertTemplateService:
    def list_templates(self) -> list[ExpertTemplateInfo]:
        items: list[ExpertTemplateInfo] = []
        for slug, meta in BUILTIN_TEMPLATES.items():
            if slug == "base":
                continue
            template_dir = self._template_dir(slug)
            files = self._list_template_files(template_dir)
            items.append(ExpertTemplateInfo(
                slug=slug,
                name=meta["name"],
                description=meta["description"],
                version="0.1.0",
                files=files,
            ))
        return items

    def get_template(self, template_slug: str) -> ExpertTemplateInfo:
        slug = validate_profile_slug(template_slug, "template_slug")
        if slug == "base" or slug not in BUILTIN_TEMPLATES:
            raise NotFoundError(
                message=f"专家模板不存在: {template_slug}",
                message_key="errors.hermes_expert.template_not_found",
            )
        meta = BUILTIN_TEMPLATES[slug]
        template_dir = self._template_dir(slug)
        return ExpertTemplateInfo(
            slug=slug,
            name=meta["name"],
            description=meta["description"],
            version="0.1.0",
            files=self._list_template_files(template_dir),
        )

    def inject_template(
        self,
        *,
        instance_slug: str,
        profile: str,
        expert_template: str,
        instance_id: str,
        instance_name: str,
        hindsight_api_url: str,
        hindsight_bank_id: str,
        init_obsidian_vault: bool = True,
    ) -> Path:
        profile_slug = validate_profile_slug(profile)
        template_slug = validate_profile_slug(expert_template, "expert_template")
        if template_slug not in BUILTIN_TEMPLATES or template_slug == "base":
            raise BadRequestError(
                message=f"不支持的专家模板: {expert_template}",
                message_key="errors.hermes_expert.template_not_found",
            )

        data_dir = expert_host_data_dir(instance_slug)
        mapping = {
            "PROFILE": profile_slug,
            "EXPERT": template_slug,
            "INSTANCE_ID": instance_id,
            "INSTANCE_NAME": instance_name,
            "HINDSIGHT_API_URL": hindsight_api_url,
            "HINDSIGHT_BANK_ID": hindsight_bank_id,
            "WORKSPACE_NAME": instance_name,
            "CREATED_AT": datetime.now(timezone.utc).isoformat(),
        }

        if data_dir.exists():
            backup_path(data_dir)

        base_dir = self._template_dir("base")
        expert_dir = self._template_dir(template_slug)
        copy_tree_with_placeholders(base_dir, data_dir, mapping)
        copy_tree_with_placeholders(expert_dir, data_dir, mapping, overwrite=True)
        ensure_default_layout(data_dir, init_obsidian=init_obsidian_vault)

        write_json(
            data_dir / ".inject-record.json",
            {
                "profile": profile_slug,
                "template": template_slug,
                "template_version": "0.1.0",
                "injected_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return data_dir

    def _template_dir(self, slug: str) -> Path:
        path = RESOURCES_ROOT / "expert-templates" / slug
        if not path.is_dir():
            raise NotFoundError(
                message=f"模板资源缺失: {slug}",
                message_key="errors.hermes_expert.template_not_found",
            )
        return path

    @staticmethod
    def _list_template_files(template_dir: Path) -> list[str]:
        files: list[str] = []
        if not template_dir.is_dir():
            return files
        for path in sorted(template_dir.rglob("*")):
            if path.is_file():
                files.append(str(path.relative_to(template_dir)).replace("\\", "/"))
        return files
