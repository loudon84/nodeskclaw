# Backend CODEMAP（Hub）

## 子系统职责

nodeskclaw-backend 是 NoDeskClaw 的 FastAPI 后端，负责 API、认证依赖、Workspace、Instance、Runtime、K8s 编排、审计、任务状态、SSE、用量汇总等服务端能力。数据库使用 PostgreSQL，不走本地 SQLite。

## 常用入口

| 文件/目录 | 用途 |
|------|------|
| `app/main.py` | FastAPI app / lifespan / 中间件 |
| `app/api/router.py` | 公共 API 与 Admin API 聚合 |
| `app/core/deps.py` | 权限依赖 + DB Session（`get_db()`） |
| `app/core/config.py` | 后端配置（Settings） |
| `app/core/feature_gate.py` | CE/EE 功能判断 |
| `app/models/` | SQLAlchemy ORM |
| `app/schemas/` | Pydantic 请求/响应 |
| `app/services/` | 业务逻辑 |
| `app/services/runtime/` | 实例运行时（详见 runtime-codemap） |
| `app/startup/` | 启动初始化 |
| `app/realtime/` | WebSocket/SSE |
| `alembic/` | 数据库迁移 |

## 设计文档（双轨衔接）

功能变动时 **先读设计、再读 CODEMAP**：`docs/backend/` 说明模块做什么、接口契约与数据流；本目录说明代码在哪、改哪几个文件。

| 步骤 | 读什么 | 目的 |
|------|--------|------|
| 1 | `docs/backend/index.md` | 能力域、分层、模块边界 |
| 2 | 下表「任务域 → 模块文档」中 **1 份** | 契约、数据流、接口清单 |
| 3 | 本 Hub + 1 个 CODEMAP 子索引 | 路由 / model / service 文件路径 |

### 任务域 → 模块设计文档

| 任务域 | 设计文档 | CODEMAP 子索引 |
|--------|----------|----------------|
| Hermes Skill、任务、产物、Agent 绑定、组织 MCP Session | `docs/backend/hermes_skill.md` | `backend-api-index.md` + `backend-services-index.md` |
| MCP Skill Gateway、tools/call、审批、产物桥接、KB 入库 | `docs/backend/mcp_skill_gateway.md` | 同上 |
| 全栈概览、API 前缀、环境变量、本地开发 | `nodeskclaw-backend/README.md` | 本 Hub |
| 实例 Runtime、K8s、消息总线、部署 | `@runtime-codemap.md` | 不读本 Hub 的 Runtime 细节 |
| 其它域（Workspace 黑板等） | `docs/backend/index.md` + `docs/后端架构设计.md`（按需） | 按改码类型选子索引 |

实现 + review 通过后：契约或架构有变 → 回写 `docs/backend/`；仅路径/目录有变 → 酌情更新本目录子索引。

## 子文档导航（CODEMAP 定位）

按任务类型只读 **Hub + 1 个子文档**，不要一次加载全部索引。

| 任务类型 | 先读 Hub | 再读子文档 |
|----------|----------|------------|
| 修改 API 路由 / Schema | 本文件 | `backend-api-index.md` |
| 修改 Model / 迁移 | 本文件 | `backend-models-migration.md` |
| 修改 Service 业务逻辑 | 本文件 | `backend-services-index.md` |
| 修改实例 / Runtime / K8s | `@runtime-codemap.md` | 不读 backend 子文档中的 Runtime 章节 |

子文档路径：`.cursor/context/backend-api-index.md`、`.cursor/context/backend-models-migration.md`、`.cursor/context/backend-services-index.md`

## API 修改默认路径

1. `app/api/<domain>.py` — 路由与权限
2. `app/schemas/<domain>.py` — 请求/响应 Schema
3. `app/services/<domain>_service.py` — 业务逻辑
4. `app/models/<domain>.py` — ORM（如有表结构变更）
5. `alembic/versions/` — 迁移（如涉及 Model）
6. `tests/` — 测试

## 权限与租户边界

- workspace、instance、profile、task、usage 数据必须考虑 tenant / workspace / user 边界。
- API 层鉴权入口：`app/core/deps.py`；业务约束在 service 层。
- 管理员 API 与用户 API 路由隔离，默认拒绝未授权访问。

## 常见任务读取范围

### 修改普通 CRUD API
Hub → `backend-api-index.md` → `backend-services-index.md` → 3～8 个目标源文件 + tests

### 修改 Model / 迁移
Hub → `backend-models-migration.md` → 对应 model + alembic/versions

### 修改实例 / Runtime / K8s / 消息
**不读本 Hub 的 Runtime 细节** → 直接读 `@runtime-codemap.md`

### 修改权限 / 认证
Hub → `app/core/deps.py`、`app/core/feature_gate.py`、`app/services/auth_service.py`

## 常见排查入口

| 症状 | 查什么 |
|------|--------|
| API 500 | api → service → RDS / deps |
| 权限问题 | deps.py → feature_gate.py → auth_service.py |
| 迁移失败 | backend-models-migration.md → alembic history |
| 实例 / 部署 / 消息 | runtime-codemap.md |

## 禁止默认读取

- `nodeskclaw-portal/`
- `nodeskclaw-llm-proxy/`
- `ee/`
- `openclaw/`
- `vibecraft/`
- `hermes-agent/`
- `node_modules/`、`dist/`
- `docs_prd/`（PRD 仅在用户点名或需求澄清时读）

**允许且鼓励**（功能变动时）：`docs/backend/`（先 `index.md`，再 1 份模块文档）。

除非任务明确要求跨端联调，不要读取以上禁止目录。

## 常用命令

```bash
cd nodeskclaw-backend
uv sync
uv run uvicorn app.main:app --reload --port 4510
uv run pytest
uv run pytest tests/test_xxx.py::test_func
uv run ruff check .
uv run ruff check --fix .
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "描述"
```
