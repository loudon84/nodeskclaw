---
work_item_id: RM-01
version: 1.6.0
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-08-30T13:17:32+08:00
source_revision: AD-SKILL-AGENT-V16@1.0.0/RM-01
grounded_commit: cdd23a22d36dcb26a9ada1dc2e0b8b5afff8065b
---

# DeskClaw 团队版 Skill Catalog 与 Run Control PRD v1.6.0

本文定义 v1.6 系列的首个 Stage（交付阶段）：修复员工公共 Run Control（运行控制）代理，冻结可由 Work（员工端）稳定消费的 Skill Catalog v1.1（技能目录合同），并保持 Skill Run v1.0.0（技能运行合同）兼容。

## Scope

本阶段只处理 Backend（控制面）的公共 Catalog、Published SkillRelease（已发布技能版本）、Run Proxy（运行代理）与 Skill Run Contract（技能运行合同）。不新增语义 Run Event（运行事件）、Edge Bundle（边缘技能包）协议或分布式生产验收行为；这些能力分别属于 RM-02、RM-03 和 RM-04。

## Product Boundary

员工客户端始终只访问 Backend 的 `/api/v1/mcp` 与 `/api/v1/runs/*`。`/internal/v1/runs/*`、`X-Skill-Agent-Token`（Agent 内部令牌）、Hermes Gateway URL（Hermes 网关地址）和 Credential Lease（凭证租约）不是员工公共合同。

Backend 负责认证、组织授权、Published Release 投影和公共错误映射；Agent 继续负责 Run 状态机、Approval（审批）事实和终态裁决。修复公共代理不得让 Backend 成为第二个 Run 状态 Owner。

## Current Capability Inventory

当前能力以 `cdd23a22d36dcb26a9ada1dc2e0b8b5afff8065b` 为源码基线；相关未提交工作树改动不计入本清单。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| 员工 Run 查询、结果、事件、产物与控制代理 | PARTIAL | `nodeskclaw-backend` Run API（运行接口） | `nodeskclaw-backend/app/api/runs.py` | `resume` 和 `approval` 把 `body` 传给只接受 `json_body` 的内部调用，其余鉴权代理已存在；MODIFY（修改） |
| Published SkillRelease Catalog 投影 | PARTIAL | `nodeskclaw-backend` Hermes Skill 域 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools` | 已投影名称、版本、摘要、审批和路由约束，但 Skill/Connector（技能/连接器）元数据形态不一致；MODIFY |
| 发布元数据冻结 | PARTIAL | `nodeskclaw-backend` `SkillReleaseService` | `nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease`、`nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService` | Release 已冻结 Schema（模式）和 `extra_metadata`（扩展元数据），但没有 Chat/Form（对话/表单）交互合同发布门禁；MODIFY |
| Chat Skill 发布合同校验 | MISSING | `nodeskclaw-backend` `SkillReleaseService` | 未发现与 prompt 字段、交互模式等价的发布校验 Owner | 由现有发布 Owner 扩展；ADD（新增能力），不新增服务 |
| Skill Run v1.0.0 合同包 | EXISTS | `nodeskclaw-backend` Contract Package（合同包） | `nodeskclaw-backend/contracts/skill-run/v1.0.0/`、`nodeskclaw-backend/app/schemas/skill_run/constants.py` | 已发布版本必须 KEEP（保持）且 checksum（校验和）不变 |
| Skill Run v1.1.0 合同包 | MISSING | `nodeskclaw-backend` Contract Package | 当前常量、生成器和 manifest（清单）只声明 `1.0.0` | 在同一合同 Owner 下 ADD，不创建第二套生成链 |
| Server-managed Route（服务端管理路由） | EXISTS | `nodeskclaw-backend` MCP Gateway（MCP 网关） | `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_handle_tools_list`、`nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool` | Catalog 寻址与业务参数路由覆盖已 fail-closed（失败关闭）；KEEP |
| Run Control 公共错误 | PARTIAL | `nodeskclaw-backend` Run API | `nodeskclaw-backend/app/api/runs.py#_agent_post` | 只专门映射 404，其余内部 4xx 可能退化为通用 HTTP client error（客户端错误）；MODIFY |

## Target End-State Inventory

目标状态只扩展现有 Owner，并提供可观察、可版本化的员工合同。

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Run Control 转发 | Resume 与 Approval 请求体、组织和用户执行身份完整转发；不发生 Python 参数错误 | Backend Run API | 只代理 Agent 响应，不在 Backend 独立推进 Agent-owned Run 状态 |
| Catalog Descriptor（目录描述符） | Skill 与 Connector 具有统一的能力类型、交互模式、附件、风险、审批、流式和产物元数据 | Backend MCP Gateway + Published SkillRelease | 路由身份和内部地址不进入公共描述符 |
| Chat Skill 发布门禁 | `interactionMode=chat` 时，`promptField` 指向 `inputSchema.properties` 中的字符串字段 | Backend SkillReleaseService | 新发布必须显式有效；既有 Release 使用确定性兼容映射，不读取可变工作副本补齐 |
| Skill Run v1.1.0 | 由现有生成器产出 Schema、Fixture、manifest 与 checksum，表达 Catalog v1.1 增量 | Backend Contract Package | v1.0.0 文件与 checksum 完全不变；不要求客户端立即切换 |
| Accepted Result（已接受结果） | 现有 `structuredContent` 字段保持兼容，可选返回 `contract_version=1.1.0` | Backend MCP Gateway | 旧客户端忽略新增字段后行为不变 |
| Stable Error（稳定错误） | 非法发布合同、路由覆盖、Run 状态和审批冲突返回稳定 `error_code`、`message_key` 与安全消息 | Backend Public API | 不向员工端泄漏 traceback、内部 Token、Runtime URL 或 Secret |

