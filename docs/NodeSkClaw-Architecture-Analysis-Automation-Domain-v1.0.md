# NodeSkClaw Architecture Analysis
## Backend / Task / Agent / Knowledge 领域边界与 Automation 长期架构分析

**文档类型**：Architecture Analysis（非 Implementation PRD）  
**日期**：2026-10-04  
**分析仓库**：`https://github.com/loudon84/nodeskclaw`  
**分析基线**：当前 `main`，并结合已冻结 `remote-expert-frontend-contract-v1.0.0`  
**目标**：重新确认 `nodeskclaw-backend`、`nodeskclaw-task`、`nodeskclaw-agent`、`nodeskclaw-knowledge` 的长期领域边界，重点评估 Automation 作为独立产品的发展方向。  
**非目标**：不输出实施步骤、不生成迁移 Todo、不讨论仓库改名、不决定具体重构提交。

---

# 0. 修订说明 — Runtime / ACP 边界修正（rev.1）

本文档在 v1.0 发布后做过一次**限定范围**的修订，只修正 Remote Expert / Backend / Agent 这一条运行链的职责定义。

**未变更**（v1.0 的判断继续成立，不受本次修订影响）：

- `nodeskclaw-task` 作为独立 Automation Bounded Context 的定位。
- `nodeskclaw-knowledge` 作为 Knowledge 业务域 + Knowledge Gateway 的双重定位。
- §7 Automation 长期领域模型、§9–§14 各类 Node 边界、§29 Permission、§39 Data Ownership 等 Automation / Knowledge 相关章节。

**本次修正的核心一句话**：

> Backend 从 "Remote Agent Run Control Plane" 收敛为"平台授权 + Expert 路由 + ACP 公共入口"；`nodeskclaw-agent` 升级为真正的 ACP Runtime Gateway + Agent Execution Plane；Remote Hermes 保持最终 Agent Engine。**SMC Production MUST NOT require local `nodeskclaw-acp.exe`。**

**被修订的章节**：§2.1、§2.3、§4.1、§4.3、§5、§8、§28、§32、§37、§49、§50、Appendix B。

**已冻结（不再未决）**：

```text
SMC 不依赖 nodeskclaw-acp.exe
Backend owns Auth / Expert ACL / Routing / Scoped Execution Capability
Agent owns ACP Runtime Gateway / Run / Attempt / Event / Artifact
Hermes remains Agent Engine
nodeskclaw-acp owns no SOT
```

**阅读规则**：§2.x 描述的是**当前代码事实（Current / Legacy Implementation）**，不代表 Target；§4.x 之后描述的是 **Target Architecture**。两者在 Remote Agent 这条链上**已经不一致**，这种不一致是有意记录的迁移债务，不是文档错误。`nodeskclaw-acp` 作为本地 stdio adapter、`nodeskclaw-agent` 当前没有 ACP 实现，一律保留在 Current State / Architecture Gap，不得写成 Target。

---

# 1. Executive Summary

经过对当前源码重新核对，当前架构不应建立在“`nodeskclaw-task` 只是 Remote Agent 的自动化辅助服务”这一假设上。

源码事实显示，`nodeskclaw-task` 已经形成一个独立 Automation 业务域的明显雏形：

- Portal Account
- Workflow Template / Version
- Workflow Binding
- Automation Task
- Agent Automation
- Trigger / Invocation
- RPA Worker / Run / Dispatch
- Human Action
- Artifact
- Audit
- MCP
- Dashboard
- Worker Lease
- Task State Machine

其当前官方模块说明也将 `nodeskclaw-task` 定义为与 `nodeskclaw-backend` **平级部署**的 AutoTask 业务后端，而不是 Backend 的内部 worker。

同时，`nodeskclaw-knowledge` 当前也不只是“Agent 检索网关”。其公开 API 已经覆盖：

- Knowledge Base
- Knowledge Set
- Source File
- Source Connector
- Ingestion Job
- Retrieval / Retrieval Profile
- Chat
- Citation
- Evaluation
- Dashboard
- Audit
- Agent Tools

因此 Knowledge 必须被视为：

> **SMC Copilot Knowledge 模块正在消费的 Knowledge 业务功能模块，同时向 Agent / Automation 提供 Knowledge Gateway 能力。**

基于用户确认的长期目标：

```text
Workflow Engine
BPM
Human Task
RPA
ETL
Timer
Event Bus
Business Process
Agent
Non-Agent Job
```

本分析的核心判断是：

> **Automation 应继续保持独立 Bounded Context。**
>
> `nodeskclaw-backend` 不应吸收 Workflow/BPM/RPA/Human Task/Timer/Event 等 Automation 领域模型。
>
> `nodeskclaw-agent` 应作为 Automation 中 `AGENT` 类型执行节点的专用执行器，而不是整个 Automation 平台的执行引擎。
>
> `nodeskclaw-knowledge` 应保持 Knowledge 业务域，并同时提供 Agent/Automation 所需的知识能力。
>
> `nodeskclaw-backend` 应继续承担平台级 Identity / Organization / Resource / Integration / Remote Expert 等控制能力，而不是成为所有业务域的数据与状态机所有者。

推荐的长期结构是：

```text
                      SMC Copilot
                          │
        ┌─────────────────┼──────────────────┐
        │                 │                  │
        ▼                 ▼                  ▼
 Platform / Expert   Automation UI      Knowledge UI
        │                 │                  │
        ▼                 ▼                  ▼
nodeskclaw-backend  nodeskclaw-task  nodeskclaw-knowledge
        │                 │                  │
        │                 │                  │
        │            Workflow Engine         │
        │            BPM / Human Task        │
        │            RPA / ETL / Timer       │
        │            Event / Job             │
        │                 │                  │
        │                 ├──────────────┐   │
        │                 │              │   │
        │                 ▼              │   │
        │          Agent Node Adapter     │   │
        │                 │              │   │
        └─────────────────┼──────────────┘   │
                          ▼                  │
                   nodeskclaw-agent          │
                          │                  │
                        Hermes               │
                                             │
                      Retrieval / Context ◄──┘
```

这里最重要的是：

```text
业务域独立
!=
用户体验割裂

统一身份
!=
所有业务都必须放进 Backend

统一产品入口
!=
只有一个内部服务
```

---

# 2. Source-Grounded Current State

本节只描述当前源码已经支持的事实，不代表未来设计决策。

## 2.1 nodeskclaw-backend 当前主要职责

> **本节是 Current / Legacy Implementation，不代表 Target Architecture。**
> 其中 `Remote Agent Public API` / `Remote Agent Session` / `Remote Agent Provider` / `RunDispatchOutbox` 四项在 Target 中不再归 Backend，见 §4.1 与 §49。

当前 Backend 已经承担：

- 用户认证与 JWT
- Organization / Membership / Role
- Expert Catalog
- Remote Expert Catalog
- Remote Agent Public API
- Remote Agent Session
- Attachment
- Connector Binding
- IntegrationAccount
- Shared IntegrationAccount / Grant
- External Action Policy
- Remote Agent Provider
- RunDispatchOutbox
- Agent 执行前 Context / Authorization 组装

当前 Remote Agent Provider 创建 Run 时，会在 Backend 侧创建：

```text
HermesTask
+
RunDispatchOutbox
```

并把 Run 下发给 Agent execution plane。

这说明 Backend **当前实现上**已经是：

> **Remote Expert / Remote Agent 的控制平面和资源授权平面。**

但这只是 Current State。"资源授权平面"在 Target 中保留并强化；"Run 控制平面"在 Target 中移交 `nodeskclaw-agent`。

当前这条链的完整形态是（含客户端侧）：

