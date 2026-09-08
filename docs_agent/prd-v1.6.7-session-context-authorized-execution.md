---
work_item_id: RM-06
version: 1.6.7
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-01T22:39:13+08:00
source_revision: AD-SKILL-AGENT-V16@1.3.0/RM-06
grounded_commit: bce2809677112802301af366c36254e5ddfb063a
---

# DeskClaw 团队版 Session 与授权执行上下文 PRD v1.6.7

本文定义 RM-06：在既有 Agent Run（运行）事实源上，使 Session（会话）成为可审计、可恢复的运行对象，并由 Backend Runtime Skill Run 在入队和执行前消费 Workspace、Attachment 与 Knowledge（工作区、附件、知识）来源域的授权证明，冻结可撤销的执行上下文。

## Scope

本阶段只收敛一个 Run 所属的 Session、上下文引用和授权复核。Backend Runtime Skill Run 是 Skill Run 入队与复核门，只消费来源域签发的授权证明，不拥有 Knowledge ACL（访问控制表），不复制 Workspace/Attachment ACL。Agent 继续拥有 Session/Run/Attempt/Event（会话/运行/尝试/事件）的执行事实、冻结 Context Descriptor（上下文描述符）的持久化事实源与终态裁决。ContextBuilder（上下文构建器）扩展既有 Runtime Skill Run 的入队链路，不建立平行执行服务、第二个 Run 状态机或第二份 Execution Context Store（执行上下文存储）。

本阶段不接管 Work Conversation（工作端会话）内容，不实现 Knowledge 检索、RAG、文件存储、Edge 身份协议、共享 Agent 合同或 OpenTelemetry（开放遥测）。附件字节和知识内容继续由其既有业务域拥有；RM-06 只输出执行所需的授权后稳定引用与最小元数据。已发布 Public Skill Run v1.0–v1.2.1 合同 KEEP（保持），结构化 Descriptor 只作为 Backend↔Agent 内部南向合同。

## Product Boundary

客户端可请求一个 Session 或提交受支持的上下文引用，但不能声称其自身拥有 Workspace、Knowledge 或 Attachment 的权限，不能直接传递未授权内容、内部路径、长期下载 URL 或覆盖 ContextBuilder 结果。Backend Runtime 必须在创建 Agent-owned Run 时向来源域取得授权证明并冻结上下文描述；冻结 Descriptor 写入 Agent Session/Run Snapshot，Backend 不持久化第二份 Execution Context SoT（事实源）。Agent 必须在实际执行前按该描述向 Backend 复核；Backend 复核 Knowledge 引用时必须再次消费 Knowledge 服务的授权证明，不得在 Runtime 内本地重放或缓存为可绕过的 ACL 副本。撤权、跨组织、软删除、过期、来源不可达或描述不一致时必须在模型、Connector 或 Edge 外部副作用前 fail-closed（失败关闭）。

Session 的历史归属、上下文摘要和授权版本可以持久化，但不得持久化原始文件、知识全文、下载凭证或 Work 对话全文。恢复同一 Session 只能复用仍被授权且可复核的引用，不得以旧 Snapshot 绕过撤权。

Architecture 中「Backend 决定可见性与撤权」在本阶段实现为：Backend 是 Skill Run 授权门，消费来源域证明后决定是否入队/继续执行；Knowledge ACL 的唯一 Owner 仍是 Knowledge 服务。这不修订 Architecture Decision，也不把 Knowledge 服务变成 Run 执行 Owner。

## Current Capability Inventory

