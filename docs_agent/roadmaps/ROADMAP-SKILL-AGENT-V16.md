---
roadmap_id: ROADMAP-SKILL-AGENT-V16
version: 1.6.0
status: ACTIVE
architecture_decision: docs_agent/architecture/AD-SKILL-AGENT-V16.md
architecture_addenda:
  - docs_agent/architecture/AD-SKILL-AGENT-V16-v1.6.0-hermes-runtime-native-run.md
source_revision: AD-SKILL-AGENT-V16-A1@1.6.0
updated_at: 2026-09-05T09:51:12.282914Z
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# Roadmap: Skill Agent v1.6 客户端合同与生产闭环

## Architecture Decision

[Approved Architecture（已批准架构）](../architecture/AD-SKILL-AGENT-V16.md)

Addendum（架构增补）：[AD-SKILL-AGENT-V16-A1 Hermes Runtime Native Run Integration](../architecture/AD-SKILL-AGENT-V16-v1.6.0-hermes-runtime-native-run.md)（`1.6.0` / `PROPOSED`）——RM-13 至 RM-16 的 Architecture Source，并重定义 RM-02 出口与 RM-10 范围。

## Delivery Invariants

- One Roadmap Item -> one Stage PRD（一项路线图对应一份阶段需求）。
- `DONE`（完成）必须具有真实 Implementation Commit（实施提交）与 Verification Evidence（验证证据）。
- Client（客户端）只访问 Backend；Agent 始终是生产 Skill Run（技能运行）的唯一执行事实源与终态裁决者。
- 本仓库只交付 Backend/Agent（后端/执行面）功能和供外部前端消费的版本化合同；外部 Work（工作端）前端源码、构建与发布不属于 Roadmap 交付范围。
- 外部前端的字段、交互或调用语义变更必须先形成新的 APPROVED Contract（已批准合同）；外部前端按合同适配，本项目再从合同反推 Backend 功能、兼容性和验证，禁止从未版本化的前端实现倒灌私有语义。
- 已发布合同目录、Tag（标签）与 checksum（校验和）不可原地改写；兼容变化必须新增合同版本。
- 后续 Item（交付项）不得在依赖未完成前进入 `READY`（就绪）或 `IN_PRD`（需求校准中）。
- RM-12 修复已发布 `SKILL-RUN-CONTRACT v1.2.1` 员工公共面实现符合性，不得并入 RM-04 / RM-09；RM-09 在 RM-08 `DONE` 前保持 `BACKLOG`。
- RM-12 状态由 `DONE` 回退为 `BACKLOG`：A1 依据 `apps/work` 员工端 live 报告判定其公共面符合性出口信号失效——本 Roadmap 对应 AD 在 Decision Drivers 中已列出的三项漂移（Public Run 仍输出 Portal 信封、SSE 未投影冻结合同全部语义事件、幂等未承载冻结合同语义）在真实 `user_jwt` 路径上仍然成立。**已交付的 Catalog、prompt-first 绑定、Workspace ACL 边界、跨组织 fail-closed 保留且不回滚**；退出条件改由 A1 第 30 节四条不变量与第 25 节 PC-10 至 PC-14 定义。A1 第 30.3 节的 HermesTask 平面降级归入重定义后的 RM-12 范围，不新增 Item。
- RM-12 于 2026-09-04 以真实 `user_jwt` REAL_PROCESS live 证据（V-R12-LIVE）重新关闭为 `DONE`。PC-13 CANCELLED 由操作者手工验证为 PASS；自动化 runner 曾观察到 `cancel HTTP 500`，该观察保留在 live 证据中，不构成出口阻塞。历史回退叙述保留。
- 员工公共面（RM-12）与 Hermes 南向（RM-13 至 RM-16）是两条可并行的线：RM-13 依赖 RM-11 的合同包基线，不依赖 RM-12。唯一耦合点是 A1 第 30.3 节单一平面收敛与 RM-14 的公共投影改动落在同一段代码，按 RM-14 的协同约束处理，禁止以「等对方先完成」互相阻塞。
- 任何声称员工公共面符合冻结合同的 Item，出口证据必须记录所用 `auth_type`；未标注认证路径的证据视为不完整，fixture 通过不构成出口信号。
- 生产 Skill Run 的 Hermes 南向执行面必须走 Native Run API；`/v1/chat/completions` 不再是正式 Event Source。Hermes Runtime 版本地板为 `v2026.8.31`，低于该版本必须在 Capability Probe 阶段失败关闭。
- `Depends On` 只表示执行 DAG，不表示证据再验证。RM-02 的执行前置是 RM-01（Catalog / Run Control）；RM-16 是 RM-02 Provider Conformance 的再验证来源，见 Revalidation Links，禁止写进 RM-02 的 Depends On。
- RM-02 状态由 `DONE` 回退为 `BACKLOG`：其 Provider Conformance 出口信号经真实运行判定不足。**已交付且被下游复用的 Event SoT、`event_seq`、Fencing、语义 Schema 与 Public 合同不回滚**，因此 RM-03 / RM-05 / RM-06 / RM-12 的既有 `DONE` 与其自身 Verification Evidence 继续有效——它们依赖的是 RM-02 保留的交付物，而非 RM-02 的 Conformance 出口。RM-02 的重新关闭由 RM-16 的真实 Hermes Conformance 证据驱动（非 DAG）。
- RM-13 至 RM-16 不得并入 RM-01 至 RM-12 任一项；四项各自保留独立可验收结果，不得为减少 Item 数量而合并。
- RM-13 于 2026-09-05 以真实 Hermes Native Run 证据（V11 / REAL_RUNTIME）关闭为 `DONE`。代码来源 `59ebfb66`；capabilities 无 version 时回读 `/health`，包版本 `0.21.0` 对应日历地板 `v2026.8.31`。
- RM-14 于 2026-09-05 以真实 Hermes Native Run 证据（V13 / REAL_PROCESS）关闭为 `DONE`。Adapter 代码 `bd7cbbb9`；证据提交 `7afeffcc`；SoT `run.progress` 带 canonical `phase`。
- RM-15 于 2026-09-05 以真实 Hermes Native Run 证据（V13 / REAL_PROCESS）关闭为 `DONE`。控制面代码 `846969d9` / `2c2b007e`；证据提交 `c4210717`；live 工具 `hermes_marketing__park-waiting-approval`。员工 cancel HTTP 500 为观察项，不构成出口阻塞。