```text
smc-copilot/apps/work （或 Zed）
      │ spawn + stdio JSON-RPC
      ▼
nodeskclaw-acp          ← 本地 adapter 进程，ACP v1 在此终止
      │ REST + SSE
      ▼
nodeskclaw-backend      ← 把 ACP 语义重新编码成 Remote Agent REST Run
      │ HermesTask + RunDispatchOutbox
      ▼
nodeskclaw-agent
      ▼
Hermes
```

**这条链是 Current State / Architecture Gap，不是 Target。** ACP 语义在 `nodeskclaw-acp` 终止后，被 Backend 二次编码成另一套 Remote Agent REST Run 模型，再交给 Agent，于是同一次执行在 Backend 与 Agent 各有一份 Run 概念。Target 要求：SMC Production 不经本地 sidecar；ACP Public Ingress 在 Backend；ACP Runtime 语义在 Agent。见 §4.1、§8、§28、§49。

此外，这一事实也不自动意味着 Backend 应成为 Automation Workflow Engine。

---

## 2.2 nodeskclaw-task 当前不是简单的 Agent Scheduler

当前 `nodeskclaw-task/app/api/router.py` 已经挂载：

```text
Dashboard
Portal Account
Workflow Template
Workflow Binding
Automation Task
Agent Automation
Agent Automation Hooks
RPA Run
Human Action
Artifact
RPA Worker
RPA Worker Dispatch API
MCP
```

当前模块说明定义其职责包括：

```text
Portal Account
Workflow Template
Workflow Binding
Automation Task
RPA Run
Human Action
Artifact Metadata
RPA Worker Scheduling
MCP Tools
```

并且其数据模型已经包含：

```text
UserCache
PortalAccount
PortalAccessGrant
WorkflowTemplate
WorkflowTemplateVersion
WorkflowBinding
AutomationTask
TaskMessage
RpaRun
StepRun
RunEvent
HumanAction
Artifact
RpaWorker
WorkerLease
RpaComponent
AutotaskSetting
AuditLog
```

后来 v1.4 / v1.5 又增加：

```text
AgentAutomation
AutomationTrigger
AutomationInvocation
RemoteAgentDispatchJob
AutomationWebhookNonce
```

所以从源码成熟度看：

```text
nodeskclaw-task
```

已经具备两个层次：

### A. 原 AutoTask / RPA / Workflow 业务域

```text
Workflow Template
Workflow Binding
AutomationTask
RPA
HumanAction
Artifact
Worker
Portal Account
```

### B. 后加入的 Agent Automation 子域

```text
AgentAutomation
Trigger
Invocation
Remote Agent dispatch
Cron
Webhook
Manual
RPA successor
```

这两个层次的关系尚未完全统一，是未来架构设计的关键问题。

---

## 2.3 nodeskclaw-agent 当前应视为 Agent Runtime Gateway + Agent Execution Plane

Agent 的长期定位是：

```text
ACP Runtime Gateway          ← Target，当前代码尚未实现
Hermes Native Runtime Bridge

Dedicated Agent Runtime
Hermes Execution Plane
Agent Tool Execution
Agent Event Stream
Agent Artifact Generation
Agent Run Result
External Action execution
```

前两项是本次修订新增的 Target 职责，必须与当前代码事实区分：

- **当前事实**：`nodeskclaw-agent` 源码中没有任何 ACP 引用（检索 `acp`、`ACP`、`nodeskclaw-acp`、`stdio` 均无命中）。它只有 `/internal/v1/runs` 这一套内部 Run API，ACP 语义完全不可见。
- **Target**：ACP 的 Runtime 语义（session / prompt / cancel / permission）应在此层落地，而不是在 Backend 被转译成 Remote Agent REST。

这是一条明确的 **capability gap**，不是已完成状态。

它不应该拥有：

```text
Workflow Definition
BPM Process
Human Task
Timer
Event Subscription
ETL Flow
RPA Business Process
Automation SLA
Workflow Compensation
```

因此：

> `nodeskclaw-agent` 是 Agent Runtime 的 Owner，可以执行 Automation 的 Agent Node，但不能成为 Automation Domain Owner。

"Runtime Owner" 与 "Automation Owner" 是两件不同的事：前者意味着 Run / Attempt / Event / Artifact 的 SOT 在 Agent；后者意味着流程拓扑与业务编排在 Task。本次修订强化前者，不改变后者。

---

## 2.4 nodeskclaw-knowledge 当前是业务模块，不只是 Gateway

当前 Knowledge API Router 已经包含：

```text
Dashboard
Audit
Chat
Citations
Evaluation
Knowledge Bases
Knowledge Base Files
Knowledge Base Connectors
Knowledge Sets
Retrieval Profiles
Source Files
Source Connectors
Ingestion Jobs
Retrieval
```

因此它至少同时承担两类能力：

### Knowledge Product Capability

面向 `smc-copilot Knowledge` 模块：

```text
Knowledge Base Management
Knowledge Set Management
Source Management
File Management
Connector Management
Ingestion
Retrieval Configuration
Evaluation
Knowledge Chat
Citation
Dashboard / Audit
```

### Knowledge Gateway Capability

面向：

```text
Remote Expert
Agent Runtime
Automation Workflow
```

提供：

```text
knowledge_ref resolution
ACL proof
retrieval
citation
context construction
```

所以正确描述应是：

> **Knowledge 业务域 + Knowledge Gateway。**

不能只定义成内部 Gateway。

---

# 3. Architecture Premise

本分析采用以下长期产品前提：

## 3.1 Automation 是独立产品域

未来 Automation 需要承载：

```text
Workflow Engine
BPM
Human Task
RPA
ETL
Timer
Event Bus
Business Process
Agent
Non-Agent Job
```

这意味着 Automation 的核心抽象不应该是：

```text
AgentAutomation
```

而应该是更高层：

```text
Workflow / Process
        │
        ├─ Agent Node
        ├─ RPA Node
        ├─ Human Node
        ├─ ETL Node
        ├─ HTTP Node
        ├─ Timer Node
        ├─ Event Node
        └─ Other Job Node
```

Agent 只是其中一种 Executor。

---

## 3.2 Remote Expert 与 Automation 是不同产品能力

Remote Expert：

```text
用户交互驱动
ACP session/prompt
Interactive
Conversation-oriented
```

Automation：

```text
Workflow / Event / Timer 驱动
Long-running
Stateful Process
Potentially unattended
```

二者可以共享 Agent Runtime，但不能共享上层状态机。

---

## 3.3 Knowledge 是独立业务功能模块

Knowledge 不是 Backend 的一个数据库子模块，也不是 Agent 的工具实现细节。

它有自己的：

```text
Knowledge Base
Knowledge Set
Sources
Files
Connector
Ingestion
Retrieval Profile
Evaluation
Citation
Chat
Audit
```

SMC Knowledge UI 需要消费这些业务能力。

---

# 4. Recommended Bounded Contexts

## 4.1 nodeskclaw-backend — Platform Control Domain

建议长期拥有：

```text
Identity
Authentication
Organization
Membership
Role / RBAC

Expert Catalog
Remote Expert Catalog
Expert ACL

IntegrationAccount
Shared IntegrationAccount
IntegrationAccountGrant

Connector Binding
External Action Policy

ACP Public Ingress
Runtime Placement / Routing
Scoped Execution Capability

Attachment public identity
Platform-level resource authorization
```

与 v1.0 的差异：原先的 `Remote Agent Public Control API` 已移除，替换为 `ACP Public Ingress` + `Runtime Placement / Routing` + `Scoped Execution Capability`。**Backend 是 ACP 的公共入口与授权权威，不是 ACP Runtime Gateway。**

名称上的精确区别：

```text
nodeskclaw-backend
≠ ACP Runtime Gateway

nodeskclaw-backend
= ACP Public Ingress
+ Authentication
+ Expert Authorization
+ Runtime Routing

nodeskclaw-agent
= ACP Runtime Gateway
+ Agent Execution Plane
```

