---
work_item_id: RM-08
version: 1.6.17
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-08T11:20:00Z
source_revision: AD-SKILL-AGENT-V16@1.7.0/RM-08
grounded_commit: 29006c0d6dfaeab5543b6951aa7b095c9edc656c
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Shared Agent Execution Contract 与 Delegation Topology PRD v1.6.17

本文定义 RM-08：在既有 Backend Contract Package（合同包）与 Runtime Skill Run / Agent Run 边界上，由单一生成链发布不可变 Internal `SKILL-AGENT-CONTRACT v1.0.0`，并冻结 Hermes（运行时）`single_agent` / `runtime_delegated` Delegation Topology（委派拓扑）。Architecture Source 为 `AD-SKILL-AGENT-V16@1.7.0` Option M。Depends On RM-06 与 RM-07（均已 `DONE`）。本项不实现 Platform Multi-Agent（平台多智能体），不提前 READY RM-09，不改写已发布 Public `SKILL-RUN-CONTRACT v1.2.1`～`v1.4.0`。

## Scope

本阶段交付：Internal Shared Agent Execution Contract 目录与 annotated tag；Schema / OpenAPI / TypeScript 类型 / Fixture / 兼容测试同源；Backend 将 Published SkillRelease（已发布技能版本）上的 `delegation_topology` 与版本化 Runtime Capability reference（运行时能力引用）冻结进 Agent 入队输入；Agent 将上述字段持久化进既有 ExecutionSnapshot（执行快照）且与 `placement` 分列；Capability 缺失或不匹配、以及 `platform_multi_agent` 请求失败关闭；可选将合同枚举 `delegation_topology` 作为 RM-10 Trace 受限属性（不得作 metric label）。

本阶段不交付：Platform Multi-Agent / Team Run / Child Run / 成员级取消审批成本 / 公开成员事件；Backend 第二份可执行 Snapshot Store；把 Hybrid Placement 映射为 Runtime Delegation；把 `gateway_sequential` 当作 `runtime_delegated`；改写 Public 合同字节；仓外 Work 适配；RM-16 live Hermes 内部委派实跑。exact 文件名、Alembic revision ID 与 Todo 归属 Plan。

本次改动无前端表现变化。不改 Portal / Admin / Work 页面、按钮、文案或路由。Internal 合同不对员工 UI 暴露。

## Product Boundary

员工只访问 Backend Public API。Internal Shared Contract 只约束 Backend→Agent 南向与 Agent 持久化 Snapshot，不得进入 Public Bundle 或 SSE。Agent 仍是 Run / Attempt / Event / Artifact / Terminal 与最终 ExecutionSnapshot 的唯一 Production Owner。Backend 只冻结 Route / Context / Policy / Topology / Capability reference，不调度 Hermes 内部成员，不成为第二终态裁决者。Hermes Runtime 仅在 `runtime_delegated` 下拥有其内部委派执行权；公开面始终只有一个 Parent Run、一个 Attempt lineage、一个 Event SoT、一个 Artifact namespace。

`delegation_topology` 与 `placement` 正交：前者只描述 Hermes 是否可在自身 Runtime 边界内委派；后者继续描述 Central / Edge / Hybrid 资源放置，Hybrid Step Plan 仍由 Agent Owner。客户端、Connector、Edge 与 Public Consumer 不得提交或覆盖 Topology、Runtime Profile 或成员列表。

## Current Capability Inventory

