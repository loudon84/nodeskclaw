# LLM Proxy CODEMAP

## 子系统职责

nodeskclaw-llm-proxy 负责 LLM 请求转发、鉴权、额度控制、用量记录、模型路由和代理层错误处理。它是一个独立的 Python FastAPI 服务（6 个源文件），不应承载 Portal UI 逻辑，也不应直接耦合后端业务页面。

核心原则：一个透明的代理层，对上游提供统一 API，对下游屏蔽不同 Provider 的差异。

## 常用入口

| 文件 | 用途 |
|------|------|
| `app/main.py` | 服务入口，FastAPI app 创建、中间件注册、路由挂载、CORS 配置 |
| `app/config.py` | 配置管理（Pydantic Settings，从 `.env` 加载）：DB URL、代理、LLM 日志、Codex 命令/超时 |
| `app/proxy.py` | 代理请求核心逻辑（~1400 行）：API Key 解析、Provider 鉴权、请求转发、流式处理、用量记录、错误处理 |
| `app/models.py` | SQLAlchemy ORM 模型：API Key、用量记录、额度记录、Provider 配置等持久化结构 |
| `app/database.py` | 数据库连接与 Session 管理（async SQLAlchemy） |
| `app/codex_cli.py` | Codex CLI 调用封装：进程管理、chat completion、stream events、模型列表 |
| `tests/` | 代理层测试 |
| `deploy/` | 部署配置脚本 |
| `.env.example` | 环境变量模板 |
| `Dockerfile` | 容器构建定义 |
| `pyproject.toml` | 项目依赖与元数据 |

## 请求链路

一个标准 LLM 请求的完整处理流程：

### 1. 接收请求
`app/main.py` 中 FastAPI 路由接收上游（Portal / Backend / Agent）发来的 chat completion 请求。
- 请求路径：`/v1/chat/completions` 或 `/v1/models` 等 OpenAI 兼容端点
- 请求体：标准 chat completion 格式（model、messages、stream 等）

### 2. 身份校验与 Key 解析
`app/proxy.py` 从请求中提取认证信息：
- 解析 Authorization header 中的 Bearer token
- 通过 HMAC + 时间戳校验 token 有效性（防重放）
- 识别 tenant、workspace、user 等归属信息
- 从数据库中查找对应的真实 Provider API Key

### 3. 额度检查
在转发前完成：
- 查询该调用方的剩余额度
- 额度不足 → 返回 429（Too Many Requests）并记录
- 额度充足 → 继续

### 4. 模型路由
- 根据请求中的 model 字段匹配 Provider
- 支持多 Provider 路由（OpenAI、Anthropic 等）
- Codex 模型走 `codex_cli.py` 本地进程调用

### 5. 请求转发
`app/proxy.py` 使用 httpx 异步客户端：
- 构造 Provider 兼容的请求格式（headers、body 转换）
- 设置超时与重试策略
- 转发到目标 Provider API

### 6. 流式处理（SSE）
对 `stream: true` 的请求：
- 接收 Provider 的 SSE 流
- 逐 chunk 中转到上游
- 流结束后记录实际 token 消耗

### 7. 用量记录
- 记录 token 消耗（prompt + completion）
- 记录请求耗时、是否成功、错误信息
- 写入数据库供后续汇总

### 8. 返回响应
- 将 Provider 响应转为统一格式
- 错误时返回标准化错误码（不含 Provider 原始错误细节）

## 配置结构

`app/config.py` 通过 Pydantic Settings 管理（从 `.env` 加载）：

| 配置项 | 用途 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | PostgreSQL 连接串 | 空（必配） |
| `HTTPS_PROXY` | 出站代理地址 | 空 |
| `LLM_LOG_CONTENT` | 是否记录请求/响应正文 | `False`（敏感） |
| `LLM_ATTRIBUTION_SECRET` | HMAC 签名密钥 | 空（必配） |
| `CODEX_COMMAND` | Codex CLI 可执行文件路径 | `codex` |
| `CODEX_HOME` | Codex 主目录 | 空 |
| `CODEX_SKIP_GIT_REPO_CHECK` | 跳过 Git 仓库检查 | `True` |
| `CODEX_BYPASS_APPROVALS_AND_SANDBOX` | 跳过审批与沙箱 | `False` |
| `CODEX_TIMEOUT_SECONDS` | Codex 执行超时 | `300` |