Backend 的核心职责应回答：

```text
你是谁？
你在哪个组织？
你能不能调用这个 Expert？
这个 Expert 运行在哪里？
允许这次执行访问哪些资源？
```

Backend **不再回答**（本次修订新增的否定清单，这些全部归 Agent）：

```text
这个 Agent Run 当前第几个 Attempt？
Hermes 现在正在执行什么？
session / prompt 该怎么映射到 Hermes？
当前有哪些 tool.call？
如何恢复 Runtime Run？
```

Backend 同样不应回答（v1.0 已有，继续成立，这些属于 Automation）：

```text
Workflow 下一步走哪个节点？
BPM Process 是否等待三天？
Human Task 由谁领取？
ETL Job 如何补偿？
RPA Run 第 8 步失败后怎样回滚？
```

**Runtime Routing 的含义边界**：Backend 负责回答"这次执行应该去哪个 Runtime、带什么 scope"，然后把一次**已授权的执行**交给 Agent。它不负责维护该执行的生命周期状态。Routing 是一次性决策，不是持续控制。

---

# 4.2 nodeskclaw-task — Automation Domain

建议长期拥有：

```text
Workflow Definition
Workflow Version
Workflow Binding

Process Instance
Workflow Run
Node Run

Automation Task
Human Task

Trigger
Schedule
Timer

Event Subscription
Event Correlation

Retry Policy
Timeout Policy
Compensation Policy
Concurrency Policy

RPA Orchestration
ETL Orchestration

Agent Orchestration
Non-Agent Job Orchestration

Worker Lease / Worker Dispatch
Automation Artifact Reference
Automation Audit
```

它回答的问题是：

```text
什么时候执行？
因为什么事件执行？
当前 Process 到哪一步？
下一步执行什么？
哪个节点正在等待？
失败后 retry / skip / compensate / human intervention？
流程是否完成？
```

---

# 4.3 nodeskclaw-agent — Agent Runtime Gateway + Agent Execution Domain

建议长期拥有：

```text
ACP Session
ACP Prompt
ACP Cancel
ACP Permission
ACP Runtime Gateway

Agent Run
Attempt
Runtime Capability
Hermes Runtime
Agent Session Execution
Tool Calling
Agent Tool Gateway
External Action Execution
Agent Event Stream
Agent Result
Agent Artifact
Agent Runtime Recovery
Hermes Native Runtime Bridge
```

v1.0 的后半部分全部保留；本次修订在其**上方**补入 ACP Runtime 层。分层形态：

```text
        Northbound
            ACP
             │
             ▼
┌─────────────────────────┐
│ nodeskclaw-agent        │
│                         │
│ ACP Runtime Gateway     │
│ Run / Attempt SOT       │
│ Tool Gateway            │
│ Runtime Capability      │
│ Event / Artifact        │
│ Hermes Bridge           │
└────────────┬────────────┘
             │
             │ Hermes Native API
             ▼
       Remote Hermes
        Southbound
```

即：

```text
ACP Session / Prompt / Cancel / Permission
        │
        ▼
Agent Run / Attempt / Runtime Capability
Tool Gateway / External Action
Artifact / Event Stream
        │
        ▼
Hermes Native Runtime
```

它回答：

```text
这个 ACP session 对应哪个 Runtime 执行？
prompt 如何映射到 Hermes？
这个 Agent Run 怎样执行？
当前第几个 Attempt？
Hermes 当前是什么状态？
模型调用结果是什么？
Tool Call 是什么？
permission 请求如何回传给 ACP 客户端？
Agent Artifact 是什么？
Runtime Run 如何恢复？
```

它不决定：

```text
业务流程下一步是什么。
这个人有没有权限调用这个 Expert。
这个 Expert 应该跑在哪里。
```

后两项属于 Backend（§4.1）。

**因此 `nodeskclaw-agent` 不是一个 HTTP 中转器，而是企业 Remote Agent Runtime Gateway。** 这是它存在价值的根据：如果 ACP 语义在 Backend 就被转译掉，Agent 就退化成了转发层；只有 Runtime 语义在 Agent 落地，这一层才是不可替代的。

---

# 4.4 nodeskclaw-knowledge — Knowledge Business Domain + Gateway

建议长期拥有：

```text
Knowledge Base
Knowledge Set

File / Source
Source Connector
Ingestion

Retrieval Profile
Retrieval

Knowledge Chat
Citation
Evaluation

Knowledge Audit
Knowledge Dashboard

Agent / Automation retrieval gateway
```

它回答：

```text
知识是什么？
属于哪个 KB / Set？
哪些 Source 构成它？
是否完成 Ingestion？
怎么检索？
如何引用？
Retrieval Profile 是什么？
```

Agent 与 Automation 不复制这些数据。

---

# 5. Key Architecture Principle: SOT by Domain

未来最重要的规则不是“服务数量”，而是每种状态只有一个 Source of Truth。

| State / Resource | SOT |
|---|---|
| User / Org / Membership | backend |
| Platform RBAC | backend |
| Expert | backend |
| Expert Authorization | backend |
| Runtime Placement | backend |
| Execution Capability | backend |
| IntegrationAccount | backend |
| Connector Binding | backend |
| Remote Agent public identity | backend |
| Workflow Definition | task |
| Workflow Version | task |
| Workflow Instance | task |
| Automation Task | task |
| Human Task | task |
| Trigger / Timer | task |
| Workflow Retry / Compensation | task |
| RPA Orchestration | task |
| ACP Session Runtime | agent |
| Agent Run | agent |
| Attempt | agent |
| Run Event | agent |
| Run Terminal State | agent |
| Agent Artifact | agent |
| Agent Tool Execution | agent |
| Hermes Native Run | Hermes |
| Knowledge Base | knowledge |
| Knowledge Set | knowledge |
| Ingestion | knowledge |
| Retrieval Profile | knowledge |
| Citation / Evaluation | knowledge |

本次修订在此表上的关键变化：v1.0 原本把 `Agent Run Execution` 写成 `agent / backend run control contract`，即**双 Owner**。这被修正为单一 Owner —— Run / Attempt / Event / Terminal State / Artifact 全部归 `agent`，`Hermes Native Run` 归 Hermes，Backend 只持有 Expert / Authorization / Placement / Capability。

这样就不会出现：

```text
Backend 一份 Run
Agent 又一份 Run
Hermes 再一份 Run
```

三个控制层都认为自己是 Owner。**这是之前架构变复杂的主要来源之一。**

任何服务需要另一领域的资源时：

```text
Reference + Contract
```

而不是：

```text
Copy + Become Secondary SOT
```

---

# 6. SMC Copilot Integration Boundary

这是需要特别澄清的部分。

## 6.1 “统一产品入口”不应等价于“只有 Backend 一个业务服务”

SMC Copilot 可以保持：

```text
统一登录
统一组织
统一用户身份
统一产品导航
统一错误模型
统一 Contract 管理
```

同时让不同业务模块消费不同领域服务。

当前 Knowledge 已经是现实例子：

```text
SMC Knowledge Module
        ↓
nodeskclaw-knowledge
```

这是合理的。

未来 Automation 如果成为大产品，同样可以是：

```text
SMC Automation Module
        ↓
nodeskclaw-task
```

而 Remote Expert / Integration 等继续：

```text
SMC Chat / Settings
        ↓
nodeskclaw-backend
```

---

## 6.2 推荐把“统一对接”重新定义为统一平台协议

建议统一的是：

```text
Authentication
JWT
Org/Tenant identity
Trace ID
Error envelope
Contract versioning
Audit correlation
Resource identity
Frontend client conventions
```

而不是强制：

```text
所有 HTTP 请求都必须通过 backend reverse proxy。
```

如果未来需要单一域名，可以在部署层使用：

