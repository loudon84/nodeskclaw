# NoDeskClaw 领域边界核心文档（Architecture Domain Boundaries）

| 项 | 值 |
|---|---|
| 文档类型 | 架构边界约束（Architecture Constraint） |
| 版本 | v1.0 |
| 范围 | `nodeskclaw-backend`、`nodeskclaw-task`、`nodeskclaw-agent`、`nodeskclaw-knowledge` |
| 上游依据 | `docs/NodeSkClaw-Architecture-Analysis-Automation-Domain-v1.0.md`（领域建议，含 rev.1 Runtime / ACP 边界修正）+ 当前代码结构扫描（事实基线） |
| 状态 | DRAFT（未 APPROVED，禁止作为已生效治理依据引用） |

---

## 0. 本文档的用法

本文档是**四个工程领域归属与边界的唯一参照**。任何 PRD、Plan、实施改动在动手前必须先过本文档第 9 节的检查清单。

三类陈述分开标注，不得混用：

- **【事实】** — 当前代码的真实状态，带文件路径依据。事实会随代码变化，发现不一致时先更新本文档再继续实施。
- **【约束】** — 必须遵守的边界规则。PRD 不得违反；确需违反时，必须先修订本文档并走架构决策，不得在 PRD 里绕过。
- **【偏差】** — 当前代码已经违背【约束】的地方。偏差是已登记的技术债，不是许可：**不得以"反正已经这样了"为理由在偏差上继续堆功能**。

与上游分析文档的关系：分析文档给出的是**目标领域划分建议**；本文档把建议落到当前代码事实上，并把"建议"固化为可执行的【约束】。两者冲突时以本文档为准。

---

## 1. 四个工程的一句话定位

| 工程 | 领域（Bounded Context） | 一句话定位 | 端口 | 数据库 | 身份来源 |
|---|---|---|---|---|---|
| `nodeskclaw-backend` | 平台控制域（Platform Control） | 身份、组织、权限、平台资源的唯一权威，兼 ACP 公共入口与 Runtime 路由 | 4510 | 独立库（`DATABASE_URL` + `DATABASE_NAME_SUFFIX`） | **自身签发 JWT** |
| `nodeskclaw-task` | 自动化编排域（Automation） | 触发、调度、流程编排、人工任务、RPA 作业的唯一权威 | 4520 | `nodeskclaw_task` | 复用 backend JWT |
| `nodeskclaw-agent` | Agent Runtime 域（Runtime Gateway + Execution Plane） | ACP Runtime 语义落地层，Run / Attempt / Event / Artifact 的唯一权威 | 4580 | 与 backend **同库不同 schema**（`agent`） | 内部共享 Token |
| `nodeskclaw-knowledge` | 知识业务域（Knowledge Business + Gateway） | 知识库建设、检索与引用的唯一权威，并对外提供检索网关 | 4530 | `nodeskclaw_knowledge` | 复用 backend JWT（身份）+ 自有 ACL（授权） |

附属组件（非独立域，不持有任何 SOT）：

| 组件 | 形态 | 定位 |
|---|---|---|
| `nodeskclaw-acp` | 被 ACP 客户端 spawn 的本地 stdio adapter 进程，无端口、无数据库 | ACP v1 客户端侧接入点。session 纯进程内存，重启不存活。Target 中的去留未决，见 §8 的 D-08 |

**【约束】** Backend 与 Agent 的职责分界是本文档最容易被 PRD 越界的一条，必须按下面这句话理解：

```text
nodeskclaw-backend = Authority + Router
nodeskclaw-agent   = Runtime Owner
```

Backend 回答"能不能执行、去哪里执行、带什么 scope"；Agent 回答"怎么跑、到哪一步、产出什么"。**同一次执行不得在 Backend 与 Agent 各有一份 Run 模型。**

**【事实】** 端口依据：backend `nodeskclaw-backend/app/core/config.py`；task `nodeskclaw-task/Dockerfile`、`.env.example`（`PORT=4520`）；agent `nodeskclaw-agent/Dockerfile`（`EXPOSE 4580`）；knowledge `nodeskclaw-knowledge/app/core/config.py`。

**【事实】** 库归属依据：task `nodeskclaw-task/.env.example`（`nodeskclaw_task`）；knowledge `nodeskclaw-knowledge/app/core/config.py`（`nodeskclaw_knowledge`）；agent `nodeskclaw-agent/.env.example`（库名默认 `nodeskclaw`，`SKILL_AGENT_SCHEMA=agent`，并注明不覆盖 backend 的 `public.alembic_version`）。

**【约束】** agent 与 backend 物理同库仅是部署便利，**不构成数据共享许可**。见第 6.2 节。

---

## 2. 事实基线：每个工程实际拥有什么

### 2.1 nodeskclaw-backend —— 平台控制域

**【事实】HTTP 面**：`app/main.py` 挂载三个根 —— `api_router` → `/api/v1`、`admin_router` → `/api/v1/admin`、`webhook_router` → 根路径。路由聚合在 `app/api/router.py`。

主要公共面分组：

| 分组 | 代表前缀 |
|---|---|
| 身份与组织 | `/auth`、`/orgs`、`/members`、`/invite`、`/settings` |
| Expert / Remote Expert | `/expert`（含 `/expert/mcp`）、`/hermes-experts`、`/remote-experts` |
| Remote Agent / Run 投影（**Legacy，见 D-09**） | `/runs`、`/remote-agent/runs`、`/remote-agent/sessions` |
| 集成与连接器 | `/integrations`、`/hermes/connectors`、`/hermes/edge-nodes` |
| 附件与工件 | `/attachments`、`/upload/policy`、`/hermes/artifacts` |
| Hermes Skill 平台 | `/hermes/*`（skills、releases、installations、agents、dispatch、queue、mcp） |
| 运行时与基础设施 | `/clusters`、`/deploy`、`/instances`、`/genes`、`/engines`、`/gateway`、`/runtime` |
| 内部面（机器到机器） | `/internal/edge`、`/internal/v1/skill-agent`、`/internal/v1/automation/remote-agent` |

**【事实】模型所有权**：`app/models/` 覆盖 User / Organization / OrgMembership / MemberToken / Instance / Cluster / Workspace 全家族 / Expert 全家族 / HermesSkill 全家族 / HermesTask / RunDispatchOutbox / IntegrationAccount / ConnectorDefinition / SkillConnectorBinding / ExternalActionExecution / ExpertExternalActionPolicy / EdgeNode / McpGateway 全家族 / Upload 全家族。