## 用量与额度

### 额度控制

- 额度判断必须在转发前完成，不允许"先转发再扣减"。
- 额度不足时返回明确 HTTP 状态码 429 和标准化错误信息，方便 Portal 展示"额度已用完"。
- 支持按 tenant / workspace / user 粒度设置额度上限。

### 用量记录

- 用量记录必须覆盖：成功请求、失败请求、流式请求、中断请求。
- 流式请求在流结束后记录实际 token 消耗。
- 中断请求（客户端断开）也要记录已消耗部分。
- 用量数据写入 PostgreSQL（通过 `database.py` 的 async session）。

### 安全注意事项

- 不要在日志里输出 API Key、Authorization header、完整 prompt 内容。
- `LLM_LOG_CONTENT` 默认 `False`——即使开启也不应记录敏感字段。
- 错误响应只返回错误码和描述，不暴露 Provider 原始错误信息（可能含 API Key）。
- HMAC 签名通过 `LLM_ATTRIBUTION_SECRET` 保障 token 不可伪造。

## 常见任务读取范围

### 修改模型路由
读取：
- `app/config.py` — 模型映射/Provider 配置
- `app/proxy.py` — 路由选择与转发逻辑（~1400 行核心文件，按函数名搜索定位）
- `tests/`

### 修改额度策略
读取：
- `app/config.py` — 额度阈值
- `app/models.py` — 额度/用量 ORM
- `app/database.py` — 数据库连接
- `app/main.py` — 中间件拦截点
- `tests/`

### 修改错误处理
读取：
- `app/proxy.py` — 错误捕获与映射
- `app/main.py` — 全局异常处理（如使用 `@app.exception_handler`）
- `tests/`

### 修改鉴权
读取：
- `app/main.py` — 中间件或依赖注入
- `app/proxy.py` — 转发前的身份校验（HMAC 解析逻辑）
- `app/config.py` — `LLM_ATTRIBUTION_SECRET`
- `tests/`

### 新增 Provider 支持
读取：
- `app/proxy.py` — Provider 适配逻辑（URL 构造、headers 转换）
- `app/config.py` — Provider 配置项
- `app/models.py` — 如有新字段
- `tests/`

### 修改 Codex 集成
读取：
- `app/codex_cli.py` — CLI 调用封装
- `app/proxy.py` — Codex 路由与结果处理
- `app/config.py` — Codex 相关配置

## 错误处理模式

`app/proxy.py`（~1400 行）是核心文件，搜索定位方式：
- 鉴权相关 → 搜索 `Authorization`、`attribution`、`hmac`
- 额度相关 → 搜索 `quota`、`429`、`insufficient`
- Provider 路由 → 搜索 `route`、`provider`、`upstream`
- 流式处理 → 搜索 `stream`、`StreamingResponse`、`chunk`
- 用量记录 → 搜索 `usage`、`token`、`record`
- Codex 调用 → 搜索 `codex`、`CODEX_PROVIDER`

## 数据库 Schema 概览

`app/models.py` 通过 SQLAlchemy ORM 定义持久化实体，主要涉及：
- API Key 表：存储各 tenant/workspace/user 绑定的真实 Provider Key
- 用量记录表：每次请求的 token 消耗、耗时、状态
- 额度配置表：各调用方的额度上限与使用情况

所有查询通过 `app/database.py` 的 async session 管理。

## 测试与调试

### 测试覆盖
`tests/` 目录包含代理层的单元测试和集成测试，覆盖：
- HMAC 签名校验
- Provider 路由正确性
- 额度计算与边界
- 错误响应格式
- 流式请求完整性