当前能力以 `bce2809677112802301af366c36254e5ddfb063a` 为准。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Run 关联的 Session 持久化 | PARTIAL | Agent Run 域 | `run_sessions`、`runs.run_session_id` 与 Agent `create_run` | 已有组织关联和跨组织拒绝，但 Session 没有明确生命周期、恢复语义、主体一致校验或上下文版本；MODIFY |
| Run Snapshot 的知识和客户端上下文字段 | PARTIAL | Agent Run 域 | `CreateRunRequest`、`build_snapshot` | 可保存 `knowledge_refs`、`client_context` 和 Session ID，但只是原始引用投影，未形成授权后的规范 Context；MODIFY |
| Runtime Skill Run 入队投影 | PARTIAL | Backend Runtime Skill Run 域 | `RuntimeSkillRunService`；MCP `tools/call` 写入 installation `workspace_id` 与 Release `knowledge_refs` | Workspace 与 Release 知识字符串可进入入队；`StartRuntimeSkillRunRequest` 无 `session_id`/`attachment_refs`，MCP 也不传入这两项；未消费来源授权证明；MODIFY |
| Workspace 与 Attachment 来源权限 | EXISTS | Backend Workspace/上传域 | `workspace_actor_access.require_workspace_actor_access`、uploads/`file_reference_service` | 成员与上传鉴权已存在；KEEP ACL，入队路径尚未调用；由 C03 消费 |
| Knowledge ACL 与内容 | EXISTS | Knowledge 服务 | `nodeskclaw-knowledge` `permission_service.has_set_permission`、`artifact_security_service.authorize_kb_artifact_access`、`agent_tools.tool_search` | ACL、软删除、停用与成员授权证明已存在；KEEP，不复制到 Backend Runtime |
| Knowledge 身份投影 | EXISTS | Backend Auth | `nodeskclaw-backend/app/api/auth.py#knowledge_context` | 只投影组织/成员身份；KEEP，不能代替 Knowledge 授权证明 |
| Knowledge 授权证明查询（供 Skill Run 消费） | MISSING | Backend Runtime Skill Run 消费 / Knowledge 服务签发 | Runtime Skill Run 与 MCP `tools/call` 无授权查询；Backend 无 Knowledge 授权 IPC | 在现有 Runtime Owner 中 ADD 最小授权证明消费，不新增 ACL Store、不实现检索 |
| Agent 执行入口和取消/Fencing | EXISTS | Agent Run/Worker 域 | RM-05 的 AgentEnginePort、Worker 与 Event SoT | 已能消费冻结运行策略；将其扩展为执行前 Context 复核，不创建第二执行 Owner；MODIFY |
| ContextBuilder | MISSING | Backend Runtime Skill Run 域 | 当前没有集中构建或复核授权执行上下文的能力 | 在现有入队 Owner 中 ADD capability，不新增独立服务 |
| 已发布 Public Skill Run 合同 | EXISTS | Backend Skill Run Contract Package | `nodeskclaw-backend/contracts/skill-run/` v1.0–v1.2.1；`ExecutionSnapshot.knowledge_refs`/`attachment_refs` 为字符串数组 | KEEP 字节与公共字段；内部 Descriptor 不得改写 Public 包 |

## Target End-State Inventory

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Formal Run Session（正式运行会话） | Session 具有组织、主体、创建/恢复状态和单调上下文版本；Run 只能关联同组织、同主体可见的 Session；不可恢复指已软删除、已过期或主体失效 | Agent Run 域 | 不保存 Work 对话内容；Session 不可跨组织或跨主体借用 |
| Authorized Execution Context（授权执行上下文） | 每次入队由 Backend Runtime 解析引用并消费来源授权证明，生成最小稳定 Descriptor；该 Descriptor 写入 Agent Snapshot | Backend Runtime Skill Run 构建；Agent Run 持久化 | Backend 不成为第二份 Context Store；不复制 ACL、原始内容或长期凭证 |
| Context Revalidation（上下文复核） | Agent 在每次实际执行前向 Backend 复核；Backend 对 Knowledge 再次消费 Knowledge 服务证明，对 Workspace/Attachment 再次消费 Backend 来源域证明 | Agent Run/Worker 域 + Backend Runtime 门 | 复核结果不能被客户端、旧 Snapshot 或 Runtime 本地 ACL 缓存覆盖 |
| Recoverable Context（可恢复上下文） | 恢复 Run/Session 时仅重用相同规范描述并再次复核；允许的引用保持可追溯，撤权后的引用不会恢复 | Agent Run 域 | 继续使用既有 Attempt/Fencing 和唯一终态规则 |
| Knowledge 授权证明 | Knowledge 服务按组织/成员签发允许或拒绝证明；超时、不可达或无证明视为拒绝 | Knowledge 服务签发；Backend Runtime 消费 | 不把检索、RAG、知识正文或 ACL 行复制进 Skill Run |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Formal Run Session lifecycle（正式运行会话生命周期） | MODIFY | Agent Run 域 | Session 的创建、关联、恢复和组织/主体隔离可审计、可拒绝；不可恢复 Session 不创建 Run |
| C02 | Authorized Execution Context（授权执行上下文） | ADD | Backend Runtime Skill Run 域 | 既有入队链路将来源引用收敛成含授权版本的最小规范描述；Descriptor 只写入 Agent Snapshot |
| C03 | Source authorization consumption（来源授权消费） | MODIFY | Backend Runtime Skill Run 域 | 入队与复核时消费 Workspace/Attachment（Backend 来源域）和 Knowledge（Knowledge 服务）的授权证明；无证明、跨组织、软删除、停用即拒绝。不修改各来源 ACL Owner |
| C04 | Execution-time context revalidation（执行时上下文复核） | MODIFY | Agent Run/Worker 域 | 每次执行/恢复前经 Backend 复核；撤权或不一致时无模型、Connector 或 Edge 副作用 |
| C05 | Run snapshot/Event fencing（运行快照/事件栅栏） | MODIFY | Agent Run/Event Owner | Context 版本、拒绝原因和恢复结果可审计，迟到结果不能绕过取消或撤权 |
| C06 | Existing source content and ACL（既有来源内容与 ACL） | KEEP | Backend Workspace/Attachment 域 + Knowledge 服务 | 不复制内容、不新建 ACL Owner、不改变来源业务域的公开接口语义、不在 Runtime 实现 Knowledge 检索 |
| C07 | Published Public Skill Run contracts（已发布公共技能运行合同） | KEEP | Backend Skill Run Contract Package | v1.0–v1.2.1 Public 包字节与 `ExecutionSnapshot` 字符串引用字段不改写；内部 Descriptor 留给 RM-08 |