```text
API Gateway / Reverse Proxy
```

例如：

```text
/api/v1/platform/*     → backend
/api/v1/automation/*   → task
/api/v1/knowledge/*    → knowledge
```

这与 Domain Ownership 不冲突。

---

# 7. Automation Long-Term Domain Model

当前最值得演进的不是简单扩大 `AgentAutomation`，而是建立统一 Workflow/Process 抽象。

概念模型建议：

```text
WorkflowDefinition
        │
        └─ version
            │
            └─ NodeDefinition[]
                 │
                 ├─ AGENT
                 ├─ RPA
                 ├─ HUMAN
                 ├─ ETL
                 ├─ HTTP
                 ├─ TIMER
                 ├─ EVENT_WAIT
                 ├─ SCRIPT
                 └─ SUBFLOW

WorkflowInstance
        │
        └─ NodeRun[]
              │
              ├─ state
              ├─ attempt
              ├─ input
              ├─ output
              ├─ executor_ref
              └─ external_run_ref
```

这不是本轮实施要求，而是长期领域方向。

---

# 8. Agent as an Automation Node

Agent 在 Automation 中建议成为标准节点类型：

```text
NodeType = AGENT
```

Automation Node 负责保存：

```text
agent_ref
prompt/input mapping
knowledge_refs
connector_binding_refs
integration_account_refs
timeout policy
retry policy
approval behavior
```

Automation 执行时：

```text
Workflow Engine
      │
      │ AGENT Node
      ▼
Backend
      │
      │ authorize
      │ resolve Expert
      │ resolve runtime
      │ issue capability
      ▼
nodeskclaw-agent
      │
      │ execute Agent Node
      ▼
Remote Hermes
```

Backend 在这条链上仍然有作用，但它的角色是：

```text
Platform Authorization Authority
+
Runtime Router
```

而**不是**：

```text
Remote Run Execution Owner
```

v1.0 原本写的是 `Agent Node Executor Adapter → Backend Remote Agent Contract → nodeskclaw-agent`，即 Backend 持有一套 Remote Agent Run 契约作为中间层。这在 Target 中被取消：Backend 做授权与路由，执行语义直达 Agent。

Automation 保存：

```text
workflow_node_run_id
external_agent_run_id
```

但不复制 Agent 内部事件状态机。

---

# 9. RPA as an Automation Node

当前 Task 已经存在：

```text
RPA Worker
Worker Lease
RPA Run
Step Run
Run Event
RPA Dispatch
```

因此 RPA 本来就是 Automation Domain 的原生 executor。

长期建议：

```text
NodeType = RPA
```

由 Automation 负责：

```text
dispatch
lease
timeout
workflow transition
retry policy
```

由 RPA Worker 负责：

```text
browser execution
local automation
CDP / Playwright
step execution
```

---

# 10. Human Task as a First-Class Node

当前已经有 `HumanAction`。

未来必须区分两类“人工介入”。

## 10.1 Workflow Human Task

属于 Automation：

```text
填写表单
确认业务数据
人工审批流程
补充材料
人工选择分支
```

特征：

```text
业务流程节点
可以等待小时/天
可以 assignment
可以 SLA / escalation
```

## 10.2 Agent Tool Permission

属于 Remote Agent / Agent execution：

```text
Agent 要发送邮件
Agent 要更新 CRM
Agent 要执行高风险 Side Effect
```

特征：

```text
Run 内安全审批
Tool Call scoped
approve / deny
```

这两者必须保持不同状态机。

禁止把：

```text
Agent approval
```

直接建模成：

```text
HumanAction
```

也禁止反过来。

Automation 可以观察 Agent Run 处于：

```text
WAITING_APPROVAL
```

但不应拥有 Agent Approval 的授权语义。

---

# 11. ETL and Non-Agent Job

如果未来支持 ETL / 非 Agent Job，Task 应拥有统一 Executor Adapter 模型：

```text
Executor
├─ AGENT
├─ RPA
├─ ETL
├─ HTTP
├─ SCRIPT
└─ EXTERNAL_JOB
```

每种 Executor 应遵循最小统一生命周期：

```text
submit
status
cancel
result
```

但允许自己的领域扩展。

Automation Engine 只关心：

```text
Node Run State
```

不应该理解每个 Executor 的内部实现。

---

# 12. Timer / Scheduler Boundary

Timer 是 Automation 原生能力。

Task 应拥有：

```text
Cron Trigger
Delayed Timer
Deadline Timer
Retry Timer
Wait Until
Escalation Timer
```

Backend 不应该持有 Workflow Timer。

Backend 自己可以存在平台维护类定时任务，但它们不是 Automation Product Timer。

---

# 13. Event Bus Boundary

未来 Event Bus 的目标不应该只是：

```text
Webhook → Agent
```

而应该支持：

```text
Business Event
Integration Event
Agent Event
Knowledge Event
Timer Event
External Webhook
RPA Event
```

Automation 可以订阅：

```text
event_type
correlation_key
filter
```

然后：

```text
start workflow
resume workflow
advance node
```

Automation 是 Event Consumer / Process Coordinator。

它不成为所有 Event 的 Source of Truth。

---

# 14. BPM Boundary

如果支持 BPM，Task 应拥有：

```text
Process Definition
Process Instance
Business Key
State Transition
Gateway
Human Task
Timer
Message Event
Boundary Event
Compensation
Escalation
```

这些概念明显不属于 Backend，也不属于 Agent。

因此从长期 BPM 目标反推：

> Automation 独立域是必要的。

---

# 15. Backend ↔ Task Contract

Automation 作为独立域并不意味着复制 Backend 权限系统。

建议 Backend 继续作为：

```text
Identity / Org / Platform Resource Authority
```

Task 保存：

```text
user_id
org_id
resource refs
```

需要时通过明确 Contract 验证。

典型资源：

```text
agent_ref
integration_account_ref
connector_binding_ref
```

原则：

```text
Task owns process authorization decision timing.
Backend owns platform resource authorization truth.
```

例如：

```text
Workflow Node 准备执行 Shared Gmail
        ↓
Task 判断节点到了执行时机
        ↓
Backend 验证当前用户/组织是否仍有 USE
        ↓
创建 Agent Run
```

这种跨域 validation 是合理的，不应因为它是网络调用就消灭领域边界。

---

# 16. Task UserCache 的定位

当前 Task 不提供登录接口，复用 Backend JWT，并把 Backend 用户同步到：

```text
autotask_user_cache
```

这是一个值得保留但必须严格约束的模式。

`UserCache` 只能是：

```text
projection / cache
```

不能成为：

```text
User SOT
Org SOT
Role SOT
```

必须允许：

```text
expired
refresh
revalidate
```

涉及高风险权限时，应回到权威来源做执行时验证。

---

# 17. Backend ↔ Knowledge Boundary

Backend 与 Knowledge 的关系不同于传统“Backend 包含 Knowledge”。

Knowledge 自己拥有业务对象。

Backend 可以提供：

```text
Identity
Org
Platform entitlement
Cross-product resource reference
```

Knowledge 自己拥有：

```text
KB ACL
Knowledge Set semantics
Source state
Ingestion state
Retrieval configuration
```

如果某些 Knowledge ACL 当前由 Backend 管理，则未来需要明确：

```text
谁是唯一 Authority
```

但不能两边同时成为 SOT。

---

# 18. Task ↔ Knowledge Boundary

Automation 可以消费：

```text
knowledge_ref
knowledge_set_ref
retrieval_profile_ref
```

但不复制：

```text
chunk
embedding
source file
index state
```

一个 Agent Node 可以引用 Knowledge：

```text
AgentNode
  knowledge_refs[]
```

Task 保存的是：

```text
Reference Snapshot
```

真正知识解析由：

```text
nodeskclaw-knowledge
```

