---
work_item_id: RM-09
version: 1.6.18
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-08T13:10:00Z
source_revision: AD-SKILL-AGENT-V16@1.7.0/RM-09
grounded_commit: 2ed2f13796d813f9f5ad09bddc937185ae4ba181
feature_id: FEAT-SKILL-FIRST-001
work_package_id: WP-SKILL-FIRST-NODESKCLAW
---

# DeskClaw 团队版 Shared Contract 公共面隔离 PRD v1.6.18

本文定义 RM-09：在 RM-08 已发布 Internal `SKILL-AGENT-CONTRACT v1.0.0` 且 Topology 已冻结之后，补齐**依赖该内部南向字段的剩余公共面符合性**。Architecture Source 为 `AD-SKILL-AGENT-V16@1.7.0` Option U / Boundaries 10、21–22。Depends On RM-08（已 `DONE`）。本项不承担 RM-17 Approval Decision 与 RM-18 Attachment 已发布 Capability，不新发第二份 Work canonical，不改写已发布 Public `SKILL-RUN-CONTRACT v1.2.1`～`v1.4.0`，不把仓外 Work 适配当作本仓 DONE。

## Scope

本阶段交付：员工 Public Skill Run 与 MCP Catalog 对 Internal 南向字段失败关闭隔离——`delegation_topology`、`runtime_capability_ref`、ExecutionSnapshot、Hermes 内部成员/Profile 不得出现在 MCP `tools/list`、`tools/call` 可观察结果、以及 `/api/v1/runs/*` GET/SSE/result；员工 `tools/call` 参数与 `client_context` 不得覆盖 Topology 或 capability reference（在既有入队剥离之上于 MCP/Public 边界再拒绝或剥离）；公开面在 `runtime_delegated` 下仍只有一个 Parent Run；自动化 oracle 证明 Public 三版字节不变。

本阶段不交付：新 Public 合同版本（无已批准的、必须暴露 Internal 字段的 Public capability）；改写 v1.2.1/v1.3.0/v1.4.0；RM-16 live Hermes 内部委派实跑；Platform Multi-Agent / Child Run；第二 Snapshot Store；仓外 Work UI/IPC；把 Portal 运营 Skill CRUD 改成第二合同面。exact 文件名与 Todo 归属 Plan。

本次改动无前端表现变化。不改 Portal / Admin / Work 页面、按钮、文案或路由。员工 Work 本就不渲染 Internal Topology；本项只收紧 Backend 公共投影与 MCP 边界。

## Product Boundary

员工只访问 Backend Public API 与 MCP Catalog。Internal Shared Contract 继续只约束 Backend→Agent 南向。公开面始终只有一个 Parent Run、一个 Attempt lineage、一个 Event SoT；`internal.runtime.trace` 与 `subagent.*` 不得投影到 Public SSE。客户端不得提交或覆盖 Topology、Runtime Profile、成员列表或 capability reference。

Portal 组织运营 Skill CRUD（`extra_metadata` 含发布时冻结的 Topology）不是 Work canonical，也不是本项要新发的 Public 合同面；本项不得把运营 API 改写成员工 MCP 字段集，也不得把运营 `extra_metadata` 泄漏进 MCP `tools/list`。

AD 未批准任何必须把 Internal 南向字段写进 Public Schema 的增量；因此本项**禁止**发布 `v1.5.0` 或把 Topology 加成 Catalog 公开字段。后续若产品要员工可见的委派摘要，必须先修订 Architecture 再开新 Item。

## Current Capability Inventory