**【事实】** 在 `app/models/` 内检索 `Workflow|Process|BPM|HumanTask|Timer|Cron|EventSubscription|RpaRun` **无匹配**；放宽为 `cron|timer|rpa|bpm|event.?sub` 后仅命中 `WorkspaceSchedule.cron_expr`（`app/models/workspace_schedule.py`）与消息信封里的 `SenderType.CRON`。

**【偏差 D-01】** 但 Workflow 模型确实存在于 backend，在 `app/modules/task_orchestrator/` 下，表前缀 `to_`（`app/modules/task_orchestrator/constants.py`）：`WorkflowTemplate` → `to_workflow_templates`、`WorkflowInstance` → `to_workflow_instances`、`WorkflowNode` → `to_workflow_nodes`、`WorkflowEvent` → `to_workflow_events`、`HumanIntervention` → `to_human_interventions`、`CheckpointSnapshot` → `to_checkpoints`、`ExecutorBinding` → `to_executor_bindings`。详见第 8 节。

**【事实】出站依赖**：仅两个 sibling 工程。

- → `nodeskclaw-agent`：`SKILL_AGENT_BASE_URL`，头 `X-Skill-Agent-Token`。调用点包括 `app/services/hermes_skill/run_dispatch_outbox_service.py`（POST `/internal/v1/runs`）、`run_projection_updater_service.py`（拉 run / events / result / artifacts）、`app/api/runs.py`、`app/api/remote_agent_runs.py`、`app/api/internal_edge.py`、`app/api/internal_automation.py`、`hermes_skill/approval_decision_service.py`。
- → `nodeskclaw-knowledge`：`KNOWLEDGE_SERVICE_BASE_URL`，仅一个端点 —— `app/services/hermes_skill/runtime_skill_run_service.py` 的 `_fetch_knowledge_proofs` POST `/api/v2/skill-run/auth-proofs`。

**【事实】** backend **不调用** `nodeskclaw-task`。检索 `nodeskclaw-task`、`TASK_SERVICE`、`autotask` 作为 HTTP 目标均无命中；`nodeskclaw_task_*` 只是 MCP 内置工具名（`app/services/mcp_skill_gateway/builtin_task_tools.py`），读的是本库 `HermesTask`。

**【事实】入站内部面与鉴权**：

| 入口 | 鉴权 | 调用方 |
|---|---|---|
| `/api/v1/internal/v1/skill-agent/*` | `X-Skill-Agent-Token`（`SKILL_AGENT_INTERNAL_TOKEN`，支持 previous 轮换） | agent |
| `/api/v1/internal/v1/automation/remote-agent/*` | `X-Autotask-Internal-Token`（`AUTOTASK_INTERNAL_TOKEN`） | task |
| `/api/v1/internal/edge/*` | Ed25519 签名信封（`X-Edge-Node-Id` / `X-Edge-Signature` / `X-Edge-Seq` …） | agent（edge 角色） |

依据：`app/api/internal_skill_agent.py`、`app/api/internal_automation.py`、`app/api/internal_edge.py`。

**【事实】契约目录**：`nodeskclaw-backend/contracts/` 共 7 个契约名 —— `skill-run`、`remote-agent`、`remote-agent-automation`、`integration-account`、`work-expert`、`skill-agent`、`remote-expert-catalog`。

### 2.2 nodeskclaw-task —— 自动化编排域

**【事实】HTTP 面**：全部挂在 `/api/v1/autotask`（`app/main.py`），聚合于 `app/api/router.py`，三个顶层 router：`api_router`、`worker_api_router`（`/worker-api`）、`mcp_router`（`/mcp`）。

**【事实】存在两套并行的自动化抽象**：

| | 套 A：流程/RPA 编排 | 套 B：Agent 自动化 |
|---|---|---|
| 入口 | `/workflow-templates`、`/workflow-bindings`、`/tasks`、`/runs`、`/human-actions`、`/rpa-workers`、`/worker-api` | `/agent-automations`、`/automation-hooks/{hook_id}` |
| 表 | `workflow_templates`、`workflow_template_versions`、`workflow_bindings`、`automation_tasks`、`rpa_runs`、`step_runs`、`run_events`、`human_actions`、`artifacts`、`rpa_workers`、`worker_leases`、`task_messages`、`task_successor_jobs` | `agent_automations`、`automation_triggers`、`automation_invocations`、`remote_agent_dispatch_jobs`、`automation_webhook_nonces` |
| 状态定义 | `app/models/enums.py` 的 `StrEnum`（`TaskStatus`、`RunStatus`、`HumanActionStatus` …）+ 转移表 `app/services/task_state_machine.py` | **无 StrEnum**，合法值散落在服务层字符串集合（`app/services/agent_automation_service.py`、`remote_agent_dispatch_service.py`） |
| 建表迁移 | `alembic/versions/` 前三个 revision | `93ebce7657cb_add_agent_automation_tables.py` |

两套的衔接点：`TaskSuccessorJob.target_kind` 可取 `WORKFLOW_BINDING` 或 `REMOTE_AGENT_AUTOMATION`（`app/models/task_successor_job.py`），成功的 RPA Run 可经 `create_successor_invocation` 以 `trigger_type="SUCCESSOR"` 进入套 B。

**【事实】调度机制**：没有 APScheduler / Celery / Redis / outbox 表。全部是 FastAPI lifespan 内的 asyncio 轮询循环（`app/main.py`），cron 解析用 `croniter`：

- `RemoteAgentDispatchProcessor`（`app/services/remote_agent_dispatch_service.py`）：`FOR UPDATE SKIP LOCKED` 捞 `PENDING`/`RETRYING` 的 `remote_agent_dispatch_jobs`，退避序列 `(5, 30, 120, 600, 1800, 3600)` 秒。
- `CronFireProcessor`（同文件）：到期触发器建 invocation，超过 `MISFIRE_GRACE_SECONDS` 记 `MISSED`。
- `SuccessorJobProcessor`（`app/services/task_successor_service.py`）：开关 `SUCCESSOR_JOB_ENABLED` 默认 **False**。
- RPA Worker 是**拉模式租约**（`app/services/dispatch_service.py`）：`/worker-api/tasks/lease` + `worker_leases` + TTL 过期回队。

**【事实】身份与权限**：`app/api/` 下无任何登录/注册/发令牌端点。`app/core/security.py` 用与 backend 共享的 `JWT_SECRET` 解 token，`app/services/user_sync.py` 在缓存过期时 `GET {NODESKCLAW_BACKEND_URL}/api/v1/auth/me` 并写入 `autotask_user_cache`。两套授权模型并存：`PortalAccessGrant` + `app/services/permission_service.py`（Portal 资源），以及 `app/services/automation_permission.py`（`automation:view|manage|run` 角色映射）。

