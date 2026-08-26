# DeskClaw 团队版 NoDeskClaw Expert Skill MCP Gateway 方案 PRD

**文档版本**：nodeskclaw expert prd v1.0
**文档状态**：方案基线，待架构评审
**发布日期**：2026-08-26
**适用仓库**：`nodeskclaw`（可视化管理系统）
**主要实现范围**：`nodeskclaw-backend`（后端服务）
**主要消费方**：`smc-copilot/apps/work`（工作台客户端）
**兼容基线**：`WORK-EXPERT-CONTRACT v1.0.2`（工作台专家契约）
**输入材料**：`03_nodeskclaw_Skill_MCP_Gateway_Chat_Interface_PRD_v3.2.md`（需求参考稿）

---

# 1. 文档目的

本文定义 NoDeskClaw Expert（专家能力）从发现、授权、路由、执行、事件、对话到产物交付的正式产品与架构方案。

本文不是附件 v3.2 的改名版本。附件只作为需求输入，其中的目标、路径、字段和实施建议均需以仓库现状、冻结契约和本方案决策重新校验。本文是后续设计、开发、迁移、测试和验收的统一基线。

本方案解决三个核心问题：

1. 将调用身份从 `Expert → Skill → Runtime`（专家→技能→运行时）收敛为 `Skill → Installation → Runtime`（技能→安装→运行时）。
2. 将 MCP Gateway（模型上下文协议网关）、Expert（专家展示）、Runtime（运行时执行）和 Work Chat（工作台对话）拆分为边界清晰的组件。
3. 建立可版本化、可审计、可恢复、可扩展的 Skill Invocation（技能调用）数据面。

---

# 2. 执行摘要

目标架构采用“一套调用内核、多个入口适配、多个消费投影”的模式。

```text
入口适配层
  ├─ Generic MCP Gateway（通用 MCP 网关）
  ├─ Work API Facade（工作台接口门面）
  └─ Legacy Expert Adapter（旧专家接口适配器）
                    │
                    ▼
Skill Invocation Core（技能调用内核）
  ├─ Principal / Policy（身份与策略）
  ├─ Skill Revision（技能修订）
  ├─ Route Resolver（路由解析器）
  ├─ Admission Control（准入与容量控制）
  ├─ Task / Lease（任务与执行租约）
  └─ Runtime Adapter（运行时适配器）
                    │
                    ▼
Canonical Run Event（规范运行事件）
  ├─ Task Projection（任务投影）
  ├─ Work Chat Projection（工作台对话投影）
  ├─ Resource Projection（资源投影）
  └─ Audit Projection（审计投影）
```

正式决策如下：

- `HermesSkill`（技能定义）是组织级 Skill（技能）逻辑身份的权威来源。
- 新增不可变 `HermesSkillRevision`（技能修订）概念，冻结版本、Schema（结构定义）、能力和内容摘要。
- `HermesSkillInstallation`（技能安装）是 Skill Revision（技能修订）到 Runtime（运行时）的部署事实，不再兼任注册来源。
- Expert（专家）只负责 Persona（角色形象）、运营编排和 Skill Collection（技能集合），不参与运行时选路。
- 所有入口统一转成 `SkillInvocationCommandV1`（技能调用命令），不得各自维护执行核心。
- MCP（模型上下文协议）只承担协议互操作，不承载 Work（工作台）专属对话语义。
- 数据库保存 `ExpertRunEventV1`（专家运行事件）作为规范事实；Task、Chat、Resource（任务、对话、资源）均为投影。
- 事件写入与发布使用 Transactional Outbox（事务发件箱），避免“未提交先通知”和进程内事件丢失。
- 路由结果在任务受理时冻结为 Route Snapshot（路由快照）；客户端不能指定 Runtime（运行时）、Installation（安装记录）或网关地址。
- `WORK-EXPERT-CONTRACT v1.0.2`（工作台专家契约）保持冻结；新增能力以兼容方式进入后续契约版本，不修改既有校验产物。

---

# 3. 背景与现状依据

## 3.1 已有能力

当前仓库已经具备以下可复用基础，不需要重写：

- Generic MCP Skill Gateway（通用 MCP 技能网关）：支持 `initialize`（初始化）、`tools/list`（工具列表）、`tools/call`（工具调用）、鉴权、审批、授权和审计。
- Expert MCP Gateway（专家 MCP 网关）：支持 Expert / Expert Team（专家/专家团队）目录和异步 Task（任务）返回。
- `HermesSkill`（技能定义）和 `HermesSkillInstallation`（技能安装）：支持组织级技能、多个安装、默认安装、优先级和作用域。
- `SkillRoutingService`（技能路由服务）：支持安装筛选、Runtime（运行时）可路由检查、工作区、默认值和优先级。
- `RuntimeSkillRegistrationService`（运行时技能注册服务）：支持从 Runtime（运行时）发现技能并登记到组织级 MCP（模型上下文协议）目录。
- `RuntimeSkillRunService`（运行时技能执行服务）：可创建 `HermesTask`（Hermes 任务）、签发 SSE（服务端推送）令牌并返回异步执行信息。
- `HermesTaskWorker`（Hermes 任务执行器）：支持队列、Worker Lock（工作进程锁）、Runtime（运行时）调用、事件、取消、超时和产物发现。
- `HermesTaskEvent`（任务事件）、SSE（服务端推送）重放、Result（结果）与 Artifact（产物）接口。
- 冻结的 `WORK-EXPERT-CONTRACT v1.0.2`（工作台专家契约）：已经覆盖异步事件、断点续传、幂等、Owner Policy（所有者策略）、安全取消和 `tools/list`（工具列表）注解。

## 3.2 已核实的现状问题

以下结论来自当前代码，不依赖附件推断：

1. `ExpertRunService`（专家运行服务）通过 Expert（专家）绑定的 Agent（智能体）选择执行实例，创建任务时 `installation_id`（安装记录标识）为空。
2. `SkillRoutingService.resolve_by_tool_name()`（按工具名解析路由）默认允许显式路由，且路由歧义错误仍引导客户端使用 `_routing`（路由覆盖参数）。
3. Runtime Skill（运行时技能）目前使用 `runtime_invocation="chat_completions"`（对话补全调用）描述实际执行，名称不能准确表达 `/v1/runs`（运行接口）或同步 API（应用接口）语义。
4. `HERMES_RUN_DELTA`（Hermes 运行增量）默认被压缩为 `task.progress`（任务进度），不足以稳定表达 Assistant（助手）、Reasoning（推理）、Tool（工具）和 Clarify（澄清）生命周期。
5. `HermesTaskEvent`（任务事件）表只有事件类型、任务内序号、Payload（载荷）和创建时间；附件声称的 `source`（来源）和 `source_event_seq`（来源事件序号）实际被包装在 Payload（载荷）中。
6. 当前 `TaskEventService`（任务事件服务）在事务提交前通知进程内 `EventBus`（事件总线），Worker（工作进程）流式执行期间多次 `flush()`（刷新）但延后 `commit()`（提交），跨进程消费者可能暂时不可见。
7. 当前 Task Status（任务状态）没有 `waiting_input`（等待输入），因此 `clarify.request`（澄清请求）只能展示，不能形成可恢复的暂停/继续闭环。
8. `HermesSkill`（技能定义）的 Version（版本）、Input Schema（输入结构）、Output Schema（输出结构）和能力均可原地修改，历史任务无法稳定指向不可变执行定义。
9. `HermesSkillInstallation`（技能安装）的唯一约束仅覆盖 `skill_id + agent_id`（技能标识+智能体标识），不能完整表达同一 Agent（智能体）下不同 Profile / Workspace / Revision（配置档/工作区/修订）的部署关系。
10. 当前冻结契约明确标记 `runtimeProgress=false`（无运行时细粒度进度）和 `loadGate=unmet`（负载门禁未达标），因此完整 Chat（对话）事件与容量验收仍是未完成能力。

## 3.3 对附件 v3.2 的继承与调整

本方案继承以下方向：

- Skill-First（技能优先）调用。
- `HermesSkillInstallation`（技能安装）驱动 Runtime（运行时）路由。
- Expert Gateway（专家网关）转为兼容适配器。
- Runtime Event Normalizer（运行时事件归一器）。
- DB Replay（数据库重放）作为正确性基础。
- Result（结果）、Chat（对话）与 Artifact（产物）解耦。

本方案调整以下设计：