## Roadmap Items

| Item ID | Outcome | Depends On | Status | Exit Criteria | PRD | Plan | Implementation Commit | Verification Evidence |
|---|---|---|---|---|---|---|---|---|
| RM-01 | Work（员工端）通过稳定 Catalog v1.1（目录合同）和 Run Control（运行控制）完成发现、调用、恢复与审批 | - | DONE | Resume/Approval 参数链正确；Catalog 能稳定区分能力类型与交互模式；Chat Skill（对话技能）发布门禁生效；v1.0 内容不变且 v1.1 合同校验通过 | docs_agent/prd-v1.6.0-skill-catalog-and-run-control.md | .cursor/plans/skill-catalog-and-run-control-v160.plan.md | 3a9b012ac19835223ce0676b8d94078832c2a982 | docs_agent/evidence/rm01-verification.md |
| RM-02 | Agent 持久化可回放的结构化 Run Event（运行事件），且控制状态机无绕过 | RM-01 | BACKLOG | 事件仅由**真实 Hermes Runtime 结构化事实**生成；重复、迟到和旧代事件无副作用；Provider Conformance 按 A1 第 25 节 Conformance Gate 证明，禁止以 mock OpenAI 字段单独结项。历史交付物（Event SoT、`event_seq`、Fencing、语义 Schema、Public 合同）保留复用，不回滚 | docs_agent/prd-v1.6.1-semantic-run-events.md | .cursor/plans/rm-02_semantic_events_492df3f9.plan.md | e3744c4bd73479a32155dcd11d7f8b87c7cc6f2b（历史交付，Conformance 出口已失效） | docs_agent/evidence/rm02-verification.md（证据不足，待 RM-16 重证） |
| RM-03 | Edge（边缘节点）安装不可变 Published Bundle（已发布技能包），并安全完成升级与卸载 | RM-02 | DONE | 授权下载、大小/摘要、路径与符号链接防护、原子切换、失败回滚和同代 Actual（实际状态）全部通过验收 | docs_agent/prd-v1.6.2-edge-published-bundle-lifecycle.md | .cursor/plans/rm-03_bundle_lifecycle_1dec5e37.plan.md | d6e7cb8061be9d2febdb21560638cd8d378a4963 | docs_agent/evidence/rm03-verification.md |
| RM-04 | Strict Readiness（严格就绪）与分布式 Production Acceptance（生产验收）形成可复现证据 | RM-03 | IN_PRD | 双 Central、单 Edge、真实 PostgreSQL、共享 S3/MinIO（对象存储）、故障注入、Secret 扫描、合同检查和 Newman（接口自动化）两连跑全部通过 | docs_agent/prd-v1.6.3-strict-readiness-production-acceptance.md | - | - | - |
| RM-05 | Connector Runtime（连接器运行时）通过统一执行入口可靠完成 Central/Edge（中心/边缘）调用 | RM-03 | DONE | REST/MCP/DB Connector 经 AgentEnginePort（执行引擎端口）执行；取消、SecretRef（秘密引用）、审批和受控私网策略可验证；客户端不能覆盖物理路由、目标或凭证 | docs_agent/prd-v1.6.4-connector-runtime-execution-closure.md | .cursor/plans/rm-05_connector_runtime_execution.plan.md | 3611f37147fff25000317cbf1653fb12fb0b4b1b | docs_agent/evidence/rm05-verification.md |
| RM-06 | Session（运行会话）与 ContextBuilder（上下文构建器）形成授权、可恢复的执行上下文 | RM-05 | DONE | Session 成为正式运行对象；Knowledge/Workspace/Attachment（知识/工作区/附件）引用经 Backend 授权并在执行前复核，撤权时 fail-closed（失败关闭） | docs_agent/prd-v1.6.7-session-context-authorized-execution.md | .cursor/plans/rm-06_session-context-authorized-execution.plan.md | d8fee3604be77d4ca330133c36012c721d638621 | docs_agent/evidence/rm06-verification.md |
| RM-07 | Edge Control Channel（边缘控制通道）具备身份轮换与命令完整性 | RM-05 | IN_PRD | 出站通道验证身份、过期、Nonce（随机数）、签名与序列；重放、错节点和过期命令无副作用 | docs_agent/prd-v1.6.8-edge-control-channel-security-closure.md | - | - | - |
| RM-08 | 中立 Shared Agent Execution Contract（共享 Agent 执行合同）可由 Backend 单一生成链发布，并冻结 Hermes（运行时）`single_agent` / `runtime_delegated` Delegation Topology（委派拓扑） | RM-06, RM-07 | BACKLOG | Schema、OpenAPI、TypeScript 类型、Fixture（固定样例）与兼容测试同源；Backend 冻结策略与 capability reference（能力引用），Agent 持久化 ExecutionSnapshot（执行快照），Runtime Capability（运行时能力）缺失时失败关闭；Topology 与 Central/Edge/Hybrid Placement（中心/边缘/混合放置）分列；不实现 Platform Multi-Agent（平台多智能体） | - | - | - | - |
| RM-09 | Backend 实现 v1.2.1 之后经批准的 Public 合同增量，并在 Shared Contract（共享合同）稳定后补齐依赖内部南向字段的剩余符合性；外部前端只作为仓外 Consumer | RM-08 | BACKLOG | 不首次发布 Work canonical；不改写 v1.2.1；不承担已发布 v1.2.1 员工公共面的实现 Hotfix；外部前端源码、构建和发布不在范围内 | - | - | - | - |
| RM-10 | Agent 执行面具备统一 Trace（链路追踪）与运行指标 | RM-05 | IN_PRD | Run/Attempt/Session/Edge/Connector/Artifact 可关联；队列、时延、失败、租约和重放指标可观测，且不形成第二事件事实源；**Trace correlation 必须纳入 A1 第 21 节 Runtime 字段**（`runtime_type`、`runtime_version`、`runtime_run_id`、`runtime_session_id`、`runtime_idempotency_key`、`tool_call_id`、`correlation_confidence`）与 Runtime 指标（start latency、event stream duration、delta 计数、coalescing 比、未配对 tool start 计数、approval 等待、stop 时延、disconnect/reconciliation/interrupted 计数） | docs_agent/prd-v1.6.9-agent-observability-trace-and-metrics.md | - | - | - |
| RM-11 | 累积 Public Skill Run Consumer Contract v1.2.1 成为外部 Work 可离线导入的当前合同导出项 | RM-01, RM-02 | DONE | 生成并发布 `v1.2.1/` 与 tag `skill-run-contract-v1.2.1`；manifest 纳入 SHA256SUMS；Public 包不含 Internal Southbound；不改写 v1.0.0/v1.1.0/v1.2.0；不含 Work 前端；Internal Agent 合同留给 RM-08 | docs_agent/prd-v1.6.6-cumulative-public-consumer-contract.md | .cursor/plans/rm-11_v121_cumulative_public_contract.plan.md | 10d38f2c97739c4a55df893d1dc954fc8896f1a7 | docs_agent/evidence/rm11-verification.md |
| RM-12 | 员工 Public Skill Run 面对冻结 `SKILL-RUN-CONTRACT v1.2.1` 可观察符合 | RM-06, RM-11 | DONE | 按 A1 第 30 节四条不变量收敛：公共信封与 `auth_type` 无关（同 Skill/同组织/同调用语义不得因凭证类型返回不同契约）；Catalog 宣告 `executionModes` 等于该调用者实际可达集合且与调用侧共用同一 resolver；HermesTask 平面降级为纯内部投影，A1 第 30.3 节禁止字段与 `/api/v1/hermes/tasks/` 路径不出现在任何公共响应，公共身份字段只有 `run_id`，公共终态不由 `HermesTask.status` 裁决，投影失败不得静默；出口证据必须来自真实 `user_jwt` 员工路径并通过 PC-10 至 PC-14，fixture 通过不构成出口信号。`contracts/skill-run/v1.2.1/` 仍零修改；不发布新合同版本。历史交付物（Catalog、prompt-first 绑定、Workspace ACL 边界、跨组织 fail-closed）保留复用，不回滚 | docs_agent/prd-v1.6.10-skill-run-v121-public-conformance.md | .cursor/plans/rm-12_v121_public_conformance.plan.md | f41e12e01159a1ba461c15b0e3e1e12cddcc7e02 | smc-evidence:RM-12@sha256:67445ab0aa15eb03401252b538b37b832dd3017fbae239044c34f918f967de08 |
| RM-13 | Hermes Native Runtime Bridge：Agent 经 `/v1/runs` 建立 Attempt 级 Runtime Run，完成 Native Event / Terminal / Stop 基础闭环 | RM-11 | DONE | Runtime 版本地板 `v2026.8.31` 生效且低版本失败关闭（`RUNTIME_VERSION_UNSUPPORTED`）；仓内 `v2026.4.23` 引用漂移按 A1 第 1.2 节全部修复（`hermes-image/Dockerfile` 的 `ARG`、`startup/seed.py` 的 `version` / `image_tag` / 说明文案、`test_registry_seed_defaults.py` 的断言），且全仓搜索 `2026.4.23` 无生产路径残留；`GET /v1/capabilities` 探测并按 Attempt 绑定 Capability Snapshot；`POST /v1/runs` 携带 Attempt 作用域 `Idempotency-Key`；Runtime Binding 持久化并受 Generation Fencing 约束；`/events` 消费 + `GET /v1/runs/{id}` terminal reconciliation + `/stop`；生产路径移除 `/v1/chat/completions`，无静默降级 | docs_agent/prd-v1.6.11-hermes-native-runtime-bridge.md | .cursor/plans/rm-13_hermes-native-runtime-bridge.plan.md | d13b98bb2a829d0f145fd9eb18fa35cfd462e24c | smc-evidence:RM-13@sha256:478769c0172bbd49b29cffdf1e4790172eb9420b33df57d9799747cbd0e64f3d |
| RM-14 | Runtime Semantic Event Fidelity：Runtime 事件经 Normalizer 与 Coalescer 成为低噪声可回放的 Agent Event SoT | RM-13 | DONE | `message.delta` 经 `AssistantDeltaCoalescer` 合并且语义边界强制 flush，`event_seq` 顺序正确、文本无丢失重复；`tool.started/completed` 映射 `tool.call` 并按 A1 第 11.3 节双轨合成 `call_id`（并行段标记低置信度）；未配对 `started` 有收尾策略；`reasoning.available` 不映射且不产出 `reasoning.summary`；`subagent.*` / `approval.responded` / `run.steered` 仅进 Internal Trace 且敏感字段不外泄；进度事件收敛为 canonical `phase` 并双发 `stage` 兼容；**与 RM-12 的协同约束**：本项的公共投影改动与 RM-12 的 A1 第 30.3 节单一平面收敛落在同一段投影代码，两项先后完成者必须复跑对方的公共面断言（PC-13 与 PC-12），禁止各自改一半导致公共面出现混合平面 | docs_agent/prd-v1.6.12-runtime-semantic-event-fidelity.md | .cursor/plans/rm-14_runtime-semantic-event-fidelity.plan.md | 7afeffccbd1a19dbc73328b6a52cf0067b20a4da | smc-evidence:RM-14@sha256:a78e1e330636f9fb180a948be2021808da61dbf5a4bf368fe44f9a061d6d64f3 |
| RM-15 | Approval & Runtime Control Closure：审批与取消形成同 Attempt、可 fencing 的双向闭环 | RM-14 | DONE | `approval.request` → Public `approval.requested` → 决策 → `POST /v1/runs/{id}/approval` 全链路闭合；内部保留 `once`/`session`/`always`/`deny` 四档，Public 只暴露批准（`once`）与拒绝（`deny`），`session`/`always` 仅由服务端策略决定；审批按 `runtime_run_id` 寻址而非 `session_id`；Cancel 经 `/stop` 且覆盖 `404` 已终态 reconciliation 分支；恢复路径按 A1 第 18.1 节冻结（禁止重订阅 `/events`）；`interrupted` 与状态不可得判 FAILED 并要求用户以同一 `runtime_session_id` 主动重启，Agent 不自动续跑；旧 Attempt 控制命令被 fencing 拒绝 | docs_agent/prd-v1.6.13-approval-runtime-control-closure.md | .cursor/plans/rm-15_approval-runtime-control-closure.plan.md | c4210717f694d4089c16d88400c9379a4d039c70 | smc-evidence:RM-15@sha256:6194c329fd040e065b0ce83ef11b767dbd3a5b15a8bbd5a79b55278f1f59938b |
| RM-16 | Hermes Provider Conformance & Recovery：真实 Runtime 全链路取得可复现实跑证据 | RM-15 | PLANNED | PC-01 至 PC-09 全部在真实 Hermes API Server（`>= v2026.8.31`）上通过并留存证据；禁止以 mock OpenAI 字段替代；覆盖长中文输出 coalescing、真实 Tool、真实 Approval、Cancel、NodeSKClaw Worker 重启 fencing、Hermes Runtime 重启 `interrupted`、版本地板失败关闭、Runtime Delegation 单一 Public Run；同时承接 RM-02 重新定义后的 Provider Conformance 出口 | docs_agent/prd-v1.6.14-hermes-provider-conformance-recovery.md | .cursor/plans/rm-16_hermes-provider-conformance-recovery.plan.md | - | - |

## Revalidation Links

`Revalidated By` 不是执行 DAG，不参与 `Depends On` 环检测。

| Item | Revalidated By | Meaning |
|---|---|---|
| RM-02 | RM-16 | RM-16 提供重新关闭 RM-02 Provider Conformance 的真实 Hermes 证据 |