当前能力以已提交基线 `2ed2f13796d813f9f5ad09bddc937185ae4ba181` 为准（含 RM-08 implementation `ddf8a653`、tag `skill-agent-contract-v1.0.0`、Roadmap RM-08 `DONE`）。Grounding 模式为 `discover`。未提交工作树不计入。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Internal SKILL-AGENT-CONTRACT v1.0.0 | EXISTS | Backend Contract Package | `contracts/skill-agent/v1.0.0/`；tag `skill-agent-contract-v1.0.0` → `ddf8a653` | KEEP 只读 |
| Public Skill Run v1.2.1～v1.4.0 | EXISTS | Backend Skill Run Contract Package | 冻结目录与 tags；Schema 无 `delegation_topology` | KEEP 只读；禁止改写；禁止新版本 |
| Backend Topology freeze | EXISTS | Backend Runtime Skill Run | `_enqueue_agent_run_outbox` 写入冻结 Topology；从 `client_context` 剥离 overlay | KEEP 入队语义；本项在 MCP/Public 边界补拒绝/剥离 |
| Agent Snapshot + fail-closed | EXISTS | Agent Run / Hermes Adapter | Snapshot 分列字段；`RUNTIME_CAPABILITY_UNAVAILABLE` / `EXECUTION_TOPOLOGY_NOT_SUPPORTED` | KEEP |
| MCP tools/list 投影 | PARTIAL | Backend MCP Gateway | `_skill_to_tool` 樱桃采摘 Catalog 字段，未 `update(release_extra)`；无显式 Internal 键拒绝测试 | MODIFY 同一 Owner：显式隔离 + oracle |
| MCP tools/call 参数门禁 | PARTIAL | Backend MCP Gateway | `forbiddenArgumentKeys` 仅 `_routing`/`_execution`/`route_config`；`_copy_frozen_attachment_refs` 只拷 `attachment_refs` | MODIFY 将 Topology/capability/snapshot 视为路由覆盖同类拒绝或剥离 |
| Public `/api/v1/runs/*` 投影 | PARTIAL | Backend Skill Run API | `_public_run_view` 白名单；`_public_run_event` 未知类型返回 `None`（含 `internal.runtime.trace`） | MODIFY 补 Internal 键/成员事件否定 oracle；发现泄漏则同一 Owner 收紧 |
| Portal Skill CRUD extra_metadata | EXISTS | Backend Hermes Skill 域 | `SkillRead.extra_metadata` 整包返回；`require_org_member` 列表/导出含 extra | KEEP 运营面；不得当作员工 Public 合同 |
| RM-17/RM-18 Public Capability | EXISTS | Contract Package + Public API | v1.3.0/v1.4.0 DONE | KEEP；本项不重做 |
| RM-16 live 委派 | MISSING as DONE | Agent Hermes Adapter | Roadmap BACKLOG | KEEP 边界；本项不以 live 委派为出口 |
| Platform Multi-Agent | MISSING | 需新 AD | AD 拒绝 | KEEP 拒绝实现 |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| 员工 MCP Catalog | `tools/list` 不含 Internal 南向键、Snapshot、成员/Profile | MCP Gateway | 不得把 `release.extra_metadata` 整包映出 |
| 员工 tools/call | 参数/`client_context` 带 Topology/capability/snapshot/成员键时拒绝或剥离且不生效；服务器冻结仍生效 | MCP Gateway + Runtime Skill Run | 不得让 MCP 成为第二 Topology Owner |
| Public Run/SSE/result | 白名单投影；无 Internal 键；无 `internal.runtime.trace` / 成员事件 | Skill Run API | 单一 Parent Run；错误码可观察但不得附带 Internal Snapshot |
| Public 合同三版 | 相对 grounded_commit 空 diff | Contract Package | 禁止 v1.5.0；禁止改 SHA256SUMS |
| 运营 Skill extra_metadata | 仍可承载发布冻结 Topology | Hermes Skill 域 | 仅运营 CRUD；不进 MCP Catalog |
| RM-16 / PMA | 仍非本项 | — | live 委派与 Multi-Agent 保持 OUT |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Public Skill Run v1.2.1～v1.4.0 | KEEP | Backend Skill Run Contract Package | 已发布目录与 tag 字节不变 |
| C02 | Internal SKILL-AGENT-CONTRACT v1.0.0 | KEEP | Backend Contract Package | Internal Bundle 与 tag 不改写 |
| C03 | Backend 入队 Topology freeze | KEEP | Backend Runtime Skill Run | 服务器冻结与 `client_context` 剥离语义不变 |
| C04 | Agent Snapshot / fail-closed | KEEP | Agent Run / Hermes Adapter | 不改 Snapshot Owner；不新增 engine |
| C05 | RM-17/RM-18 已发布 Public Capability | KEEP | Contract Package + Public API | 不重做 Approval/Attachment |
| C06 | RM-16 / Platform Multi-Agent | KEEP | Roadmap | RM-16 仍 BACKLOG；无 Child Run |
| C07 | MCP Catalog Internal 隔离 | MODIFY | Backend MCP Gateway | `tools/list` 可观察对象无 Internal 南向键 |
| C08 | MCP tools/call overlay 拒绝 | MODIFY | Backend MCP Gateway | 员工参数/`client_context` 覆盖 Topology/capability/snapshot 不生效或失败关闭 |
| C09 | Public Run/SSE Internal 隔离 | MODIFY | Backend Skill Run API | GET/SSE/result 无 Internal 键与成员事件；单一 Parent Run |
| C10 | 仓外 Work / 新合同版本 | KEEP | Roadmap | 无 Work 源码 Todo；无 v1.5.0 |

