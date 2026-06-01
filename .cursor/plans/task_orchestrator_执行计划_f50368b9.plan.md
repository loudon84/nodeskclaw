---
name: Task Orchestrator 执行计划
overview: 基于 PRD 在 NoDeskClaw 后端新增 task_orchestrator 独立模块（含 LangGraph 编排内核、4 类 Executor Adapter、PaperClip 同步契约），分 4 个 Phase 交付。PaperClip 侧变更作为独立子计划。
todos:
  - id: phase1-infra
    content: Phase 1.1：基础设施准备 — 新增 langgraph 依赖、创建 modules/task_orchestrator 目录骨架、constants/enums/errors
    status: pending
  - id: phase1-models
    content: Phase 1.2：SQLAlchemy Models（7 张表）+ Alembic 迁移文件
    status: pending
  - id: phase1-schemas
    content: Phase 1.3：Pydantic Schemas（template/workflow/intervention/adapters）
    status: pending
  - id: phase1-repos
    content: Phase 1.4：Repositories（template_repo/workflow_repo/event_repo/checkpoint_repo）
    status: pending
  - id: phase1-langgraph
    content: Phase 1.5：LangGraph 编排内核（state/reducers/nodes/commands/compiled_graph）
    status: pending
  - id: phase1-services
    content: Phase 1.6：核心 Services（facade/template/workflow/runtime/graph_builder/checkpoint/routing）
    status: pending
  - id: phase1-adapters
    content: Phase 1.7：Adapters 最小集（base + human_review + openclaw stub）
    status: pending
  - id: phase1-router
    content: Phase 1.8：API Router + 在 router.py 和 main.py 中注册
    status: pending
  - id: phase2-sync
    content: Phase 2：PaperClip 对接 — paperclip_sync_service + callback_service + paperclip schemas
    status: pending
  - id: phase3-executors
    content: Phase 3：执行器扩展 — dify_adapter + deerflow_adapter + callback_worker + reconciliation_worker + projection_service
    status: pending
  - id: phase4-ops
    content: Phase 4：运营能力 — timeout_worker + escalation_worker + sla_service + intervention_service + timeline/replay API
    status: pending
  - id: paperclip-subplan
    content: PaperClip 子计划：生成独立规格文档供 PaperClip 团队执行（client/routes/services/types）
    status: pending
isProject: false
---

# Task Orchestrator 执行计划

## PRD 与代码库分歧适配

在将 PRD 映射到实际代码库时，发现以下分歧并作出适配决策：

- **目录模式**：PRD 要求 `app/modules/task_orchestrator/`，项目当前无 `modules/` 目录。**决策：按 PRD 新建 `modules/`**，因 task_orchestrator 包含 7 个子目录（models/services/schemas/adapters/workers/langgraph/repositories），散装到现有 `app/models/`、`app/services/` 会严重污染现有结构。
- **迁移方式**：PRD 写"不引入 Alembic"，但项目实际已在用 Alembic（`alembic/versions/` 下 18 个迁移，`main.py` lifespan 调 `alembic upgrade head`）。**决策：沿用 Alembic**，生成标准 revision 文件。
- **路由目录**：PRD 写 `app/api/v1/task_orchestrator.py`，但项目无 `app/api/v1/` 子目录，所有路由直接在 `app/api/` 下。**决策：路由文件放 `app/api/task_orchestrator.py`**，在 `app/api/router.py` 中注册。
- **前端技术栈**：PRD 提到"前端保持 React"，实际项目前端是 Vue 3。本期纯后端，无影响。
- **LangGraph 依赖**：`pyproject.toml` 中尚未引入 `langgraph`，需新增。

## 前端表现变化

本次改动无前端表现变化。全部为后端新增模块，API 契约为 PaperClip 和未来前端消费。

---

## 目标目录结构