## Behaviour And Security Contract

### Session Lifecycle

Session 必须绑定组织与发起主体（与 Run 相同的 `user_id`）。新 Run 关联新或既有 Session 时，Agent 拒绝跨组织、主体不一致或不可恢复 Session，且不得在拒绝后再创建 Run。不可恢复指 Session 已软删除、已过期，或其绑定主体已失效。Session 的恢复不等于重新授权：恢复只恢复稳定引用和历史上下文版本，随后仍必须走 ContextBuilder 和执行前复核。

### Context Construction

Backend Runtime 在创建 Agent-owned Run 前，从已发布 Release 要求和允许的请求上下文中解析 Knowledge、Workspace、Attachment 引用。Session/Attachment 引用若请求携带，必须经授权后写入 Descriptor，不能假设 MCP 入口已经投影完整。结果必须是规范、可审计且最小化的 Context Descriptor，包含引用类型、稳定 ID、来源授权版本/失效条件以及必要的非敏感执行元数据。

对每个 required Knowledge 引用，ContextBuilder 必须向 Knowledge 服务取得针对当前组织与成员的授权证明；对每个 required Workspace/Attachment 引用，必须向 Backend 既有来源域取得授权证明。任何未授权、重复冲突、跨组织、软删除、不可用、来源不可达或无法解析的 required 引用必须拒绝入队。客户端字段不能注入内容、扩大已发布 Release 声明的引用集合或覆盖已冻结的授权结果。Descriptor 只作为内部南向合同写入 Agent Snapshot；不得改写已发布 Public `ExecutionSnapshot` 的字符串引用字段。

### Revalidation And Revocation

Agent 在开始一个 Attempt、恢复一个 Session 或将上下文交给 Central/Edge 执行前，向 Backend 复核 Context Descriptor。Backend 不得用入队时缓存的 ACL 副本代替当场证明。若任一 required 引用在冻结后被撤权、软删除、禁用、转移组织或版本不匹配，或 Knowledge 服务/来源域超时、不可达、返回跨组织或版本不一致，Run 进入稳定的失败/取消安全路径并记录非敏感原因；不得调用模型、Connector（含外部 HTTP/MCP/DB Connector）或创建 EdgeJob。Agent 仍可写入自己的 Run/Attempt/Event 失败终态。复核超时或无法证明授权时同样 fail-closed，不降级为信任客户端 Snapshot。

### Data Minimization And Observability

Snapshot、Event、Artifact、日志和错误只保留 opaque ID、来源类型、版本与安全状态；不得包含知识正文、附件字节、内部文件路径、下载 URL、凭证、完整 Work Conversation 或 Knowledge ACL 行。Context 版本及授权拒绝必须与既有 Run/Attempt/Fencing 关联，重复、旧 Attempt 或迟到事件不得恢复已撤销上下文。