## Public Catalog Contract v1.1

`tools/list` 中每个 Tool Descriptor（工具描述符）至少包含现有 MCP 字段，以及下列稳定增量：

| Field | Required | Contract |
|---|---:|---|
| `capabilityKind`（能力类型） | 是 | `skill` 或 `connector` |
| `interactionMode`（交互模式） | 是 | `chat` 或 `form` |
| `promptField`（提示词字段） | Chat Skill 必须 | 指向 `inputSchema.properties` 中 `type=string` 的业务字段 |
| `supportsAttachments`（支持附件） | 是 | 布尔值；未声明的兼容值为 `false` |
| `skillReleaseId`（技能发布标识） | Skill 必须 | Published SkillRelease 的不可变标识 |
| `skillReleaseDigest`（技能发布摘要） | Skill 必须 | Published SkillRelease 的不可变摘要 |
| `annotations`（能力注解） | 是 | 包含 `riskLevel`、`requiresApproval`、`approvalMode`、`streaming`、`artifacts` |

新发布的 Skill 必须把上述发布态字段冻结到 Published SkillRelease；Connector 字段来自 Connector Tool（连接器工具）及其定义 Owner。为兼容已发布数据，缺少显式交互元数据的旧 Skill 仅可按冻结的 Release `inputSchema` 确定性映射：存在字符串 `prompt` 字段时映射为 `chat/prompt`，否则映射为 `form`；不得回读可变 Skill 工作副本产生不同结果。

## Publish Gate

Chat Skill（对话技能）发布必须同时满足：

1. `interactionMode` 等于 `chat`；
2. `promptField` 非空；
3. `inputSchema.type` 为 `object`；
4. `inputSchema.properties[promptField].type` 为 `string`；
5. `promptField` 不是 `_routing`、`_execution`、`route_config`、`agent_alias`、`profile`、`workspace_id` 或 `hermes_agent_instance_id`；
6. 发布快照包含确定的 `supportsAttachments` 与 `annotations`。

不满足时拒绝发布并返回 `errors.skill.catalog.invalid_interaction_contract`。校验只阻止新的无效 Published Release，不就地改写历史 Release。

## Change Classification

每个 Change ID（变更编号）代表一个可由后续 Plan 继承的架构原子变更。

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Run Control 请求转发 | MODIFY | Backend Run API | Resume 与 Approval 完整转发 JSON（结构化请求体）和执行身份，不再发生调用参数错误 |
| C02 | Catalog Descriptor 投影 | MODIFY | Backend MCP Gateway | Skill/Connector 输出统一 v1.1 类型、交互与能力字段，且不泄漏运行路由 |
| C03 | Chat Skill 发布门禁 | ADD | Backend SkillReleaseService | 无效 prompt/interaction 合同不能进入 Published 状态 |
| C04 | Skill Run v1.1.0 合同包 | ADD | Backend Contract Package | 新版本 Schema、Fixture、manifest、checksum 可重复生成和校验 |
| C05 | Skill Run v1.0.0 冻结 | KEEP | Backend Contract Package | 已发布文件逐字节和 checksum 保持不变 |
| C06 | Server-managed Route | KEEP | Backend MCP Gateway | Catalog 寻址参数与 Tool arguments（工具参数）中的运行路由覆盖继续被拒绝 |
| C07 | Run Control 稳定错误映射 | MODIFY | Backend Run API | Agent 4xx 状态被映射为稳定、无敏感信息的公共错误合同 |
| C08 | `tools/call` Accepted Result | MODIFY | Backend MCP Gateway | 现有字段不变，仅允许可选增加 `contract_version` |

## Acceptance Criteria

以下 AC（验收条件）证明公共行为，不规定私有实现文件或测试文件。

### AC-RM01-01 — Resume 请求正确转发

对有权访问且处于可恢复状态的 Run 调用 `POST /api/v1/runs/{run_id}/resume` 时，Backend 必须把原始 JSON 请求体及组织/用户执行身份转发给 Agent，不产生 `unexpected keyword argument` 或等价 Python 参数错误。

### AC-RM01-02 — Approval 请求正确且幂等转发

对有权访问的 Approval 调用 `POST /api/v1/runs/{run_id}/approvals/{approval_id}` 时，Backend 必须完整转发 decision（决策）与 evidence（证据）；Agent 返回的已处理结果必须安全投影，重复相同决策不得产生第二次状态副作用。