**【事实】出站依赖**：

- → backend：`app/services/user_sync.py`（`/api/v1/auth/me`，用户 Bearer）；`app/services/agent_automation_service.py` 与 `remote_agent_dispatch_service.py`（`/api/v1/internal/v1/automation/remote-agent/*`，`X-Autotask-Internal-Token`）。
- → RPA Engine：`app/services/rpa_engine_client.py`（`RPA_ENGINE_BASE_URL`，可由 `RPA_ENGINE_VALIDATE_BINDING=false` 关闭）。
- **不调用** agent、不调用 knowledge。检索 `KNOWLEDGE_SERVICE`、`/api/v2/agent/tools`、`4530` 在该工程均无命中；`knowledge_refs` 只是存表并原样转发给 backend 的 JSON 字段。

**【事实】契约目录**：`nodeskclaw-task/contracts/` 仅 `agent-automation`，版本 `v1.0.0`、`v1.1.0`，consumer 标注为 `smc-copilot/apps/work`。

### 2.3 nodeskclaw-agent —— Agent Runtime 域

**【约束】目标定位**：`Agent Runtime Gateway + Agent Execution Plane`。ACP 的 Runtime 语义（session / prompt / cancel / permission）应在此层落地，Run / Attempt / Event / Artifact / Terminal State 的 SOT 也在此层。

**【事实】** 当前代码**尚未**实现 ACP 层：在 `nodeskclaw-agent/` 下检索 `acp`、`ACP`、`nodeskclaw-acp`、`stdio` 均无命中。它目前只有 `/internal/v1/runs` 这一套内部 Run API。这是一条已登记的 capability gap（D-09），不是已完成状态。

**【事实】形态**：FastAPI HTTP 服务 + 同进程 Worker。`app/main.py` 的 lifespan 在 `SKILL_AGENT_WORKER_ENABLED` 为真时按 `SKILL_AGENT_ROLE` 启动 `RunWorker`（central）或 `EdgeWorker`（edge）。

**【事实】HTTP 面**：只有两个 router 加探针。

| 面 | 前缀 | 鉴权 |
|---|---|---|
| 内部 Run API | `/internal/v1` | `X-Skill-Agent-Token` + `X-Exec-Org-Id` / `X-Exec-User-Id` |
| Agent Tools MCP | `/internal/v1/agent-tools/mcp` | `X-Agent-Tool-Capability`（HMAC 短时能力令牌，`app/services/attempt_capability.py`） |
| 探针 | `/health*`、`/metrics` | 无 |

依据：`app/api/internal_runs.py`、`app/api/agent_tools_mcp.py`、`app/auth.py`、`app/main.py`。**agent 没有任何面向最终用户的公共 API，也不解 JWT。**

**【事实】模型所有权**：不存在 `app/models/` 目录；表定义在 `app/db_metadata.py` + `alembic/versions/`，schema `agent`。全部表：`runs`、`run_attempts`、`run_events`、`run_artifacts`、`run_approvals`、`run_sessions`、`run_steps`、`run_event_rejections`、`alembic_version`。

**【事实】** 检索 `Workflow|BPM|HumanTask|Timer|EventSubscription|RPA`（及放宽后的小写变体）在该工程无领域匹配，仅命中指标辅助函数 `observe_timer`。**agent 不持有任何编排模型。**

**【事实】执行链路**：不拉 outbox（该工程检索 `outbox` 无匹配）。backend POST `/internal/v1/runs` 入库为 `QUEUED`，`RunWorker` 以 `FOR UPDATE SKIP LOCKED` 认领（`app/services/worker.py`）。Hermes 调用在 `app/services/hermes_engine.py`：凭证经 backend mint → 探测 `/v1/capabilities` → `POST /v1/runs`（`Idempotency-Key = {run_id}:{attempt_id}:{generation}`）→ 消费 SSE events → 归一化为语义事件（`app/services/native_event_normalizer.py`）→ 写入 `agent.run_events`。调用方以 `GET /internal/v1/runs/{id}/events?after_seq=` **轮询**取事件；**agent 自身不对外提供 SSE**。

**【事实】Hermes gateway 地址来自凭证租约或 run snapshot，不是环境变量**。该工程唯一的 sibling base URL 是 `SKILL_AGENT_CENTRAL_BASE_URL`（指向 backend）。

**【事实】审批**：agent 没有 External Action 表、没有 permission 模块。审批靠 Run 状态 `WAITING_APPROVAL` + `run_approvals` + 回调 backend。`remote_agent` 工具调用一律先 `wait_approval`，不在调用当下执行副作用（`app/services/agent_tool_gateway.py`）；批准后 `source == "external"` 走 backend `.../external-execute`，否则本地 `execute_connector_run`（`app/services/connector_router.py`）。`WAITING_APPROVAL` 不接受 resume，必须走 approvals 端点。

**【事实】** 该工程源码中**没有**对 `nodeskclaw-acp`、`openclaw-channel-nodeskclaw`、`hermes-nodeskclaw-bridge` 的任何引用（多轮关键词检索均无匹配）。与 Hermes 的耦合纯粹是 HTTP 协议级。

### 2.4 nodeskclaw-knowledge —— 知识业务域 + 检索网关

**【事实】HTTP 面**：`app/main.py` 挂 `/api/v1`（`app/api/router.py`）与 `/api/v2`（`app/api/v2/router.py`）。多数 v2 业务 handler 内部检查 `KNOWLEDGE_API_V2_ENABLED`。

两层必须区分：

| 层 | 代表路径 | 鉴权依赖 |
|---|---|---|
| 面向 Knowledge UI 的业务 API | `/api/v1/knowledge-bases`、`/knowledge-sets`、`/source-files`、`/source-connectors`、`/ingestion-jobs`、`/retrieval`、`/retrieval-profiles`、`/chat`、`/citations`、`/evaluation`、`/dashboard`、`/audit`；`/api/v2/applications`、`/artifacts`、`/engineering`、`/knowledge-models`、`/quality`、`/translations` | `get_member_context`（backend JWT 换 Principal） |
| 面向 Agent / Automation 的网关 | `/api/v2/agent/tools/knowledge.*`（search / retrieve / get_document / get_evidence / get_structure / get_table）、`/api/v2/mcp/tools/{list,call}` | 同样是 `get_member_context`；`app/api/agent_tools.py` 文件头明确写 `KNOWLEDGE_SERVICE_TOKEN must not authorize this route` |
| 服务间证明 | `POST /api/v2/skill-run/auth-proofs` | `require_knowledge_service_token`（全仓**唯一**使用该依赖的端点，`app/api/v2/skill_run_auth.py`） |