当前能力以已提交基线 `29006c0d6dfaeab5543b6951aa7b095c9edc656c` 为准。Grounding 模式为 `discover`。未提交工作树不计入。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Public Skill Run Bundles v1.2.1～v1.4.0 | EXISTS | Backend Skill Run Contract Package | `contracts/skill-run/v1.2.1/`～`v1.4.0/`；tags `skill-run-contract-v1.2.1` / `v1.3.0` / `v1.4.0`；v1.2.1 SHA256SUMS 无 Internal 路径 | KEEP 只读 |
| 单一 `contracts.py` 生成链 | EXISTS | Backend `scripts/contracts.py` | `--family` 仅 `work-expert` / `skill-run` / `all`；无 `skill-agent` | MODIFY 扩展 family，不新增第二生成器 |
| Internal `contracts/skill-agent/` | MISSING | Backend Contract Package（RM-08） | 仓库无该目录 | ADD |
| 历史混包 execution-snapshot | EXISTS（冻结污染） | 同上 | `contracts/skill-run/v1.1.0/runs/execution-snapshot.schema.json` 与 `v1.2.0/` 同路径；无 `delegation_topology`；v1.2.1 Public 已排除 | KEEP 只读；禁止改写；不得再打进 Public |
| Agent ExecutionSnapshot 持久化 | PARTIAL | Agent Run 域 | `run_service.build_snapshot` 已写 `placement`、`runtime_policy`、`execution_context`、`request_trace_id`；无 `delegation_topology` / capability reference | MODIFY 同一 Owner |
| Backend 入队冻结 Route/Context | PARTIAL | Backend Runtime Skill Run | `_enqueue_agent_run_outbox` 写 `placement`、`route_snapshot`、`execution_context`；无 Topology；客户端不得覆盖 org/run | MODIFY 同一 Owner |
| SkillRelease extra_metadata | EXISTS | Backend Skill Release | JSONB `extra_metadata` 可承载 Catalog 键；无 Topology 合同校验 | MODIFY 发布时冻结允许枚举，不新建 Release 服务 |
| Hermes capability probe | PARTIAL | Agent Hermes Adapter | `GET /v1/capabilities` + 版本地板；缺失用 `RUNTIME_CAPABILITY_MISSING`；无 Topology 专用 `RUNTIME_CAPABILITY_UNAVAILABLE`；无 `EXECUTION_TOPOLOGY_NOT_SUPPORTED` | MODIFY 同一 Adapter，不新增 Engine |
| EnginePort | EXISTS | Agent Execution Plane | `execute_engine` 仅 Hermes / Connector；未知 engine fail-closed | KEEP；Topology 不得变成新 engine |
| Hybrid Step Plan | EXISTS | Agent Worker | `build_hybrid_step_plan`；placement 与 Topology 未混用 | KEEP |
| RM-06 execution_context | EXISTS | Backend Runtime + Agent revalidate | `_build_authorized_execution_context`；Edge 执行前 `revalidate_execution_context` | KEEP 字段集合；Internal 合同引用其稳定形状 |
| RM-07 Edge Envelope | EXISTS | Backend/Agent Edge Control Channel | `COMMAND_PURPOSES`、nonce、`command_seq`、验签后才副作用 | KEEP 字段集合；Internal 合同引用封套身份，不重做通道 |
| RM-10 Trace allowlist | EXISTS | Agent Execution Observability | `ALLOWED_TRACE_ATTRS` 明确排除 `delegation_topology` | MODIFY 仅在本项合同发布后允许可选枚举属性 |
| `subagent.*` 内部痕迹 | EXISTS | Agent Event SoT | `internal.runtime.trace`；Public 不投影；无 Child Run | KEEP；不得升级为成员 Run |
| RM-09 符合性 Item | MISSING as READY | Roadmap | RM-09 `BACKLOG`，Depends On RM-08 | KEEP 边界；本项不得提前 READY |
| Platform Multi-Agent | MISSING | 需新 AD | AD 保留为未来概念 | KEEP 拒绝实现 |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Internal Shared Agent Contract | `contracts/skill-agent/v1.0.0/` + annotated tag `skill-agent-contract-v1.0.0` 为 Internal 当前 pin | Backend Contract Package | 禁止进入任何 Public `skill-run` SHA256SUMS；禁止改写已发布 Public 目录 |
| 同源生成 | Schema、OpenAPI、TypeScript、Fixture、兼容测试由同一 `contracts.py` family 生成与 check | `scripts/contracts.py` | 禁止第二生成链或手写分叉目录 |
| Topology freeze | Published SkillRelease 声明且 Backend 冻结 `delegation_topology` ∈ {`single_agent`,`runtime_delegated`} 与版本化 capability reference 到 Agent 输入 | Backend Runtime Skill Run + Skill Release | 客户端/Public/Edge 不能覆盖；Backend 不持久化第二 Snapshot |
| Snapshot persist | Agent `build_snapshot` 持久化冻结 Topology 与 capability reference，且与 `placement` 分列 | Agent Run 域 | 不创建 Child Run；不把 Topology 当 Engine |
| Fail-closed capability | `runtime_delegated` 而 Runtime 无匹配 Capability → `RUNTIME_CAPABILITY_UNAVAILABLE`；请求 `platform_multi_agent` 或非枚举值 → `EXECUTION_TOPOLOGY_NOT_SUPPORTED` | Agent Execution Plane | 禁止降级 `single_agent` 或 `gateway_sequential` |
| Optional Trace attr | 合同枚举可作为受限 Trace 属性；不作 metric label | Agent Observability | 缺失只报告缺失，不推断 |
| Public / RM-09 | Public 字节不变；RM-09 仍 BACKLOG 直至本项 DONE | Roadmap + Contract Package | 不并入 RM-09；不把 Internal 字段投影进 Public SSE |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Public Skill Run v1.2.1～v1.4.0 | KEEP | Backend Skill Run Contract Package | 已发布目录与 tag 字节不变；Public SHA256SUMS 仍无 Internal 路径 |
| C02 | Agent Run/Event/Terminal Owner | KEEP | Agent Run/Event 域 | 无第二终态裁决者；无 Child Run / 成员状态机 |
| C03 | Placement 与 Hybrid Step Plan | KEEP | Agent Worker | Hybrid 不被映射为 `runtime_delegated`；`execute_engine` 不出现 `multi_agent` |
| C04 | RM-06 Context Descriptor | KEEP | Backend Runtime Skill Run | `execution_context` 形状与复核路径不变；Internal 合同只引用稳定字段 |
| C05 | RM-07 Edge Envelope | KEEP | Edge Control Channel | 封套验签与 nonce/seq 不变；Internal 合同只引用身份绑定字段 |
| C06 | Internal `SKILL-AGENT-CONTRACT v1.0.0` Bundle | ADD | Backend Contract Package | 存在完整 Internal 目录：manifest、SHA256SUMS、ExecutionSnapshot schema、delegation/placement/capability 描述、OpenAPI、TypeScript、fixtures；无秘密 |
| C07 | Generator / Checker family `skill-agent` | MODIFY | `scripts/contracts.py` | `generate/check --family skill-agent --version 1.0.0`（含 `--release`）成功；损坏/extra/CRLF/混入 Public 失败；不静默覆盖 skill-run 冻结目录 |
| C08 | Backend Topology / capability freeze | MODIFY | Backend Runtime Skill Run + Skill Release | 入队 payload 含服务器冻结的 `delegation_topology` 与 capability reference；客户端提交被忽略或拒绝 |
| C09 | Agent Snapshot persist + fail-closed | MODIFY | Agent Run 域 + Hermes Adapter | Snapshot 持久化分列字段；Capability 不匹配失败关闭；不降级 engine |
| C10 | 稳定错误码 | ADD | Agent Execution Plane（映射到既有错误契约） | `RUNTIME_CAPABILITY_UNAVAILABLE` 与 `EXECUTION_TOPOLOGY_NOT_SUPPORTED` 可观察；响应含 `error_code` + `message_key` + `message` |
| C11 | RM-09 / Public Release Lane 边界 | KEEP | Roadmap | RM-09 仍 BACKLOG 且 Depends On RM-08；不并入 RM-17/RM-18 |
| C12 | 发布身份与证据 | ADD | Repository Acceptance Assets | annotated tag `skill-agent-contract-v1.0.0`；禁止 `git tag -f`；archive 复验；证据不含 Work 路径 |
| C13 | Optional Trace topology attr | MODIFY | Agent Execution Observability | allowlist 可含合同枚举 `delegation_topology`；禁止 UUID/用户输入作标签；观测 fail-open |

