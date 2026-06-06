import logging
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.schemas.hermes_skill.common import (
    ConflictType,
    ConflictStrategy,
    SourceType,
    DEFAULT_CONFLICT_STRATEGIES,
)

logger = logging.getLogger(__name__)


@dataclass
class ConflictItem:
    conflict_type: ConflictType
    existing_id: str = ""
    existing_version: str = ""
    detail: str = ""


@dataclass
class ConflictReport:
    has_conflict: bool = False
    items: list[ConflictItem] = field(default_factory=list)


class ConflictDetector:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def detect(
        self,
        skill_id: str,
        agent_id: str,
        target_path: str,
        new_version: str,
        new_source_type: str,
        is_read_only: bool,
        skill_agent_type: str,
        target_agent_type: str,
    ) -> ConflictReport:
        report = ConflictReport()

        same_skill = await self.db.execute(
            select(HermesSkillInstallation).where(
                not_deleted(HermesSkillInstallation),
                HermesSkillInstallation.skill_id == skill_id,
                HermesSkillInstallation.agent_id == agent_id,
                HermesSkillInstallation.status == "installed",
            )
        )
        if same_skill.scalar_one_or_none():
            report.has_conflict = True
            report.items.append(ConflictItem(
                conflict_type=ConflictType.SAME_SKILL_ID,
                detail=f"Skill {skill_id} 已安装到 Agent {agent_id}",
            ))

        skill_row = await self.db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.skill_id == skill_id,
            )
        )
        skill_obj = skill_row.scalar_one_or_none()
        if skill_obj and skill_obj.tool_name:
            same_tool = await self.db.execute(
                select(HermesSkillInstallation).where(
                    not_deleted(HermesSkillInstallation),
                    HermesSkillInstallation.agent_id == agent_id,
                    HermesSkillInstallation.status == "installed",
                )
            )
            for inst in same_tool.scalars().all():
                installed_skill = await self.db.execute(
                    select(HermesSkill).where(
                        not_deleted(HermesSkill),
                        HermesSkill.skill_id == inst.skill_id,
                        HermesSkill.tool_name == skill_obj.tool_name,
                    )
                )
                if installed_skill.scalar_one_or_none():
                    report.has_conflict = True
                    report.items.append(ConflictItem(
                        conflict_type=ConflictType.SAME_TOOL_NAME,
                        detail=f"tool_name {skill_obj.tool_name} 在 Agent {agent_id} 已被占用",
                    ))
                    break

        import os
        if os.path.exists(target_path):
            report.has_conflict = True
            report.items.append(ConflictItem(
                conflict_type=ConflictType.SAME_INSTALL_PATH,
                detail=f"安装路径已存在: {target_path}",
            ))

        if same_skill.scalar_one_or_none() and new_version and skill_obj:
            existing_ver = skill_obj.version
            if self._is_version_downgrade(new_version, existing_ver):
                report.has_conflict = True
                report.items.append(ConflictItem(
                    conflict_type=ConflictType.VERSION_DOWNGRADE,
                    existing_version=existing_ver,
                    detail=f"版本降级: {existing_ver} -> {new_version}",
                ))

        if is_read_only:
            report.has_conflict = True
            report.items.append(ConflictItem(
                conflict_type=ConflictType.READ_ONLY_OVERRIDE,
                detail="目标 Skill 为只读，不允许覆盖",
            ))

        if skill_agent_type and target_agent_type and skill_agent_type != target_agent_type:
            report.has_conflict = True
            report.items.append(ConflictItem(
                conflict_type=ConflictType.AGENT_TYPE_MISMATCH,
                detail=f"Skill agent_type={skill_agent_type} 与 Agent 类型 {target_agent_type} 不匹配",
            ))

        return report

    async def resolve(
        self,
        report: ConflictReport,
        strategy: ConflictStrategy,
    ) -> ConflictStrategy:
        if not report.has_conflict:
            return strategy

        for item in report.items:
            if item.conflict_type == ConflictType.READ_ONLY_OVERRIDE:
                if strategy != ConflictStrategy.ABORT:
                    logger.warning("只读 Skill 冲突，强制 abort")
                    return ConflictStrategy.ABORT

        if strategy == ConflictStrategy.ABORT:
            return ConflictStrategy.ABORT
        if strategy == ConflictStrategy.SKIP:
            return ConflictStrategy.SKIP
        if strategy == ConflictStrategy.RENAME:
            return ConflictStrategy.RENAME
        if strategy == ConflictStrategy.INSTALL_AS_NEW_VERSION:
            return ConflictStrategy.INSTALL_AS_NEW_VERSION
        if strategy == ConflictStrategy.OVERWRITE:
            return ConflictStrategy.OVERWRITE

        return strategy

    def get_default_strategy(self, source_type: str) -> ConflictStrategy:
        try:
            st = SourceType(source_type)
        except ValueError:
            st = SourceType.CENTRAL
        return DEFAULT_CONFLICT_STRATEGIES.get(st, ConflictStrategy.INSTALL_AS_NEW_VERSION)

    @staticmethod
    def _is_version_downgrade(new_version: str, existing_version: str) -> bool:
        try:
            new_parts = [int(x) for x in new_version.split(".")]
            existing_parts = [int(x) for x in existing_version.split(".")]
            max_len = max(len(new_parts), len(existing_parts))
            new_parts.extend([0] * (max_len - len(new_parts)))
            existing_parts.extend([0] * (max_len - len(existing_parts)))
            return new_parts < existing_parts
        except (ValueError, AttributeError):
            return False
