---
work_item_id: RM-05
version: 1.6.4
status: APPROVED
target_branch: main
review_verdict: PASS
approved_at: 2026-09-01T17:00:00+08:00
source_revision: AD-SKILL-AGENT-V16@1.3.0/RM-05
grounded_commit: 640e504e403554c972e2ae1fc30fe45cac5e6fa0
---

# DeskClaw 团队版 Connector Runtime Execution Closure PRD v1.6.4

本文定义 v1.6 系列的第五个 Stage（交付阶段）：复用现有 Backend Connector（后端连接器）领域和 Agent Execution Plane（执行面），让 REST/MCP/DB Connector 通过唯一 AgentEnginePort（执行引擎端口）在 Central/Edge（中心/边缘）可靠执行，并关闭路由、审批、SecretRef（秘密引用）、私网访问、取消和只读数据库边界。

## Scope

本阶段只处理 ConnectorDefinition、ConnectorInstance、ConnectorTool、SkillConnectorBinding（连接器定义/实例/工具/技能绑定）到不可变 Route Snapshot（路由快照），以及 Agent Central/Edge 对该快照的实际执行。目标覆盖公共 Connector Tool（连接器工具）直接调用和 Published SkillRelease（已发布技能版本）绑定 Connector 的编排调用。

本阶段不新增 Connector 服务、第二 Run（运行）状态机、外部 Work（工作端）前端实现、Session/ContextBuilder（会话/上下文构建器）、Edge Identity（边缘身份）协议或 OpenTelemetry（开放遥测）。RM-04 的分布式生产验收继续独立治理，本 PRD 不把未执行的 Docker（容器）/多实例证据声明为通过。

## Product Boundary

外部客户端只通过 Backend 的 MCP Catalog（MCP 目录）和 Run API（运行接口）调用 Connector，不得提供物理 URL、DB URL（数据库地址）、认证 Header（请求头）、Secret、Edge Node（边缘节点）或 Placement（放置位置）。Backend 继续拥有组织鉴权、Connector 配置、Published Binding（已发布绑定）、审批策略和 Route Snapshot 冻结；Agent 继续拥有 Run/Attempt/Event/Artifact（运行/尝试/事件/产物）执行事实、取消和终态裁决。

Backend 可以保存 EdgeJob（边缘任务）控制面事实，但只有 Agent 执行编排链可以为同一 Run Step（运行步骤）请求一次派发。MCP Mapper（MCP 映射器）不得在创建 Agent-owned Run 后再平行派发第二个 EdgeJob。

## Current Capability Inventory

当前能力以已提交基线 `8ed46fc35e766898a0ffaa45624ebc7caa596123` 为准。工作树中未提交的 RM-04 readiness/storage/harness（就绪/存储/验收工具）改动不计入本清单。