完成。

---

# 19. Agent ↔ Knowledge Boundary

Agent 在执行时需要的是：

```text
authorized retrieval context
```

不是 Knowledge 管理权限。

因此：

```text
Agent
→ Knowledge Gateway
→ authorized retrieval
```

而不是：

```text
Agent
→ manage KB
```

知识管理仍属于 SMC Knowledge / Knowledge Domain。

---

# 20. Current v1.4 AgentAutomation: Keep, but Reinterpret

v1.4 增加：

```text
AgentAutomation
AutomationTrigger
AutomationInvocation
RemoteAgentDispatchJob
AutomationWebhookNonce
```

在新架构下不应简单删除。

其中：

```text
AgentAutomation
Trigger
Invocation
Webhook nonce
```

都可以理解为 Automation Domain 对 Agent 类型任务的第一版产品化。

真正需要未来重新审视的是：

```text
AgentAutomation
```

是否长期保持独立顶层模型，还是成为：

```text
WorkflowDefinition 的简化 Profile / Agent-only Automation 类型
```

这是领域演进问题，不是当前删除问题。

---

# 21. Current v1.5 Shared IntegrationAccount: Correct Cross-Domain Dependency

v1.5 让 AgentAutomation 保存：

```text
integration_account_refs
```

而 IntegrationAccount 的权威状态由 Backend 管理。

这是合理的：

```text
Automation owns:
什么时候需要账号

Backend owns:
这个账号是谁的
谁能使用
当前是否有效
```

因此：

```text
Task → Backend resource validation
```

本身不是架构错误。

真正需要避免的是：

```text
Task 复制 IntegrationAccount ACL
```

或：

```text
Backend 接管 Workflow 状态机
```

---

# 22. Retry Ownership

多 Executor 架构最容易出问题的是双 retry。

必须区分：

## Executor-local Retry

例如：

```text
Agent HTTP transport reconnect
RPA browser transient retry
ETL connector transient retry
```

属于 executor。

## Workflow Retry

例如：

```text
节点失败后 5 分钟重试
最多 3 次
换人工处理
走 compensation
```

属于 Automation。

原则：

```text
Executor Retry
≠
Workflow Retry
```

Automation 不应该重放一个“不知道结果”的 Agent side effect。

Agent 也不应该决定 BPM 是否重试整个节点。

---

# 23. Idempotency Boundary

建议未来统一：

```text
workflow_instance_id
node_run_id
attempt_no
```

Automation 调用 executor 时生成稳定：

```text
execution_request_id
```

例如 Agent：

```text
automation:<workflow_instance_id>:<node_run_id>:<attempt>
```

Agent/Backend 使用它实现 request idempotency。

Automation 是：

```text
business retry authority
```

Executor 是：

```text
same request replay authority
```

---

# 24. Cancellation Boundary

Automation 的 Cancel：

```text
cancel workflow
cancel node
```

它需要传播到 executor。

Agent 的 Cancel：

```text
cancel agent run
```

只终止 Agent Run。

典型：

```text
Workflow Cancel
    ↓
Node Run CANCEL_REQUESTED
    ↓
Agent cancel
    ↓
Agent terminal CANCELLED
    ↓
Node Run CANCELLED
    ↓
Workflow state advance/terminal
```

Automation 不直接修改 Agent 内部状态。

---

# 25. Artifact Boundary

目前：

```text
Task 有 Artifact
Agent 有 Agent Artifact
Knowledge 有文件/Source
```

未来必须区分：

### Automation Artifact

```text
Workflow-level output
RPA screenshot
ETL result
Human uploaded result
```

Task owns metadata/reference。

### Agent Artifact

```text
Agent generated report
spreadsheet
document
```

Agent/Backend Remote Agent Contract owns。

Automation 如果使用 Agent Artifact：

```text
保存 artifact_ref
```

而不是复制 byte/object metadata 成第二 SOT。

### Knowledge Source

不是 Artifact。

只有用户明确把 Artifact 纳入 Knowledge 时，才触发：

```text
Artifact
→ Knowledge ingestion
```

---

# 26. Event Boundary

建议每个域产生自己的 Domain Events。

Backend：

```text
integration.account.revoked
expert.disabled
membership.changed
```

Task：

```text
workflow.started
node.completed
human_task.created
workflow.failed
```

Agent：

```text
agent.run.started
agent.run.waiting_approval
agent.run.completed
agent.artifact.persisted
```

Knowledge：

```text
knowledge.ingestion.completed
knowledge.source.updated
knowledge.index.failed
```

Automation 可以消费其他域事件。

但事件消费不改变 SOT ownership。

---

# 27. Architectural Problem in Current Task: Two Parallel Automation Models

当前最值得关注的不是“Task 要不要存在”，而是 Task 内部已经有两套自动化抽象：

## Legacy / General Automation

```text
WorkflowTemplate
WorkflowBinding
AutomationTask
RpaRun
HumanAction
```

## Agent Automation

```text
AgentAutomation
AutomationTrigger
AutomationInvocation
RemoteAgentDispatchJob
```

长期如果继续各自扩展，会形成：

```text
两套 Trigger
两套 Run
两套 Task
两套 Artifact
两套 Retry
两套 UI
```

所以未来 Architecture Work 的核心应该是：

> **建立统一 Automation Meta-Model，并决定 AgentAutomation 如何落入统一 Workflow/Process 模型。**

这比“把 AgentAutomation 搬进 Backend”重要得多。

---

# 28. Architectural Problem: Dispatch Layering

当前 Agent Automation：

```text
AutomationInvocation
      ↓
RemoteAgentDispatchJob
      ↓
Backend RemoteAgentProvider
      ↓
Backend RunDispatchOutbox
      ↓
Agent
```

> **本次修订结论：这属于当前实现路径与迁移债务（current migration debt），不应被提升为长期架构。**

v1.0 曾把问题开放为"两层可靠派发是否可以共存"。按修订后的 Runtime 边界，这个问题不再开放：Backend 不是 Run Execution Owner，因此 `Backend RemoteAgentProvider` + `Backend RunDispatchOutbox` 这两级不应作为 Target 的组成部分存在。

长期应收敛为：

```text
Automation Invocation
        ↓
Agent Node Dispatch
        ↓
Backend Authorization / Routing
        ↓
nodeskclaw-agent
        ↓
Hermes
```

两点必须分清：

**第一，Task → Agent 的网络路径是否经过 Backend proxy，是 transport / security deployment 问题，不是领域问题。** 出于网络隔离、统一入口、审计等理由让流量过 Backend 是完全可以接受的；关键是 Backend 在这条路径上不得持有执行域模型。

**第二，领域上不能再有四套 Run 状态机：**

```text
Task Run
→ Backend Run
→ Agent Run
→ Hermes Run
```

Target 只允许三层，且各层语义不同、不互为镜像：

```text
Task  : NodeRun（编排语义：这个流程节点成功了吗）
Agent : Run / Attempt（执行语义：这次执行怎么跑的）
Hermes: Native Run（引擎语义：模型侧实际执行）
```

Backend 在这三层中**不占一层**。它持有的是 Expert / Authorization / Placement / Capability，而不是某个 Run 的生命周期。

这不意味着 Task Domain 应被删除 —— Task 的 Node 级可靠派发（保证"Node execution request 最终被接收一次"）仍然是 Automation 域的正当职责。被取消的是 Backend 侧那一层重复的 Run 投递语义。

---

# 29. Architectural Problem: Permission Duplication

当前 Task 有：

```text
PortalAccessGrant
automation_permission
permission_service
```

Backend 有平台：

```text
RBAC
IntegrationAccountGrant
Expert permission
```

必须避免形成一个“大一统 Permission DB”。

推荐区分：

Backend 权限：

```text
Platform Resource Permission
```

Task 权限：