- 不把 `WorkChatEventV1`（工作台对话事件）直接作为核心事件事实源，改为先保存与客户端无关的 `ExpertRunEventV1`（专家运行事件），再生成消费投影。
- 不把 Work（工作台）专属逻辑放入 Generic MCP Gateway（通用 MCP 网关），改由 Work API Facade（工作台接口门面）和 Projection（投影）承担。
- 不仅区分 Registration Origin（注册来源）和 Invocation Route（调用路由），还增加不可变 Revision（修订）、Route Snapshot（路由快照）和 Execution Lease（执行租约）。
- 不采用“提交后直接发布”的弱一致做法，改用 Transactional Outbox（事务发件箱）保证事件记录与发布意图原子化。
- 不把 Clarify（澄清）只定义为前端事件，增加 `waiting_input`（等待输入）状态和 Resume（继续）协议。
- 不把路由歧义交给客户端解决；默认由服务端稳定选路，只有配置错误才拒绝调用。

---

# 4. 产品目标

## 4.1 目标

### G1：统一技能发现

Work（工作台）用户按 Skill（技能）发现能力，不需要先选择 Expert（专家）或知道 Runtime（运行时）。

### G2：统一调用内核

Generic MCP（通用模型上下文协议）、Work API（工作台接口）和旧 Expert API（专家接口）必须共享同一授权、路由、任务、事件和结果链路。

### G3：稳定且安全的服务端路由

同一个 Skill（技能）可安装到多个 Runtime（运行时），系统基于组织、工作区、会话亲和、健康、容量和策略完成确定性选择。

### G4：完整对话体验

Work Chat（工作台对话）可稳定展示 Assistant Delta（助手增量）、Reasoning（推理）、Tool Call（工具调用）、Tool Result（工具结果）、Clarify（澄清）和 Final Answer（最终回答）。

### G5：可恢复执行

断线重连、Worker（工作进程）重启、事件重复、审批等待、澄清等待、取消和超时均有明确状态与恢复语义。

### G6：可追溯和可审计

每次调用均可回答“谁在何时以什么权限调用了哪个 Skill Revision（技能修订），为什么路由到哪个 Runtime（运行时），产生了哪些事件、结果和产物”。

### G7：平滑迁移

现有 Expert Gateway（专家网关）和 `WORK-EXPERT-CONTRACT v1.0.2`（工作台专家契约）在迁移期可继续工作，不要求一次性替换客户端。

## 4.2 非目标

本版本不包含：

- 重写 Hermes Runtime（Hermes 运行时）。
- 在浏览器或 Work（工作台）客户端中暴露 Runtime Token（运行时令牌）、Provider Key（模型供应商密钥）或路由配置。
- 让 Expert（专家）继续充当 Runtime（运行时）地址。
- 让 MCP（模型上下文协议）承担产品专属 UI（用户界面）全部字段。
- 用进程内 EventBus（事件总线）替代持久化事件和跨进程通知。
- 自动物理删除 `ExpertSkill`（专家技能）或历史事件。
- 在 PRD（产品需求文档）阶段直接改写已冻结的契约校验产物。

## 4.3 成功指标

- Work（工作台）新调用中，Skill-First（技能优先）入口占比达到 95% 以上。
- 100% 新任务包含 `skill_revision_id`（技能修订标识）、`installation_id`（安装记录标识）和 Route Snapshot（路由快照）。
- 客户端路由覆盖请求拦截率为 100%。
- 事件重放后 Chat Projection（对话投影）与在线流结果一致率为 100%。
- 同一 Idempotency Key（幂等键）和相同请求摘要只创建一个任务。
- 同一 Idempotency Key（幂等键）但不同请求摘要被明确拒绝，不复用错误任务。
- 终态任务不存在仍持有有效 Worker Lease（工作进程租约）的记录。
- 事件、结果、审计和 Artifact（产物）均可由 `trace_id`（追踪标识）关联。

---

# 5. 用户与核心场景

## 5.1 Work 用户（工作台用户）

用户查看自己可用的 Skill（技能），发起请求，实时查看过程，必要时补充澄清信息，最后获得回答和产物。

## 5.2 组织管理员

管理员管理 Skill（技能）的可见性、调用权限、风险等级、审批模式、默认安装、路由策略和容量限制。

## 5.3 Expert 运营人员（专家运营人员）

运营人员配置 Expert（专家）的名称、头像、描述、推荐 Skill Collection（技能集合）和排序，不直接绑定调用地址。

## 5.4 Runtime 运维人员（运行时运维人员）

运维人员注册 Runtime（运行时）能力、安装 Skill Revision（技能修订）、查看健康和容量、下线安装并排查路由。

## 5.5 审计人员

审计人员查看身份、授权、审批、路由原因、运行事件、错误、结果与产物链路，不获取敏感正文或密钥。

---

# 6. 设计原则

## 6.1 逻辑身份与部署实例分离

Skill（技能）回答“能做什么”，Revision（修订）回答“以哪个不可变版本做”，Installation（安装）回答“部署在哪里”，Route Policy（路由策略）回答“本次选择哪个”。

## 6.2 Expert 是组合，不是地址

Expert（专家）是 Persona（角色形象）和 Skill Collection（技能集合）。删除或修改 Expert（专家）不得改变 Skill（技能）的逻辑身份，也不得使历史任务失去路由证据。

## 6.3 协议适配与业务内核分离

MCP（模型上下文协议）、REST（表述性状态传输）或内部调用只负责把请求转换为统一命令；业务内核不依赖 JSON-RPC（远程过程调用）字段。

## 6.4 核心事件与消费投影分离

Runtime（运行时）私有事件先归一化为规范运行事件，再投影成 Task、Work Chat 和 Resource（任务、工作台对话和资源）契约。

## 6.5 服务端拥有路由权

客户端只提供业务输入和允许的业务上下文，不提供安装、实例、Profile（配置档）、Gateway URL（网关地址）或强制路由指令。

## 6.6 持久化先于可见

任何可被 SSE（服务端推送）或轮询读取的事件必须已经提交。实时通知只负责唤醒，不负责保存历史。

## 6.7 默认拒绝与最小权限

缺失 Skill Revision（技能修订）、Schema（结构定义）、权限、审批、健康或容量信息时默认拒绝调用，不进行猜测性路由。

---

# 7. 领域模型

## 7.1 Expert（专家）

职责：

- Persona（角色形象）、头像、名称和介绍。
- 推荐 Skill Collection（技能集合）。
- Expert Team（专家团队）的运营编排。
- Work（工作台）中的展示和筛选。

禁止职责：

- 不保存 Runtime Gateway URL（运行时网关地址）。
- 不决定 Installation（安装记录）。
- 不直接持有执行凭据。
- 不成为 `tools/call`（工具调用）的必需路径参数。

## 7.2 HermesSkill（技能定义）

作为组织级 Skill（技能）逻辑身份，保存稳定字段：

- `org_id`（组织标识）。
- `skill_id`（技能标识）。
- `tool_name`（工具名，MCP 调用稳定键）。
- `name/title/description`（名称、标题、描述）。
- `category/tags`（分类、标签）。
- `is_active/is_mcp_exposed`（是否启用、是否经 MCP 暴露）。
- 默认风险、审批和输出策略引用。

`tool_name`（工具名）在组织内唯一。显示名称可变，不能作为调用键。

## 7.3 HermesSkillRevision（技能修订）

新增不可变修订概念，用于版本固定和可重放。

建议字段：

```text
id                         修订标识
org_id                     组织标识
skill_id                   技能标识
version                    语义版本
content_digest             内容摘要
input_schema               输入结构
output_schema              输出结构
capabilities               能力声明
runtime_contract           运行时契约
source_provenance          注册来源证明
status                     draft / published / retired
published_at               发布时间
```

要求：

- Published Revision（已发布修订）不得原地修改。
- Schema（结构定义）、Capability（能力）或 Runtime Contract（运行时契约）变化必须创建新 Revision（修订）。
- 历史任务永久引用具体 Revision（修订），不随当前 Skill（技能）配置变化。
- `content_digest`（内容摘要）用于注册对账、幂等和供应链审计。

## 7.4 HermesSkillInstallation（技能安装）

表示某个 Skill Revision（技能修订）部署到某个 Runtime Endpoint（运行时端点）的事实。

建议职责字段：

```text
org_id                     组织标识
skill_id                   技能标识
skill_revision_id          技能修订标识
runtime_binding_id         运行时绑定标识
agent_id                   智能体标识
profile_id                 配置档标识
workspace_id               工作区标识
status                     pending / installed / draining / offline / failed
is_default                 是否默认
priority                   优先级
capability_snapshot        运行时能力快照
health_snapshot            健康快照
capacity_policy            容量策略
installed_version          已安装版本
```

调整要求：

- Registration Origin（注册来源）进入 Revision Provenance（修订来源证明），不进入调用路由。
- Installation（安装）只描述部署事实，不保存客户端可覆盖参数。
- 唯一约束必须包含 `org_id`（组织标识）和能区分 Revision / Runtime / Profile / Workspace（修订/运行时/配置档/工作区）的键。
- 下线使用 `draining`（排空）和软删除，禁止物理删除历史路由证据。