| Capability | Current State | Production Owner | Evidence | Grounding Result |
|---|---|---|---|---|
| Connector 一等领域模型与组织隔离 CRUD（增删改查） | EXISTS | Backend Connector 域 | `nodeskclaw-backend/app/models/connector/`、`nodeskclaw-backend/app/services/connector/connector_service.py#ConnectorService` | Definition/Instance/Tool/Binding/SecretRef 与软删除、组织过滤已存在；KEEP（保持） |
| Connector Catalog 与 Server-managed Route（服务端管理路由） | EXISTS | Backend Hermes Skill/MCP Gateway | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools`、`#_call_connector_tool` | Catalog 只列公开且激活的 Tool，并拒绝客户端 Route Override（路由覆盖）；KEEP |
| AgentEnginePort Connector 分发 | CONFLICT | Agent Engine Port + Connector Adapter | `nodeskclaw-agent/app/services/engine_port.py#execute_engine`、`nodeskclaw-agent/app/services/connector_router.py#execute_connector_run` | Port 传 `route_snapshot/org_id/cancel_event`，Adapter 只接受嵌套 `snapshot`；实际调用在进入 Adapter 前失败；MODIFY（修改） |
| Connector Route Snapshot 形态 | CONFLICT | Backend RuntimeSkillRunService + Agent Run | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService`、`nodeskclaw-agent/app/services/run_service.py#build_snapshot` | Backend 发送 route，Agent 再嵌入 `runtime_policy`；Central 与 Edge 又分别传完整 Snapshot/Prepared Snapshot，Adapter 额外读取一层，缺少唯一规范形态；REPLACE（替换）旧的多形态消费并 REMOVE（移除）平行解释 |
| Public Connector Central/Edge 单次派发 | CONFLICT | Agent Run Worker（执行编排） | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_call_connector_tool`、`nodeskclaw-agent/app/services/worker.py#RunWorker` | Edge Connector 在创建 Agent Run 后由 Mapper 直接创建 EdgeJob，同时 Agent Worker 仍根据 Placement 建 Step Plan；存在重复派发/错误本地执行风险；REPLACE + REMOVE Mapper 平行派发 |
| SkillConnectorBinding 执行快照 | PARTIAL | Backend Connector/SkillRelease 域 | `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService#_resolve_placement`、Agent `build_hybrid_step_plan` | Release 只携带 binding ID；Placement 可判定 hybrid，但 `runtime_policy.connector_bindings` 未由现有 Owner 冻结为可执行列表，Agent 无稳定 Edge Step 输入；MODIFY |
| Connector 审批策略 | PARTIAL | Backend Published Connector Metadata + Agent Approval | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_call_connector_tool`、`nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService` | Catalog 可声明 risk/approval，但 Run 的 `requires_approval` 取自传入 `client_context`，没有强制从服务端 Connector 元数据派生；MODIFY |
| SecretRef 本地解析 | CONFLICT | Backend SecretRef + Agent SecretStore | `nodeskclaw-agent/app/services/run_service.py#build_snapshot`、`nodeskclaw-agent/app/services/secret_store.py#SecretStore` | Agent 通用脱敏会把 `connector_secret_ref_id` 也替换为 `[REDACTED]`，导致 Adapter 无法解析合法引用；任意 Connector config 又可携带未受约束的明文连接信息；MODIFY |
| REST/MCP 网络目标保护 | PARTIAL | Agent Connector Adapter | `nodeskclaw-agent/app/services/connector_router.py#_validate_ssrf` | 已阻断元数据、loopback、link-local 和私网 IP，并在重定向后复核；但 Edge 的合法内网 Connector 同样被全部阻断，缺少服务端冻结的 Trust Zone/Allowlist（信任域/允许列表）；MODIFY |
| DB Connector 只读执行 | PARTIAL | Agent Connector Adapter | `nodeskclaw-agent/app/services/connector_router.py#execute_connector_run` | 仅按 `SELECT/WITH` 前缀检查；`SET TRANSACTION READ ONLY` 失败被忽略，且使用 AUTOCOMMIT（自动提交），不能证明 CTE（公共表表达式）写入或多语句无副作用；MODIFY |
| Connector 取消与 Fencing（栅栏） | PARTIAL | Agent Run/Edge Worker | `nodeskclaw-agent/app/services/worker.py#RunWorker`、`nodeskclaw-agent/app/services/edge_worker.py#EdgeWorker`、Connector Adapter | Worker/Edge 已产生 `cancel_event`，但 Adapter 不接收；网络请求或 DB 查询可能在取消、租约抢占后继续运行并返回完成；MODIFY |
| Connector Adapter 单元测试 | PARTIAL | Agent Test Suite（测试套件） | `nodeskclaw-agent/tests/test_connector_router.py`、`test_hermes_engine.py`、`test_worker.py` | Adapter 直调测试通过，但没有真实 AgentEnginePort Connector 分发；名为 dispatch 的测试只覆盖 Hermes 和 unsupported engine；MODIFY |

