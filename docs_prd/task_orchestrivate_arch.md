# Task Orchestrator Cursor 执行版

**范围：NoDeskClaw 新增独立模块，实现 `Task Orchestrator Facade -> LangGraph Orchestrator Service`，并完成对 PaperClip、OpenClaw、Dify、DeerFlow、Human Review 的编排接入。**

## 0. 落地基线

### 0.1 既定约束

* 后端主框架继续走 **Python + PostgreSQL + async API**，前端保持 React，数据权限在 API 层裁剪。
* NoDeskClaw 是 **FastAPI + SQLAlchemy + PostgreSQL 异步平台后端**，并且已有 `api_router` / `admin_router`、RBAC、组织上下文、K8s 生命周期管理、FeatureGate 等平台基础设施。
* NoDeskClaw 的 schema 变更约定是：**不引入 Alembic**，迁移以内联编号方式维护在 `main.py` lifespan 中，且必须幂等；数据库必须走 PostgreSQL；全量 DB 访问走 SQLAlchemy async session。
* PaperClip 是 **Control Plane**，负责任务/issue、atomic checkout、预算、审计、heartbeat 治理，不运行 Agent。Issue 状态机与 checkout 语义已有明确定义。
* LangGraph 是 **有状态工作流协调基础设施**，关键能力是 `StateGraph.compile(checkpointer=...)`、checkpoint、interrupt/resume、thread_id 驱动恢复，不应拿来承载平台控制面。
* DeerFlow 的可借鉴点是 **Harness/App 分层**、LangGraph Server 与 Gateway 分离、per-thread isolated runtime，而不是整套 super-agent 产品边界。

---

# 1. 本期交付目标

## 1.1 要交付什么

1. NoDeskClaw 新增 `task_orchestrator` 独立模块
2. 提供 `Task Orchestrator Facade` API
3. 提供 `LangGraph Orchestrator Service` 编排内核
4. 提供 4 类 Adapter：

   * OpenClaw Executor Adapter
   * Dify Executor Adapter
   * DeerFlow Executor Adapter
   * Human Review Adapter
5. 提供与 PaperClip 的任务下发/回写契约
6. 提供 SQLAlchemy 表结构与幂等迁移方案
7. 输出到可直接让 Cursor 拆分实现的文件级代码骨架

## 1.2 不做什么

1. 不改 NoDeskClaw `deploy_service.py`、`corridor_router.py`、`gene_service.py`
2. 不改 NoDeskClaw Factory 抽象轴
3. 不改 PaperClip issue 状态机 / checkout 内核
4. 不改 OpenClaw / DeerFlow / Dify 内核
5. 不新增第二套 org / RBAC / agent lifecycle

---

# 2. 代码落位原则

## 2.1 NoDeskClaw 内只新增独立模块

NoDeskClaw 当前低风险扩展区域是：在 `api/` 下新增 router，在 `services/` 或独立模块目录下新增 service 文件；高风险区域是 `BaseModel`、FeatureGate、BFS 路由、K8s Manifest、Deploy Steps。
因此 Task Orchestrator 采用：

* **新增目录**
* **新增 router**
* **新增 models / services / workers**
* **复用现有 `deps.py`、`get_db`、`require_org_role`、用户认证依赖**
* **不改既有部署/协作主链路**

## 2.2 编排层与平台层分离

借鉴 DeerFlow 的 Harness/App 单向依赖原则：

* Facade/API 层：NoDeskClaw 内
* Graph Runtime 层：Orchestrator Core
* Executor Adapter 层：Orchestrator 内部
* Platform 生命周期 / RBAC / Workspace：仍在 NoDeskClaw 平台层

---

# 3. 目标目录结构

## 3.1 NoDeskClaw 后端目录改造

```text
nodeskclaw-backend/
  app/
    api/
      v1/
        task_orchestrator.py
        task_orchestrator_admin.py
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
        migrations/
          __init__.py
          migration_032_task_orchestrator.py
```

## 3.2 PaperClip 侧建议新增目录

```text
paperclip/
  server/
    src/
      clients/
        task-orchestrator-client.ts
      routes/
        task-orchestrations.ts
      services/
        task-orchestration-sync.ts
  packages/
    shared/
      src/
        api.ts
        types/
          task-orchestrator.ts
```

---

# 4. NoDeskClaw 文件级代码骨架

---

## 4.1 API Router

### `app/api/v1/task_orchestrator.py`

职责：

* 创建流程实例
* 查询实例详情
* 查询 graph / timeline
* pause / resume / cancel
* 提交人工介入
* 触发节点重试
* 处理执行器回调

代码骨架：