## Behaviour And Security Contract

Backend 必须从 Published SkillRelease / 策略解析 Topology，而不是从 Public `tools/call`、客户端 `client_context` 或 Edge Job 裸负载。缺省未声明时只能冻结为 `single_agent`，不得默认为 `runtime_delegated`。`runtime_delegated` 必须携带可验证的版本化 capability reference；Agent 在建立 Native Run 前对照 Runtime `GET /v1/capabilities`（及既有版本地板）。Descriptor 缺失、不匹配或不支持时必须失败关闭，错误码 `RUNTIME_CAPABILITY_UNAVAILABLE`，不得改写 Snapshot 为 `single_agent`，不得回退 ChatCompletion 或 `gateway_sequential`。

请求或推断 `platform_multi_agent` / `team` / `swarm` / 非合同枚举必须 `EXECUTION_TOPOLOGY_NOT_SUPPORTED`。Hybrid Placement 继续走既有 Step Plan，不得改写 Topology。

Internal Bundle 必须拒绝真实 token、DSN、客户数据与私有绝对路径。Fixture 使用 synthetic identity。Public SSE / Catalog 不得新增 Topology、Runtime Profile 或成员字段。Trace 若记录 Topology，仅允许合同枚举字符串。

观测继续 fail-open；Topology 与 Capability 门禁 fail-closed。RM-06 授权复核与 RM-07 封套验签不被本项削弱。