## Target End-State Inventory

目标状态只扩展现有 Owner，不新增平行 Connector Runtime。

| Capability | Target State | Production Owner | Boundary |
|---|---|---|---|
| Canonical Connector Route Snapshot（规范连接器路由快照） | 每个 Run/Step 只消费一种冻结形态，包含 Connector kind、Tool、Instance/Binding 引用、Placement、目标策略、非明文 SecretRef 和必要配置摘要 | Backend Connector + SkillRelease 域 | 客户端参数不得覆盖；执行时不得回读可变工作副本或未冻结 Connector 配置 |
| Unified Connector Engine Adapter（统一连接器引擎适配） | Central 与 Edge 都经同一 AgentEnginePort 调用 REST/MCP/DB Adapter，输入、取消和事件合同一致 | Agent Engine Port | 未知 engine/kind、缺字段或形态不一致必须 fail-closed |
| Single Dispatch Ownership（单一派发归属） | Direct Connector 与 Skill-bound Hybrid Run 都由 Agent Step Plan 决定 Central 执行或请求 EdgeJob；同一 Run/Step/Generation 只产生一次有效派发 | Agent Run Worker | Backend MCP Mapper 只创建 Run 和冻结 Snapshot，不平行创建执行副作用 |
| Server-enforced Approval（服务端强制审批） | 有效审批策略从冻结 Connector Tool/Binding 元数据派生；客户端只能请求更严格策略，不能降低 `requiresApproval` 或绕过 `WAITING_APPROVAL` | Backend Connector/Catalog Owner + Agent Approval 状态机 | Agent 仍是审批事实和状态推进 Owner；Backend 只冻结策略并代理决策 |
| SecretRef-safe Execution（安全秘密引用执行） | Snapshot 保留 opaque SecretRef ID（不透明秘密引用标识）但不含明文；Central/Edge 在本地解析，缺失、错作用域或解析失败无外部调用 | Backend SecretRef + Agent SecretStore | 明文 Token、密码、Authorization、带凭证 URL 不得持久化到 Run/Event/Artifact |
| Controlled Network Access（受控网络访问） | Central 默认只允许公共目标；Edge 仅在 Backend 冻结的明确 Trust Zone/Allowlist 内访问私网；云元数据、link-local、loopback、未授权 DNS/重定向目标始终拒绝 | Backend Connector Policy + Agent Connector Adapter | 客户端 arguments 不得扩大目标集合；策略缺失时 fail-closed |
| Read-only DB Execution（只读数据库执行） | DB Connector 使用数据库可证明的只读事务、单语句、超时和行数上限；写 CTE、多语句和只读设置失败均在执行前/执行时拒绝 | Agent Connector Adapter | 不以 SQL 前缀或忽略数据库只读失败作为成功证据 |
| Cancellation-safe Result（取消安全结果） | Cancel、租约丢失或 Delivery Generation（交付代次）失效后，中止可取消的 HTTP/MCP/DB 操作；迟到完成不能推进 Step/Run 终态 | Agent Run/Event Owner | Fencing 和唯一终态规则保持不变 |

## Change Classification