```python
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.modules.task_orchestrator.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowCreateResponse,
    WorkflowDetailResponse,
    WorkflowTimelineResponse,
    WorkflowActionResponse,
    RetryNodeRequest,
)
from app.modules.task_orchestrator.schemas.intervention import (
    InterventionCreateRequest,
    InterventionResponse,
)
from app.modules.task_orchestrator.services.facade_service import TaskOrchestratorFacadeService

router = APIRouter(prefix="/api/v1/task-orchestrator", tags=["task-orchestrator"])

@router.post("/workflow-instances", response_model=WorkflowCreateResponse)
async def create_workflow_instance(
    body: WorkflowCreateRequest,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    service = TaskOrchestratorFacadeService(db, user)
    return await service.create_workflow_instance(body)

@router.get("/workflow-instances/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow_instance(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    service = TaskOrchestratorFacadeService(db, user)
    return await service.get_workflow_instance(workflow_id)

@router.get("/workflow-instances/{workflow_id}/timeline", response_model=WorkflowTimelineResponse)
async def get_workflow_timeline(...): ...

@router.post("/workflow-instances/{workflow_id}/pause", response_model=WorkflowActionResponse)
async def pause_workflow(...): ...

@router.post("/workflow-instances/{workflow_id}/resume", response_model=WorkflowActionResponse)
async def resume_workflow(...): ...

@router.post("/workflow-instances/{workflow_id}/cancel", response_model=WorkflowActionResponse)
async def cancel_workflow(...): ...

@router.post("/workflow-instances/{workflow_id}/interventions", response_model=InterventionResponse)
async def create_intervention(...): ...

@router.post("/workflow-instances/{workflow_id}/retry-node", response_model=WorkflowActionResponse)
async def retry_node(...): ...

@router.post("/callbacks/{executor_type}/{workflow_id}", response_model=WorkflowActionResponse)
async def handle_executor_callback(...): ...
```

---

### `app/api/v1/task_orchestrator_admin.py`

职责：

* 模板管理
* 运行规则管理
* 运营调试接口
* 手工恢复、补偿、强制完成

> 建议挂在 admin 权限路由下，复用 `require_org_role("admin")`。NoDeskClaw 已有 org 级 RBAC dependency 工厂。

---

## 4.2 Schemas

### `schemas/template.py`

```python
from pydantic import BaseModel, Field
from typing import Any, Literal

class WorkflowNodeTemplate(BaseModel):
    node_key: str
    node_type: Literal["role_task", "system_task", "human_review", "gateway_task"]
    role_code: str | None = None
    executor_type: Literal["openclaw", "dify", "deerflow", "human_review", "system"]
    timeout_sec: int = 1800
    retry_max_attempts: int = 2
    required_capabilities: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)

class WorkflowEdgeTemplate(BaseModel):
    from_node: str
    to_node: str
    condition_type: Literal["always", "success", "failure", "manual_gate", "expr"] = "always"
    condition_expr: dict[str, Any] | None = None

class WorkflowTemplateCreateRequest(BaseModel):
    template_key: str
    name: str
    version: int = 1
    source_type: Literal["paperclip_issue", "portal", "api", "event"]
    definition: dict[str, Any]

class WorkflowTemplateResponse(BaseModel):
    id: str
    template_key: str
    version: int
    status: str
```

### `schemas/workflow.py`

```python
class WorkflowCreateRequest(BaseModel):
    template_key: str
    source_type: str
    source_ref_id: str
    org_id: str
    workspace_id: str | None = None
    input_payload: dict[str, Any]
    options: dict[str, Any] = Field(default_factory=dict)

class WorkflowCreateResponse(BaseModel):
    workflow_instance_id: str
    thread_id: str
    status: str

class WorkflowNodeDTO(BaseModel):
    id: str
    node_key: str
    status: str
    executor_type: str
    assigned_agent_id: str | None = None
    external_run_id: str | None = None

class WorkflowDetailResponse(BaseModel):
    id: str
    template_key: str
    status: str
    thread_id: str
    nodes: list[WorkflowNodeDTO]
    current_node_keys: list[str]
```

---

## 4.3 SQLAlchemy Models

> 约束：NoDeskClaw 的所有新表必须继承同一个 `BaseModel`，保留 `id / created_at / updated_at / deleted_at`，采用 soft-delete，不得物理删除。

### `models/workflow_template.py`

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, JSON, Boolean, Text
from app.models.base import BaseModel

class WorkflowTemplate(BaseModel):
    __tablename__ = "to_workflow_templates"

    template_key: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="draft")
    definition_json: Mapped[dict] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