**【事实】身份与 ACL 的权威是分离的**：

- 身份权威在 backend。knowledge 不解 JWT（检索 `jwt`、`decode.*token`、`PyJWT` 在 `app/` 下无命中）；`app/core/deps.py` 的 `get_member_context` 调 backend `GET /api/v1/auth/knowledge-context` 换取 `KnowledgePrincipal`。
- 对象授权权威在 knowledge 自己。四张 ACL 表 `knowledge_base_acl`、`knowledge_set_acl`、`source_file_acl`、`knowledge_application_acl`，评估逻辑在 `app/services/permission_service.py`：super admin 放行 → owner 放行 → subject 匹配（organization / department / role / member）→ deny 优先 → 更具体 subject 优先 → `manage` 覆盖非 read → 文件级回退 KB 级。`build_access_plan` 把 ACL 编译成 RAGFlow 检索切片（`full_access` / `filtered_access` / `no_access`）。

**【事实】检索后端**：RAGFlow。客户端 `app/integrations/ragflow/client.py`，运行时适配 `app/runtime/ragflow.py`（`runtime_type = "ragflow"`），配置项 `RAGFLOW_BASE_URL` / `RAGFLOW_API_KEY` / `RAGFLOW_TIMEOUT_SECONDS` / `RAGFLOW_BUILD_BATCH_SIZE` / `RAGFLOW_METADATA_PUSHDOWN_ENABLED`。KB 与 dataset 的绑定在 `KnowledgeBase.ragflow_dataset_id` + `knowledge_runtime_bindings`。其他外部依赖：LLM Proxy（Chat 补全）、DocuTranslate、MinerU、Ollama。

**【事实】后台 worker**：`app/workers/` 下 ingestion / build / connector / translation / reconciliation / maintenance 六个，均为本域内数据加工，不编排跨域流程。

**【事实】出站依赖**：只有 backend 两处 —— `fetch_knowledge_context`（换 Principal）与 `health_check`（就绪探针），均在 `app/integrations/nodeskclaw_backend/client.py`。

**【事实】** agent 与 task 都**不**直接调用 knowledge HTTP。`knowledge_refs` 在两者中都只是引用字段。真正打检索网关的是 knowledge 仓内的 Hermes 插件 `plugins/hermes-plugin-nodeskclaw-knowledge/client.py`（`POST /api/v2/agent/tools/knowledge.retrieve`）。

**【事实】契约目录**：`nodeskclaw-knowledge/contracts/` 仅 `frontend/v1.0.0`（契约名 `knowledge-frontend-contract`），生成器 `scripts/frontend_contract.py`，规范源 `scripts/frontend_contract_spec.py`，门禁 `tests/test_frontend_contract_v100.py`。

---

## 3. SOT 归属表

**【约束】** 每个概念只有一个工程是唯一事实来源。其他工程只能按 id 引用，不得持久化副本作为判断依据（缓存投影除外，且投影必须标注来源与新鲜度）。

| 概念 | SOT | 其他工程的合法姿势 |
|---|---|---|
| User / Organization / Membership / RBAC 角色 | backend | 按 id 引用；task 的 `autotask_user_cache` 是**带 TTL 的投影**，不是权威 |
| JWT 签发与校验密钥 | backend | task 共享 `JWT_SECRET` 仅为校验；knowledge 不解 JWT，换 Principal |
| Expert / Remote Expert Catalog | backend | 按 `agent_ref` / slug 引用 |
| Expert 授权结论（能不能调这个 Expert） | backend | agent 必须回源取授权，不得自行判断 |
| Runtime Placement（这个 Expert 跑在哪） | backend | agent 接受路由结果，不自行选址 |
| Scoped Execution Capability（本次执行可访问哪些资源） | backend | agent 按 capability 执行，不扩权 |
| IntegrationAccount / Grant / Connector 定义与绑定 | backend | task 只能调 backend 校验引用；agent 只能向 backend 要路由 |
| External Action 策略与执行账本 | backend | agent 只能请求 backend 代执行并记录 |
| Instance / Cluster / Deploy / Gene / Engine | backend | 不得在其他域建模 |
| Attachment / Artifact 的公共身份 | backend | agent 产出工件后由 backend 暴露公共下载身份 |
| 触发器 / 调度 / cron / webhook 入口 | task | 其他工程不得自建触发器 |
| 流程定义 / 流程实例 / 节点运行 | task | agent 不得感知流程拓扑 |
| 人工任务（Human Task / Human Action） | task | backend 只提供人的身份与权限 |
| RPA 作业与 Worker 租约 | task | — |
| 自动化重试 / 超时 / 并发策略 | task | agent 只负责单次执行内的技术重试 |
| ACP Session Runtime | agent | backend 不得持有 ACP session 到 Hermes 的映射 |
| Agent Run | agent | backend 只做投影与代理（`app/api/runs.py` 文件头自述为 auth proxy） |
| Attempt | agent | — |
| Run Event | agent | — |
| Run Terminal State | agent | backend 不得反向写执行态 |
| Agent Artifact（执行态） | agent | 公共下载身份归 backend，字节与元数据归 agent |
| Tool Execution | agent | — |
| Hermes runtime 绑定与会话 | agent | — |
| Hermes Native Run | Hermes | 三层 Run 语义不同、不互为镜像 |
| Knowledge Base / Set / File / Application | knowledge | 按 id 引用（`knowledge_refs`） |
| 知识对象 ACL | knowledge | backend 提供人的身份，不提供知识对象授权结论 |
| 检索结果与引用（Citation / Evidence） | knowledge | — |

**【约束】** Run 语义严格三层，Backend **不占一层**：

```text
task   : NodeRun（编排语义：这个流程节点成功了吗）
agent  : Run / Attempt（执行语义：这次执行怎么跑的）
Hermes : Native Run（引擎语义：模型侧实际执行）
```

禁止出现第四层 `Backend Run`。backend 当前的 `HermesTask` + `RunDispatchOutbox` 正是这第四层，已登记为 D-09。

---

## 4. 依赖方向与调用白名单

### 4.1 允许的调用通道（当前实际存在的全集）

**【约束】** 下表是白名单。**新增任何跨工程调用通道都必须先修订本表**，不得在 PRD 里直接开新通道。