| Change ID | Capability | Action | Production Owner | Observable Target |
|---|---|---|---|---|
| C01 | Connector Engine Port 合同 | MODIFY | Agent Engine Port | REST/MCP/DB 经统一入口可执行，参数形态一致；缺失/未知输入稳定失败 |
| C02 | Connector Route Snapshot | REPLACE + REMOVE | Backend Connector/SkillRelease + Agent Run | 一种冻结形态替代完整 Snapshot、嵌套 runtime_policy 和裸 route 的平行解释；执行不回读可变配置 |
| C03 | Central/Edge/Hybrid 单次派发 | REPLACE + REMOVE | Agent Run Worker | Agent Step Plan 成为唯一执行编排入口；移除 Mapper 在创建 Agent Run 后的平行 EdgeJob 派发 |
| C04 | Connector Approval Policy（审批策略） | MODIFY | Backend Connector/Catalog Owner | 服务端冻结策略决定 WAITING_APPROVAL；客户端不能降低审批要求 |
| C05 | SecretRef 与敏感配置边界 | MODIFY | Backend SecretRef + Agent SecretStore | opaque 引用可解析，明文不进入 Snapshot/Event/日志，失败不产生外部调用 |
| C06 | REST/MCP Network Target Policy（网络目标策略） | MODIFY | Backend Connector Policy + Agent Adapter | Central 公网默认、Edge 显式私网允许列表、元数据永久拒绝、重定向/DNS 复核 |
| C07 | DB Read-only Guard（数据库只读门禁） | MODIFY | Agent Connector Adapter | 写 CTE、多语句、只读事务失败、超时和超量结果均 fail-closed |
| C08 | Connector Cancellation/Event Integration（取消/事件集成） | MODIFY | Agent Run/Event Owner | 取消和抢占可传播；迟到完成被 Fencing 拒绝；Central/Edge 结果语义一致 |
| C09 | Connector Domain/Catalog/Route Override | KEEP | Backend Connector/MCP Gateway | 组织隔离、软删除、公开/激活门禁和客户端路由覆盖拒绝保持不变 |
| C10 | 已发布 Skill Run 合同 | KEEP | Backend Contract Package | v1.0/v1.1/v1.2 合同、Tag 与 checksum 不被本阶段原地改写 |

## Behaviour And Security Contract

### Route Freeze

Backend 在接受调用时必须解析唯一组织内 Connector Tool、Instance、Definition、Published Binding 和 Edge Node，并冻结足以执行的 Route Snapshot。Snapshot 可以保存 opaque ID、非敏感目标配置、策略和摘要，但不能保存明文 Secret、内部鉴权 Token 或由客户端提交的物理路由。

同一 Run 的 Central 与 Edge 消费相同语义的 Route Snapshot；允许传输封装不同，但不得通过“完整 Snapshot 再嵌套 runtime_policy”产生第二种字段解释。Snapshot 缺失必需字段、引用跨组织、Instance 非激活、Tool 非公开或 Binding 不属于 Published Release 时，必须在外部调用前失败。

### Approval

有效审批策略由冻结的 Connector 元数据决定。`requiresApproval=true` 或等价高风险策略必须让 Run 先进入 `WAITING_APPROVAL`，批准后才可派发 Connector；拒绝、取消或未批准不得产生网络/数据库副作用。客户端 `client_context` 不得把 `true` 降为 `false`，也不得通过伪造 `approvalMode` 选择客户端侧旁路。

### SecretRef

SecretRef ID 是可持久化的 opaque reference（不透明引用），不是明文 Secret，不能被通用敏感值脱敏器破坏。Secret 明文只在目标 Agent 的执行时本地解析并注入请求或连接；不得进入 Snapshot、Event、Result、Artifact、日志或错误消息。Backend Connector config 必须拒绝或规范化明显的明文认证字段和带凭证 URL，要求使用 SecretRef/占位符。

### Network Trust

Central Connector 默认只能访问明确允许的公共目标。Edge Connector 可以访问客户内网，但必须由 Backend 冻结的 Trust Zone/Allowlist 授权到协议、主机/网段和端口；客户端业务参数不能扩大该集合。云元数据、link-local、unspecified、multicast 和未授权 loopback 永久拒绝。域名解析和每次重定向都必须重新执行同一目标策略，防止 DNS rebinding（域名重绑定）与跳转绕过。

### DB Read-only

DB Connector 只接受一个只读查询，拒绝多语句、写 CTE、DDL/DML（数据定义/操作语言）、事务控制和未绑定的动态连接地址。数据库连接必须确认只读事务设置成功；无法证明只读时不得执行用户 SQL。查询必须有时间和结果上限，超时、取消或超过上限返回稳定失败，不提交任何写副作用。