```text
Automation Resource Permission
Workflow Permission
Portal Resource Permission
```

Knowledge 权限：

```text
Knowledge Resource Permission
```

但统一：

```text
Subject Identity
Org Identity
Role Identity
```

来自 Backend。

---

# 30. Architectural Problem: Human Action vs Approval

必须冻结概念：

```text
HumanAction
=
Business Process Human Node

Agent Approval
=
Agent Side-effect Security Decision
```

可以在 SMC UI 中统一视觉风格。

但不能合并底层状态机。

---

# 31. Architectural Problem: Public API Topology

未来有三种方案：

## Option A — SMC Direct Domain Clients

```text
SMC
├─ Backend Client
├─ Automation Client
└─ Knowledge Client
```

优点：

```text
领域独立
避免 Backend Proxy
Contract 清楚
服务可独立演进
```

缺点：

```text
客户端 service discovery 较多
需要统一 auth / error / tracing
```

---

## Option B — Backend Reverse Proxy Everything

```text
SMC
→ Backend
   → Task
   → Knowledge
```

优点：

```text
客户端一个 endpoint
```

缺点：

```text
Backend 变成网络中转层
增加 latency / coupling
大量 pass-through contract
Backend release 被其他域 API 牵制
```

---

## Option C — Unified Edge Gateway + Independent Domains

```text
SMC
     ↓
Unified API Gateway
     │
     ├─ /platform    → backend
     ├─ /automation  → task
     └─ /knowledge   → knowledge
```

Backend 继续：

```text
identity authority
```

但不承担纯 proxy 代码。

对于 Automation 大产品 + Knowledge 业务模块的长期目标，

> **Option C 是最干净的目标形态。**

当前阶段无需立即引入新 Gateway 产品。

现有 Electron Main / deployment reverse proxy 也可以承担统一入口作用。

---

# 32. Recommended Product Surface

从 SMC 用户视角：

```text
SMC Copilot
│
├─ Chat / Remote Expert
│    → Backend ACP ingress
│         → Agent ACP Runtime Gateway
│              → Remote Hermes
│
├─ Automation
│    → Task Automation APIs
│
├─ Knowledge
│    → Knowledge APIs
│
├─ Integrations / Accounts
│    → Backend
│
└─ Settings / Identity
     → Backend
```

这是产品模块化，而不是技术割裂。

统一的：

```text
Login
Organization
Identity
Design System
File Preview
Notifications
Audit navigation
```

仍然属于一个 SMC 产品体验。

---

# 33. What Backend Should NOT Become

基于 Automation 和 Knowledge 都是业务模块，Backend 不应逐渐吸收：

```text
WorkflowDefinition
ProcessInstance
HumanTask
RpaRun
EtlJob
Timer
EventSubscription

KnowledgeBase
KnowledgeSet
IngestionJob
RetrievalProfile
Citation
Evaluation
```

否则最终会形成：

```text
Backend God Service
```

而 Task / Knowledge 退化成 worker。

这会严重限制后续产品独立迭代。

---

# 34. What Task Should NOT Become

Task 也不能变成平台主数据服务。

不应拥有权威：

```text
User
Organization
Expert
IntegrationAccount
Connector
KnowledgeBase
```

Task 只保存：

```text
ID reference
snapshot required for historical reproducibility
```

---

# 35. What Agent Should NOT Become

Agent 不应拥有：

```text
Workflow
BPM
Human Task
RPA orchestration
ETL
Timer
Event Bus
Knowledge management
```

Agent 应保持足够专用。

这样未来才可以独立优化：

```text
model routing
Hermes runtime
tool execution
sandbox
agent memory
agent workspace
agent recovery
```

而不被 Workflow Engine 绑死。

---

# 36. What Knowledge Should NOT Become

Knowledge 不应成为：

```text
General File Platform
Workflow Artifact Service
Agent Runtime Store
Identity Provider
```

Knowledge 的文件是：

```text
Knowledge Source
```

不是所有系统文件。

这可以避免：

```text
Attachment
Artifact
Knowledge Source
```

再次混在一起。

---

# 37. Recommended Dependency Direction

建议业务依赖方向：

```text
SMC
 │
 ├───────────────┬────────────────┐
 ▼               ▼                ▼
Backend          Task          Knowledge
 │               │                │
 │               ├───────┐        │
 │               │       │        │
 │               ▼       ▼        ▼
 │            Backend    Agent  Retrieval
 │               │       │
 └───────────────┴───────┘
```

原则：

```text
Task may depend on Backend contracts.
Task may depend on Agent execution contracts.
Task may depend on Knowledge contracts.

Agent may depend on Backend authorization/proof contracts.
Agent may depend on Knowledge retrieval contracts.

Knowledge may depend on Backend identity claims.

Backend SHOULD NOT depend on Task domain internals.
Backend SHOULD NOT depend on Knowledge internal models.
Backend SHOULD NOT own Agent runtime state.
```

**Backend 与 Agent 的关系必须明确**（v1.0 在此处表述模糊，本次修订补齐）：

```text
nodeskclaw-backend = Authority + Router
nodeskclaw-agent   = Runtime Owner
```

含义：

```text
Backend 决定「这次执行是否被允许、去哪里、带什么 scope」。
Agent  决定「这次执行怎么跑、跑到哪一步、产出了什么」。
```

因此依赖是**单向的授权依赖，不是控制依赖**：

```text
Agent → Backend   ：取授权与 capability（允许）
Backend → Agent   ：移交一次已授权的执行（允许）
Backend → Agent   ：持续控制该执行的生命周期（禁止）
Agent → Backend   ：把 Run 状态写回 Backend 作为权威（禁止）
```

最后两条是本次修订新增的禁止项，对应 §5 中 `Agent Run Execution` 双 Owner 的取消。

---

# 38. Cyclic Dependency Guard

必须避免：

```text
Backend domain service
→ Task
→ Backend same transaction
```

也避免：

```text
Task
→ Agent
→ Task callback requiring synchronous transaction
```

跨域调用应采用：

```text
stable HTTP contract
event
reference
idempotency
```

而不是共享 ORM model。

---

# 39. Data Ownership Principle

每个服务拥有自己的数据库表是合理的。

跨域不应该：

```text
JOIN another service DB
```

历史显示 Task 已经通过：

```text
autotask_user_cache
```

采用 projection。

这种模式未来还可以用于：

```text
ExpertSnapshot
IntegrationAccountDisplaySnapshot
KnowledgeDisplaySnapshot
```

但 Snapshot 只能用于：

```text
display
history
routing hint
```

不能替代执行时 Authority。

---

# 40. Long-Running Process Requirement

未来 BPM / Human Task 可能运行：

```text
minutes
hours
days
weeks
```

因此 Automation Engine 必须独立考虑：

```text
durable state
timer persistence
event correlation
resume
version pin
workflow migration
compensation
operator intervention
```

这些特征进一步证明它不应该嵌入 Web Backend 的普通 Request/Response 生命周期。

---

# 41. Workflow Versioning

未来 Workflow 必须：

```text
Definition
Version
Published Version
Instance-bound Version
```

一个运行中的 WorkflowInstance：

```text
MUST keep pinned workflow version
```

不能因为管理员编辑模板就改变历史运行中的节点图。

当前已经存在：

```text
WorkflowTemplateVersion
```

说明早期设计已经意识到这个问题。

---

# 42. Agent Version / Expert Version Interaction

Automation Workflow 可以引用：

```text
agent_ref
```

但企业长期运行需要进一步考虑：

```text
Expert current
vs
Expert pinned version
```

本分析不决定版本策略。

但必须把它视为：

```text
cross-domain version pin problem
```

而不是 Task 复制 Expert 配置。

---

# 43. Knowledge Version / Retrieval Snapshot

同样，一个长期 Workflow 使用 Knowledge 时：