| 源 | 目标 | 入口 | 鉴权 | 用途 |
|---|---|---|---|---|
| task | backend | `/api/v1/auth/me` | 用户 Bearer | 同步用户投影 |
| task | backend | `/api/v1/internal/v1/automation/remote-agent/*` | `X-Autotask-Internal-Token` | 校验集成账户引用、创建/查询/取消 Remote Agent run |
| backend | agent | `/internal/v1/runs*` | `X-Skill-Agent-Token` | 派发 run、拉取 run / events / result / artifacts、取消、恢复、审批 |
| agent | backend | `/api/v1/internal/v1/skill-agent/*` | `X-Skill-Agent-Token` | 凭证 mint、授权复核、远程工具目录、connector 路由、外部动作执行与关闭 |
| agent（edge） | backend | `/api/v1/internal/edge/*` | Ed25519 签名信封 | enroll / heartbeat / rotate / 拉取 job / 回传事件与工件 |
| backend | knowledge | `/api/v2/skill-run/auth-proofs` | `KNOWLEDGE_SERVICE_TOKEN` | 为 skill run 取知识集授权证明 |
| knowledge | backend | `/api/v1/auth/knowledge-context` | 用户 Bearer | 换取 `KnowledgePrincipal` |
| knowledge | backend | `/health` | 无 | 就绪探针 |
| Hermes runtime（插件） | knowledge | `/api/v2/agent/tools/knowledge.retrieve` | member Bearer | Agent 运行时检索 |
| `nodeskclaw-acp`（本地 adapter） | backend | `/api/v1/auth/account-login`、`/auth/refresh`、`/auth/me` | 无 / 用户 Bearer | adapter 登录与凭证刷新 |
| `nodeskclaw-acp`（本地 adapter） | backend | `/api/v1/remote-agent/runs*`、`/remote-agent/sessions/*`（含 SSE events、approvals decision、cancel） | 用户 Bearer（+ `X-Idempotency-Key`） | **Legacy 链路，见 D-09**：ACP 语义在此被转译为 Remote Agent REST |

### 4.2 禁止的方向

**【约束】**

- **backend 不得调用 task。** 当前事实已满足（backend 无 task HTTP 客户端）。backend 若需要自动化能力，必须由 task 主动来取，不得反向推送。
- **task 不得直连 agent。** 所有 Remote Agent 操作必须经 backend 内部 automation 面。当前事实已满足。
- **task 不得直连 knowledge。** `knowledge_refs` 只能原样转发给 backend，由 backend 换取授权证明。当前事实已满足。
- **agent 不得调用 task，也不得直连 knowledge。** agent 不感知流程，也不自行决定知识可见性。当前事实已满足。
- **knowledge 不得调用 task 或 agent。** knowledge 是被调用方。当前事实已满足。
- **不得出现环**。合法形状是：task → backend → agent，backend → knowledge，knowledge → backend（仅身份与探针）。`knowledge → backend → ...` 这条回边只允许停留在身份与健康检查，不得扩展为业务调用，否则会与 `backend → knowledge` 构成业务环。
- **backend → agent 只能是"移交一次已授权的执行"，不能是"持续控制该执行的生命周期"。** 移交（含取消的逐层传递）允许；backend 把 run 状态当作自己的权威来维护不允许。对应地，`agent → backend` 只能取授权与 capability，不得把 Run 状态写回 backend 作为权威。这两条是 D-09 收敛方向的落地判据。

### 4.3 公共 API 表面

**【约束】** 面向浏览器/桌面端的公共 API 表面按域划分，各域自持前缀，不得互相代理业务语义：

- backend：`/api/v1`、`/api/v1/admin`
- task：`/api/v1/autotask`
- knowledge：`/api/v1`、`/api/v2`（独立服务，不经 backend 转发）
- agent：**无公共表面**。agent 的用户可见投影由 backend `/runs`、`/remote-agent/runs` 提供。

**【约束】** backend 的 `/runs`、`/remote-agent/runs` 只能做鉴权代理与投影，不得在其中加入编排决策或流程状态机。

---

## 5. 每个工程的 MUST NOT

### 5.1 backend 不得成为

**【约束】**

- 不得成为流程引擎。不得新增流程定义、流程实例、节点运行、人工任务、触发器、cron、事件订阅类模型。
- 不得成为 Agent 执行引擎。不得直接调用 Hermes runtime 执行 run；执行必须经 agent。
- **不得成为 Run Control Plane。** 不得新增属于 backend 的 Run / Attempt / 执行事件模型，不得扩张现有 `HermesTask` / `RunDispatchOutbox` 的语义。
- **不得把 ACP 转译成另一套执行域模型。** backend 作为 ACP 公共入口，职责是鉴权、解析 Expert、选址、签发 capability，然后移交一次已授权的执行；不得把 ACP session / prompt / cancel / permission 重新编码成 backend 自有的 Run REST 再交给 agent。
- 不得持有 ACP session 到 Hermes 的映射关系。
- 不得成为知识检索引擎。不得直连 RAGFlow，不得自建 chunk / embedding / 检索逻辑。
- 不得持有知识对象 ACL 结论。只能回答"这个人是谁、属于哪个组织、什么角色"。
- 不得为了方便而在公共 API 里代理 task 的业务语义。

### 5.2 task 不得成为

**【约束】**

- 不得成为身份系统。不得新增登录、注册、发令牌、改密码端点；不得把 `autotask_user_cache` 当权威。
- 不得成为 Agent 执行引擎。不得直连 Hermes、不得持有 Agent Run 的事件流与工件字节。
- 不得成为知识系统。不得解析 `knowledge_refs` 的语义、不得判断知识可见性。
- 不得持有集成账户凭证。账户有效性必须问 backend。
- 不得成为平台资源管理器。不得建模 Instance / Cluster / Deploy / Gene。

### 5.3 agent 不得成为

**【约束】**

- 不得成为编排器。不得新增 Workflow / 节点 / 依赖边 / 流程级重试与超时策略模型。Runtime Owner 与 Automation Owner 是两件事。
- 不得成为触发器宿主。不得新增 cron / webhook / 事件订阅入口。
- 不得成为权限系统。授权结论必须向 backend 取（`authorizations/review`、`skill-run/revalidate`）；不得自行判断某人能否调用某个 Expert。
- 不得自行决定 Runtime 选址，不得超出 backend 下发的 capability 范围执行。
- 不得把 Run 状态写回 backend 作为权威。backend 侧的 run 视图只能是读出来的投影。
- 不得开放公共用户 API，不得解析用户 JWT。**注意**：未来落地 ACP Runtime Gateway 时，北向入口依然是机器到机器的内部面，ACP 的用户身份由 backend 在 ingress 处解析并以 capability 形式下发，agent 不解 JWT 这条约束不因 ACP 而放宽。
- 不得直连 knowledge 决定知识可见性。