```text
nodeskclaw-backend/
  app/
    api/
      task_orchestrator.py              # 用户 API router
      task_orchestrator_admin.py        # Admin API router
    modules/
      task_orchestrator/
        __init__.py
        constants.py
        enums.py
        errors.py
        schemas/
          __init__.py
          common.py
          template.py
          workflow.py
          intervention.py
          paperclip.py
          adapters.py
        models/
          __init__.py
          workflow_template.py
          workflow_instance.py
          workflow_node.py
          workflow_event.py
          human_intervention.py
          checkpoint_snapshot.py
          executor_binding.py
        repositories/
          __init__.py
          template_repo.py
          workflow_repo.py
          event_repo.py
          checkpoint_repo.py
        services/
          __init__.py
          facade_service.py
          template_service.py
          workflow_service.py
          runtime_service.py
          graph_builder.py
          routing_service.py
          checkpoint_service.py
          intervention_service.py
          sla_service.py
          paperclip_sync_service.py
          callback_service.py
          projection_service.py
        adapters/
          __init__.py
          base.py
          openclaw_adapter.py
          dify_adapter.py
          deerflow_adapter.py
          human_review_adapter.py
        workers/
          __init__.py
          timeout_worker.py
          escalation_worker.py
          callback_worker.py
          reconciliation_worker.py
        langgraph/
          __init__.py
          state.py
          reducers.py
          nodes.py
          commands.py
          compiled_graph.py
  alembic/
    versions/
      xxxx_add_task_orchestrator_tables.py   # Alembic 迁移
```

---

## Phase 1：最小闭环

目标：跑通 create -> dispatch -> waiting_human -> resume -> complete 完整链路。

### 1.1 基础设施准备

- **新增 LangGraph 依赖**：在 [nodeskclaw-backend/pyproject.toml](nodeskclaw-backend/pyproject.toml) 的 `[project.dependencies]` 中加入 `langgraph`
- **创建 `app/modules/` 目录**及 `task_orchestrator/` 完整子目录骨架（所有 `__init__.py`）
- **创建 `app/modules/task_orchestrator/constants.py`**：表前缀 `to_`、默认超时、状态常量
- **创建 `app/modules/task_orchestrator/enums.py`**：`WorkflowStatus`、`NodeStatus`、`ExecutorType`、`InterventionType`、`InterventionStatus` 等枚举
- **创建 `app/modules/task_orchestrator/errors.py`**：模块专用异常类

### 1.2 SQLAlchemy Models + Alembic 迁移

创建 7 个 Model，全部继承 `app.models.base.BaseModel`，遵循 soft-delete + Partial Unique Index 约定。表名统一 `to_` 前缀。

- `models/workflow_template.py` — `to_workflow_templates` 表
- `models/workflow_instance.py` — `to_workflow_instances` 表
- `models/workflow_node.py` — `to_workflow_nodes` 表
- `models/workflow_event.py` — `to_workflow_events` 表
- `models/human_intervention.py` — `to_human_interventions` 表
- `models/checkpoint_snapshot.py` — `to_checkpoints` 表
- `models/executor_binding.py` — `to_executor_bindings` 表

生成 Alembic 迁移：`alembic revision --autogenerate -m "add_task_orchestrator_tables"`

注意：需要在 `alembic/env.py` 的 `target_metadata` 中确保能扫描到 `app.modules.task_orchestrator.models`（通过在 models `__init__.py` 中统一导入）。

### 1.3 Schemas

- `schemas/common.py` — 通用分页、响应包装
- `schemas/template.py` — `WorkflowNodeTemplate`、`WorkflowEdgeTemplate`、`WorkflowTemplateCreateRequest`、`WorkflowTemplateResponse`
- `schemas/workflow.py` — `WorkflowCreateRequest`、`WorkflowCreateResponse`、`WorkflowDetailResponse`、`WorkflowNodeDTO`、`WorkflowTimelineResponse`、`WorkflowActionResponse`、`RetryNodeRequest`
- `schemas/intervention.py` — `InterventionCreateRequest`、`InterventionResponse`
- `schemas/adapters.py` — `ExecutorSubmitContext`、`ExecutorSubmitResult`、`ExecutorPollResult`

### 1.4 Repositories

- `repositories/template_repo.py` — 模板 CRUD（`get_by_key_version`、`list_active`、`create`、`update_status`）
- `repositories/workflow_repo.py` — 实例 CRUD + 节点批量操作（`create_instance`、`get_with_nodes`、`update_status`、`update_node_status`）
- `repositories/event_repo.py` — 事件追加 + timeline 查询
- `repositories/checkpoint_repo.py` — checkpoint 读写（供 `PostgresCheckpointSaver` 使用）