## 7.5 ExpertSkillBinding（专家技能绑定）

将现有 `ExpertSkill`（专家技能）逐步降级为展示绑定或兼容投影。

长期语义：

```text
Expert / Expert Team（专家/专家团队）
            │
            ▼
HermesSkill（技能定义）
```

绑定可保存展示别名、排序和推荐文案，但风险、审批、Schema（结构定义）和调用开关必须来自 Skill Policy（技能策略）或其明确覆盖层，不能形成第二套事实源。

## 7.6 HermesTask（Hermes 任务）

任务是一次受理后的执行记录，必须保存：

- Principal Snapshot（身份快照）。
- Skill / Revision / Installation（技能/修订/安装）标识。
- Route Snapshot（路由快照）及路由原因。
- Request Digest（请求摘要）和 Idempotency Key（幂等键）。
- Execution Contract（执行契约）。
- Runtime Run ID（运行标识）。
- Worker Lease Token（工作进程租约令牌）和 Lease Generation（租约代次）。
- 状态、超时、重试和取消信息。
- Result（结果）引用与 Artifact（产物）引用。

---

# 8. 目标架构

## 8.1 控制面

Control Plane（控制面）负责低频配置和治理：

```text
Skill Registry（技能注册中心）
  ├─ Skill Identity（技能身份）
  ├─ Immutable Revision（不可变修订）
  └─ Schema / Capability（结构定义/能力）

Installation Registry（安装注册中心）
  ├─ Runtime Binding（运行时绑定）
  ├─ Health / Capacity（健康/容量）
  └─ Drain / Offline（排空/离线）

Policy Center（策略中心）
  ├─ Visibility / Invoke（可见/调用）
  ├─ Risk / Approval（风险/审批）
  ├─ Routing Policy（路由策略）
  └─ Quota / Rate Limit（配额/限流）

Expert Composition（专家组合）
  └─ Persona + Skill Collection（角色形象+技能集合）
```

## 8.2 数据面

Data Plane（数据面）负责高频调用：

```text
Client（客户端）
  │
  ▼
Entry Adapter（入口适配器）
  │
  ▼
Invocation Orchestrator（调用编排器）
  ├─ Authenticate（认证）
  ├─ Authorize（授权）
  ├─ Validate Schema（校验结构）
  ├─ Evaluate Approval（判断审批）
  ├─ Admission Control（准入控制）
  ├─ Resolve Route（解析路由）
  └─ Create Task + Outbox（创建任务+事务发件箱）
  │
  ▼
Task Worker（任务工作进程）
  ├─ Acquire Lease（获取租约）
  ├─ Runtime Adapter（运行时适配器）
  ├─ Normalize Event（归一化事件）
  └─ Finalize Result（完成结果）
  │
  ▼
Durable Event Log（持久事件日志）
  ├─ Task SSE（任务服务端推送）
  ├─ Work Chat（工作台对话）
  ├─ Resource（资源）
  └─ Audit（审计）
```

## 8.3 服务边界

建议形成以下模块边界，具体文件名可在技术设计阶段调整：

```text
app/services/skill_invocation/
├─ command.py                       统一调用命令
├─ orchestrator.py                  调用编排
├─ policy_service.py                授权与审批策略
├─ admission_service.py             准入与容量控制
├─ route_resolver.py                服务端路由
├─ idempotency_service.py           幂等与冲突检测
└─ runtime_contract.py              运行时契约

app/services/skill_event/
├─ contract.py                      规范运行事件
├─ normalizers/                     各运行时事件归一器
├─ event_store.py                   持久化事件
├─ outbox_service.py                事务发件箱
└─ projections/                     任务/对话/资源投影

app/services/work_skill/
├─ catalog_projection.py            工作台技能目录
└─ chat_projection.py               工作台对话投影
```

现有 `mcp_skill_gateway`（MCP 技能网关）、`expert_gateway`（专家网关）和 `hermes_skill`（Hermes 技能）模块作为入口或基础设施逐步委托给新内核，不并行复制业务逻辑。

---

# 9. Skill Catalog（技能目录）

## 9.1 通用 MCP 发现

第三方 MCP Client（模型上下文协议客户端）继续使用 `tools/list`（工具列表）。

Tool Descriptor（工具描述）必须包含标准字段：

```json
{
  "name": "customer_profiling",
  "description": "生成企业客户画像",
  "inputSchema": {
    "type": "object",
    "properties": {
      "prompt": {"type": "string"},
      "attachmentRefs": {
        "type": "array",
        "items": {"type": "string"}
      }
    },
    "required": ["prompt"],
    "additionalProperties": false
  },
  "annotations": {
    "skillId": "customer-profiling",
    "revision": "1.2.0",
    "displayName": "客户画像",
    "category": "sales",
    "status": "ready",
    "callEnabled": true,
    "riskLevel": "low",
    "approvalMode": "auto",
    "capabilities": {
      "streaming": true,
      "reasoning": true,
      "toolEvents": true,
      "clarify": true,
      "artifacts": true
    }
  }
}
```

`annotations`（注解）是增强字段。标准 MCP Client（模型上下文协议客户端）可忽略，Work（工作台）可消费。

## 9.2 Work Skill Catalog API（工作台技能目录接口）

Work（工作台）需要分类、可用性、能力、权限和展示信息，因此提供只读 Projection API（投影接口）：

```http
GET /api/v1/work/skills
```

支持参数：

```text
keyword                     关键字
category                    分类
status                      状态
expert_slug                 专家标识，仅用于展示筛选
cursor                      游标
limit                       数量上限
```

目录项目由以下信息合成：

```text
HermesSkill（技能定义）
+ Published Revision（已发布修订）
+ Authorization（授权）
+ Approval Policy（审批策略）
+ Routable Installation（可路由安装）
+ Runtime Health / Capacity（运行时健康/容量）
= WorkSkillItem（工作台技能项）
```

`status=ready`（可用）必须同时满足：

- Skill（技能）启用且对当前 Channel（渠道）暴露。
- 存在 Published Revision（已发布修订）。
- 当前 Principal（身份主体）可见并可调用。
- 至少一个 Installation（安装）通过健康、版本和容量硬过滤。
- 不存在阻断调用的审批或策略配置错误。

目录接口不得返回 Runtime Endpoint（运行时端点）、Installation ID（安装记录标识）、Token（令牌）或内部路由分数。

## 9.3 缓存与一致性

- Catalog Projection（目录投影）允许短时缓存，建议 TTL（生存时间）为 30 秒。
- 权限、Skill（技能）停用、Installation（安装）排空和 Runtime（运行时）离线必须主动失效缓存。
- `tools/call`（工具调用）必须重新执行授权、路由和容量检查，不能信任目录缓存。

---

# 10. 统一调用命令

## 10.1 SkillInvocationCommandV1（技能调用命令）

所有入口必须转换为以下内部结构：

```json
{
  "schemaVersion": "1.0",
  "entrypoint": "mcp",
  "principal": {
    "orgId": "org-1",
    "userId": "user-1",
    "memberId": "member-1",
    "scopes": ["skill:view", "skill:invoke"]
  },
  "toolName": "customer_profiling",
  "arguments": {
    "prompt": "请生成客户画像",
    "attachmentRefs": []
  },
  "businessContext": {
    "workspaceId": "ws-1",
    "conversationId": "conv-1"
  },
  "client": {
    "source": "apps/work",
    "version": "1.0",
    "deviceId": "device-1"
  },
  "clientRequestId": "request-1",
  "traceId": "trace-1"
}
```

`principal`（身份主体）只能由服务端认证层生成。客户端 Payload（载荷）中的同名字段不得覆盖。

## 10.2 保留字段

外部调用参数出现以下字段时必须拒绝，而不是静默删除：

```text
_routing                    路由覆盖
_execution                  执行覆盖
route_config                路由配置
installation_id             安装记录标识
agent_id                    智能体标识
profile_id                  配置档标识
runtime_id                  运行时标识
gateway_url                 网关地址
force_instance              强制实例
execution_contract          执行契约
```

错误返回必须包含 `error_code`（错误码）、`message_key`（消息键）和 `message`（消息）。

## 10.3 处理顺序

调用编排器必须按以下顺序执行：

```text
01 解析并冻结 Principal（身份主体）
02 解析 Skill（技能）和 Published Revision（已发布修订）
03 校验可见性、调用权限和 Channel（渠道）
04 拒绝保留字段
05 校验 Input Schema（输入结构）
06 计算 Request Digest（请求摘要）
07 执行 Idempotency（幂等）检查
08 判断 Risk / Approval（风险/审批）
09 执行 Admission Control（准入控制）
10 解析 Installation（安装）
11 冻结 Route Snapshot（路由快照）和 Execution Contract（执行契约）
12 同一事务创建 Task / Initial Event / Outbox（任务/初始事件/发件箱）
13 提交事务
14 签发短期 SSE Token（服务端推送令牌）
15 返回 Accepted Response（已受理响应）
```