```

### `models/workflow_instance.py`

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, JSON, DateTime, Text
from app.models.base import BaseModel

class WorkflowInstance(BaseModel):
    __tablename__ = "to_workflow_instances"

    template_id: Mapped[str] = mapped_column(String(36), index=True)
    template_key: Mapped[str] = mapped_column(String(128), index=True)
    thread_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    source_ref_id: Mapped[str] = mapped_column(String(128), index=True)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    trigger_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    input_payload: Mapped[dict] = mapped_column(JSON)
    runtime_state: Mapped[dict] = mapped_column(JSON, default=dict)
    current_node_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_trace: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checkpoint_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### `models/workflow_node.py`

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, JSON, DateTime, Text
from app.models.base import BaseModel

class WorkflowNode(BaseModel):
    __tablename__ = "to_workflow_nodes"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True)
    node_key: Mapped[str] = mapped_column(String(128), index=True)
    node_type: Mapped[str] = mapped_column(String(64))
    role_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    executor_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    assigned_agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    external_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    timeout_sec: Mapped[int] = mapped_column(Integer, default=1800)
    timeout_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
```

### `models/workflow_event.py`

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, JSON, DateTime
from app.models.base import BaseModel

class WorkflowEvent(BaseModel):
    __tablename__ = "to_workflow_events"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True)
    workflow_node_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_by_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
```

### `models/human_intervention.py`

```python
class HumanIntervention(BaseModel):
    __tablename__ = "to_human_interventions"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True)
    workflow_node_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    intervention_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

### `models/checkpoint_snapshot.py`

```python
class CheckpointSnapshot(BaseModel):
    __tablename__ = "to_checkpoints"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True)
    checkpoint_ns: Mapped[str] = mapped_column(String(128), index=True)
    checkpoint_id: Mapped[str] = mapped_column(String(128), index=True)
    checkpoint_data: Mapped[dict] = mapped_column(JSON)
    channel_versions: Mapped[dict] = mapped_column(JSON, default=dict)
```

### `models/executor_binding.py`