## Acceptance Criteria

- **AC-01 / C01**：通过公共 Connector Tool 创建 Central REST、MCP 或 DB Run 后，AgentEnginePort 必须进入对应 Adapter 并产生标准 progress/terminal（进度/终态）事件；不得因 `snapshot/route_snapshot/org_id/cancel_event` 参数不一致返回未处理 TypeError（类型错误）或 500。
- **AC-02 / C01–C02**：相同冻结 Route Snapshot 经 Central Worker 和 Edge Worker 消费时，Connector kind、Tool、目标、SecretRef、Placement 和策略语义一致；多包一层、少一层或缺少必需字段必须在外部调用前返回稳定失败。
- **AC-03 / C02/C09**：客户端在 `tools/call.arguments`、control args（控制参数）或 `client_context` 中提交 URL、DB URL、认证 Header、Secret、`_routing`、`_execution`、`route_config`、Edge Node 或 Placement 时，不能覆盖服务端冻结路由；拒绝保持稳定、无敏感信息。
- **AC-04 / C03**：Direct Edge Connector 创建一个 Agent-owned Run 后，同一 `run_id + step_id + run_generation` 只能产生一个有效 EdgeJob；MCP Mapper 不得平行派发，重复消息通过既有幂等/Fencing 收敛。
- **AC-05 / C02–C03**：Published SkillRelease 同时绑定 Central 与 Edge Connector 时，冻结 Snapshot 必须包含每个有效 Binding 的执行描述符；Agent 先完成满足依赖的 Central Step，再派发目标 Edge Step，并由既有终态聚合器在所有 required step（必需步骤）满足后写唯一终态。
- **AC-06 / C02/C09**：Binding、Instance、Tool 或 Edge Node 跨组织、已软删除、未激活、未公开或不属于该 Published Release 时，Run 创建/派发必须 fail-closed，且不得回读可变工作副本补齐。
- **AC-07 / C04**：服务端 Connector 元数据要求审批时，未批准 Run 稳定处于 `WAITING_APPROVAL`，无 Connector 外部调用或 EdgeJob；批准后只派发一次。客户端传 `requires_approval=false` 或更宽松 `approvalMode` 不能绕过。
- **AC-08 / C04**：服务端策略不要求审批时，客户端可以请求更严格的服务端审批，但不能选择绕过 Agent Approval 状态机的客户端私有模式；最终有效策略和来源可审计。
- **AC-09 / C05**：有效 SecretRef ID 经 Run Snapshot 到 Central/Edge Agent 后仍保持原值并在本地解析；Snapshot、事件、结果、Artifact、日志和错误中不存在明文。引用缺失、错节点、错组织或无法解析时，不发送 HTTP/MCP 请求、不建立 DB 连接。
- **AC-10 / C05**：Connector Instance config 中包含明文 Authorization、Token、Password、API Key 或 URL userinfo（用户信息）时，创建/更新或发布门禁必须拒绝并返回稳定错误；使用 SecretRef 与显式占位符的配置可冻结。
- **AC-11 / C06**：Central 对公共 HTTPS 允许目标可执行；未配置 Edge Trust Policy（边缘信任策略）时私网目标继续拒绝。Edge 只有在冻结 Allowlist 匹配协议、解析地址和端口时可访问内网 MCP/REST，客户端参数不能新增目标。
- **AC-12 / C06**：云元数据、link-local、未授权 loopback、DNS 解析到禁止网段以及重定向到禁止目标均被拒绝；失败响应不得泄漏 Secret 或完整内部连接信息。
- **AC-13 / C07**：DB Connector 拒绝 `WITH ... DELETE/UPDATE/INSERT`、多语句、DDL/DML 和事务控制；只读事务设置失败时不执行用户 SQL。合法参数化 `SELECT`/只读 CTE 在超时和行数上限内返回结果。
- **AC-14 / C08**：Run Cancel、Edge lease（租约）抢占或 Delivery Generation 失效时，Connector Adapter 收到取消信号并停止可取消操作；之后到达的 completed/result 事件不能推进 Step 或 Run 终态。
- **AC-15 / C08**：Central 与 Edge Connector 对成功、上游 4xx/5xx、超时、取消、SecretRef 失败、策略拒绝和 DB 只读拒绝产生一致的标准事件与安全错误；同一来源事件重放不产生第二终态或第二 Artifact。
- **AC-16 / C01–C10**：自动化验证必须从 Backend `tools/call` 进入真实 AgentEnginePort，而不是只直调 Adapter 或完全 mock（模拟）执行入口；同时证明既有组织隔离、软删除、Catalog 门禁、Route Override 拒绝和 Skill Run v1.0/v1.1/v1.2 冻结合同无回归。