## Acceptance Criteria

- **AC-01 / C01**：创建或关联 Session 时，Session 与 Run 必须同组织且主体一致；跨组织、主体不一致、不可恢复（软删除、过期或主体失效）或伪造 Session ID 被拒绝，且不创建 Run。
- **AC-02 / C01/C05**：同一可恢复 Session 的后续 Run 可追溯到单调 Context 版本与历史 Run；重复请求按既有幂等语义收敛，不创建第二个执行事实。
- **AC-03 / C02/C03**：Backend Runtime 对每个 Knowledge、Workspace、Attachment required 引用消费来源授权证明并生成最小 Context Descriptor。Knowledge 证明必须来自 Knowledge 服务，不得由 Runtime 按组织字符串本地判定。未授权、软删除、跨组织、禁用、来源不可达或无法解析的 required 引用在入队前失败。
- **AC-04 / C02**：客户端不能通过 `client_context`、arguments（参数）或伪造引用注入知识正文、附件字节、内部路径、下载 URL，或扩大已发布 Release 声明的引用集合。
- **AC-05 / C02/C06**：Context Descriptor 只保存 opaque ID、类型、授权版本/失效条件和必要非敏感元数据。Knowledge 服务继续拥有 Knowledge ACL 与内容；Backend Workspace/Attachment 域继续拥有对应 ACL 与内容；不产生第二份授权或内容副本，不实现检索。
- **AC-06 / C04**：Central Connector/Hermes 执行、Direct Edge 和 Hybrid Edge 在首次执行、重试或恢复前均经 Backend 复核 Context；复核失败时没有外部 HTTP/MCP/DB Connector、模型或 EdgeJob 副作用。
- **AC-07 / C04/C05**：Context 冻结后，在 Knowledge 服务撤销成员对 Knowledge 对象的权限或软删除/停用该对象，或在 Backend 来源域撤销 Workspace/Attachment 权限或软删除/停用来源，再恢复或执行 Run 必须 fail-closed；旧 Snapshot 和旧 Attempt 不能绕过撤权。
- **AC-08 / C04**：Backend 或 Knowledge 服务授权复核超时、不可达、返回跨组织或版本不一致结果时，Agent 以稳定、非敏感错误阻断执行，不降级为信任客户端 Snapshot，也不在 Runtime 内回退为仅比对组织 ID。
- **AC-09 / C05**：Context 版本、授权拒绝和恢复决定可在既有 Run/Attempt/Event 事实中审计；重复或迟到事件不能改变已撤权 Run 的终态或重新产生 Artifact。
- **AC-10 / C07**：已发布 Public Skill Run v1.0–v1.2.1 目录字节与公共 `ExecutionSnapshot` 的 `session_id`/`workspace_id`/`knowledge_refs`/`attachment_refs` 字段形态保持不变；内部 Context Descriptor 不进入本阶段 Public 包。
- **AC-11 / C01–C07**：覆盖 Session 创建/恢复、三类来源正反向授权（含 Knowledge 服务撤权而非仅组织比对）、执行前复核、撤权后的 Central/Edge/Hybrid 阻断、Public 合同不改写与数据最小化的自动化验证均通过，且不回归 RM-05 Connector Snapshot、取消与单次派发边界。

## Definition of Done

- **DOD-01**：C01–C07 均有正向、跨组织、撤权、软删除、超时和重放验证证据；Knowledge 正向/撤权证据必须经过 Knowledge 服务授权证明，不能只用 Backend 组织过滤代替；所有 required Context 引用均在执行副作用前复核。
- **DOD-02**：Session 与冻结 Descriptor 持久化只扩展 Agent Run Owner；ContextBuilder 与授权门只扩展 Backend Runtime Skill Run Owner；Knowledge ACL 仍只属于 Knowledge 服务。未新增第二 Run 状态机、独立 ACL Store、来源内容副本或第二份 Execution Context Store。
- **DOD-03**：Snapshot、Event、Artifact、日志和错误经验证不含知识正文、附件字节、内部路径、长期 URL、凭证或 ACL 行。
- **DOD-04**：Review 与 Verification 均 PASS，真实 implementation commit 和验证证据写入 Roadmap 后，RM-06 才可标记 `DONE`。
- **DOD-05**：Session/Context/来源授权消费/执行前复核的 Owner 与边界同步到 `lat.md`，且 `lat check` 通过。

