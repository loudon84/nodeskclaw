# Backend Architecture

`nodeskclaw-backend` 是 FastAPI 中枢：认证、组织治理、实例编排、工作区协作、基因分发、Hermes/MCP 网关与审计。

技术栈：Python 3.12、SQLAlchemy asyncio、PostgreSQL、Alembic、kubernetes-asyncio、JWT。设计文档入口 `docs/backend/index.md`；改码定位用 `.cursor/context/backend-codemap.md`。

## Dual API Prefix

同一套路由处理函数挂在 `/api/v1`（Portal）与 `/api/v1/admin`（管理端）；成员表分离。

管理端校验 `admin_memberships`，Portal 校验 `org_memberships`。详见 [[decisions/dual-api-prefix]]。

## Auth And Tenancy

鉴权依赖集中在 `app/core/deps.py`；业务层仍须强制 org / workspace / user 边界。

租户隔离不能只靠路由装饰器：列表与写入查询必须过滤 `deleted_at` 与归属字段。Feature 开关见 [[nodeskclaw-backend/app/core/feature_gate.py#FeatureGate]]。

## Service Domains

业务按域拆分 service，Runtime 与 K8s 为专项子树。

高频域：`auth_service`、`deploy_service`、`gene_service`、`collaboration_service`、`cluster_service`、`hermes_*`、`mcp_skill_gateway/`、`runtime/`、`k8s/`。

修改 API 的默认触及链：`api` → `schemas` → `services` →（可选）`models` + Alembic + tests。

## Hermes And MCP

Hermes Skill、任务产物、Agent 绑定与 MCP Skill Gateway 是独立能力域，契约写在 `docs/backend/hermes_skill.md` 与 `mcp_skill_gateway.md`。

MCP 对外 JSON-RPC 2.0；写操作需治理与审批语义。Expert MCP Gateway 另见 `docs/backend/expert_mcp_gateway.md`。

## Startup

`app/main.py` lifespan 负责迁移、种子、队列消费者与 PG NOTIFY 监听；缺迁移即启动失败。

新增 Model 必须同 commit 生成 Alembic revision（禁止手写 revision ID）。基类：[[nodeskclaw-backend/app/models/base.py#BaseModel]]。
