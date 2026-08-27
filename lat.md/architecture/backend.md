# Backend Architecture

`nodeskclaw-backend` 是 FastAPI 中枢：认证、组织治理、实例编排、工作区协作、基因分发、Hermes/MCP 网关、Skill Run 投影与审计。

技术栈：Python 3.12、SQLAlchemy asyncio、PostgreSQL、Alembic、kubernetes-asyncio、JWT。设计文档入口 `docs/backend/index.md`；改码定位用 `.cursor/context/backend-codemap.md`。Skill 执行内核见 [[decisions/skill-platform-execution]]（`nodeskclaw-agent`）。

## Dual API Prefix

同一套路由处理函数挂在 `/api/v1`（Portal）与 `/api/v1/admin`（管理端）；成员表分离。

管理端校验 `admin_memberships`，Portal 校验 `org_memberships`。详见 [[decisions/dual-api-prefix]]。

## Auth And Tenancy

鉴权依赖集中在 `app/core/deps.py`；业务层仍须强制 org / workspace / user 边界。

租户隔离不能只靠路由装饰器：列表与写入查询必须过滤 `deleted_at` 与归属字段。例外：`GET /members/{member_id}/subordinate` 在查询对象为 `is_task_admin` 或 `is_super_admin` 时返回全部未软删除用户，见 [[core-concepts#User]]。Feature 开关见 [[nodeskclaw-backend/app/core/feature_gate.py#FeatureGate]]。

## Service Domains

业务按域拆分 service，Runtime 与 K8s 为专项子树。

高频域：`auth_service`、`deploy_service`、`gene_service`、`collaboration_service`、`cluster_service`、`hermes_*`、`connector/`（[[nodeskclaw-backend/app/services/connector/connector_service.py#ConnectorService]]、[[nodeskclaw-backend/app/services/connector/edge_node_service.py#EdgeNodeService]]）、`mcp_skill_gateway/`、`runtime/`、`k8s/`；Skill Run 投影路由 `app/api/runs.py`（执行在 `nodeskclaw-agent`）。

修改 API 的默认触及链：`api` → `schemas` → `services` →（可选）`models` + Alembic + tests。

## Hermes And MCP

Hermes Skill、任务产物、Agent 绑定与 MCP Skill Gateway 是独立能力域。组织 MCP 契约见 `docs/backend/mcp_skill_gateway.md`；Hermes Task 见 `docs/backend/hermes_skill.md`。

**员工 Catalog 发布门禁**：`HermesSkill` 是工作副本；员工 `tools/list` 只投影 **已 published** 的 [[nodeskclaw-backend/app/models/hermes_skill/skill_release.py#HermesSkillRelease]]（见 [[decisions/skill-platform-execution]]）。仅 `is_mcp_exposed` 不足以进入 Catalog。

**员工 Skill 执行平面**已迁到独立进程 `nodeskclaw-agent`（[[decisions/skill-platform-execution]]）：Gateway 仍在 Backend；入队经 [[nodeskclaw-backend/app/services/hermes_skill/runtime_skill_run_service.py#RuntimeSkillRunService]]（冻结 Release digest + gateway）；对外 Run 投影为 `/api/v1/runs/*`（剥离内部凭证）。员工 Catalog 合同为 `contracts/skill-run/v1.0.0/`。

**Expert MCP 对 apps/work 的冻结契约**为 WORK-EXPERT-CONTRACT（[[decisions/work-expert-contract]]）：当前消费版本 v1.0.2，产物在 `nodeskclaw-backend/contracts/work-expert/v1.0.2/`；v1.0.0 与 v1.0.1 目录与 tag 不可改写。由 `scripts/contracts.py` 从 FastAPI OpenAPI 与 Pydantic 生成（`--family skill-run` 生成员工合同，不改写 v1.0.2）。勿用 `gateway.version`。

MCP 对外 JSON-RPC 2.0；应用错误以 HTTP 200 + `error.data.errorCode` 返回（Expert MCP 冻结行为）。

P0 实现锚点：Expert 网关 [[nodeskclaw-backend/app/services/expert_gateway/expert_mcp_gateway_service.py#ExpertMcpGatewayService]]、MCP token 校验 [[nodeskclaw-backend/app/services/expert_gateway/expert_mcp_auth_guard.py#ExpertMcpAuthGuard]]、任务域投影 [[nodeskclaw-backend/app/services/hermes_skill/task_service.py#TaskService]]、SkillRelease [[nodeskclaw-backend/app/services/hermes_skill/skill_release_service.py#SkillReleaseService]]、Backend Worker（仅 drain `routing_metadata.execution_owner == "backend"` 的任务，无标记或 agent-owned 一律跳过）[[nodeskclaw-backend/app/services/hermes_skill/hermes_task_worker.py#HermesTaskWorker]]、Agent Worker [[nodeskclaw-agent/app/services/worker.py#RunWorker]]。Schema 事实源：`app/schemas/work_expert/`、`app/schemas/skill_run/`、`app/schemas/hermes_skill/sse_events.py`、`task_result_contract.py`。

## Startup

`app/main.py` lifespan 负责迁移、种子、队列消费者与 PG NOTIFY 监听；缺迁移即启动失败。

新增 Model 必须同 commit 生成 Alembic revision（禁止手写 revision ID）。基类：[[nodeskclaw-backend/app/models/base.py#BaseModel]]。

## Download Content-Disposition

HTTP 响应头只能是 latin-1；含中文的下载文件名必须用 RFC 5987 `filename*=UTF-8''`，禁止把原文写进 `filename="..."`。

共享编码入口：[[nodeskclaw-backend/app/api/file_downloads.py#content_disposition_attachment]]。Hermes 产物字节流下载走同一 helper：[[nodeskclaw-backend/app/api/hermes_skill/artifacts_router.py#download_artifact]]。员工 Skill Run 产物下载走鉴权代理 [[nodeskclaw-backend/app/api/runs.py#download_run_artifact]]（字节 SoT 在 Agent，见 [[decisions/skill-platform-execution]]）。Starlette `FileResponse(filename=...)` 已内置 RFC 5987，本地文件路径下载可直接传原始文件名。
