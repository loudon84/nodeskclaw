# System Overview

NoDeskClaw 由 Portal、Backend、Skill Agent、LLM Proxy、Knowledge、Task、运行时 Provider 与 Channel 插件组成；Backend 是 API 与编排中枢。

请求从 Portal / Admin / Desktop / MCP Client 进入双前缀 API，经 services 编排后落到 PostgreSQL、K8s/Docker 与外部 GeneHub / Provider / RAGFlow。Skill Run 执行面见 [[decisions/skill-platform-execution]]。组件边界见 [[lat#Component Boundaries]]。AutoTask 见 [[task]]。

## Request Paths

用户与 Agent 流量分五条主路径，不可混用职责。

1. **Portal / Admin REST**：`/api/v1` 与 `/api/v1/admin` → Backend 业务服务。
2. **LLM 调用**：实例 / Agent → LLM Proxy → Provider（额度先检后转）。
3. **MCP / Expert / Skill Run**：JSON-RPC MCP Gateway（组织 MCP + Expert MCP）；员工 Catalog 只列 published SkillRelease，执行经 [[decisions/skill-platform-execution|Skill Platform]] 入队 `nodeskclaw-agent`；apps/work Expert 消费面仍冻结 [[decisions/work-expert-contract|WORK-EXPERT-CONTRACT v1.0.2]]，员工新合同为 `contracts/skill-run/v1.0.0`。
4. **Knowledge / RAG**：Desktop / Agent → Knowledge（ACL + Adapter）→ RAGFlow；禁止直连 RAGFlow。
5. **AutoTask**：Portal / Worker / MCP → `nodeskclaw-task`（`/api/v1/autotask`）→ 自有 PostgreSQL 与 RPA Engine；后继作业与模板生命周期见 [[task]]、[[autotask-objects]]。

错误契约统一为 `error_code` + `message_key` + `message`（见 [[decisions/error-contract]]）。Knowledge 边界见 [[knowledge]] 与 [[decisions/knowledge-ragflow-split]]。

## Layering

Backend 分层固定为 api → schemas → services → models；runtime / k8s 为 services 下的专项子系统。

| 层 | 路径 | 职责 |
|----|------|------|
| 入口 | `app/main.py` | lifespan、迁移、队列、NOTIFY |
| 路由 | `app/api/` | REST / SSE / JSON-RPC |
| 服务 | `app/services/` | 业务与外部系统交互 |
| 模型 | `app/models/` | ORM |
| Schema | `app/schemas/` | 请求响应契约 |
| 核心 | `app/core/` | 配置、依赖、FeatureGate |

Portal 页面不得散落 axios；LLM Proxy 不得承载 Portal UI 逻辑。

## Data Store

权威数据在火山云 RDS PostgreSQL；启动走 Alembic `upgrade head`，禁止依赖 `create_all` 作为生产建表路径。Skill Agent 在同一库使用独立 schema `agent` 存放 Run / Event SoT（见 [[decisions/skill-platform-execution]]）。

软删除与 Partial Unique Index 是全库不变量（[[decisions/soft-delete]]）。对象存储经 `storage_service`（S3 + 本地双后端）服务共享文件与产物。AutoTask 自有库含 `task_successor_jobs` 与 `rpa_runs.output`（迁移 `7c1f4d8e2a90`，见 [[task#Schema Migration Successor]]）。

## Security Boundaries

默认拒绝：未授权 API、跨租户数据、未开额度的 LLM 转发、未确认的破坏性 K8s 操作、Desktop/Agent 直连 RAGFlow。

敏感配置（KubeConfig、RAGFlow API Key 等）不得暴露给客户端。日志与错误响应不得泄露 API Key 或完整 prompt。CE/EE 功能由 [[decisions/ce-ee-split|FeatureGate]] 控制。