### AC-RM01-03 — Run Control 保持组织隔离

无权限、组织不匹配或响应中的 `run_id/org_id` 与请求上下文不一致时，Backend 必须 fail-closed，且不得返回 Agent Internal Token（内部令牌）、Runtime URL 或 traceback（调用栈）。

### AC-RM01-04 — Catalog 类型可判定

每个 `tools/list` 条目必须具有 `capabilityKind`、`interactionMode`、`supportsAttachments` 和完整 `annotations`。Skill 还必须具有与 Published Release 一致的 `skillReleaseId` 与 `skillReleaseDigest`；Connector 不得伪造 SkillRelease 标识。

### AC-RM01-05 — Chat Skill 发布门禁

发布 `interactionMode=chat` 的 Release 时，缺失 `promptField`、字段不存在、字段类型不是字符串或字段属于禁止的运行路由键，均必须以 `errors.skill.catalog.invalid_interaction_contract` 拒绝；有效合同可发布并在后续 Catalog 请求中保持稳定。

### AC-RM01-06 — 历史 Release 兼容映射稳定

对缺少 v1.1 元数据的既有 Published Release，Catalog 必须只依据该冻结 Release 的 Schema 与元数据做确定性映射；修改工作副本后，同一 Release 的 v1.1 投影不得改变。

### AC-RM01-07 — 路由覆盖继续拒绝

`tools/list` 携带 `agent_alias/profile/workspace_id`，或 `tools/call.arguments` 携带 `_routing/_execution/route_config` 等运行路由字段时，必须返回既有稳定拒绝错误；v1.1 不得放宽该边界。

### AC-RM01-08 — 合同版本兼容

生成 v1.1.0 后，v1.0.0 的全部文件和 manifest checksum 必须保持不变。v1.1.0 的 Schema 必须验证其正向 Fixture，并拒绝缺少必填字段或枚举非法的负向 Fixture。

### AC-RM01-09 — Accepted Result 向后兼容

`tools/call` 已接受响应中的 `committed`、`run_id`、`status`、`tool_name`、`event_stream`、`result_url`、`artifact_url`、`execution_mode` 和 `request_trace_id` 语义不变；新增 `contract_version` 时必须是可选字段，旧客户端忽略它后仍能工作。

### AC-RM01-10 — 稳定错误而非通用 500

Agent 对 Resume/Approval 返回可预期 4xx 时，Backend 必须返回稳定 `error_code`、`message_key` 与安全 `message`，不能退化为未处理 HTTP client exception（HTTP 客户端异常）或 500。

## Non-Goals

- 不定义 RM-02 的 assistant/reasoning/tool/clarify/artifact（助手/推理/工具/澄清/产物）语义事件。
- 不定义 RM-03 的 Bundle Descriptor、下载或原子安装协议。
- 不宣称 RM-04 的双 Central、Edge、S3/MinIO 或 Newman 两连跑已经通过。
- 不开发 Work UI（员工端界面），不修改 `work-expert v1.0.2` 冻结合同。
- 不新增独立 Catalog Service（目录服务）或 Run Control Service（运行控制服务）。

## Evidence Baseline

证据只覆盖 RM-01 所需的最小 Owner、合同和行为锚点；`grounded_commit` 之后的工作树变化必须通过 Evidence Freshness（证据新鲜度）重新判断。

| Claim | Evidence Anchor | Result |
|---|---|---|
| Backend 是公共 Run Proxy Owner | `nodeskclaw-backend/app/api/runs.py#_agent_post`、`#resume_run`、`#approve_run` at `cdd23a2` | 已证实；C01/C07 修改现有 Owner |
| Resume/Approval 当前存在关键字参数不一致 | 同上 | 已证实；调用传入 `body`，被调用者只声明 `json_body` |
| Published Release 是员工 Catalog 的发布事实源 | `nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease`、`nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools` at `cdd23a2` | 已证实；不新增元数据 Owner |
| 现有 Release 可承载结构化发布元数据 | `nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease` 的结构化列与 `extra_metadata` | 已证实；只有现有结构无法满足约束时才允许数据库变更 |
| Chat 交互发布门禁不存在 | `nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService` at `cdd23a2` | 未发现等价校验；C03 为现有 Owner 下的新增能力 |
| v1.0.0 合同包及生成链存在 | `nodeskclaw-backend/contracts/skill-run/v1.0.0/`、`nodeskclaw-backend/scripts/contracts.py` at `cdd23a2` | 已证实；C04 复用生成链，C05 冻结旧版本 |
| Server-managed Route 已 fail-closed | `nodeskclaw-backend/app/services/mcp_skill_gateway/handler.py#_handle_tools_list`、`nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#call_tool` at `cdd23a2` | 已证实；C06 保持 |

## Dependencies And Handoff

本 PRD 已批准。下一步由 `smc-plan-from-approved-prd-ponytail` 生成实施计划。只有 RM-01 实施、Review（代码审查）、Verification（验证）和真实 implementation commit（实施提交）完成并把 Roadmap 更新为 `DONE`，RM-02 才能进入 `READY` 与下一轮 Grounding。