任何外部 Runtime I/O（运行时输入输出）不得发生在受理事务内。

---

# 11. 服务端路由

## 11.1 路由输入

Route Resolver（路由解析器）只接收服务端可信输入：

- `org_id`（组织标识）。
- `skill_revision_id`（技能修订标识）。
- `workspace_id`（工作区标识）。
- `conversation_id`（会话标识）。
- Principal Policy（身份策略）。
- Installation Health / Capacity（安装健康/容量）。
- Admin Route Policy（管理员路由策略）。

## 11.2 两阶段选择

第一阶段为 Hard Filter（硬过滤）：

```text
同组织
未软删除
status = installed
revision 兼容
runtime 可路由
未处于 draining / offline
权限允许
协议能力满足
未超过硬容量
```

第二阶段为 Deterministic Ranking（确定性排序）：

```text
1. 管理员 Pinned Policy（固定策略）
2. Conversation Affinity（会话亲和）
3. Workspace Affinity（工作区亲和）
4. 唯一 Default Installation（默认安装）
5. Policy Weight + Available Capacity（策略权重+可用容量）
6. Stable Hash（稳定哈希）
```

Stable Hash（稳定哈希）建议基于：

```text
org_id + skill_revision_id + workspace_id/conversation_id
```

这保证在候选集合不变时选择稳定，同时避免依赖创建时间的隐式随机性。

## 11.3 路由模式

- `auto`（自动）：默认模式，执行硬过滤和确定性排序。
- `pinned`（固定）：仅由管理员策略或兼容适配器产生，必须引用有效 Installation（安装记录）。
- `affinity`（亲和）：优先保持会话或工作区一致；原安装不可用时按明确策略失败或重新选择。

客户端不能选择模式。

## 11.4 路由快照

受理时保存不可变 Route Snapshot（路由快照）：

```json
{
  "schemaVersion": "1.0",
  "policyVersion": "route-policy-7",
  "skillId": "customer-profiling",
  "skillRevisionId": "revision-12",
  "installationId": "installation-3",
  "runtimeBindingId": "runtime-2",
  "adapter": "hermes_runs_v1",
  "reason": "workspace_affinity",
  "candidateCount": 3,
  "selectedAt": "2026-08-26T01:00:00Z"
}
```

快照不返回普通客户端，只用于 Worker（工作进程）、调试和审计。

## 11.5 重试与重路由

- Runtime（运行时）调用开始前失败，可按 Retry Policy（重试策略）重新选路。
- Runtime（运行时）已确认创建 Run（运行）后，禁止自动切换到另一 Installation（安装），除非 Skill Revision（技能修订）声明幂等且上游可提供幂等 Run Key（运行键）。
- 每次重路由增加 `route_generation`（路由代次）并记录旧、新路由原因。
- Pinned Policy（固定策略）默认不允许自动重路由。

---

# 12. Runtime Contract（运行时契约）

## 12.1 版本化适配器

替换含糊的 `chat_completions`（对话补全）描述，使用明确适配器：

```text
hermes_runs_v1              Hermes /v1/runs + /events
hermes_sync_v1              Hermes 同步 API Server
mcp_upstream_v1             上游 MCP Server
```

Execution Contract（执行契约）示例：

```json
{
  "schemaVersion": "1.0",
  "adapter": "hermes_runs_v1",
  "mode": "async_event",
  "supports": {
    "streaming": true,
    "reasoning": true,
    "toolEvents": true,
    "clarify": true,
    "cancel": true,
    "artifacts": true
  },
  "timeouts": {
    "connectSeconds": 10,
    "idleSeconds": 120,
    "totalSeconds": 1800
  }
}
```

## 12.2 能力协商

有效能力取交集：

```text
Skill Revision Capability（技能修订能力）
∩ Installation Capability Snapshot（安装能力快照）
∩ Runtime Health Capability（运行时健康能力）
= Effective Capability（有效能力）
```

如果 Work（工作台）请求的体验依赖 `clarify=true`（支持澄清）或 `toolEvents=true`（支持工具事件），而候选 Runtime（运行时）不支持，则该候选在硬过滤阶段淘汰。

## 12.3 Runtime Adapter（运行时适配器）职责

- 构建上游请求。
- 注入服务端凭据，禁止把凭据写入 Task Payload（任务载荷）。
- 创建、查询、取消 Runtime Run（运行时运行）。
- 将原始事件交给对应 Normalizer（归一器）。
- 处理连接、空闲和总时长超时。
- 报告明确的 Retryable（可重试）分类。

Runtime Adapter（运行时适配器）不得决定业务授权、Skill（技能）可见性和 Work Chat（工作台对话）结构。

---

# 13. Task（任务）状态机

## 13.1 状态集合

目标状态：

```text
queued                       已排队
accepted                     已受理
waiting_approval             等待审批
running                      运行中
waiting_input                等待用户输入
cancel_requested             已请求取消
completed                    已完成
failed                       已失败
cancelled                    已取消
timeout                      已超时
```

## 13.2 主要转换

```text
queued → accepted → running → completed
                    ├──────→ failed
                    ├──────→ timeout
                    ├──────→ cancel_requested → cancelled
                    └──────→ waiting_input → running

accepted → waiting_approval → queued / failed
```

状态转换必须使用 Compare-And-Set（比较并设置）或数据库条件更新，旧 Worker（工作进程）不能覆盖新状态。

## 13.3 Worker Lease（工作进程租约）

任务领取必须生成：

```text
worker_id                    工作进程标识
lease_token                  租约令牌
lease_generation             租约代次
lease_expires_at             租约到期时间
heartbeat_at                 心跳时间
```

终态写入必须校验 `lease_token + lease_generation`（租约令牌+租约代次）。租约过期后，旧 Worker（工作进程）的迟到结果不得覆盖新 Worker（工作进程）。

## 13.4 Clarify / Resume（澄清/继续）

Runtime（运行时）发出澄清请求时：

1. 写入 `input.requested`（请求输入）规范事件。
2. 将任务从 `running`（运行中）转换为 `waiting_input`（等待输入）。
3. 释放执行槽位，但保留任务和 Runtime Run（运行时运行）关联。
4. Work（工作台）显示 Clarify Message（澄清消息）。
5. 用户通过 Resume API（继续接口）提交输入。
6. 服务端重新校验 Owner（所有者）、期限和 Input Schema（输入结构）。
7. 写入 `input.received`（已收到输入）事件并恢复 `running`（运行中）。

建议接口：

```http
POST /api/v1/hermes/tasks/{task_id}/inputs
```

重复提交使用 `input_request_id + client_request_id`（输入请求标识+客户端请求标识）幂等。

---

# 14. 规范事件与对话投影

## 14.1 ExpertRunEventV1（专家运行事件）

核心事件与客户端无关：

```json
{
  "schemaVersion": "1.0",
  "eventId": "task-1:17",
  "orgId": "org-1",
  "taskId": "task-1",
  "runId": "run-1",
  "seq": 17,
  "occurredAt": "2026-08-26T01:00:00Z",
  "type": "tool.completed",
  "source": {
    "adapter": "hermes_runs_v1",
    "sourceEventId": "runtime-event-33",
    "sourceSeq": 33
  },
  "payload": {
    "callId": "call-1",
    "toolName": "search",
    "summary": "检索完成"
  }
}
```

要求：

- `taskId + seq`（任务标识+序号）唯一。
- `sourceEventId`（来源事件标识）存在时用于去重。
- 同一 Task（任务）内序号严格递增。
- Payload（载荷）必须通过按事件类型定义的 Schema（结构定义）校验。
- 敏感参数、密钥、全文文件和未经授权的工具输出不得进入事件。

## 14.2 事件类型

最小集合：

```text
run.accepted                 运行已受理
run.started                  运行已开始
message.delta                助手消息增量
message.completed            助手消息完成
reasoning.delta              推理增量
reasoning.completed          推理完成
tool.started                 工具开始
tool.progress                工具进度
tool.completed               工具完成
tool.failed                  工具失败
input.requested              请求用户输入
input.received               已收到用户输入
artifact.ready               产物可用
run.completed                运行完成
run.failed                   运行失败
run.cancelled                运行取消
run.timeout                  运行超时
```

## 14.3 Runtime Normalizer（运行时归一器）

每种 Runtime Adapter（运行时适配器）有独立 Normalizer（归一器）：

```text
Hermes Raw Event（Hermes 原始事件）
            │
            ▼
HermesRunsV1Normalizer（Hermes Runs v1 归一器）
            │
            ▼
ExpertRunEventV1（专家运行事件）
```

未知事件：