```python
class ExecutorBinding(BaseModel):
    __tablename__ = "to_executor_bindings"

    workflow_instance_id: Mapped[str] = mapped_column(String(36), index=True)
    workflow_node_id: Mapped[str] = mapped_column(String(36), index=True)
    executor_type: Mapped[str] = mapped_column(String(64), index=True)
    assigned_agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    external_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    callback_mode: Mapped[str] = mapped_column(String(32), default="poll")
    callback_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_polled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

---

# 5. SQL 表结构 DDL（供 Cursor 生成 migration）

> NoDeskClaw 迁移必须幂等、内联、不使用 Alembic。

```sql
CREATE TABLE IF NOT EXISTS to_workflow_templates (
  id varchar(36) PRIMARY KEY,
  template_key varchar(128) NOT NULL,
  name varchar(255) NOT NULL,
  version integer NOT NULL DEFAULT 1,
  source_type varchar(64) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'draft',
  definition_json jsonb NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  description text NULL,
  created_by varchar(36) NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_to_workflow_templates_key_version_alive
ON to_workflow_templates(template_key, version)
WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS to_workflow_instances (
  id varchar(36) PRIMARY KEY,
  template_id varchar(36) NOT NULL,
  template_key varchar(128) NOT NULL,
  thread_id varchar(128) NOT NULL,
  source_type varchar(64) NOT NULL,
  source_ref_id varchar(128) NOT NULL,
  org_id varchar(36) NOT NULL,
  workspace_id varchar(36) NULL,
  trigger_user_id varchar(36) NULL,
  status varchar(32) NOT NULL,
  input_payload jsonb NOT NULL,
  runtime_state jsonb NOT NULL DEFAULT '{}'::jsonb,
  current_node_keys jsonb NOT NULL DEFAULT '[]'::jsonb,
  source_trace jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz NULL,
  completed_at timestamptz NULL,
  last_checkpoint_id varchar(128) NULL,
  error_summary text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_to_workflow_instances_thread_alive
ON to_workflow_instances(thread_id)
WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS to_workflow_nodes (
  id varchar(36) PRIMARY KEY,
  workflow_instance_id varchar(36) NOT NULL,
  node_key varchar(128) NOT NULL,
  node_type varchar(64) NOT NULL,
  role_code varchar(64) NULL,
  executor_type varchar(64) NOT NULL,
  status varchar(32) NOT NULL,
  assigned_agent_id varchar(36) NULL,
  external_run_id varchar(128) NULL,
  retry_count integer NOT NULL DEFAULT 0,
  timeout_sec integer NOT NULL DEFAULT 1800,
  timeout_at timestamptz NULL,
  input_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  output_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  started_at timestamptz NULL,
  completed_at timestamptz NULL,
  blocked_reason text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL
);

CREATE INDEX IF NOT EXISTS idx_to_workflow_nodes_instance_alive
ON to_workflow_nodes(workflow_instance_id)
WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS to_workflow_events (
  id varchar(36) PRIMARY KEY,
  workflow_instance_id varchar(36) NOT NULL,
  workflow_node_id varchar(36) NULL,
  event_type varchar(64) NOT NULL,
  event_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  trace_id varchar(128) NULL,
  created_by_type varchar(32) NULL,
  created_by_id varchar(36) NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL
);

CREATE TABLE IF NOT EXISTS to_human_interventions (
  id varchar(36) PRIMARY KEY,
  workflow_instance_id varchar(36) NOT NULL,
  workflow_node_id varchar(36) NULL,
  intervention_type varchar(64) NOT NULL,
  status varchar(32) NOT NULL,
  requested_by varchar(36) NULL,
  request_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  response_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  resolved_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL
);

CREATE TABLE IF NOT EXISTS to_checkpoints (
  id varchar(36) PRIMARY KEY,
  workflow_instance_id varchar(36) NOT NULL,
  checkpoint_ns varchar(128) NOT NULL,
  checkpoint_id varchar(128) NOT NULL,
  checkpoint_data jsonb NOT NULL,
  channel_versions jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL
);

CREATE TABLE IF NOT EXISTS to_executor_bindings (
  id varchar(36) PRIMARY KEY,
  workflow_instance_id varchar(36) NOT NULL,
  workflow_node_id varchar(36) NOT NULL,
  executor_type varchar(64) NOT NULL,
  assigned_agent_id varchar(36) NULL,
  external_run_id varchar(128) NULL,
  callback_mode varchar(32) NOT NULL DEFAULT 'poll',
  callback_url varchar(512) NULL,
  last_polled_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz NULL
);
```

---

# 6. LangGraph 编排内核代码骨架

## 6.1 State

### `langgraph/state.py`

```python
from typing_extensions import TypedDict, Annotated
import operator

def merge_dict(left: dict, right: dict) -> dict:
    out = dict(left or {})
    out.update(right or {})
    return out

class WorkflowState(TypedDict):
    workflow_instance_id: str
    thread_id: str
    template_key: str
    source_ref: dict
    input_payload: dict
    node_statuses: Annotated[dict[str, str], merge_dict]
    node_results: Annotated[dict[str, dict], merge_dict]
    node_errors: Annotated[dict[str, dict], merge_dict]
    pending_human_actions: Annotated[list[dict], operator.add]
    audit_events: Annotated[list[dict], operator.add]
```

> 这里必须显式使用 reducer 聚合并行节点写入。LangGraph 的 `LastValue` 默认单步单写，多节点同 key 写入会触发 `INVALID_CONCURRENT_GRAPH_UPDATE`。

---

## 6.2 Graph Builder

### `services/graph_builder.py`

```python
from langgraph.graph import StateGraph, START, END
from app.modules.task_orchestrator.langgraph.state import WorkflowState
from app.modules.task_orchestrator.langgraph.nodes import (
    dispatch_node,
    wait_human_node,
    finalize_node,
)

class WorkflowGraphBuilder:
    def __init__(self, template: dict, checkpoint_saver):
        self.template = template
        self.checkpoint_saver = checkpoint_saver

    def build(self):
        builder = StateGraph(WorkflowState)

        for node in self.template["nodes"]:
            node_key = node["node_key"]
            builder.add_node(node_key, dispatch_node)

        builder.add_node("wait_human", wait_human_node)
        builder.add_node("finalize", finalize_node)

        entry = self.template["entry_node"]
        builder.add_edge(START, entry)

        for edge in self.template["edges"]:
            builder.add_edge(edge["from"], edge["to"])

        builder.add_edge(self.template["terminal_node"], "finalize")
        builder.add_edge("finalize", END)

        return builder.compile(checkpointer=self.checkpoint_saver)
```

> Graph 编译必须带 checkpointer；否则无法恢复 interrupt/resume。LangGraph 明确要求中断恢复依赖 checkpointer 与 `thread_id`。

---

## 6.3 Nodes

### `langgraph/nodes.py`

```python
from langgraph.types import interrupt, Command

async def dispatch_node(state: dict, config):
    # 读取当前 node_key / executor_type
    # 调 routing_service -> adapter.submit
    # 返回状态更新
    return {
        "node_statuses": {"current": "running"},
        "audit_events": [{"type": "node_dispatched"}],
    }

async def wait_human_node(state: dict, config):
    human_payload = {
        "type": "approval_required",
        "workflow_instance_id": state["workflow_instance_id"],
    }
    human_input = interrupt(human_payload)
    return {
        "pending_human_actions": [],
        "node_results": {"human_review": human_input},
        "audit_events": [{"type": "human_resumed"}],
    }

async def finalize_node(state: dict, config):
    return {
        "audit_events": [{"type": "workflow_completed"}],
    }
```

> `interrupt()` + `Command(resume=...)` 是 HITL 核心原语。LangGraph 会在节点开头重放执行，因此节点副作用必须幂等。

---

## 6.4 Checkpoint Service

### `services/checkpoint_service.py`

```python
from langgraph.checkpoint.base import BaseCheckpointSaver

class PostgresCheckpointSaver(BaseCheckpointSaver):
    def __init__(self, repo):
        self.repo = repo

    async def aget_tuple(self, config):
        thread_id = config["configurable"]["thread_id"]
        return await self.repo.get_latest_by_thread_id(thread_id)

    async def aput(self, config, checkpoint, metadata, new_versions):
        thread_id = config["configurable"]["thread_id"]
        await self.repo.save_checkpoint(
            thread_id=thread_id,
            checkpoint_id=checkpoint["id"],
            checkpoint_data=checkpoint,
            channel_versions=checkpoint.get("channel_versions", {}),
            metadata=metadata,
        )
        return config
```

> `BaseCheckpointSaver` 的主键就是 `thread_id`；checkpoint 结构包含 `channel_values / channel_versions / versions_seen`。

---

# 7. Services 层代码骨架

## 7.1 Facade Service

### `services/facade_service.py`

```python
class TaskOrchestratorFacadeService:
    def __init__(self, db, user):
        self.db = db
        self.user = user

    async def create_workflow_instance(self, body):
        # 1. org/workspace 权限校验
        # 2. 模板读取
        # 3. workflow_instance 持久化
        # 4. 调 runtime_service.start()
        ...

    async def get_workflow_instance(self, workflow_id):
        ...

    async def pause_workflow(self, workflow_id):
        ...

    async def resume_workflow(self, workflow_id):
        ...

    async def cancel_workflow(self, workflow_id):
        ...

    async def create_intervention(self, workflow_id, body):
        ...
```

## 7.2 Workflow Service

### `services/workflow_service.py`

```python
class WorkflowService:
    async def create_instance(self, template, source_payload, org_id, workspace_id, user_id): ...
    async def mark_running(self, workflow_id): ...
    async def mark_waiting_human(self, workflow_id): ...
    async def mark_blocked(self, workflow_id, reason): ...
    async def mark_completed(self, workflow_id): ...
```

## 7.3 Runtime Service

### `services/runtime_service.py`

```python
class RuntimeService:
    async def start(self, workflow_instance): ...
    async def resume(self, workflow_instance, resume_value: dict): ...
    async def retry_node(self, workflow_instance, node_key: str): ...
    async def cancel(self, workflow_instance): ...
```

## 7.4 Routing Service

### `services/routing_service.py`

```python
class RoutingService:
    async def resolve_executor(self, workflow_node, org_id, workspace_id):
        # 1. 模板 executor 显式指定
        # 2. role_code 默认绑定
        # 3. capability 匹配
        # 4. fallback 到 human_review
        ...
```

## 7.5 SLA Service

### `services/sla_service.py`

```python
class SLAService:
    async def scan_timeout_nodes(self): ...
    async def schedule_retry(self, workflow_node): ...
    async def escalate(self, workflow_node, reason: str): ...
```

## 7.6 PaperClip Sync Service

### `services/paperclip_sync_service.py`

```python
class PaperclipSyncService:
    async def sync_workflow_created(self, workflow_instance): ...
    async def sync_node_blocked(self, workflow_node, reason: str): ...
    async def sync_workflow_completed(self, workflow_instance): ...
    async def sync_comment(self, issue_id: str, message: str): ...
```

---

# 8. Executor Adapter 代码骨架

---

## 8.1 Base Adapter

### `adapters/base.py`

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel

class ExecutorSubmitContext(BaseModel):
    workflow_instance_id: str
    workflow_node_id: str
    thread_id: str
    role_code: str | None = None
    assigned_agent_id: str | None = None
    input_payload: dict
    callback_url: str | None = None
    timeout_sec: int = 1800
    trace_id: str | None = None

class ExecutorSubmitResult(BaseModel):
    accepted: bool
    external_run_id: str | None = None
    callback_mode: str = "poll"
    raw: dict = {}

class ExecutorPollResult(BaseModel):
    status: str
    result: dict = {}
    error: dict = {}

class BaseExecutorAdapter(ABC):
    @abstractmethod
    async def submit(self, ctx: ExecutorSubmitContext) -> ExecutorSubmitResult: ...
    @abstractmethod
    async def poll(self, external_run_id: str) -> ExecutorPollResult: ...
    @abstractmethod
    async def cancel(self, external_run_id: str) -> None: ...
    @abstractmethod
    def normalize_output(self, raw: dict) -> dict: ...
```

---

## 8.2 OpenClaw Adapter

### `adapters/openclaw_adapter.py`

```python
class OpenClawExecutorAdapter(BaseExecutorAdapter):
    def __init__(self, openclaw_client, projection_service):
        self.client = openclaw_client
        self.projection_service = projection_service

    async def submit(self, ctx):
        # 1. 从 projection_service 取可用 agent 实例
        # 2. 选择 assigned_agent_id
        # 3. 调 OpenClaw 已有入口
        # 4. 落 external_run_id
        return ExecutorSubmitResult(
            accepted=True,
            external_run_id="oc_run_xxx",
            callback_mode="poll",
            raw={},
        )

    async def poll(self, external_run_id):
        ...

    async def cancel(self, external_run_id):
        ...

    def normalize_output(self, raw):
        return {
            "summary": raw.get("summary"),
            "structured": raw.get("structured", {}),
        }
```

> 本期默认 **不改 OpenClaw 插件/运行时接口**。只做外部 Adapter。OpenClaw 的 session lane、tool policy、gateway/plugin contract 属于高风险内核，不应侵入。

---

## 8.3 Dify Adapter

### `adapters/dify_adapter.py`

```python
class DifyExecutorAdapter(BaseExecutorAdapter):
    async def submit(self, ctx):
        # POST workflow run
        ...
    async def poll(self, external_run_id):
        ...
    async def cancel(self, external_run_id):
        ...
    def normalize_output(self, raw):
        ...
```

---

## 8.4 DeerFlow Adapter

### `adapters/deerflow_adapter.py`

```python
class DeerFlowExecutorAdapter(BaseExecutorAdapter):
    async def submit(self, ctx):
        # 调 DeerFlow Gateway API 或 client
        ...
    async def poll(self, external_run_id):
        ...
    async def cancel(self, external_run_id):
        ...
    def normalize_output(self, raw):
        ...
```

> 本期默认 **不改 DeerFlow Harness**。只消费现有 LangGraph Server / Gateway API 或 client 契约。DeerFlow 的核心边界是 Harness/App 分层，不应被平台侧反向侵入。

---

## 8.5 Human Review Adapter

### `adapters/human_review_adapter.py`

```python
class HumanReviewAdapter(BaseExecutorAdapter):
    async def submit(self, ctx):
        return ExecutorSubmitResult(
            accepted=True,
            external_run_id=f"human:{ctx.workflow_node_id}",
            callback_mode="interrupt",
            raw={},
        )

    async def poll(self, external_run_id):
        return ExecutorPollResult(status="waiting_human")

    async def cancel(self, external_run_id):
        return None

    def normalize_output(self, raw):
        return raw
```

---

# 9. Worker 代码骨架

## 9.1 `workers/timeout_worker.py`

```python
class TimeoutWorker:
    async def run_forever(self):
        while True:
            await self.scan()
            await asyncio.sleep(15)

    async def scan(self):
        # 找 running 且 timeout_at < now() 的 node
        # -> retry or escalate
        ...
```

## 9.2 `workers/escalation_worker.py`

```python
class EscalationWorker:
    async def run_forever(self):
        ...
```

## 9.3 `workers/callback_worker.py`

```python
class CallbackWorker:
    async def consume(self):
        # 消费 executor 回调或统一 webhook queue
        ...
```

## 9.4 `workers/reconciliation_worker.py`

```python
class ReconciliationWorker:
    async def reconcile_external_runs(self):
        # 对 poll 模式执行器做状态对账
        ...
```

> NoDeskClaw 已大量使用 `asyncio.create_task` 进行后台任务，并要求 task 引用被持有，防止 GC。新 worker 也应保持同样模式。

---

# 10. NoDeskClaw 入口集成点

## 10.1 `app/main.py`

新增：

* import task_orchestrator router
* 注册 worker 启动逻辑
* 执行 migration_032_task_orchestrator

伪代码：

```python
from app.api.v1.task_orchestrator import router as task_orchestrator_router

api_router.include_router(task_orchestrator_router)

# lifespan 里
await run_task_orchestrator_migration(engine)
start_task_orchestrator_workers()
```

---

# 11. PaperClip 对接：API 契约

---

## 11.1 PaperClip -> NoDeskClaw Task Orchestrator Facade

### 创建编排实例

`POST /api/v1/task-orchestrator/workflow-instances`

请求：

```json
{
  "template_key": "pre_order_validation_v1",
  "source_type": "paperclip_issue",
  "source_ref_id": "iss_123",
  "org_id": "org_001",
  "workspace_id": "ws_001",
  "input_payload": {
    "company_id": "cmp_001",
    "issue_id": "iss_123",
    "run_id": "run_abc",
    "customer_id": "cust_001",
    "payment_ratio": 0.3
  },
  "options": {
    "priority": "high",
    "trace_id": "trace_001"
  }
}
```

响应：

```json
{
  "workflow_instance_id": "wf_001",
  "thread_id": "wf_001",
  "status": "created"
}
```

---

## 11.2 查询编排实例

`GET /api/v1/task-orchestrator/workflow-instances/{workflow_instance_id}`

响应：

```json
{
  "id": "wf_001",
  "template_key": "pre_order_validation_v1",
  "status": "running",
  "thread_id": "wf_001",
  "source_type": "paperclip_issue",
  "source_ref_id": "iss_123",
  "current_node_keys": ["inventory_and_procurement_check", "credit_risk_review"],
  "nodes": [
    {
      "id": "node_01",
      "node_key": "collect_order_info",
      "status": "completed",
      "executor_type": "openclaw",
      "assigned_agent_id": "agent_cs_001",
      "external_run_id": "oc_run_01"
    }
  ]
}
```

---

## 11.3 Timeline

`GET /api/v1/task-orchestrator/workflow-instances/{workflow_instance_id}/timeline`

---

## 11.4 人工介入

`POST /api/v1/task-orchestrator/workflow-instances/{workflow_instance_id}/interventions`

请求：

```json
{
  "workflow_node_id": "node_03",
  "intervention_type": "approve",
  "request_payload": {
    "decision": "approved",
    "comment": "允许继续执行"
  }
}
```

---

## 11.5 节点重试

`POST /api/v1/task-orchestrator/workflow-instances/{workflow_instance_id}/retry-node`

请求：

```json
{
  "node_key": "inventory_and_procurement_check",
  "reason": "supplier api recovered"
}
```

---

# 12. Task Orchestrator -> PaperClip 回写契约

PaperClip 继续做 Control Plane，不变更 issue 内核。其强约束是：

* entity 必须 company-scoped
* issue checkout 是单 SQL 原子更新
* `in_progress` 只能单 assignee
* agent 通过 heartbeat 使用 issue/checkout/comment/subtask 推进任务

因此 Orchestrator 对 PaperClip 只做以下回写：

## 12.1 更新 issue 状态

`PATCH /api/issues/{issueId}`

```json
{
  "status": "blocked"
}
```

Header：

```http
X-Paperclip-Run-Id: run_abc
```

## 12.2 追加 comment

`POST /api/issues/{issueId}/comments`

```json
{
  "body": "AI采购节点失败：供应商 ETA 晚于客户要求交期，建议人工审批或替代料研究。"
}
```

## 12.3 创建子任务

`POST /api/companies/{companyId}/issues`

```json
{
  "title": "采购例外研究",
  "parentIssueId": "iss_123",
  "status": "todo",
  "assigneeAgentId": "agent_procurement_001",
  "metadata": {
    "orchestratorRef": {
      "workflowInstanceId": "wf_001",
      "workflowNodeKey": "inventory_and_procurement_check"
    }
  }
}
```

## 12.4 PaperClip 侧新增接口

为了让 Cursor 可落地，建议新增：

### `server/src/routes/task-orchestrations.ts`

* `POST /api/task-orchestrations`
* `GET /api/task-orchestrations/:id`
* `GET /api/task-orchestrations/:id/timeline`
* `POST /api/task-orchestrations/:id/events`

### `packages/shared/src/types/task-orchestrator.ts`

```ts
export type TaskOrchestrationRef = {
  workflowInstanceId: string;
  threadId: string;
  sourceType: "paperclip_issue";
  sourceRefId: string;
};

export type TaskOrchestrationEvent = {
  type:
    | "workflow_created"
    | "workflow_running"
    | "node_dispatched"
    | "node_blocked"
    | "waiting_human"
    | "workflow_completed"
    | "workflow_failed";
  workflowInstanceId: string;
  issueId: string;
  nodeKey?: string;
  payload?: Record<string, unknown>;
  traceId?: string;
};
```

### `server/src/clients/task-orchestrator-client.ts`

```ts
export class TaskOrchestratorClient {
  async createWorkflowInstance(input: CreateWorkflowInstanceInput) {}
  async getWorkflowInstance(id: string) {}
  async getWorkflowTimeline(id: string) {}
  async publishEvent(id: string, event: TaskOrchestrationEvent) {}
}
```

---

# 13. PaperClip 代码改动清单

## 13.1 必加文件

```text
paperclip/
  server/src/clients/task-orchestrator-client.ts
  server/src/routes/task-orchestrations.ts
  server/src/services/task-orchestration-sync.ts
  packages/shared/src/types/task-orchestrator.ts
```

## 13.2 可选轻量改动

* issue metadata 增加 `orchestratorRef`
* issue detail UI 增加 orchestration timeline tab

## 13.3 禁止改动

* `checkout` 原子语义
* issue 状态机
* heartbeat 核心循环
* adapter registry fallback 逻辑

PaperClip 当前已经明确：V1 不做自动自愈编排器，因此 Orchestrator 是外挂接入，不应反向污染其控制平面边界。

---

# 14. 迁移脚本骨架

### `migrations/migration_032_task_orchestrator.py`

```python
from sqlalchemy import text

async def run(conn):
    statements = [
        """CREATE TABLE IF NOT EXISTS to_workflow_templates (...);""",
        """CREATE TABLE IF NOT EXISTS to_workflow_instances (...);""",
        """CREATE TABLE IF NOT EXISTS to_workflow_nodes (...);""",
        """CREATE TABLE IF NOT EXISTS to_workflow_events (...);""",
        """CREATE TABLE IF NOT EXISTS to_human_interventions (...);""",
        """CREATE TABLE IF NOT EXISTS to_checkpoints (...);""",
        """CREATE TABLE IF NOT EXISTS to_executor_bindings (...);""",
        """CREATE UNIQUE INDEX IF NOT EXISTS uq_to_workflow_templates_key_version_alive ...;""",
    ]
    for sql in statements:
        await conn.execute(text(sql))
```

---

# 15. Cursor 实施顺序

## Phase 1：最小闭环

1. 新增 models + migrations
2. 新增 template CRUD
3. 新增 workflow create/query API
4. 新增 LangGraph state + graph_builder
5. 新增 HumanReviewAdapter
6. 新增 OpenClawAdapter 占位
7. 跑通 create -> waiting_human -> resume -> complete

## Phase 2：控制平面对接

1. 新增 PaperClip client
2. 新增 PaperClip route + shared types
3. 接入 issue 创建 / comment / 状态回写
4. 在 workflow_event 中记录 trace_id / paperclip refs

## Phase 3：执行器扩展

1. DifyAdapter
2. DeerFlowAdapter
3. poll/callback worker
4. routing_service capability match
5. executor_binding 持久化

## Phase 4：运营能力

1. timeout_worker
2. escalation_worker
3. timeline API
4. intervention UI contract
5. replay / restore API

---

# 16. 必须单独确认的点

以下如果要做，不能默认推进：

## 16.1 OpenClaw 是否新增专用回调接口

默认：**不改**
当前只通过 Adapter 轮询/既有入口接入。OpenClaw 的 gateway/plugin/runtime contract 属于高风险区。

## 16.2 DeerFlow 是否新增专用 orchestration endpoint

默认：**不改**
先消费既有 Gateway/LangGraph 接口。Harness 不做定制修改。

## 16.3 Dify 是否要求结构化输出模板统一

默认：**由 Adapter normalize**
若要求各 workflow 节点标准化 schema，需单独确认 Dify workflow 输出格式改造。

## 16.4 NoDeskClaw 是否将 Task Orchestrator 作为 EE Feature

默认：**否**
先按 CE 通用独立模块落地；若后续需要 `require_feature()`，再上 feature registry。

---

# 17. 最终收口

这版 Cursor 执行版的关键不是“多写点代码骨架”，而是把边界锁死：

* **NoDeskClaw**：平台宿主，新增独立 `task_orchestrator` 模块，不动 deploy/corridor/gene 主链路。
* **LangGraph Orchestrator Service**：编排内核，负责 graph、checkpoint、interrupt/resume、SLA。
* **PaperClip**：Control Plane，只负责 issue 治理、atomic checkout、comment/subtask、审计，不接管执行。
* **OpenClaw / Dify / DeerFlow / Human**：统一作为执行器 Adapter，默认零侵入接入。

下一步最合适的是继续收敛成 **“Cursor 文件创建顺序 + 每个文件首版代码内容”**，直接到可复制生成的程度。