### 调试要点
- 启动前检查 `.env` 中 `DATABASE_URL` 和 `LLM_ATTRIBUTION_SECRET` 是否配置
- 代理超时时检查 `HTTPS_PROXY` 是否设置正确
- Codex 调用失败时检查 `CODEX_COMMAND` 路径和 `CODEX_HOME` 目录
- Provider 报错时先确认 API Key 在数据库中是否正确存储

## 禁止默认读取

- `nodeskclaw-backend/`
- `nodeskclaw-portal/`
- `ee/`
- `openclaw/`
- `vibecraft/`
- `hermes-agent/`
- `node_modules/`
- `dist/`

除非任务明确要求跨服务联调，不要读取以上目录。

## 部署与运维

### Provider 集成模式

添加新 LLM Provider 时的标准模式（在 `app/proxy.py` 中）：
1. 定义 Provider 配置（base URL、API 版本、headers 模板）
2. 实现请求转换函数（NoDeskClaw 格式 → Provider 格式）
3. 实现响应转换函数（Provider 格式 → NoDeskClaw 统一格式）
4. 注册到模型路由表
5. 添加 Stream 和非 Stream 两种路径的处理
6. 补充测试覆盖

### 环境变量（必配）
启动前 `.env` 必须配置：
- `DATABASE_URL`：PostgreSQL 连接串（与 Backend 共享同一 RDS）
- `LLM_ATTRIBUTION_SECRET`：HMAC 签名密钥（与 Backend 保持一致）

### 部署方式
- **Docker**：`docker build --platform linux/amd64 -t llm-proxy:latest .`
- **直接运行**：`uv run uvicorn app.main:app --reload --port <port>`

### 构建与推送
参考 `deploy/` 目录下的部署脚本和 `build-and-push.sh`。

### 健康检查
LLM Proxy 没有独立的健康检查端点设计，依赖 FastAPI 默认行为。如需添加：
- 在 `app/main.py` 中新增 `/health` GET 路由
- 检查项：数据库连接、Provider API 可达性
- 返回 JSON `{"status": "ok"}` 或 `{"status": "degraded", "details": [...]}`

### 常见错误码

> 注：以下为 HTTP 代理层的标准错误映射，具体实现见 `app/proxy.py` 中的异常捕获逻辑。

| HTTP 状态 | 含义 | 排查方向 |
|-----------|------|---------|
| 401 | 鉴权失败 | HMAC 签名校验 → `LLM_ATTRIBUTION_SECRET` 是否与 Backend 一致 |
| 429 | 额度不足 | 查询 models 中的额度表 → 确认计费周期和配额设置 |
| 502 | Provider 不可达 | 检查 `HTTPS_PROXY` → 确认 Provider API 可达性 |
| 504 | Provider 超时 | 检查 httpx timeout 配置 → Provider 健康状态 |
| 500 | 内部错误 | 查看日志 → `app/proxy.py` 异常处理逻辑 |

以上错误码均通过 JSON 响应体返回，格式为 `{"error": {"code": "...", "message": "..."}}`。

## 常用命令

```bash
cd nodeskclaw-llm-proxy
uv sync                                    # 安装依赖
uv run uvicorn app.main:app --reload --port <port>  # 启动开发服务器
uv run pytest                              # 运行测试
uv run ruff check .                        # Lint 检查
uv run ruff check --fix .                  # 自动修复
docker build --platform linux/amd64 -t llm-proxy:latest .  # 构建镜像
```

## 与 Backend 的交互边界

- **上游**：Portal/Backend/Agent 通过 HTTP 调用 LLM Proxy 的 `/v1/chat/completions` 端点
- **鉴权**：Backend 生成带 HMAC 签名的 Bearer token，LLM Proxy 验证后查找真实 Provider Key
- **额度**：额度数据与 Backend 共享同一 PostgreSQL，但额度检查和扣减在 Proxy 侧完成
- **用量回传**：Proxy 记录用量后，Backend 可查询汇总数据用于 Portal 展示
- **不耦合**：Proxy 不 import Backend 代码，不调用 Backend API，是纯独立服务