### 1.5 LangGraph 编排内核

- `langgraph/state.py` — `WorkflowState` TypedDict，带 `Annotated` reducer（`merge_dict` 合并 `node_statuses`/`node_results`，`operator.add` 追加 `audit_events`）
- `langgraph/reducers.py` — 自定义 reducer 函数
- `langgraph/nodes.py` — `dispatch_node`（调 routing_service -> adapter.submit）、`wait_human_node`（`interrupt()` 阻塞）、`finalize_node`
- `langgraph/commands.py` — `Command(resume=...)` 封装
- `langgraph/compiled_graph.py` — 预编译 graph 缓存

### 1.6 核心 Services

- `services/facade_service.py` — `TaskOrchestratorFacadeService`：统一入口（create/get/pause/resume/cancel/retry/intervention）
- `services/template_service.py` — 模板 CRUD 逻辑
- `services/workflow_service.py` — 实例生命周期状态机
- `services/runtime_service.py` — 调用 `graph_builder.build()` 执行 graph，管理 `thread_id` 驱动的 checkpoint 恢复
- `services/graph_builder.py` — `WorkflowGraphBuilder`：从模板 definition 构建 `StateGraph`，编译时注入 `PostgresCheckpointSaver`
- `services/checkpoint_service.py` — `PostgresCheckpointSaver`（继承 `langgraph.checkpoint.base.BaseCheckpointSaver`），通过 `checkpoint_repo` 实现 `aget_tuple` / `aput`
- `services/routing_service.py` — 执行器路由决策（模板显式指定 > role_code 默认绑定 > capability 匹配 > fallback human_review）

### 1.7 Adapters（Phase 1 最小集）

- `adapters/base.py` — `BaseExecutorAdapter` ABC（`submit` / `poll` / `cancel` / `normalize_output`）+ `ExecutorSubmitContext` / `ExecutorSubmitResult` / `ExecutorPollResult`
- `adapters/human_review_adapter.py` — `HumanReviewAdapter`（submit 返回 `callback_mode="interrupt"`，poll 返回 `waiting_human`）
- `adapters/openclaw_adapter.py` — `OpenClawExecutorAdapter`（Phase 1 为占位实现，stub submit/poll）

### 1.8 API Router + 注册

- **`app/api/task_orchestrator.py`**：用户级 API（创建实例、查询实例/timeline、pause/resume/cancel、提交人工介入、retry-node、executor callback）
- **`app/api/task_orchestrator_admin.py`**：管理级 API（模板 CRUD、运营调试、手工恢复/补偿/强制完成）
- **在 [app/api/router.py](nodeskclaw-backend/app/api/router.py) 中注册**：
  - `api_router.include_router(task_orch_router, prefix="/task-orchestrator", tags=["任务编排"])`
  - `admin_router.include_router(task_orch_admin_router, prefix="/task-orchestrator", tags=["Admin - 任务编排"], dependencies=[Depends(require_org_role("admin"))])`
- **在 [app/main.py](nodeskclaw-backend/app/main.py) lifespan 中**：导入 task_orchestrator models 以确保 Alembic metadata 注册

### 1.9 验证目标

跑通链路：`POST /api/v1/task-orchestrator/workflow-instances` -> graph 执行 -> `wait_human_node` 中断 -> `POST .../interventions` 恢复 -> `finalize_node` -> 实例状态 `completed`

---

## Phase 2：控制平面对接（PaperClip Sync）

### 2.1 NoDeskClaw 侧

- `services/paperclip_sync_service.py` — `PaperclipSyncService`：
  - `sync_workflow_created()` — 创建编排后回写 PaperClip issue 状态
  - `sync_node_blocked()` — 节点阻塞时追加 comment + 创建子任务
  - `sync_workflow_completed()` — 完成时回写 issue 状态
  - `sync_comment()` — 追加评论
- `schemas/paperclip.py` — PaperClip 回写 payload 类型定义
- `services/callback_service.py` — 处理执行器回调，更新节点状态并触发 PaperClip 同步
- 在 `langgraph/nodes.py` 的 `dispatch_node` 和 `finalize_node` 中注入 PaperClip 同步调用