```text
Knowledge changes
```

可能影响结果。

未来需要选择：

```text
latest authorized knowledge
```

或：

```text
retrieval snapshot/version
```

这是 Knowledge ↔ Automation Contract 的版本问题。

不应由 Agent 隐式决定。

---

# 44. Event-Driven Architecture Opportunity

Automation 产品成熟后，可逐步从：

```text
HTTP orchestration
```

扩展为：

```text
Event-driven orchestration
```

例如：

```text
Backend:
integration revoked
expert disabled

Knowledge:
ingestion completed

Agent:
run completed

RPA:
run failed

Business:
ERP order created
```

Automation 订阅并关联：

```text
workflow_instance
business_key
correlation_id
```

这将是独立 Automation Domain 的核心扩展能力。

---

# 45. AgentAutomation's Strategic Role

建议把当前 `AgentAutomation` 理解为：

> **Automation 平台第一类“Agent-first Automation Profile”。**

它当前很适合简单场景：

```text
Cron
Webhook
Manual
→ one Agent Run
```

未来无需立即删除。

它可以继续作为：

```text
Simple Automation
```

而复杂 Automation 使用：

```text
Workflow
```

最终可能形成：

```text
Simple Agent Automation
        │
        └─ compiled / represented as
           one-node Workflow
```

这是一种未来可能的统一方向。

本分析不要求现在实现。

---

# 46. Current AutoTask Assets Worth Preserving

当前 Task 中值得明确保留为长期资产的设计包括：

```text
Workflow Template / Version
Workflow Binding

Automation Task
Task State Machine

Human Action

RPA Worker
Worker Lease
RPA Run
Step Run
Run Event

Artifact metadata

Audit

AgentAutomation
Trigger
Invocation
Idempotency
Cron/Webhook semantics
```

这些不应该因为 Remote Expert 架构演进而被当成“历史废代码”。

---

# 47. Areas That Need Future Architecture Review

以下是后续应单独做 Architecture Decision / Domain Design 的问题，而不是现在直接实施：

```text
A-001
AutomationTask 与 AgentAutomation 如何统一？

A-002
WorkflowTemplate 是否成为所有 Automation 的核心定义？

A-003
Simple AgentAutomation 是否映射成单节点 Workflow？

A-004
RemoteAgentDispatchJob 与 Backend RunDispatchOutbox 的责任是否重复？

A-005
Automation Artifact 与 Agent Artifact 怎样引用？

A-006
HumanAction 与更完整 BPM Human Task 如何演进？

A-007
Portal Account 与 Backend IntegrationAccount 的长期边界是什么？

A-008
RPA Credential 与 IntegrationAccount 是否有交叉？

A-009
Event Bus 的 envelope / correlation 模型是什么？

A-010
Timer persistence 使用什么 durable scheduler 模型？

A-011
Workflow DAG / Gateway / Conditional expression 模型是什么？

A-012
Compensation / Saga 如何定义？

A-013
ETL Worker 与 RPA Worker 是否共享 Worker Protocol？

A-014
Executor Plugin Contract 如何定义？

A-015
Knowledge refs 的 latest / pinned semantics 是什么？

A-016
Expert refs 的 latest / pinned semantics 是什么？

A-017
SMC Automation 是否直接消费 Task，还是经统一 Edge？

A-018
跨域 Audit 如何关联同一个 trace/business process？
```

---

# 48. Architecture Decision Direction

基于当前产品目标，本分析推荐以下方向作为后续讨论基线：

## Direction 1

```text
保留 nodeskclaw-task 作为 Automation 独立业务域。
```

## Direction 2

```text
不把 Automation Workflow/BPM 状态机迁入 nodeskclaw-backend。
```

## Direction 3

```text
nodeskclaw-agent 只作为 AGENT 类型执行器。
```

## Direction 4

```text
nodeskclaw-knowledge 保持 Knowledge 业务模块，
同时提供 Knowledge Gateway 能力。
```

## Direction 5

```text
Backend 继续是 Identity / Org / Platform Resource Authority，
但不是所有业务域的数据库 Owner。
```

## Direction 6

```text
未来 SMC 的统一性应来自统一身份、Contract、API Gateway/客户端规范，
而不是通过把所有业务代码合并进 Backend。
```

---

# 49. Target Conceptual Architecture

四域总体结构沿用 v1.0；本次修订替换 Remote Expert / Agent Runtime 这一段。

```text
┌───────────────────────────────────────────────────────────────┐
│                         SMC Copilot                           │
│                                                               │
│ Chat / Remote Expert        Automation        Knowledge       │
└───────────┬────────────────────┬─────────────────┬────────────┘
            │                    │                 │
            │ ACP                │                 │
            ▼                    ▼                 ▼
┌──────────────────────┐ ┌─────────────────┐ ┌──────────────────┐
│ nodeskclaw-backend   │ │ nodeskclaw-task │ │ nodeskclaw-      │
│                      │ │                 │ │ knowledge        │
│ Identity             │ │ Workflow        │ │                  │
│ Org / RBAC           │ │ BPM             │ │ KB / Set         │
│ Expert Catalog       │ │ Human Task      │ │ Source / File    │
│ Expert ACL           │ │ Timer / Event   │ │ Ingestion        │
│ IntegrationAccount   │ │ RPA / ETL       │ │ Retrieval        │
│ Connector            │ │ Agent Node      │ │ Evaluation       │
│                      │ │                 │ │                  │
│ ACP Public Ingress   │ │                 │ │                  │
│ Runtime Routing      │ │                 │ │                  │
│ Capability Authority │ │                 │ │                  │
└──────────┬───────────┘ └────────┬────────┘ └──────────────────┘
           │                      │
           └──────────────┬───────┘
                          │ authorized execution
                          ▼
              ┌──────────────────────────┐
              │ nodeskclaw-agent         │
              │                          │
              │ ACP Runtime Gateway      │
              │ Agent Run / Attempt SOT  │
              │ Tool Gateway             │
              │ Approval / Artifact      │
              │ Event Stream             │
              │ Hermes Runtime Bridge    │
              └────────────┬─────────────┘
                           │
                           │ Native Runtime API
                           ▼
                    ┌──────────────┐
                    │ Remote Hermes│
                    │ Agent Engine │
                    └──────────────┘
```

与 v1.0 图的差异只有两处，但都是本质性的：

1. Backend 框内的 `Remote Agent Ctrl` 被删除，替换为 `ACP Public Ingress` / `Runtime Routing` / `Capability Authority`。
2. Agent 框从 `Dedicated Agent` 升级为 `ACP Runtime Gateway` + `Agent Run / Attempt SOT`，并显式画出其南向 `Remote Hermes Agent Engine`。

Backend 与 Task 两条线汇聚到 Agent 的那条边，语义是 **authorized execution**（一次已授权的执行移交），不是 run control（持续控制）。

**Target 已冻结 `nodeskclaw-acp` 的生产角色**（不再把"位置"整体标为未决）：

```text
smc-copilot MUST NOT require local nodeskclaw-acp.exe
```

当前 `SMC → local nodeskclaw-acp → Backend REST/SSE` 是 Current Implementation（见 §2.1），不是目标生产拓扑。`nodeskclaw-acp` MAY 保留为 Zed / 第三方 stdio ACP Client 的 compatibility adapter 以及 ACP compatibility testing；MUST NOT 持有业务或运行状态 SOT。工程是否保留、代码如何复用，属于实现层事项。

本图 `smc-copilot --ACP--> nodeskclaw-backend` 表示 SMC Production 走 Backend ACP Public Ingress，不经本地 sidecar。ingress 的具体 network transport 仍属实现未决（Appendix B）。

---

# 50. Final Conclusions

本次 Architecture Analysis 得出的主要结论不是“立即实施某个重构”，而是重新确认正确的问题边界。

