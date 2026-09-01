---
roadmap_id: ROADMAP-SKILL-AGENT-V16
version: 1.2.0
status: ACTIVE
architecture_decision: docs_agent/architecture/AD-SKILL-AGENT-V16.md
source_revision: AD-SKILL-AGENT-V16@1.2.0
updated_at: 2026-09-01T11:33:35+08:00
---

# Roadmap: Skill Agent v1.6 客户端合同与生产闭环

## Architecture Decision

[Approved Architecture（已批准架构）](../architecture/AD-SKILL-AGENT-V16.md)

## Delivery Invariants

- One Roadmap Item -> one Stage PRD（一项路线图对应一份阶段需求）。
- `DONE`（完成）必须具有真实 Implementation Commit（实施提交）与 Verification Evidence（验证证据）。
- Client（客户端）只访问 Backend；Agent 始终是生产 Skill Run（技能运行）的唯一执行事实源与终态裁决者。
- 本仓库只交付 Backend/Agent（后端/执行面）功能和供外部前端消费的版本化合同；外部 Work（工作端）前端源码、构建与发布不属于 Roadmap 交付范围。
- 外部前端的字段、交互或调用语义变更必须先形成新的 APPROVED Contract（已批准合同）；外部前端按合同适配，本项目再从合同反推 Backend 功能、兼容性和验证，禁止从未版本化的前端实现倒灌私有语义。
- 已发布合同目录、Tag（标签）与 checksum（校验和）不可原地改写；兼容变化必须新增合同版本。
- 后续 Item（交付项）不得在依赖未完成前进入 `READY`（就绪）或 `IN_PRD`（需求校准中）。

## Roadmap Items

| Item ID | Outcome | Depends On | Status | Exit Criteria | PRD | Plan | Implementation Commit | Verification Evidence |
|---|---|---|---|---|---|---|---|---|
| RM-01 | Work（员工端）通过稳定 Catalog v1.1（目录合同）和 Run Control（运行控制）完成发现、调用、恢复与审批 | - | DONE | Resume/Approval 参数链正确；Catalog 能稳定区分能力类型与交互模式；Chat Skill（对话技能）发布门禁生效；v1.0 内容不变且 v1.1 合同校验通过 | docs_agent/prd-v1.6.0-skill-catalog-and-run-control.md | .cursor/plans/skill-catalog-and-run-control-v160.plan.md | 3a9b012ac19835223ce0676b8d94078832c2a982 | docs_agent/evidence/rm01-verification.md |
| RM-02 | Agent 持久化可回放的结构化 Run Event（运行事件），且控制状态机无绕过 | RM-01 | DONE | assistant/reasoning/tool/clarify/approval/artifact（助手/推理/工具/澄清/审批/产物）事件仅由结构化事实生成；重复、迟到和旧代事件无副作用 | docs_agent/prd-v1.6.1-semantic-run-events.md | .cursor/plans/rm-02_semantic_events_492df3f9.plan.md | e3744c4bd73479a32155dcd11d7f8b87c7cc6f2b | docs_agent/evidence/rm02-verification.md |
| RM-03 | Edge（边缘节点）安装不可变 Published Bundle（已发布技能包），并安全完成升级与卸载 | RM-02 | DONE | 授权下载、大小/摘要、路径与符号链接防护、原子切换、失败回滚和同代 Actual（实际状态）全部通过验收 | docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md | .cursor/plans/rm-03_bundle_lifecycle_1dec5e37.plan.md | d6e7cb8061be9d2febdb21560638cd8d378a4963 | docs_agent/evidence/rm03-verification.md |
| RM-04 | Strict Readiness（严格就绪）与分布式 Production Acceptance（生产验收）形成可复现证据 | RM-03 | IN_PRD | 双 Central、单 Edge、真实 PostgreSQL、共享 S3/MinIO（对象存储）、故障注入、Secret 扫描、合同检查和 Newman（接口自动化）两连跑全部通过 | docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md | - | - | - |
| RM-05 | Connector Runtime（连接器运行时）通过统一执行入口可靠完成 Central/Edge（中心/边缘）调用 | RM-03 | IN_PRD | REST/MCP/DB Connector 经 AgentEnginePort（执行引擎端口）执行；取消、SecretRef（秘密引用）、审批和受控私网策略可验证；客户端不能覆盖物理路由、目标或凭证 | docs_agent/prd-v1.6.4-connector-runtime-execution-closure.md | - | - | - |
| RM-06 | Session（运行会话）与 ContextBuilder（上下文构建器）形成授权、可恢复的执行上下文 | RM-05 | BACKLOG | Session 成为正式运行对象；Knowledge/Workspace/Attachment（知识/工作区/附件）引用经 Backend 授权并在执行前复核，撤权时 fail-closed（失败关闭） | - | - | - | - |
| RM-07 | Edge Control Channel（边缘控制通道）具备身份轮换与命令完整性 | RM-05 | BACKLOG | 出站通道验证身份、过期、Nonce（随机数）、签名与序列；重放、错节点和过期命令无副作用 | - | - | - | - |
| RM-08 | 中立 Shared Agent Contract（共享执行合同）可由 Backend 单一生成链发布 | RM-06, RM-07 | BACKLOG | Schema、OpenAPI、TypeScript 类型、Fixture（固定样例）与兼容测试同源；旧合同不可改写，不形成第二手写 Schema 事实源 | - | - | - | - |
| RM-09 | Backend 发布外部 Work Skill-first Consumer Contract（技能优先消费合同）并实现合同符合性；外部前端只作为仓外 Consumer（消费者） | RM-08 | BACKLOG | 本仓只交付版本化合同、Backend 公共行为和 Conformance（符合性）证据；外部前端源码、构建和发布不在范围内；任何新前端需求先修订合同，再由本项目按批准合同反推 Backend 实现 | - | - | - | - |
| RM-10 | Agent 执行面具备统一 Trace（链路追踪）与运行指标 | RM-05 | BACKLOG | Run/Attempt/Session/Edge/Connector/Artifact 可关联；队列、时延、失败、租约和重放指标可观测，且不形成第二事件事实源 | - | - | - | - |
| RM-11 | 已发布 P0 Skill Run Consumer Contract Bundle（消费合同包）成为外部 Work 可离线导入的合同导出项 | RM-01 | IN_PRD | Provider 侧证明 tag `skill-run-contract-v1.0.0` 身份、LF checksum 与 P0 产物集完整；不改写 v1.0.0 字节；不含 Work 前端；矩阵增量留给 RM-09 | docs_agent/prd-v1.6.5-p0-consumer-contract-export.md | - | - | - |