## Acceptance Criteria

- **AC-01 / C06**：存在完整 `nodeskclaw-backend/contracts/skill-agent/v1.0.0/` Internal Bundle，含 ExecutionSnapshot、`delegation_topology` 枚举、`placement` 正交描述、capability reference、OpenAPI、TypeScript 与 fixtures。
- **AC-02 / C06**：Internal Bundle 无 Public Consumer 专属路径混入；Public `skill-run` v1.2.1～v1.4.0 SHA256SUMS 不出现 `skill-agent/` 或新 Internal 文件。
- **AC-03 / C07**：`python nodeskclaw-backend/scripts/contracts.py generate --family skill-agent --version 1.0.0` 与 `check --family skill-agent --version 1.0.0` 通过；`--family skill-run` 行为不因本项改变冻结目录。
- **AC-04 / C07**：Internal SHA256SUMS 为 UTF-8 LF-only；listed == actual（排除 SHA256SUMS 自身）；tamper/extra/CRLF 使 check 失败。
- **AC-05 / C08**：Backend 入队后 Agent 可见的冻结输入含服务器决定的 `delegation_topology`；客户端覆盖组织、Run、Topology 或 capability reference 失败关闭或被忽略且不生效。
- **AC-06 / C09**：Agent ExecutionSnapshot 持久化 Topology 与 `placement` 为分列字段；同一 Snapshot 可同时表达 Hybrid placement 与 `single_agent` topology。
- **AC-07 / C09 / C10**：`runtime_delegated` 且 Capability 缺失/不匹配时执行失败，错误码 `RUNTIME_CAPABILITY_UNAVAILABLE`，Run 不得以成功终态关闭，不得改 Topology 后重试为 `single_agent`。
- **AC-08 / C10**：请求 `platform_multi_agent` 或非法枚举时错误码 `EXECUTION_TOPOLOGY_NOT_SUPPORTED`，不得回退 `gateway_sequential`。
- **AC-09 / C03 / C02**：无 Child Run、无成员级 Public 事件、无 `engine=multi_agent`；`subagent.*` 仍只进 `internal.runtime.trace`。
- **AC-10 / C01**：`git diff --exit-code <grounded_commit> -- nodeskclaw-backend/contracts/skill-run/v1.2.1 nodeskclaw-backend/contracts/skill-run/v1.3.0 nodeskclaw-backend/contracts/skill-run/v1.4.0` 为空（实施后相对本 grounded_commit 的 Public 冻结目录无改写）。
- **AC-11 / C12**：存在 annotated tag `skill-agent-contract-v1.0.0`；`check --family skill-agent --version 1.0.0 --release` 在 tag 指向 freeze commit 时通过；禁止 `git tag -f`。
- **AC-12 / C13**：Trace 可包含可选合同枚举 `delegation_topology`；该值不得作为 metric label；缺失不阻断已授权 `single_agent` 执行。
- **AC-13 / C11**：Roadmap 上 RM-09 在本项 DONE 前保持 BACKLOG 且 Depends On RM-08。
- **AC-14 / C04 / C05**：RM-06 Context 复核与 RM-07 封套验签回归仍 PASS；Internal 合同不把秘密写入 Snapshot。

## Definition of Done

- **DOD-01**：AC-01 至 AC-14 的 Provider/Agent 侧验证证据已留存。
- **DOD-02**：Internal `v1.0.0` 已由单一生成链发布；Public 三版未改写；未新增第三个服务或第二 Snapshot Store。
- **DOD-03**：Capability / Topology 失败关闭有自动化 oracle；无静默降级。
- **DOD-04**：Review 与 Verification 均 PASS；真实 implementation commit 写入 Roadmap 后 RM-08 才可 `DONE`（Roadmap DONE 属 Plan Delivery，非本 PRD 治理轮次出口）。
- **DOD-05**：`lat.md` 将 Runtime Delegation 从「目标状态」更新为已发布 Internal 合同与失败关闭语义，且 `lat check` 通过。

## Non-Goals

