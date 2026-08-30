---
roadmap_id: ROADMAP-SKILL-AGENT-V16
version: 1.0.0
status: ACTIVE
architecture_decision: docs_agent/architecture/AD-SKILL-AGENT-V16.md
source_revision: AD-SKILL-AGENT-V16@1.0.0
updated_at: 2026-08-30T12:45:00+08:00
---

# Roadmap: Skill Agent v1.6 客户端合同与生产闭环

## Architecture Decision

[Approved Architecture（已批准架构）](../architecture/AD-SKILL-AGENT-V16.md)

## Delivery Invariants

- One Roadmap Item -> one Stage PRD（一项路线图对应一份阶段需求）。
- `DONE`（完成）必须具有真实 Implementation Commit（实施提交）与 Verification Evidence（验证证据）。
- Client（客户端）只访问 Backend；Agent 始终是生产 Skill Run（技能运行）的唯一执行事实源与终态裁决者。
- 后续 Item（交付项）不得在依赖未完成前进入 `READY`（就绪）或 `IN_PRD`（需求校准中）。

## Roadmap Items

| Item ID | Outcome | Depends On | Status | Exit Criteria | PRD | Plan | Implementation Commit | Verification Evidence |
|---|---|---|---|---|---|---|---|---|
| RM-01 | Work（员工端）通过稳定 Catalog v1.1（目录合同）和 Run Control（运行控制）完成发现、调用、恢复与审批 | - | IN_PRD | Resume/Approval 参数链正确；Catalog 能稳定区分能力类型与交互模式；Chat Skill（对话技能）发布门禁生效；v1.0 内容不变且 v1.1 合同校验通过 | `docs_agent/prd-v1.6.0-skill-catalog-and-run-control.md` | - | - | - |
| RM-02 | Agent 持久化可回放的结构化 Run Event（运行事件），且控制状态机无绕过 | RM-01 | BACKLOG | assistant/reasoning/tool/clarify/approval/artifact（助手/推理/工具/澄清/审批/产物）事件仅由结构化事实生成；重复、迟到和旧代事件无副作用 | - | - | - | - |
| RM-03 | Edge（边缘节点）安装不可变 Published Bundle（已发布技能包），并安全完成升级与卸载 | RM-02 | BACKLOG | 授权下载、大小/摘要、路径与符号链接防护、原子切换、失败回滚和同代 Actual（实际状态）全部通过验收 | - | - | - | - |
| RM-04 | Strict Readiness（严格就绪）与分布式 Production Acceptance（生产验收）形成可复现证据 | RM-03 | BACKLOG | 双 Central、单 Edge、真实 PostgreSQL、共享 S3/MinIO（对象存储）、故障注入、Secret 扫描、合同检查和 Newman（接口自动化）两连跑全部通过 | - | - | - | - |