## Behaviour And Security Contract

员工 MCP `tools/list` 只投影已冻结 Public Catalog 字段（名称、描述、inputSchema、executionModes、审批/附件注解等）。`delegation_topology`、`runtime_capability_ref`、ExecutionSnapshot、Hermes instance/profile、成员列表不得出现在工具对象或其嵌套 payload。即使 Published Release `extra_metadata` 含这些键，也不得整包映射。

员工 `tools/call` 不得通过 arguments、`client_context`、headers 覆盖 Topology 或 capability reference。此类键与既有 `_routing`/`_execution`/`route_config` 同类：拒绝或剥离后服务器冻结值仍生效。不得把拒绝降级为静默改写 Topology。

`/api/v1/runs/*` 继续白名单投影。`internal.runtime.trace`、未知内部事件、Snapshot 正文、Topology 枚举不得进入 Public SSE 或 Run view。`runtime_delegated` 成功路径仍只暴露一个 `run_id`。Topology/capability 失败可映射既有 Public `error_code`/`error_message`，但响应不得附带 Internal Snapshot 或 capability 探测原文。

观测 fail-open 不被本项改变。Public 合同三版 fail-closed：任何改写即本项失败。RM-08 入队冻结与 Agent 门禁不被削弱。

## Acceptance Criteria

- **AC-01 / C07**：MCP `tools/list`（员工 `user_jwt` / `mcp_client_token` 可达集合）返回的每个 tool 对象及其嵌套字段不含 `delegation_topology`、`runtime_capability_ref`、ExecutionSnapshot、成员列表或 Internal `skill-agent/` 路径。
- **AC-02 / C07**：Published Release `extra_metadata` 含 Topology 时，Catalog 仍不映出这些键（不得 `update(extra_metadata)`）。
- **AC-03 / C08**：`tools/call` 在 arguments 或 `client_context` 携带 Topology/capability/snapshot/成员键时失败关闭或剥离后不生效；Outbox/Agent 所见仍为服务器冻结值。
- **AC-04 / C08**：既有路由覆盖拒绝（`_routing`/`_execution`/`route_config`）回归仍成立。
- **AC-05 / C09**：`GET /api/v1/runs/{id}`、result、SSE 投影不含 Internal 南向键；`internal.runtime.trace` 与 `subagent.*` 不出现。
- **AC-06 / C09**：同一 Public Run 在 `runtime_delegated` 下仍只有一个 `run_id`，无 Child Run 标识。
- **AC-07 / C01 / C10**：`git diff --exit-code <grounded_commit> -- nodeskclaw-backend/contracts/skill-run/v1.2.1 nodeskclaw-backend/contracts/skill-run/v1.3.0 nodeskclaw-backend/contracts/skill-run/v1.4.0` 为空；不存在新 Public 目录或 tag。
- **AC-08 / C02 / C03 / C04**：Internal Bundle 与 RM-08 freeze/fail-closed 回归仍 PASS。
- **AC-09 / C05 / C06**：本项未重做 RM-17/RM-18；Roadmap 上 RM-16 仍 BACKLOG。
- **AC-10 / C10**：实施与证据不含仓外 Work 源码、构建或发布路径。

## Definition of Done

- **DOD-01**：AC-01 至 AC-10 的 Provider 侧验证证据已留存。
- **DOD-02**：未发布新 Public 合同版本；未改写 v1.2.1～v1.4.0；未新增第三个服务。
- **DOD-03**：MCP/Public 隔离有自动化 oracle；员工 overlay 不生效。
- **DOD-04**：Review 与 Verification 均 PASS；真实 implementation commit 写入 Roadmap 后 RM-09 才可 `DONE`。
- **DOD-05**：`lat.md` 写明员工公共面不暴露 Internal Topology，且 `lat check` 通过。