- 保留到受限 Raw Event Log（原始事件日志）供诊断。
- 不直接透传到外部客户端。
- 记录 `event_normalization_unknown_total`（未知事件归一计数）。
- 不得伪装成 `message.delta`（消息增量）。

## 14.4 WorkChatEventV1（工作台对话事件）

由规范事件投影生成：

```text
run.started                  → work.run.started
message.delta                → work.message.delta
message.completed            → work.message.complete
reasoning.delta              → work.reasoning.delta
tool.started                 → work.tool.start
tool.progress                → work.tool.progress
tool.completed               → work.tool.complete
tool.failed                  → work.tool.failed
input.requested              → work.clarify.request
run.completed                → work.run.completed
run.failed                   → work.run.failed
run.cancelled                → work.run.cancelled
```

Work（工作台）只能消费 `work.*`（工作台事件）投影构建 Chat（对话）；`task.progress`（任务进度）仅用于通用 Task Timeline（任务时间线）。

## 14.5 Resource Projection（资源投影）

Artifact（产物）进入独立 Resource Event（资源事件）：

```text
artifact.ready
  └─ WorkResourceEventV1（工作台资源事件）
       ├─ artifactId          产物标识
       ├─ name                名称
       ├─ mediaType           媒体类型
       ├─ size                大小
       ├─ previewUrl          预览地址
       └─ downloadUrl         下载地址
```

Chat Message（对话消息）只保存引用，不内嵌文件正文。

## 14.6 持久化与发布

同一短事务执行：

```text
写 ExpertRunEventV1（专家运行事件）
+ 写 Projection Cursor（投影游标）或 Outbox（发件箱）
+ 更新必要 Task State（任务状态）
→ commit（提交）
```

Outbox Dispatcher（发件箱分发器）在提交后发布到 PostgreSQL NOTIFY（数据库通知）、Redis Pub/Sub（Redis 发布订阅）或未来消息系统。发布至少一次，消费者以 Event ID（事件标识）去重。

SSE（服务端推送）正确性来自数据库重放，通知只降低延迟。

---

# 15. MCP Gateway（模型上下文协议网关）

## 15.1 职责

Generic MCP Gateway（通用 MCP 网关）只负责：

- JSON-RPC 2.0（远程过程调用）解析。
- MCP Protocol Version（协议版本）协商。
- Bearer Token（持有者令牌）认证入口。
- `tools/list`（工具列表）和 `tools/call`（工具调用）协议映射。
- 将内部错误映射为 JSON-RPC Error（远程过程调用错误）。
- 调用统一 Skill Invocation Core（技能调用内核）。

禁止在 Gateway（网关）中新增 Work Chat（工作台对话）拼装、Runtime（运行时）选路或长时间阻塞等待。

## 15.2 tools/call（工具调用）

请求示例：

```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "method": "tools/call",
  "params": {
    "name": "customer_profiling",
    "arguments": {
      "prompt": "请生成客户画像",
      "attachmentRefs": [],
      "context": {
        "workspaceId": "ws-1",
        "conversationId": "conv-1",
        "clientRequestId": "request-1"
      }
    }
  }
}
```

受理响应示例：

```json
{
  "content": [
    {"type": "text", "text": "任务已启动，请等待事件流通知完成"}
  ],
  "structuredContent": {
    "task_id": "task-1",
    "status": "running",
    "event_stream": "/api/v1/hermes/tasks/task-1/events?token=sse_xxx",
    "event_token_url": "/api/v1/hermes/tasks/task-1/events-token",
    "result_url": "/api/v1/hermes/tasks/task-1/result",
    "artifact_url": "/api/v1/hermes/tasks/task-1/artifacts",
    "wait_strategy": {
      "type": "sse",
      "fallback": "poll"
    },
    "committed": true
  },
  "isError": false
}
```

响应中的 `committed=true`（已提交）表示 Task（任务）、初始事件和幂等记录已经提交。

## 15.3 Poll Fallback（轮询降级）

保留：

```http
GET /api/v1/hermes/tasks/{task_id}
GET /api/v1/hermes/tasks/{task_id}/result
GET /api/v1/hermes/tasks/{task_id}/events?after_seq={seq}
GET /api/v1/hermes/tasks/{task_id}/artifacts
```

SSE（服务端推送）与 Poll（轮询）必须读取同一规范事件和投影，不得各自定义字段。

---

# 16. 身份、权限与安全

## 16.1 Principal Snapshot（身份快照）

任务受理时冻结：

```text
org_id                      组织标识
user_id                     用户标识
member_id                   成员标识
roles                       角色
scopes                      权限范围
workspace_id                工作区标识
client_source               客户端来源
auth_subject_hash           认证主体摘要
```

不保存原始 Bearer Token（持有者令牌）。

## 16.2 权限模型

目标权限：

```text
skill:view                  查看技能
skill:invoke                调用技能
skill:manage                管理技能
skill:approve               审批技能调用
skill:route_manage          管理路由
task:view_own               查看自己的任务
task:cancel_own             取消自己的任务
task:audit                  审计任务
```

兼容期可将 `expert_skill:*`（专家技能权限）映射到新权限，但新入口不得要求 Expert（专家）管理权限。

## 16.3 授权时点

- `tools/list`（工具列表）检查可见权限。
- `tools/call`（工具调用）重新检查调用权限和审批。
- SSE Token（服务端推送令牌）签发时检查 Task Owner（任务所有者）。
- Result / Artifact（结果/产物）读取时按当前权限重新鉴权。
- 历史 Chat（对话）或 Artifact URL（产物地址）不是长期权限凭证。

## 16.4 风险与审批

审批策略由 Skill Policy（技能策略）决定：

```text
auto                        自动
server                      服务端审批
desktop                     桌面端确认
hybrid                      混合审批
```

审批通过必须绑定：

```text
principal + skill_revision + arguments_digest + expiry
```

修改参数或 Revision（修订）后必须重新审批。

## 16.5 附件安全

- `attachmentRefs`（附件引用）只能引用当前用户可访问的受管资源。
- 服务端在调用前重新校验 Owner / ACL（所有者/访问控制）。
- Runtime（运行时）只接收短期授权或受控内容，不接收对象存储主密钥。
- Artifact（产物）下载使用短期签名或受鉴权代理。

## 16.6 日志脱敏

禁止记录：

- Bearer Token（持有者令牌）。
- Runtime Token（运行时令牌）。
- Provider Key（模型供应商密钥）。
- 原始附件全文。
- 未经脱敏的高风险工具参数和结果。

---

# 17. 幂等、限流与容量

## 17.1 幂等键

幂等作用域：

```text
org_id + principal_id + tool_name + skill_revision_id + client_request_id
```

同时保存规范化 `arguments_digest`（参数摘要）。

处理规则：

- 相同幂等键、相同摘要：返回已有任务。
- 相同幂等键、不同摘要：返回 `IDEMPOTENCY_CONFLICT`（幂等冲突），不得复用。
- 已完成任务：返回已有结果地址和新签发的短期事件令牌。
- 运行中任务：返回已有任务和新签发的短期事件令牌。

## 17.2 准入控制

任务创建前检查：

```text
org_max_queued              组织最大排队数
user_max_running            用户最大运行数
skill_max_running           技能最大运行数
installation_max_running    安装最大运行数
runtime_max_running         运行时最大运行数
```

超限时返回稳定错误和 `retry_after_seconds`（建议重试秒数），不先创建任务再让队列无限增长。

## 17.3 公平性

Worker（工作进程）调度至少按组织和用户实现基本公平，避免单一组织、用户或 Skill（技能）占满全局执行槽。

建议调度键：

```text
priority + org_fair_share + queue_entered_at
```

管理员优先级不能绕过硬容量和租户隔离。

## 17.4 背压

- Runtime（运行时）事件生产速度高于写入速度时使用有界 Buffer（缓冲区）。
- Buffer（缓冲区）接近上限时优先合并连续 `message.delta`（消息增量），不得丢失 Tool / Input / Terminal（工具/输入/终态）事件。
- 事件持久化失败时暂停读取或取消上游 Run（运行），不得继续产生不可恢复的 UI（用户界面）事件。

---

# 18. 事务、一致性与恢复

## 18.1 短事务边界

```text
Tx1 受理：幂等记录 + Task + Route Snapshot + 初始 Event + Outbox
Tx2 领取：Lease + accepted Event + Outbox
Tx3 开始：running + run.started + Outbox
Txn 事件：单个或小批规范 Event + Outbox
TxN 终态：状态 + Result Ref + terminal Event + Outbox
TxA 产物：Artifact Record + artifact.ready + Outbox
```

任何 Runtime Network I/O（运行时网络输入输出）不得持有数据库事务。

## 18.2 事件写入