## Definition of Done

- **DOD-01**：C01 至 C10 均有正向、拒绝、取消和幂等验证；至少覆盖 Direct Central REST/MCP/DB、Direct Edge Connector 和 Skill-bound Hybrid Connector 三类调用。
- **DOD-02**：AgentEnginePort、Central Worker 与 Edge Worker 只消费一个规范 Route Snapshot 语义；旧的多层解释和 Mapper 平行 EdgeJob 派发已移除，未新增第二执行 Owner。
- **DOD-03**：审批、SecretRef、网络 Trust Policy 和 DB read-only 门禁均在外部副作用前 fail-closed；验证输出不含明文 Secret。
- **DOD-04**：面向 smc-copilot 的当前可交付 `SKILL-RUN-CONTRACT v1.2.1` 必须通过生成、完整性与 release（发布）校验。历史 v1.0/v1.1/v1.2 发布物不由 RM-05 原地改写，但其既有校验和不作为本阶段阻断门禁；如需表达新的公共字段，必须返回 Architecture/Roadmap 创建独立合同 Item，不能在 RM-05 原地扩展。
- **DOD-05**：Review（审查）与 Verification（验证）均 PASS，真实 implementation commit（实施提交）和证据写入 Roadmap 后，RM-05 才可进入 `DONE`。
- **DOD-06**：Connector Runtime 的 Backend/Agent Owner、Snapshot、审批、SecretRef、网络和取消边界同步到 `lat.md`，且 `lat check` 通过。

## Non-Goals

- 不实现 RM-06 Session/ContextBuilder/Knowledge Authorization（会话/上下文/知识授权）。
- 不实现 RM-07 Edge Identity 轮换、消息签名、Nonce 或控制通道协议升级；本阶段只复用既有 Edge Token/HTTPS 边界并关闭 Connector 执行语义。
- 不创建 RM-08 Shared Agent Contract Package（共享执行合同包）。
- 不修改外部 Work 前端，不把前端源码、构建或发布加入 RM-05 验收。
- 不实现 RM-09 外部 Work Skill-first Consumer Contract，也不从外部前端实现反推未批准字段。
- 不实现 RM-10 Agent OpenTelemetry 或完整运行指标。
- 不宣称 RM-04 的 Docker、多 Central、MinIO 或 Newman 两连跑已完成。

## Evidence Baseline

本轮为 RM-05 首次 `discover` Grounding（发现式校准），证据只覆盖 Connector 执行闭环所需的最小 Owner、合同与安全锚点。