## Non-Goals

- 不实现 Knowledge 检索、RAG、Workspace 文件存储、Attachment 上传或 Work Conversation 内容管理。
- 不把 Knowledge ACL 复制进 Backend Runtime，不把 Knowledge 服务变成 Run 执行 Owner。
- 不实现 RM-07 Edge 身份轮换、消息签名、Nonce 或控制通道协议升级。
- 不实现 RM-08 Shared Agent Contract、RM-09 Consumer Contract 或 RM-10 Trace/Metrics。
- 不改写已发布 Public Skill Run v1.0–v1.2.1 合同字节。
- 不修改外部 Work 前端，不把其构建、发布或导入测试作为本仓交付条件。

## Evidence Baseline

当前证据以 `bce28096` 为准。Knowledge ACL 的生产 Owner 是 Knowledge 服务；Backend Runtime 只消费其授权证明。

| Claim | Evidence Anchor | Result |
|---|---|---|
| Agent 已持久化 Run Session 并在创建 Run 时拒绝跨组织关联 | `nodeskclaw-agent/app/db_metadata.py#run_sessions`、`nodeskclaw-agent/app/services/run_service.py#create_run` at `bce28096` | PARTIAL：可复用表与组织边界，缺正式生命周期、主体一致和 Context 版本 |
| Agent Snapshot 已保存 Session 和知识引用 | `nodeskclaw-agent/app/schemas.py#CreateRunRequest`、`nodeskclaw-agent/app/services/run_service.py#build_snapshot` at `bce28096` | PARTIAL：原始引用可保存，未授权构建/复核 |
| Backend Runtime Run 已投影部分来源引用 | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService` at `bce28096` | PARTIAL：installation `workspace_id` 与 Release `knowledge_refs` 可进入 payload；无 `session_id`/`attachment_refs` 字段，无来源授权证明 |
| Workspace/Attachment 鉴权在 Backend | `nodeskclaw-backend/app/services/workspace_actor_access.py#require_workspace_actor_access`、`nodeskclaw-backend/app/api/uploads.py` at `bce28096` | EXISTS：C03 消费该证明，C06 KEEP ACL |
| Knowledge ACL 在 Knowledge 服务，不在 Backend Runtime | `nodeskclaw-knowledge/app/services/permission_service.py#has_set_permission`、`nodeskclaw-knowledge/app/api/agent_tools.py#tool_search` at `bce28096` | EXISTS：C06 KEEP；Skill Run 不得复制 ACL 或走检索接口完成授权 |
| Backend 仅有 Knowledge 身份投影 | `nodeskclaw-backend/app/api/auth.py#knowledge_context` at `bce28096` | EXISTS：不能代替授权证明；C03 需新增证明消费 |
| Architecture 冻结 Agent Session Owner 与 Backend 来源授权门 | `docs_agent/architecture/AD-SKILL-AGENT-V16.md#Ownership & Boundaries` at `AD-SKILL-AGENT-V16@1.3.0` | 已证实：Backend 是 Skill Run 授权门；Agent 只消费授权结果；Knowledge ACL Owner 是 Knowledge 服务 |
| 已发布 Public Snapshot 使用字符串引用数组 | `nodeskclaw-backend/contracts/skill-run/v1.2.0/runs/run.schema.json`、`nodeskclaw-backend/app/schemas/skill_run/mcp_jsonrpc.py#ExecutionSnapshot` at `bce28096` | EXISTS：C07 KEEP |
| RM-05 已完成统一执行入口 | `docs_agent/roadmaps/ROADMAP-SKILL-AGENT-V16.md` RM-05 at `bce28096` | 已证实：RM-06 可复用执行前 Worker gate，不改变 Connector 归属 |

## Dependencies And Handoff

RM-05 已 `DONE`，RM-06 为 `IN_PRD`。本 PRD 已批准。下一步由 `smc-plan-from-approved-prd-ponytail` 生成实施计划。RM-07 可与本阶段独立推进，但 RM-08 仍必须等待 RM-06 与 RM-07 都完成。