### 5.4 knowledge 不得成为

**【约束】**

- 不得成为身份系统。不得解 JWT、不得签发用户令牌。
- 不得成为编排器。`app/workers/` 下的后台 worker 只能做本域数据加工，不得编排跨域流程、不得调用 agent 或 task。
- 不得成为 Agent 执行平面。检索网关只返回检索结果，不得代为执行工具或副作用。
- 不得把 `KNOWLEDGE_SERVICE_TOKEN` 的授权范围扩大到 agent tools 路由（`app/api/agent_tools.py` 已显式禁止）。

---

## 6. 跨域引用规则

### 6.1 按 id 引用，不按内容复制

**【约束】** 跨域引用一律使用稳定标识（`agent_ref`、`knowledge_refs`、`integration_account_refs`、`attachment_refs`、`remote_agent_run_id`）。禁止把对方域的业务字段复制进本域表作为判断依据。

允许的例外是**显式投影**，且必须满足三条：标注来源域、带新鲜度字段（如 `synced_at`）、权威判断仍回源。`autotask_user_cache`（`nodeskclaw-task/app/models/user_cache.py`）是符合该形态的唯一既有投影。

### 6.2 禁止跨库与跨 schema 访问

**【约束】**

- 四个工程的数据访问必须经各自的 ORM session，禁止任何跨库连接、跨库查询、外部库视图。
- **特别点名**：agent 与 backend 默认部署在同一个 PostgreSQL 实例，agent 使用 schema `agent`。这使得跨 schema JOIN 在物理上可行。**禁止**：backend 不得直接查 `agent.*` 任何表，agent 不得直接查 `public.*` 任何表。两者之间只走第 4.1 节的 HTTP 通道。
- 禁止一个工程的 Alembic 迁移触碰另一个工程的表或 `alembic_version`。

### 6.3 状态不得双写

**【约束】** 一个状态只有一个写入方。

- Agent Run 的真实状态由 agent 写。backend 的 run 投影是读出来的，不得由 backend 直接改写执行态。
- `AutomationInvocation` 的状态由 task 写，来源是对 backend 的查询结果映射（`app/services/remote_agent_dispatch_service.py`）。backend 不得反向写 task 的状态。
- `IndexState` / `KnowledgeArtifact` 状态由 knowledge 写，其他域只读。

### 6.4 枚举不得复制

**【约束】** 跨域传递状态时，接收方要么直接存字符串并标注"外部状态原值"，要么在本域做显式映射并把映射表集中在一个文件。**禁止**在接收方复制一份对方的枚举定义。

当前符合该约束的做法：task 的 `remote_agent_dispatch_service.py` 把远端状态（`IN_PROGRESS`、`AWAITING_APPROVAL`、`COMPLETED` …）映射为本域 invocation 状态，映射集中在一处。

---

## 7. 横切职责边界

**【约束】** 以下五件事最容易越界，归属固定如下。

| 关注点 | 归属 | 规则 |
|---|---|---|
| 重试 | **双层，不得混淆** | **执行层重试**归 agent：单次 run 内的 Hermes 调用失败、网络抖动、attempt 重开，由 agent 负责（`run_attempts` + generation）。**编排层重试**归 task：整个自动化调用的失败重投，由 task 负责（`remote_agent_dispatch_jobs` + 退避序列）。agent 不得实现"整个自动化重跑"，task 不得实现"Hermes 调用级重试"。 |
| 幂等 | 调用方生成，被调用方校验 | task → backend 用 `AutomationInvocation.idempotency_key`；backend → agent 用 `run_id` / `dispatch_id` / `idempotency_key`（`nodeskclaw-agent/app/api/internal_runs.py`）；agent → Hermes 用 `{run_id}:{attempt_id}:{generation}`。**约束**：新增跨域调用必须带幂等键，禁止依赖"调一次就不会重"。 |
| 取消 | 自上而下传递，不得跳层 | task 取消 invocation → 调 backend cancel → backend 转发 agent `/internal/v1/runs/{id}/cancel` → agent 终止执行并可取消 edge job。禁止 task 直接取消 agent run。 |
| 工件 | 执行态归 agent，公共身份归 backend | agent 写 `agent.run_artifacts` 并落存储（`SKILL_AGENT_STORAGE_DRIVER`）；对外下载身份与权限由 backend 暴露。task 的 `artifacts` 表是自动化域自己的产物（RPA Worker 上传），与 agent 工件是两套，不得互相冒用。 |
| 审批 | 决策人归 backend，等待态归 agent，流程级人工任务归 task | agent 的 `WAITING_APPROVAL` + `run_approvals` 是**执行内审批**（工具调用是否放行）；task 的 `human_actions` 是**流程内人工任务**（人去做一件事）。两者语义不同，禁止合并、禁止用一方实现另一方。 |

---

## 8. 已识别架构偏差登记

**【约束】** 偏差是技术债登记，不是许可。PRD 不得在偏差上继续堆功能；触碰到偏差相关代码时，方向必须是收敛而非扩张。

### D-01：backend 内含一套完整的 Workflow 编排模型 —— 已决定 DEPRECATED 冻结

**结论（已决策）**：`app/modules/task_orchestrator/` 整个模块及其 `/api/v1/task-orchestrator` 对外面标记为 **DEPRECATED，并即刻冻结**。不迁移、不续建、不删除。

**证据**：`nodeskclaw-backend/app/modules/task_orchestrator/`，表前缀 `to_`。

- 模型：`WorkflowTemplate` / `WorkflowInstance` / `WorkflowNode` / `WorkflowEvent` / `HumanIntervention` / `CheckpointSnapshot` / `ExecutorBinding`（`models/`）
- 引擎：LangGraph（`langgraph/state.py`、`reducers.py`、`commands.py`、`compiled_graph.py`、`nodes.py`）
- 枚举（`enums.py`）：`WorkflowStatus`、`NodeStatus`、`NodeType`（`role_task` / `system_task` / `human_review` / `gateway_task`）、`ExecutorType`（`openclaw` / `dify` / `deerflow` / `human_review` / `system`）、`InterventionType`、`SourceType`（含 `paperclip_issue`）、`EdgeConditionType`、`CallbackMode`
- 执行器适配：`adapters/base.py` 定义 `submit` / `poll` / `cancel` / `normalize_output` 接口；`adapters/openclaw_adapter.py` 文件 docstring 自述 **"stub implementation for Phase 1"**，`submit` 返回 `oc_stub:{workflow_node_id}`，`poll` 直接返回 `completed`，三个方法全是 TODO
- HTTP 面：`/api/v1/task-orchestrator`（`app/api/router.py`）与 admin 侧复挂
- 该模块在 `nodeskclaw-backend/app/core/config.py` 中**没有**开关项（检索 `TASK_ORCHESTRATOR` / `task_orchestrator` 无命中）