- Event Sequence（事件序号）分配必须在 Task Row Lock（任务行锁）或等价原子机制内完成。
- Event（事件）与 Outbox（发件箱）同事务写入。
- EventBus（事件总线）只能由已提交 Outbox（发件箱）驱动。
- SSE（服务端推送）先按 `Last-Event-ID`（最后事件标识）重放，再等待通知，再补拉数据库，防止通知竞争窗口。

## 18.3 Worker 恢复

- Worker（工作进程）定期 Heartbeat（心跳）。
- Lease（租约）过期的非终态任务进入 Reconciliation（对账）。
- 已有 Runtime Run ID（运行标识）时先查询上游状态，不盲目创建新 Run（运行）。
- 上游状态未知时进入显式 `reconciling`（对账中）诊断状态或内部标记，禁止直接判定完成。
- 迟到终态必须经过 Lease Fence（租约栅栏）校验。

---

# 19. 结果与产物

## 19.1 Result（结果）

Result（结果）表示主要业务回答：

```text
result_summary              结果摘要
result_content              结果正文
result_schema_version       结果结构版本
completed_at                完成时间
```

Result（结果）只在 `run.completed`（运行完成）后可标记 Ready（就绪）。

## 19.2 Artifact（产物）

Artifact（产物）独立保存：

```text
artifact_id                 产物标识
task_id                     任务标识
owner / acl                 所有者/访问控制
storage_type                存储类型
object_key                  对象键
media_type                  媒体类型
size                        大小
checksum                    校验和
status                      状态
```

Artifact Discovery（产物发现）可在任务完成后异步继续。任务已完成但产物尚未完成时，Resource Projection（资源投影）后续补发 `artifact.ready`（产物可用）。

## 19.3 失败隔离

- Artifact（产物）物化失败不回滚已完成 Result（结果）。
- Result（结果）完成后发现恶意或越权 Artifact（产物）必须隔离资源并写审计，不修改历史回答内容。
- 下载时重新鉴权，历史 URL（地址）不保证永久有效。

---

# 20. API 与契约演进

## 20.1 稳定入口

保留并强化：

```http
POST /api/v1/hermes/mcp
GET  /api/v1/hermes/tasks/{task_id}/events
POST /api/v1/hermes/tasks/{task_id}/events-token
GET  /api/v1/hermes/tasks/{task_id}/result
GET  /api/v1/hermes/tasks/{task_id}/artifacts
POST /api/v1/hermes/tasks/{task_id}/cancel
```

新增：

```http
GET  /api/v1/work/skills
POST /api/v1/hermes/tasks/{task_id}/inputs
```

## 20.2 Legacy Expert API（旧专家接口）

迁移期保留：

```http
POST /api/v1/expert/mcp
POST /api/v1/expert/mcp/{slug}
```

旧接口处理方式：

```text
解析 Expert / ExpertTeam（专家/专家团队）展示项
→ 将旧 ExpertSkill（专家技能）映射到 HermesSkill（技能定义）
→ 生成 SkillInvocationCommandV1（技能调用命令）
→ 调用统一 Invocation Orchestrator（调用编排器）
```

旧 Adapter（适配器）可生成服务端 Pinned Policy（固定策略）用于兼容，但不能继续直接组装 Runtime Route（运行时路由）。

## 20.3 契约版本

- `WORK-EXPERT-CONTRACT v1.0.2`（工作台专家契约）保持只读和校验和稳定。
- 本方案实现产生的新 Schema（结构定义）进入后续兼容契约版本，建议为 `v1.1.0`（1.1.0 版）。
- 新契约至少新增 `ExpertRunEventV1`（专家运行事件）、`WorkChatEventV1`（工作台对话事件）、`WorkResourceEventV1`（工作台资源事件）、Clarify Resume（澄清继续）和 Skill Revision（技能修订）字段。
- 任何 Breaking Change（破坏性变更）必须使用新 Major Version（主版本）。
- 合同产物继续生成 Schema（结构定义）、Fixture（样例）、OpenAPI（开放接口定义）和 SHA256SUMS（校验和）。

## 20.4 错误契约

REST（表述性状态传输）错误必须包含：

```json
{
  "error_code": "SKILL_ROUTE_UNAVAILABLE",
  "message_key": "errors.skill.route_unavailable",
  "message": "当前没有可用的技能运行实例",
  "retryable": true,
  "retry_after_seconds": 10,
  "trace_id": "trace-1"
}
```

MCP（模型上下文协议）将同一领域错误映射到 JSON-RPC Error（远程过程调用错误）的 `data`（数据）字段，语义不得丢失。

最低错误集合：

```text
SKILL_NOT_FOUND                     技能不存在
SKILL_REVISION_UNAVAILABLE          技能修订不可用
SKILL_NOT_AUTHORIZED                技能未授权
SKILL_APPROVAL_REQUIRED             技能需要审批
SKILL_ROUTE_OVERRIDE_NOT_ALLOWED    禁止路由覆盖
SKILL_ROUTE_UNAVAILABLE             无可用路由
SKILL_ROUTE_POLICY_INVALID          路由策略错误
SKILL_CAPACITY_EXCEEDED             技能容量超限
IDEMPOTENCY_CONFLICT                幂等冲突
TASK_NOT_OWNER                      非任务所有者
TASK_INPUT_NOT_EXPECTED             任务不等待输入
RUNTIME_CONTRACT_UNSUPPORTED        运行时契约不支持
EVENT_NORMALIZATION_FAILED          事件归一失败
```

---

# 21. 数据迁移方案

## 21.1 Phase A：盘点与只读映射

- 盘点 `ExpertSkill.upstream_tool_name`（专家技能上游工具名）到 `HermesSkill.tool_name`（技能工具名）的映射。
- 输出未匹配、重复、Schema Drift（结构漂移）和风险策略冲突报告。
- 不静默创建错误映射。

退出条件：所有 Active Expert Skill（活跃专家技能）均有明确处理结论。

## 21.2 Phase B：建立 Skill Revision（技能修订）

- 从当前 `HermesSkill`（技能定义）生成首个 Published Revision（已发布修订）。
- 计算 `content_digest`（内容摘要）。
- Installation（安装）回填 `skill_revision_id`（技能修订标识）。
- Task（任务）新增可空 Revision（修订）和 Lease（租约）字段，兼容历史记录。

退出条件：所有可调用 Skill（技能）至少有一个 Published Revision（已发布修订）。

## 21.3 Phase C：统一调用内核

- Generic MCP Gateway（通用 MCP 网关）先切换到 Invocation Orchestrator（调用编排器）。
- Expert Gateway（专家网关）切换为 Adapter（适配器）。
- 双写新 Route Snapshot（路由快照）和旧兼容字段。
- 禁止新入口客户端路由覆盖。

退出条件：两类入口对同一 Skill（技能）产生一致授权、路由和 Task（任务）结构。

## 21.4 Phase D：规范事件与投影

- 增加 ExpertRunEventV1（专家运行事件）Schema（结构定义）。
- 引入 Runtime Normalizer（运行时归一器）和 Outbox（发件箱）。
- 同时输出旧 Task Event（任务事件）和新 Work Chat Projection（工作台对话投影）。
- 增加 `waiting_input`（等待输入）和 Resume API（继续接口）。

退出条件：SSE（服务端推送）重放、Poll（轮询）和在线流可生成同一对话结果。

## 21.5 Phase E：Work Skill-First（工作台技能优先）

- Work（工作台）改用 `/work/skills`（工作台技能目录）和通用 `tools/call`（工具调用）。
- Expert（专家）只作为目录筛选和展示组合。
- 监控旧接口调用量和兼容错误。

退出条件：连续两个发布周期内 95% 以上调用走新入口。

## 21.6 Phase F：Legacy 收口

- `ExpertSkill`（专家技能）停止作为执行事实源。
- 旧接口只读或进入明确弃用期。
- 任何删除仍使用软删除。

退出条件：无活跃客户端依赖旧路由语义，且历史 Task（任务）和审计可完整查询。

## 21.7 回滚原则

- 每个 Phase（阶段）均由 Feature Flag（功能开关）控制入口切换。
- 冻结契约和旧 Projection（投影）在迁移期保留。
- 数据迁移采用新增字段/表和双读，不通过物理删除回滚。
- 新事件可停止投影，但已写事件不得删除。

---

# 22. 实施范围与优先级

## P0：调用安全与正确性

- 统一 `SkillInvocationCommandV1`（技能调用命令）。
- 客户端路由覆盖强制拒绝。
- Skill Revision（技能修订）与 Installation（安装）关系。
- Idempotency Conflict（幂等冲突）检测。
- Route Snapshot（路由快照）与服务端确定性路由。
- Task Lease Fence（任务租约栅栏）。
- Worker（工作进程）短事务。

## P0：事件正确性