| Claim | Evidence Anchor | Result |
|---|---|---|
| Backend 已拥有 Connector 一等模型、组织隔离、软删除与 Published Release 锁定 | `nodeskclaw-backend/app/models/connector/`、`nodeskclaw-backend/app/services/connector/connector_service.py#ConnectorService` at `8ed46fc3` | 已证实；C09 KEEP，不新增服务 |
| Connector Catalog 已冻结 server-managed route 并拒绝客户端覆盖 | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#list_tools`、`#_call_connector_tool` at `8ed46fc3` | 已证实；C09 KEEP |
| Engine Port 与 Connector Adapter 参数合同不一致 | `nodeskclaw-agent/app/services/engine_port.py#execute_engine`、`nodeskclaw-agent/app/services/connector_router.py#execute_connector_run` at `8ed46fc3` | 已证实；Python signature bind 返回 `TypeError: missing a required argument: 'snapshot'`；C01 MODIFY |
| Central/Edge 使用不同嵌套方式传 Connector route | Agent `worker.py#RunWorker`、`edge_worker.py#EdgeWorker`、`connector_router.py#execute_connector_run` at `8ed46fc3` | 已证实；C02 REPLACE 多形态解释 |
| Direct Edge Connector 在 Mapper 创建 Agent Run 后又直接创建 EdgeJob | `nodeskclaw-backend/app/services/hermes_skill/mcp_tool_mapper.py#McpToolMapper#_call_connector_tool` at `8ed46fc3` | 已证实；C03 移除平行派发，执行编排归 Agent |
| Skill binding IDs 可决定 Placement，但没有冻结 Agent Step Plan 所需 binding 描述符 | Backend `runtime_skill_run_service.py#RuntimeSkillRunService#_resolve_placement`、Agent `worker.py#build_hybrid_step_plan` at `8ed46fc3` | 已证实；C02/C03 修改现有 Owner |
| Connector Catalog 审批元数据已存在，但 Run 审批取自 client_context | Backend `mcp_tool_mapper.py#McpToolMapper#_call_connector_tool`、`runtime_skill_run_service.py#RuntimeSkillRunService#_enqueue_agent_run_outbox` at `8ed46fc3` | 已证实；C04 必须服务端派生有效策略 |
| 通用脱敏器会破坏 connector_secret_ref_id | `nodeskclaw-agent/app/services/run_service.py#_sanitize_sensitive_keys`、`#build_snapshot` at `8ed46fc3` | 已证实：key 含 `secret` 即整体替换；C05 保留引用、继续剥离明文 |
| REST/MCP 已有基础 SSRF 防护但全部私网均被拒绝 | `nodeskclaw-agent/app/services/connector_router.py#_validate_ssrf` at `8ed46fc3` | 已证实；C06 增加服务端冻结的 Trust Policy，元数据范围继续永久拒绝 |
| DB 只读依赖前缀正则且忽略只读事务设置失败 | `nodeskclaw-agent/app/services/connector_router.py#execute_connector_run` at `8ed46fc3` | 已证实；C07 必须由数据库只读事务与语句门禁共同证明 |
| 现有测试直调 Adapter，未覆盖 Connector Engine Port | `nodeskclaw-agent/tests/test_connector_router.py`、`test_hermes_engine.py#test_execute_engine_dispatches_hermes_and_connector_fail_closed` at `8ed46fc3` | 已证实：Connector Adapter 6 个测试通过，但所谓 dispatch 测试只执行 Hermes 与 unsupported engine；C01/C16 补真实入口证据 |
| Skill Run v1.0/v1.1/v1.2 合同已发布 | `nodeskclaw-backend/contracts/skill-run/` at `8ed46fc3` | 已证实；C10 KEEP，RM-05 不原地改写合同 |

## Dependencies And Handoff

RM-05 依赖 RM-03，Roadmap 状态已满足；它不依赖仍在 `IN_PRD` 的 RM-04。该分支只允许功能交付继续推进，不改变 RM-04 的生产验收结论。

Stage PRD 已通过 Review Gate 并收敛为 `APPROVED`，下一步由 `smc-plan-from-approved-prd-ponytail` 创建 Plan。当前未提交工作树不能作为 RM-05 已实现证据；若 implementation 前已提交变更触及上述 Evidence Anchor，必须先运行 Evidence Freshness 并定向重校准。