**影响**：这是全仓**第三套**自动化抽象（前两套都在 task，见第 2.2 节），且位置违反第 5.1 节 —— backend 不得成为流程引擎。它的 executor 适配层是空壳，意味着它不是一条生产编排路径，而是一个未完成的平行实现。更危险的是它与 task 的 `workflow_templates` 同名不同库，极易在 PRD 里被误当成同一个东西。

**冻结范围（FROZEN）**：下列内容一律不得变更，只接受"使现有行为不崩"的安全性修复（如依赖升级导致的 import 失败、安全补丁）：

- `app/modules/task_orchestrator/**` 全部模型、枚举、常量、服务、仓储、LangGraph 图、执行器适配
- `app/api/task_orchestrator.py`、`app/api/task_orchestrator_admin.py`
- `to_*` 全部表结构与其 Alembic 迁移 `b2c3d4e5f6a7_add_task_orchestrator_tables.py`

**禁止事项**：

- **禁止**在该模块下新增节点类型、执行器类型、状态值、表、端点。
- **禁止**把 `openclaw_adapter.py` 等 stub 适配器补完。它们是冻结面的一部分，补完等于续建这条平行实现。
- **禁止**任何 PRD 把新的自动化需求落到这个模块。自动化需求一律落 `nodeskclaw-task`。
- **禁止**新增对该模块的调用方 —— 包括 backend 内部其他 service、其他工程、前端。
- **禁止**把 `to_*` 表与 task 的 `workflow_*` 表在文档或代码里混称。提及时必须写全限定名（`backend/to_workflow_templates` vs `task/workflow_templates`）。

**不删除的理由**：`to_*` 表已随迁移 `b2c3d4e5f6a7` 建立，可能已有环境写入过数据；删除属于破坏性变更，需要独立的数据处置决策。冻结先行，退场另议。

**退场前置条件**（满足后才讨论删除，本文档不预设时间点）：

1. 确认所有部署环境的 `to_*` 表无业务数据，或数据已有明确归档去向。
2. 确认 `/api/v1/task-orchestrator` 在所有环境均无外部调用方（当前已知：`nodeskclaw-portal` 无任何引用）。
3. task 域已覆盖该模块原本设想的能力（human_review 节点、executor 绑定、checkpoint 恢复）。

**代码侧标记（已落地）**：

- `app/modules/task_orchestrator/__init__.py` 模块 docstring 写明 DEPRECATED / FROZEN 与本节锚点。
- `app/api/task_orchestrator.py` 与 `app/api/task_orchestrator_admin.py` 的 `APIRouter` 均带 `deprecated=True`，OpenAPI 文档中全部 18 个端点（用户面 9 + admin 面 9）显示为废弃。该标记只影响 OpenAPI 元数据，不改变任何运行时行为。

### D-02：task 内两套自动化抽象并行

**证据**：见第 2.2 节表格。套 A（`workflow_*` + `automation_tasks` + `rpa_runs`）与套 B（`agent_automations` + `automation_invocations`）各有独立 API、独立状态表达、独立调度器，仅通过 `TaskSuccessorJob.target_kind` 单向衔接。

**影响**：同一个"自动化"概念有两种建模；用户要先选对入口才能用对功能。

**处置原则**：新增自动化能力必须明确声明落在哪一套，并在 PRD 中写明为什么不落另一套。禁止新增第三套。禁止在套 A 与套 B 之间增加新的隐式衔接点。

### D-03：套 B 的状态缺少类型化定义

**证据**：套 A 的状态在 `app/models/enums.py` 有 `StrEnum` 与集中转移表 `app/services/task_state_machine.py`；套 B 的合法状态散落在 `app/services/agent_automation_service.py` 与 `remote_agent_dispatch_service.py` 的字符串集合里，模型层默认值（`automation_invocations.status` 默认 `RECEIVED`）与服务层创建值（`PENDING`）还不一致。

**处置原则**：触碰套 B 状态的改动必须同时补齐枚举与转移约束，不得继续新增裸字符串状态。

### D-04：task 内两套授权模型并行

**证据**：`app/services/permission_service.py`（`PortalAccessGrant` + `PortalPermission`）与 `app/services/automation_permission.py`（角色 → `automation:view|manage|run`）互不相通。

**处置原则**：新增自动化相关权限点必须明确归入其中一套并说明理由；禁止新增第三套授权模型。

### D-05：knowledge v1 / v2 双套 KB 与 Set CRUD 并存

**证据**：v1 `app/api/knowledge_bases.py`、`app/api/knowledge_sets.py`；v2 `app/api/v2/assets.py` 提供另一套 `/api/v2/knowledge-bases`、`/api/v2/knowledge-sets`。

**处置原则**：新功能只落 v2；v1 只接受缺陷修复。禁止在两套之间产生行为差异。

### D-06：Application ACL 有表无 REST

**证据**：`knowledge_application_acl` 表与 `ApplicationPermission` 枚举存在，创建应用时插入 owner `manage` 行（`app/services/knowledge_application_service.py`），但检索 `applications/.*/acl` 无 HTTP 端点。

**影响**：应用级共享只能由 owner 自己用，无法授权他人 —— 这是功能缺口而非仅架构问题。

**处置原则**：涉及应用共享的 PRD 必须先补这组端点，不得用 KB/Set ACL 绕过。

### D-07：agent 与 backend 物理同库

**证据**：`nodeskclaw-agent/.env.example` 默认库名与 backend 一致，仅靠 `SKILL_AGENT_SCHEMA=agent` 隔离。

**处置原则**：严格执行第 6.2 节。任何改动不得引入跨 schema 查询。

### D-08：`nodeskclaw-acp` 在 Target 拓扑中的位置未决

**证据**：`nodeskclaw-acp` 是被 ACP 客户端 spawn 的本地 stdio adapter（`app/cli.py` 的 `serve`、`app/jsonrpc.py` 读 stdin 写 stdout，工程内无 `uvicorn` / `FastAPI` / `EXPOSE` / Dockerfile / 数据库）。session 状态纯进程内存（`app/session_registry.py` 的 `SessionRegistry._sessions`），README 写明重启不存活。契约 `contracts/acp-v1-adapter/v1.1.0/manifest.json` 的 `provider = nodeskclaw-acp`、`consumer = smc-copilot/apps/work`。