## Non-Goals

- 不发布 `SKILL-RUN-CONTRACT v1.5.0` 或把 Topology 加成员工可见 Catalog 字段。
- 不承担 RM-17/RM-18 已发布 Capability 的返工。
- 不以 RM-16 live Hermes 内部委派实跑为本项出口。
- 不实现 Platform Multi-Agent / Child Run / 公开成员事件。
- 不改写 Internal `skill-agent` Bundle 或 RM-08 tag。
- 不开发或修改 Work / Portal UI。
- 不把 Portal 运营 Skill CRUD 的 `extra_metadata` 删除（运营仍需发布冻结 Topology）。

## Evidence Baseline

| Claim ID | Requirement | Observable Fact | Blocking | Prior Evidence | Prior Result | Evidence Action | Invalidation Reason |
|---|---|---|---|---|---|---|---|
| CL-01 | Public 三版只读 | 冻结目录与 RM-11/17/18 DONE | yes | rm11/rm17/rm18 verification | PROVEN_FRESH | REUSE_EVIDENCE | 仅当本项改写这些目录 |
| CL-02 | Internal 合同已发布 | tag `skill-agent-contract-v1.0.0` | yes | `docs_agent/evidence/rm08-verification.md` | PROVEN_FRESH | REUSE_EVIDENCE | 仅当改写 Internal Bundle |
| CL-03 | 入队已剥离 Topology overlay | enqueue 测试 | yes | RM-08 V03 | PROVEN_FRESH | TARGETED_RERUN | 本项改 MCP 边界，须证明入队冻结仍在 |
| CL-04 | Public 事件白名单丢弃未知类型 | `_public_run_event` 末尾 `return None` | yes | RM-12/14 公共面 | PROVEN_BUT_AFFECTED | TARGETED_RERUN | 本项须用 Internal 键/trace 类型做否定 oracle |
| CL-05 | MCP list 未整包 extra | `_skill_to_tool` 樱桃采摘 | yes | `mcp_tool_mapper.py` at grounded_commit | NOT_TESTED | NEW_EVIDENCE | — |
| CL-06 | forbidden keys 不含 Topology | `RUNTIME_SKILL_FORBIDDEN_ARGUMENT_KEYS` 三元组 | yes | `mcp_tool_mapper.py` | NOT_TESTED | NEW_EVIDENCE | — |
| CL-07 | RM-17/RM-18 已交付 | Roadmap DONE | yes | rm17/rm18 evidence | PROVEN_FRESH | REUSE_EVIDENCE | 若本项重做 Approval/Attachment |
| CL-08 | RM-16 仍 BACKLOG | Roadmap 表 | yes | ROADMAP RM-16 行 | PROVEN_FRESH | REUSE_EVIDENCE | 若本项把 RM-16 标 READY/DONE |
| CL-09 | 无 Child Run 公共投影 | Public 不投影 `subagent.*` | yes | RM-08 AC-09 / RM-14 | PROVEN_FRESH | TARGETED_RERUN | 若新增 Public 成员事件 |
| CL-10 | 无新 Public 版本 | 无 v1.5.0 目录/tag | yes | contracts/skill-run 目录 | NOT_TESTED | NEW_EVIDENCE | — |

未提交工作树若合入并碰到上述锚点，必须再跑 Evidence Freshness。

## Source Anchors

- `docs_agent/architecture/AD-SKILL-AGENT-V16.md` RM-09 / Option U / Boundaries 10、21–22 / 「客户端不感知委派拓扑」
- `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` RM-09
- `docs_agent/prd-v1.6.17-shared-agent-execution-contract.md`（RM-08 APPROVED；本项不得削弱其 freeze）
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools`
- `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool`
- `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_copy_frozen_attachment_refs`
- `nodeskclaw-backend/app/api/runs.py#_public_run_view`
- `nodeskclaw-backend/app/api/runs.py#_public_run_event`
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_enqueue_agent_run_outbox`
- `nodeskclaw-backend/contracts/skill-run/v1.2.1`～`v1.4.0`
- `nodeskclaw-backend/contracts/skill-agent/v1.0.0`