- `ExpertRunEventV1`（专家运行事件）。
- Runtime Normalizer（运行时归一器）。
- Transactional Outbox（事务发件箱）。
- SSE Replay（服务端推送重放）和去重。
- Work Chat Projection（工作台对话投影）。

## P1：完整体验

- Work Skill Catalog（工作台技能目录）。
- Reasoning / Tool / Clarify（推理/工具/澄清）事件。
- `waiting_input`（等待输入）和 Resume（继续）。
- Resource Projection（资源投影）。
- Catalog Cache Invalidation（目录缓存失效）。

## P1：容量与运维

- Admission Control（准入控制）。
- 组织/用户/技能/安装/运行时配额。
- Route Diagnostics（路由诊断）。
- Outbox Lag（发件箱延迟）与 Event Lag（事件延迟）监控。
- 多 Worker（工作进程）负载验收。

## P2：兼容收口

- Expert Gateway（专家网关）完全适配化。
- `ExpertSkill`（专家技能）转为展示绑定。
- 旧契约弃用公告和调用统计。

---

# 23. 测试与验收

## 23.1 Catalog（目录）

- 单 Skill（技能）单 Installation（安装）可用。
- 单 Skill（技能）多 Installation（安装）状态合成正确。
- Skill（技能）停用、Revision（修订）退役、Runtime（运行时）离线时不可调用。
- 用户无权限时目录不可见或 `callEnabled=false`（禁止调用），行为符合策略。
- Catalog Cache（目录缓存）在授权撤销和 Runtime（运行时）离线后及时失效。

## 23.2 Routing（路由）

- Pinned / Conversation Affinity / Workspace Affinity / Default / Capacity / Stable Hash（固定/会话亲和/工作区亲和/默认/容量/稳定哈希）顺序正确。
- 客户端提交任一保留字段均被拒绝。
- 候选顺序变化但候选集合不变时，Stable Hash（稳定哈希）结果不变。
- Runtime（运行时）排空后不接收新任务。
- 路由失败返回明确错误，不提示客户端指定 `_routing`（路由覆盖）。
- Route Snapshot（路由快照）可重建完整选择依据。

## 23.3 Invocation（调用）

- 相同幂等键与相同参数返回同一 Task（任务）。
- 相同幂等键与不同参数返回冲突。
- Schema（结构定义）校验发生在 Task（任务）创建前。
- 审批绑定 Revision（修订）和参数摘要。
- 超容量时不创建 Task（任务）。
- 已受理响应中的 `committed=true`（已提交）与数据库状态一致。

## 23.4 Worker / Lease（工作进程/租约）

- Worker（工作进程）崩溃后租约到期可恢复。
- 旧 Worker（工作进程）迟到完成不能覆盖新租约。
- 已存在 Runtime Run ID（运行标识）时恢复流程不重复创建 Run（运行）。
- 取消、超时和正常完成并发时只产生一个合法终态。
- 外部网络调用期间没有长数据库事务。

## 23.5 Event / Chat（事件/对话）

- Assistant Delta（助手增量）按序合并。
- Reasoning（推理）与 Assistant（助手）不混淆。
- Tool Start / Progress / Complete / Failed（工具开始/进度/完成/失败）按 `callId`（调用标识）关联。
- Clarify（澄清）进入 `waiting_input`（等待输入），恢复后继续同一 Task（任务）。
- 重复来源事件只保存一次。
- SSE（服务端推送）断线重连不丢、不乱序，允许至少一次重复并由 Event ID（事件标识）去重。
- Poll（轮询）与 SSE（服务端推送）生成相同 Work Chat Projection（工作台对话投影）。
- 未知 Runtime Event（运行时事件）不直接透传。

## 23.6 Security（安全）

- 跨组织 Skill / Task / Event / Artifact（技能/任务/事件/产物）访问被拒绝。
- SSE Token（服务端推送令牌）不能读取其他 Owner（所有者）的任务。
- 权限撤销后历史 Artifact URL（产物地址）不可继续下载。
- 日志不包含 Token（令牌）、Provider Key（模型供应商密钥）和附件全文。
- 路由和 Execution Contract（执行契约）不能被客户端 Payload（载荷）污染。

## 23.7 Contract Gate（契约门禁）

- 旧 `v1.0.2`（1.0.2 版）合同校验继续通过。
- 新合同 Schema（结构定义）和 Fixture（样例）全部通过。
- OpenAPI（开放接口定义）中的成功响应不得使用空 Schema（结构定义）。
- 负例 Fixture（样例）必须验证保留字段、幂等冲突、非法事件和越权访问。

---

# 24. 非功能要求

## 24.1 性能目标

在约定基准环境下：

```text
Work Skill Catalog P95                 < 300 ms（缓存命中）
Work Skill Catalog P95                 < 800 ms（缓存未命中）
tools/call accepted P95                < 800 ms
Task commit → first SSE event P95      < 1 s
Event commit → SSE visible P95         < 500 ms
SSE reconnect replay 1000 events P95   < 2 s
Cancel accepted P95                    < 500 ms
```

Runtime（运行时）业务执行耗时不计入 `tools/call accepted`（工具调用受理）延迟。

## 24.2 可用性与恢复

- API（应用接口）月可用性目标不低于 99.9%。
- 已提交 Task（任务）在单 API（应用接口）或 Worker（工作进程）进程故障后可恢复。
- 恢复点目标 RPO（恢复点目标）为 0 个已提交规范事件。
- 恢复时间目标 RTO（恢复时间目标）不超过一个 Lease Timeout（租约超时）周期加一次调度周期。

## 24.3 数据保留

- Task / Event / Audit（任务/事件/审计）保留期由组织策略控制。
- 删除一律逻辑删除，法规要求的物理清理进入独立受审计流程，不属于普通业务删除接口。
- Raw Event Log（原始事件日志）保留期短于规范事件，且访问权限更严格。

---

# 25. 可观测性与审计

## 25.1 统一关联字段

日志、指标、事件和审计统一包含：

```text
trace_id                    追踪标识
client_request_id           客户端请求标识
task_id                     任务标识
run_id                      运行标识
org_id                      组织标识
user_id                     用户标识
tool_name                   工具名
skill_revision_id           技能修订标识
installation_id             安装记录标识
route_generation            路由代次
event_seq                   事件序号
```

## 25.2 指标

最低指标：

```text
skill_catalog_latency_seconds                技能目录延迟
skill_invocation_total                       技能调用总数
skill_invocation_rejected_total              技能调用拒绝数
skill_route_decision_total                   技能路由决策数
skill_route_unavailable_total                技能路由不可用数
skill_admission_rejected_total               技能准入拒绝数
skill_task_queue_wait_seconds                技能任务排队时间
skill_worker_lease_expired_total             技能工作进程租约过期数
skill_runtime_call_seconds                   技能运行时调用时间
skill_event_normalization_failed_total       技能事件归一失败数
skill_event_outbox_lag_seconds               技能事件发件箱延迟
skill_sse_reconnect_total                    技能服务端推送重连数
skill_sse_replay_events_total                技能服务端推送重放事件数
skill_clarify_wait_seconds                   技能澄清等待时间
skill_artifact_ready_seconds                 技能产物就绪时间
```

禁止将 `org_id`（组织标识）、`user_id`（用户标识）、`task_id`（任务标识）作为 Prometheus（监控系统）高基数 Label（标签）。

## 25.3 审计内容

每次调用至少记录：

- 调用身份和组织。
- Entry Point（入口）和客户端版本。
- Skill / Revision（技能/修订）。
- 授权与审批决策。
- 候选数量、选中 Installation（安装）和路由原因。
- Task / Runtime Run（任务/运行时运行）。
- 开始、结束、状态和错误码。
- Artifact（产物）数量和安全状态。

审计记录不保存密钥和非必要全文。

---

# 26. 发布、灰度与回滚

## 26.1 功能开关

建议开关：

```text
EXPERT_SKILL_INVOCATION_CORE_ENABLED        统一调用内核开关
EXPERT_SKILL_REVISION_ENABLED               技能修订开关
EXPERT_SKILL_SERVER_ROUTING_ENABLED         服务端路由开关
EXPERT_RUN_EVENT_V1_ENABLED                 规范运行事件开关
WORK_CHAT_PROJECTION_V1_ENABLED             工作台对话投影开关
EXPERT_EVENT_OUTBOX_ENABLED                 事件发件箱开关
EXPERT_CLARIFY_RESUME_ENABLED               澄清继续开关
```

配置项必须有中文说明、默认值、作用域和回滚行为。

## 26.2 灰度顺序

1. 内部测试组织。
2. 单一低风险 Skill（技能）。
3. 10% Work（工作台）新调用。
4. 50% Work（工作台）新调用。
5. 100% Work（工作台）新调用。
6. Expert Legacy Adapter（专家旧接口适配器）统一切换。