**影响**：Target 拓扑中 ACP 入口画在 backend，而当前 ACP 协议实际终止在这个本地进程。两者的衔接方式决定了该组件是保留为纯传输 shim 还是退场。

**处置原则**：该组件**不持有任何 SOT**，这一点现在就成立且不得改变——禁止在 adapter 内新增持久化状态、禁止让它成为 session 权威。去留需要独立 Architecture Decision，本文档不预设结论。

### D-09：backend 当前是 Remote Agent Run Control Plane（迁移债务）

**证据**：`app/services/remote_agent_provider_service.py` 创建 `HermesTask` + `RunDispatchOutbox`；`app/services/hermes_skill/run_dispatch_outbox_service.py` 把 run 投递给 agent；`app/api/remote_agent_runs.py`、`app/api/remote_agent_sessions.py`、`app/api/runs.py` 对外暴露 Remote Agent REST + SSE。完整当前链路：

```text
smc-copilot/apps/work（或 Zed）
  → spawn nodeskclaw-acp（ACP v1 在此终止）
    → backend /api/v1/remote-agent/*（ACP 被转译为 Remote Agent REST Run）
      → backend HermesTask + RunDispatchOutbox
        → agent /internal/v1/runs
          → Hermes
```

**影响**：这条链让同一次执行在 backend 与 agent 各有一份 Run 概念，构成第 3 节禁止的"第四层 Run"。它违反本文档对 backend 的 MUST NOT（不得成为 Run Control Plane），也是 `nodeskclaw-agent` 存在价值被削弱的原因——ACP 语义在 backend 就被转译掉，agent 退化为转发层。

**处置原则**：

- 这是 **current migration debt，不是 Target**。禁止任何 PRD 以"现有链路就是这样"为理由在 backend 侧扩张 Run / Attempt / 执行事件语义。
- **禁止**新增 backend 侧的 Remote Agent Run 字段、状态值、事件类型。
- 现有公开面（`/api/v1/remote-agent/*`）出于兼容性保留，只接受缺陷修复。
- 收敛方向已定：ACP Runtime 语义移入 agent，backend 收敛为 ACP ingress + 授权 + 路由 + capability。但**迁移方案、废弃节奏、`RunDispatchOutbox` 拆除方式均未决**，需要独立 Architecture Decision。
- 注意区分：Task → Agent 的网络路径是否经过 backend proxy 是 transport / security 部署问题，**不是**领域问题。流量过 backend 可以接受；backend 在该路径上持有执行域模型不可以接受。

---

## 9. PRD 实施前检查清单

**【约束】** 任何 PRD / Plan 在进入实施前必须逐条过。任一条不通过即为越界，必须先改设计。

**定位**

- [ ] 这个需求的核心概念，在第 3 节 SOT 表里归属哪个工程？写出来。
- [ ] 要改动的代码，是否全部落在该工程内？如果跨了工程，每个工程各承担什么、为什么不能收敛到一个工程？
- [ ] 是否触碰了第 8 节的任何偏差（尤其 D-01、D-02、D-09）？如果是，改动方向是收敛还是扩张？

**Runtime / ACP 专项**（涉及 Remote Expert、Remote Agent、ACP、Hermes 的改动必答）

- [ ] 这个改动是在回答"能不能 / 去哪里 / 带什么 scope"（backend），还是"怎么跑 / 到哪一步 / 产出什么"（agent）？写出来。
- [ ] 有没有在 backend 侧新增或扩张 Run / Attempt / 执行事件语义？（禁止，见 D-09）
- [ ] 有没有把 ACP 的 session / prompt / cancel / permission 在 backend 转译成另一套执行域模型？（禁止）
- [ ] 同一次执行会不会产生两份 Run 权威？三层 Run（task NodeRun / agent Run / Hermes Native Run）各自语义是否清晰且不互为镜像？
- [ ] 如果改动涉及 `nodeskclaw-acp`：有没有在 adapter 内新增持久化状态或让它成为 session 权威？（禁止，见 D-08）

**模型**

- [ ] 新增的表/模型，是否属于本工程的 SOT 范围？有没有在复制其他域已有的概念？
- [ ] 是否新增了触发器 / cron / 流程节点 / 人工任务 / Agent Run 类模型？如果是，确认落在了正确的域（task / task / task / task / agent）。
- [ ] 跨域引用是否只用了 id？有没有复制对方的业务字段作为判断依据？
- [ ] 有没有引入跨库或跨 schema 访问？
- [ ] 新增/修改模型是否同时生成了 Alembic 迁移（本工程的）？

**API**

- [ ] 新增端点挂在本工程的公共前缀下（backend `/api/v1`、task `/api/v1/autotask`、knowledge `/api/v1` 或 `/api/v2`），还是内部面？
- [ ] 如果是 agent 的改动：是否确认没有新增公共用户 API、没有解析用户 JWT？
- [ ] 如果需要新的跨工程调用通道：是否已在第 4.1 节白名单中？不在就必须先修订本文档。
- [ ] 新增跨域调用是否带了幂等键？

**横切**

- [ ] 重试是执行层还是编排层？实现是否落在对应的域（第 7 节）？
- [ ] 取消是否自上而下逐层传递，没有跳层直连？
- [ ] 审批是"执行内审批"还是"流程内人工任务"？有没有用一方实现另一方？
- [ ] 状态是否只有一个写入方？
- [ ] 有没有复制对方的状态枚举定义？

**鉴权**

- [ ] 身份判断是否回到 backend？
- [ ] 知识对象可见性判断是否回到 knowledge 的 ACL？
- [ ] 服务间令牌的授权范围有没有被扩大（特别是 `KNOWLEDGE_SERVICE_TOKEN` 不得进 agent tools 路由）？

---

## 10. 本文档的维护规则

**【约束】**

- 本文档的【事实】章节与代码同生命周期。扫描结论与代码不符时，先更新本文档再继续实施，不得在实施中"顺手"带过。
- 【约束】章节的变更属于架构决策，必须独立评审，不得与功能实施混在同一个 commit。
- 新增偏差必须登记到第 8 节并给出处置原则，禁止只在 PRD 里备注。
- 本文档状态为 DRAFT 期间，不得被引用为"已生效的治理依据"；仅作为实施参照与评审输入。