- 不实现 Platform Multi-Agent、Team Run、Child Run、成员级取消/审批/成本或公开成员事件。
- 不把 Hermes 内部成员提升为 Backend 业务对象。
- 不提前 READY RM-09，不把本项并入 RM-04 / RM-16 / RM-17 / RM-18。
- 不改写 `contracts/skill-run/v1.2.1`～`v1.4.0` 或既有 Public tags。
- 不把 live Hermes 内部委派实跑当作本项唯一出口（那是 RM-16 重开范围）；本项出口是合同发布 + 冻结 + fail-closed oracle。
- 不开发或修改 Work / Portal UI。

## Evidence Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CL-01 | Public v1.2.1～v1.4.0 只读 | 冻结目录存在且 RM-11/17/18 DONE | yes | `docs_agent/evidence/rm11-verification.md` 等 | PROVEN_FRESH | REUSE_EVIDENCE | 仅当本项改写这些目录 |
| CL-02 | `contracts.py` 无 skill-agent family | `--family` choices 不含 skill-agent | yes | `scripts/contracts.py` at `29006c0d` | NOT_TESTED | NEW_EVIDENCE | — |
| CL-03 | Internal 目录不存在 | 无 `contracts/skill-agent/` | yes | 仓库 glob | NOT_TESTED | NEW_EVIDENCE | — |
| CL-04 | Snapshot 无 Topology | `build_snapshot` 无该键 | yes | `run_service.build_snapshot` | NOT_TESTED | NEW_EVIDENCE | — |
| CL-05 | 入队无 Topology freeze | `_enqueue_agent_run_outbox` 无该键 | yes | `runtime_skill_run_service.py` | NOT_TESTED | NEW_EVIDENCE | — |
| CL-06 | Capability 门禁仅为版本地板 | `RUNTIME_CAPABILITY_MISSING` 非 Topology 码 | yes | `hermes_engine.py` | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 本项新增 Topology 专用失败码，须证明旧地板仍成立 |
| CL-07 | RM-06 context KEEP | 授权描述符与复核 | yes | RM-06 evidence | PROVEN_FRESH | REUSE_EVIDENCE | 仅当改 revalidate 语义 |
| CL-08 | RM-07 envelope KEEP | 签名心跳/命令 | yes | `docs_agent/evidence/rm07-verification.md` | PROVEN_FRESH | REUSE_EVIDENCE | 仅当改 COMMAND_PURPOSES |
| CL-09 | RM-10 排除 topology attr | allowlist 测试拒绝该键 | yes | `test_execution_observability.py` | PROVEN_BUT_AFFECTED | TARGETED_RERUN | C13 将改为可选枚举 |
| CL-10 | RM-09 边界 | BACKLOG / Depends On RM-08 | yes | Roadmap 表 | PROVEN_FRESH | REUSE_EVIDENCE | 若本项把 RM-09 标 READY |
| CL-11 | 无 Child Run | Public 不投影 `subagent.*` | yes | RM-14/16 路径 | PROVEN_FRESH | REUSE_EVIDENCE | 若新增 Public 成员事件 |
| CL-12 | Tag / release check | 尚无 `skill-agent-contract-v1.0.0` | yes | git tags | NOT_TESTED | NEW_EVIDENCE | — |

未提交工作树若合入并碰到上述锚点，必须再跑 Evidence Freshness。

## Source Anchors

- `docs_agent/architecture/AD-SKILL-AGENT-V16.md` RM-08 / Option M / Boundaries 15–16 / Error `EXECUTION_TOPOLOGY_NOT_SUPPORTED` / `RUNTIME_CAPABILITY_UNAVAILABLE`
- `docs_agent/architecture/AD-SKILL-AGENT-V16-v1.6.0-hermes-runtime-native-run.md` §22 SoT（ExecutionSnapshot Agent；Runtime delegation Hermes）
- `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` RM-08
- `nodeskclaw-backend/scripts/contracts.py`
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_enqueue_agent_run_outbox`
- `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py`
- `nodeskclaw-agent/app/services/run_service.py#build_snapshot`
- `nodeskclaw-agent/app/services/engine_port.py#execute_engine`
- `nodeskclaw-agent/app/services/hermes_engine.py` capabilities probe
- `nodeskclaw-agent/app/services/execution_observability.py#ALLOWED_TRACE_ATTRS`
- `lat.md/architecture/skill-agent.md#Runtime Delegation Boundary`