每一步至少观察：错误率、路由不可用、重复任务、Outbox Lag（发件箱延迟）、SSE Replay（服务端推送重放）、取消和产物成功率。

## 26.3 回滚

- 回滚入口路由，不回滚已创建 Task（任务）的 Route Snapshot（路由快照）。
- 已由新 Worker（工作进程）领取的任务继续按原 Execution Contract（执行契约）完成。
- 新 Projection（投影）可暂停，规范事件继续保存。
- 禁止通过删除任务、事件或迁移数据实现回滚。

---

# 27. 风险与缓解

## 27.1 Runtime 事件语义不稳定

风险：不同 Hermes Runtime（Hermes 运行时）版本输出字段不一致。

缓解：按 Adapter Version（适配器版本）维护 Normalizer（归一器）、Contract Test（契约测试）和未知事件隔离。

## 27.2 双契约迁移复杂

风险：旧 Task Event（任务事件）与新 Work Chat Event（工作台对话事件）并存导致客户端误消费。

缓解：事件命名空间分离，Work（工作台）只消费 `work.*`（工作台事件），冻结旧 Fixture（样例）并做双流对照测试。

## 27.3 路由策略过度复杂

风险：健康、容量、亲和和优先级组合难以解释。

缓解：硬过滤与排序分层，保存 Policy Version（策略版本）、Candidate Count（候选数）、Reason Code（原因码）和 Route Diagnostics（路由诊断）。

## 27.4 事件量增长

风险：Reasoning / Delta（推理/增量）事件显著增加数据库写入量。

缓解：增量小批提交、连续文本 Delta（增量）合并、分区/归档策略和保留期；不得合并 Tool / Input / Terminal（工具/输入/终态）事件。

## 27.5 历史数据缺少 Revision（修订）

风险：旧 Task（任务）无法准确绑定不可变版本。

缓解：迁移时记录 `legacy_unresolved`（旧数据未解析），保留原 Request / Route Snapshot（请求/路由快照），不得伪造 Revision（修订）。

---

# 28. 架构决策记录

## ADR-01：Skill（技能）是调用身份

`tool_name`（工具名）是外部稳定调用键，Expert Slug（专家标识）不是执行地址。

## ADR-02：Revision（修订）不可变

已发布 Skill Revision（技能修订）不可原地修改，历史任务必须可重放和审计。

## ADR-03：Installation（安装）是部署事实

Registration Origin（注册来源）进入 Provenance（来源证明），Invocation Route（调用路由）由服务端策略决定。

## ADR-04：统一调用内核

MCP（模型上下文协议）、Work API（工作台接口）和 Expert Legacy（专家旧接口）只作为 Adapter（适配器）。

## ADR-05：客户端不拥有路由权

所有 Runtime（运行时）和 Installation（安装）选择均由服务端完成并审计。

## ADR-06：规范事件是事实源

`ExpertRunEventV1`（专家运行事件）是核心事实；Task、Chat、Resource（任务、对话、资源）是可重建投影。

## ADR-07：Outbox（发件箱）保证可见性

事件与发布意图同事务写入，实时通知只能来自已提交 Outbox（发件箱）。

## ADR-08：Clarify（澄清）是状态，不只是消息

澄清请求进入 `waiting_input`（等待输入），通过受鉴权和幂等的 Resume（继续）操作恢复。

## ADR-09：Result 与 Artifact（结果与产物）解耦

主要回答进入 Result（结果）；文件和报告进入受访问控制的 Resource（资源）链路。

## ADR-10：冻结旧契约

`WORK-EXPERT-CONTRACT v1.0.2`（工作台专家契约）不原地修改，新能力发布新版本。

---

# 29. 最终调用闭环

```text
apps/work（工作台）
  │
  │ GET /api/v1/work/skills
  ▼
选择 Skill（技能）
  │
  │ MCP tools/call
  ▼
Generic MCP Gateway（通用 MCP 网关）
  │
  ▼
SkillInvocationCommandV1（技能调用命令）
  │
  ▼
Invocation Orchestrator（调用编排器）
  ├─ Principal / Authorization（身份/授权）
  ├─ Revision / Schema（修订/结构定义）
  ├─ Approval / Admission（审批/准入）
  ├─ Route Resolver（路由解析器）
  └─ Task + Event + Outbox（任务+事件+发件箱）
  │
  ▼
HermesTaskWorker（Hermes 任务工作进程）
  ├─ Lease Fence（租约栅栏）
  ├─ Runtime Adapter（运行时适配器）
  └─ Runtime Normalizer（运行时归一器）
  │
  ▼
ExpertRunEventV1（专家运行事件）
  ├─ WorkChatEventV1（工作台对话事件）
  ├─ WorkResourceEventV1（工作台资源事件）
  ├─ Task Projection（任务投影）
  └─ Audit Projection（审计投影）
  │
  ▼
SSE Replay / Poll / Result / Artifact（服务端推送重放/轮询/结果/产物）
  │
  ▼
apps/work Chat + Files（工作台对话+文件）
```

最终形态是：Work（工作台）只认识 Skill（技能）、Task（任务）和稳定的 Chat / Resource Contract（对话/资源契约）；Expert（专家）负责展示与组合；NoDeskClaw 服务端负责身份、策略、路由、执行、恢复和审计；Runtime（运行时）只通过版本化 Adapter（适配器）接入。

---

# 30. Definition of Done（完成定义）

本方案只有同时满足以下条件才视为 v1.0 目标完成：

- 新 Work（工作台）调用不再依赖 Expert Slug（专家标识）定位 Runtime（运行时）。
- 所有新 Task（任务）均绑定 Skill Revision（技能修订）和 Installation（安装）。
- 客户端路由覆盖被统一拒绝。
- Generic MCP Gateway（通用 MCP 网关）和 Expert Legacy Adapter（专家旧接口适配器）共享调用内核。
- Runtime（运行时）事件通过版本化 Normalizer（归一器）进入规范事件。
- Chat（对话）、Task（任务）和 Resource（资源）可由同一事件事实重建。
- SSE（服务端推送）支持断点重放，事件不依赖进程内内存保证正确性。
- Clarify（澄清）具备等待输入和恢复闭环。
- Worker Lease（工作进程租约）、取消、超时、重试和迟到结果通过并发测试。
- Admission Control（准入控制）和 Load Gate（负载门禁）达到约定指标。
- 新旧契约校验、OpenAPI（开放接口定义）、Fixture（样例）、迁移测试和安全测试全部通过。
- `lat check`（架构知识图谱检查）通过，相关架构决策已同步到 `lat.md/`（架构知识图谱目录）。

---

# 附录 A：术语

- Expert（专家）：面向用户的角色形象与技能组合，不是运行时地址。
- Skill（技能）：组织级可调用能力的逻辑身份。
- Skill Revision（技能修订）：不可变的技能版本、结构定义和能力快照。
- Installation（安装）：技能修订部署到运行时端点的事实。
- MCP Gateway（模型上下文协议网关）：提供标准工具发现和调用的协议适配层。
- Runtime（运行时）：实际执行技能的 Hermes Agent（Hermes 智能体）或兼容服务。
- Task（任务）：一次已受理技能调用的持久执行记录。
- Route Snapshot（路由快照）：任务受理时冻结的服务端选路结果。
- Execution Lease（执行租约）：防止多个工作进程同时或迟到写入任务结果的所有权凭证。
- Canonical Event（规范事件）：与客户端无关、可持久化和重放的运行事实。
- Projection（投影）：从规范事件生成的任务、对话、资源或审计视图。
- Outbox（事务发件箱）：与业务数据同事务保存的待发布消息记录。

# 附录 B：现状依据文件

本方案基于以下仓库文件核实当前实现：

- `nodeskclaw-backend/app/models/hermes_skill/skill.py`（技能定义模型）。
- `nodeskclaw-backend/app/models/hermes_skill/skill_installation.py`（技能安装模型）。
- `nodeskclaw-backend/app/models/hermes_skill/hermes_task.py`（任务与事件模型）。
- `nodeskclaw-backend/app/models/expert_skill.py`（专家技能模型）。
- `nodeskclaw-backend/app/services/hermes_skill/skill_routing_service.py`（技能路由服务）。
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_registration_service.py`（运行时技能注册服务）。
- `nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py`（运行时技能执行服务）。
- `nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py`（任务工作进程）。
- `nodeskclaw-backend/app/services/hermes_skill/task_event_service.py`（任务事件服务）。
- `nodeskclaw-backend/app/services/hermes_skill/task_event_stream_formatter.py`（事件流格式化器）。
- `nodeskclaw-backend/app/services/expert_gateway/expert_run_service.py`（专家运行服务）。
- `nodeskclaw-backend/contracts/work-expert/v1.0.2/`（冻结的工作台专家契约）。
- `lat.md/decisions/work-expert-contract.md`（工作台专家契约决策）。