### 2.2 PaperClip 侧（独立子计划，见下方）

---

## Phase 3：执行器扩展

- `adapters/dify_adapter.py` — `DifyExecutorAdapter`（POST workflow run、poll status、cancel）
- `adapters/deerflow_adapter.py` — `DeerFlowExecutorAdapter`（调 DeerFlow Gateway API / LangGraph Server）
- `workers/callback_worker.py` — 消费执行器 webhook 回调
- `workers/reconciliation_worker.py` — 对 poll 模式执行器做状态对账
- `services/routing_service.py` 扩展 — capability 匹配逻辑
- `services/projection_service.py` — 可用 agent 实例投影查询（供 OpenClaw Adapter 选择 assigned_agent）

Worker 启动方式：在 `main.py` lifespan 中通过 `asyncio.create_task` 启动，保持 task 引用防 GC（与现有 `HealthChecker`、`ScheduleRunner` 模式一致）。

---

## Phase 4：运营能力

- `workers/timeout_worker.py` — 每 15s 扫描 running 且 `timeout_at < now()` 的节点，触发 retry 或 escalate
- `workers/escalation_worker.py` — 升级处理（通知、转人工）
- `services/sla_service.py` — SLA 扫描 + retry 调度 + 升级
- `services/intervention_service.py` — 人工介入完整生命周期管理
- Timeline API 完善 — `GET /api/v1/task-orchestrator/workflow-instances/{id}/timeline`
- Replay/Restore API — 从 checkpoint 恢复运行

---

## PaperClip 侧独立子计划

> PaperClip 不在本仓库中。以下为 PaperClip 团队的实施规格，需在 PaperClip 仓库独立执行。

### 目标

让 PaperClip 能：
1. 向 NoDeskClaw Task Orchestrator 下发编排任务
2. 接收编排过程中的状态同步事件
3. 在 issue detail 中展示编排 timeline

### 必加文件

```text
paperclip/
  server/src/
    clients/task-orchestrator-client.ts
    routes/task-orchestrations.ts
    services/task-orchestration-sync.ts
  packages/shared/src/
    types/task-orchestrator.ts
    api.ts  (追加 TaskOrchestrator 相关类型)
```

### `packages/shared/src/types/task-orchestrator.ts`

定义共享类型：`TaskOrchestrationRef`、`TaskOrchestrationEvent`（事件类型：`workflow_created` / `workflow_running` / `node_dispatched` / `node_blocked` / `waiting_human` / `workflow_completed` / `workflow_failed`）

### `server/src/clients/task-orchestrator-client.ts`

HTTP 客户端 `TaskOrchestratorClient`：
- `createWorkflowInstance(input)` — POST `/api/v1/task-orchestrator/workflow-instances`
- `getWorkflowInstance(id)` — GET `.../workflow-instances/{id}`
- `getWorkflowTimeline(id)` — GET `.../workflow-instances/{id}/timeline`
- `publishEvent(id, event)` — POST `.../workflow-instances/{id}/events`

### `server/src/routes/task-orchestrations.ts`

PaperClip 新增路由：
- `POST /api/task-orchestrations` — 创建编排（内部调 `TaskOrchestratorClient.createWorkflowInstance`）
- `GET /api/task-orchestrations/:id` — 查询编排
- `GET /api/task-orchestrations/:id/timeline` — 查询 timeline
- `POST /api/task-orchestrations/:id/events` — 接收 NoDeskClaw 回写的状态事件

### `server/src/services/task-orchestration-sync.ts`

事件同步服务：
- 接收 `TaskOrchestrationEvent` 后更新 issue 状态、追加 comment
- 映射关系：`node_blocked` -> issue status `blocked` + comment、`workflow_completed` -> issue status `done`

### 可选轻量改动

- issue metadata 增加 `orchestratorRef` 字段（`{ workflowInstanceId, threadId }`）
- issue detail UI 增加 orchestration timeline tab

### 禁止改动

- `checkout` 原子语义
- issue 状态机核心
- heartbeat 核心循环
- adapter registry fallback 逻辑