第一，当前 `nodeskclaw-task` 不能再简单理解成 v1.4 为 Remote Agent 增加的 Cron/Webhook 辅助服务。它在 v1.4 之前已经拥有 Workflow、RPA、Human Action、Worker、Task、Artifact 等完整业务资产。未来 Automation 又明确要覆盖 Workflow Engine、BPM、Human Task、RPA、ETL、Timer、Event Bus、Agent 与 Non-Agent Job，因此 Automation 是独立 Bounded Context 的长期方向。

第二，`nodeskclaw-backend` 应继续保持平台 Identity / Org / Expert / Integration / Connector 等 Authority，并作为 ACP Public Ingress、Runtime Router 与 Capability Authority，而不应为了“统一前端对接”把 Workflow/BPM 状态机吸收入 Backend。**同时它应从 "Remote Agent Run Control Plane" 收敛出去 —— Run 的生命周期不再归 Backend。**

第三，`nodeskclaw-agent` 是 **Agent Runtime Gateway + Agent Execution Plane**，而不只是一个专用 Execution Plane。ACP 的 Runtime 语义（session / prompt / cancel / permission）应在此层落地，Run / Attempt / Event / Artifact / Terminal State 的 SOT 也在此层。对于 Automation，它仍然只是 `AGENT` Node Executor，而不是 Workflow Engine —— Runtime Owner 与 Automation Owner 是两件事。

第四，`nodeskclaw-knowledge` 当前已经是 SMC Copilot Knowledge 模块所使用的业务功能模块。它同时可以为 Agent / Automation 提供 Knowledge Gateway，但不能因此被定义成纯内部 Gateway。

第五，当前真正需要后续深入设计的，是 `nodeskclaw-task` 内部的 Automation Meta-Model：现有通用 `AutomationTask / Workflow / RPA` 与后来加入的 `AgentAutomation / Trigger / Invocation` 如何最终统一。这比讨论是否把 Task 搬回 Backend 更重要。

第六，v1.4 / v1.5 不是需要被推翻的错误版本。v1.4 中 Agent Automation 作为 Automation Domain 的一类能力是合理的；v1.5 中 Task 对 Backend 的 IntegrationAccount 权威状态进行验证，也是合理的跨领域依赖。需要审视的是具体 Dispatch、Retry、Permission、Artifact 等边界是否重复，而不是消灭 Domain Boundary。

第七，后续架构工作的正确顺序应当是：

```text
先冻结 Domain Ownership
        ↓
再统一 Automation Meta-Model
        ↓
再定义 Executor Contract
        ↓
再定义跨域 Contract
        ↓
最后才决定哪些现有代码需要调整
```

而不是先迁移代码再定义架构。

第八（rev.1 新增），Remote Expert 这条运行链的 Target 可以压缩成一句话：

> **Backend 从 "Remote Agent Run Control Plane" 收敛为"平台授权 + Expert 路由 + ACP 公共入口"；`nodeskclaw-agent` 升级为真正的 ACP Runtime Gateway + Agent Execution Plane；Remote Hermes 保持最终 Agent Engine。SMC Production MUST NOT require local `nodeskclaw-acp.exe`。**

其直接推论是：同一次执行不得在 Backend 与 Agent 各有一份 Run 模型。

```text
Backend：能不能执行？找谁执行？去哪里执行？带什么授权执行？
Agent  ：怎么执行？当前执行到哪里？调用了什么 Tool？产生了什么 Event / Artifact？
Hermes ：真正运行 Agent Loop。
```

---

# Appendix A — Source Evidence Used

当前分析主要依据以下源码事实：

```text
nodeskclaw-task/app/api/router.py
nodeskclaw-task/app/models/agent_automation.py
nodeskclaw-task/app/models/automation_task.py
nodeskclaw-task/app/models/human_action.py
nodeskclaw-task/app/api/workflow_templates.py
nodeskclaw-task/app/services/*
docs/backend/nodeskclaw_task.md

nodeskclaw-backend/app/api/router.py
nodeskclaw-backend/app/services/remote_agent_provider_service.py

nodeskclaw-knowledge/app/api/router.py
nodeskclaw-knowledge/app/api/*
```

rev.1 的 Runtime / ACP 章节另外依据以下源码事实：

```text
nodeskclaw-acp/app/cli.py                 — serve/login/doctor，无监听端口
nodeskclaw-acp/app/jsonrpc.py             — stdio JSON-RPC，stdin/stdout
nodeskclaw-acp/app/agent.py               — initialize / session new|resume|close|prompt|cancel
nodeskclaw-acp/app/prompt_turn.py         — prompt turn 与事件映射
nodeskclaw-acp/app/session_registry.py    — session 纯进程内存，重启不存活
nodeskclaw-acp/app/remote_client.py       — 南向只调 backend /api/v1/auth/* 与 /api/v1/remote-agent/*
nodeskclaw-acp/contracts/acp-v1-adapter/v1.1.0/manifest.json — provider=nodeskclaw-acp, consumer=smc-copilot/apps/work

nodeskclaw-agent/app/api/internal_runs.py — 仅 /internal/v1/runs，无 ACP 语义
nodeskclaw-agent/app/services/hermes_engine.py — Hermes Native Run 调用与 SSE 消费
nodeskclaw-agent/app/db_metadata.py       — schema agent，runs/run_attempts/run_events/run_artifacts
```

两条关键否定性事实（用于区分 Current 与 Target）：

```text
nodeskclaw-agent 源码中检索 acp / ACP / nodeskclaw-acp / stdio：无命中
nodeskclaw-acp   源码中检索 nodeskclaw-agent / skill-agent / 4580 / hermes：无命中
```

即当前 ACP 与 Agent Runtime **没有任何直接关系**，两者之间隔着 Backend 的 Remote Agent REST。这正是 rev.1 要修正的对象。

其中当前 `docs/backend/nodeskclaw_task.md` 已明确把 Task 描述为：

```text
与 nodeskclaw-backend 平级部署的 AutoTask 业务后端。
```

而 Knowledge Router 当前公开的 API 面证明 Knowledge 已经是完整业务模块，而不仅是 Agent retrieval adapter。

---

# Appendix B — Explicit Non-Decisions

本分析故意不做以下决策：

```text
不决定仓库改名。
不决定服务合并。
不决定代码迁移。
不决定删除 nodeskclaw-task。
不决定新增服务。
不决定具体 Event Bus 产品。
不决定 Workflow Engine 第三方选型。
不决定 Temporal / Camunda / Airflow / Prefect 等选型。
不决定数据库拆分方式。
不决定消息队列选型。
不决定 SMC 是否立即引入统一 API Gateway。
不决定 AgentAutomation 是否现在改成 Workflow。
不生成 Implementation Todo。
```

rev.1 另外明确不决定（仅实现机制，所有权方向已冻结）：

```text
不决定 Backend ACP ingress 最终使用何种 network transport。
不决定 Backend → Agent 是透明 stream proxy 还是 capability 后直连。
不决定 Agent ACP Gateway 如何复用现有 nodeskclaw-acp 代码。
不决定 Remote Agent REST/SSE 的兼容退役节奏。
不决定 RunDispatchOutbox / HermesTask 的迁移方式。
不决定 nodeskclaw-acp 工程是否最终保留为第三方 stdio 兼容适配器（它已确定不是 SMC Production 必经依赖，且不得持有 SOT）。
```

以下**不再未决**：

```text
SMC 不依赖 nodeskclaw-acp.exe
Backend owns Auth / Expert ACL / Routing / Scoped Execution Capability
Agent owns ACP Runtime Gateway / Run execution
Hermes remains Agent Engine
nodeskclaw-acp owns no SOT
```

这些应在 Domain Architecture 被接受后分别进入专项 Architecture Decision。
