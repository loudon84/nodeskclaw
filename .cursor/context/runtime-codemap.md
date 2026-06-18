# Runtime CODEMAP

## 子系统职责

Runtime 相关代码负责 NoDeskClaw 实例生命周期管理、运行时适配器、K8s 编排、消息事件路由、上下文桥接、Channel 插件和外部 Agent 运行时（OpenClaw、Hermes）集成。

核心抽象：屏蔽不同 Agent 运行时的差异，为上层 API 提供统一的实例创建、启动、停止、销毁、状态查询接口。

## 后端 Runtime v2 入口

所有 Runtime 代码集中在 `nodeskclaw-backend/app/services/runtime/`：

### 适配器（adapters）
各平台运行时抽象层。每种外部运行时对应一个 adapter 实现。

文件：
- `adapters/base.py` — 适配器基类
- `adapters/__init__.py`

### 计算资源（compute）
K8s 调度、Pod 创建/销毁、资源分配（CPU/Memory）、PVC 挂载、NFS 绑定。

文件：
- `compute/base.py` — 计算 Provider 基类
- `compute/docker_provider.py` — Docker Provider 实现
- `compute/k8s_provider.py` — K8s Provider 实现
- `compute/process_provider.py` — 本地进程 Provider 实现
- `compute/__init__.py`

### 消息（messaging）
实例间消息路由、事件总线、通知推送。处理 Agent 输出 → 用户的投递链路。

文件：
- `messaging/bus.py` — 消息总线（核心路由）
- `messaging/pipeline.py` — 消息处理管线
- `messaging/queue.py` — 消息队列
- `messaging/queue_consumer.py` — 队列消费者
- `messaging/envelope.py` — 消息信封
- `messaging/event_log.py` — 事件日志
- `messaging/delivery_plan.py` — 投递计划
- `messaging/ingestion/` — 消息摄入子模块
- `messaging/middlewares/` — 消息中间件子模块

### 上下文桥接（context_bridges）
实例运行时上下文 ↔ Agent 上下文的双向同步。确保 Agent 能感知实例状态，Portal 能获取 Agent 运行信息。

桥接方向：
1. **下行**（Agent → 实例）：Agent 输出内容通过桥接写入实例上下文（blackboard、file、message 等）
2. **上行**（实例 → Agent）：实例状态变更（成员加入、文件上传、设置修改）通过桥接通知 Agent

### 生命周期钩子（hooks）
pre-deploy、post-deploy、pre-stop、post-destroy 等钩子点，供 EE 扩展和自定义逻辑挂载。

常见钩子用途：
- `pre-deploy`：部署前校验（资源可用性、集群健康）、注入默认配置
- `post-deploy`：部署后初始化（Gene 安装、配置推送、Companion 启动）
- `pre-stop`：停止前清理（保存状态、通知 Agent）
- `post-destroy`：销毁后回收（清理 PVC、释放资源、审计记录）

### 注册表（registries）
运行时组件的注册与发现。Adapter、Plugin、Provider 在此注册。

### 传输层（transport）
SSE、WebSocket、HTTP 传输协议适配。

### 核心文件

| 文件 | 用途 |
|------|------|
| `companion.py` | 实例 Companion 管理（每个实例的运维代理进程） |
| `config_adapter.py` | 实例配置 ↔ Runtime 配置的双向转换 |
| `failure_recovery.py` | 实例故障检测与自动恢复逻辑 |
| `gene_install_adapter.py` | Gene/Skill 安装适配器基类 |
| `hermes_gene_install_adapter.py` | Hermes 平台 Gene 安装实现 |
| `openclaw_gene_install_adapter.py` | OpenClaw 平台 Gene 安装实现 |
| `noop_gene_install_adapter.py` | 空实现（当不允许安装 Gene 时） |
| `migration.py` | 运行时数据迁移（如旧实例升级） |
| `node_card.py` | 实例节点信息卡片生成 |
| `pg_notify.py` | PostgreSQL LISTEN/NOTIFY 实时通知 |
| `platform_endpoint_resolver.py` | 平台端点解析（URL/域名 → 实例映射） |
| `retention.py` | 实例数据保留策略（自动清理过期数据） |
| `route_cache.py` | 路由缓存（加速端点查找） |
| `security.py` | 实例运行时安全策略（网络隔离、密钥管理） |
| `sse_registry.py` | SSE 连接注册与管理 |
| `telemetry.py` | 实例运行遥测数据采集 |

### 相关 API 和 Schema

涉及实例操作时必读：
- `app/api/instances.py` — 实例 CRUD、启停、日志、终端
- `app/schemas/instance*.py` — 实例相关请求/响应 Schema
- `app/models/instance*.py` — 实例 ORM 模型

## Channel 插件

当前已存在的 Channel 插件目录：

| 目录 | 用途 |
|------|------|
| `openclaw-channel-nodeskclaw/` | DeskClaw 主 channel plugin（消息路由核心） |
| `openclaw-channel-dingtalk/` | 钉钉 Channel plugin（Stream 协议集成） |
| `openclaw-channel-learning/` | Learning Channel plugin（学习/训练集成） |

### Channel 插件使用规则

- 只有在任务明确涉及 Channel 协议、插件注册、消息收发、运行时适配时才读取 Channel 插件目录。
- 不要为了普通 backend 或 portal 任务读取全部 Channel 插件。
- 修改 Channel 插件时，同时检查 `backend/app/services/runtime/adapters/` 中对应桥接代码。
- Channel 插件是独立 TypeScript 项目（有自己的 package.json、tsconfig），不依赖 Portal 或 Backend 的构建系统。

## Gene 安装流程

Gene/Skill 安装到实例的标准流程：

1. **触发**：Portal/API 调用基因安装接口（`app/api/genes.py`）
2. **调度**：`gene_service.py` 创建安装任务，写入 `hermes_skill_install_job` 表
3. **适配选择**：`adapters/` 根据实例运行时类型选择对应 adapter：
   - OpenClaw 实例 → `openclaw_gene_install_adapter.py`
   - Hermes 实例 → `hermes_gene_install_adapter.py`
   - 不允许安装 → `noop_gene_install_adapter.py`
4. **执行**：adapter 通过 Channel 插件或直接操作 Pod 文件系统安装 Skill
5. **验证**：检查实例上的 `.openclaw/skills/` 是否成功写入
6. **记录**：更新 `hermes_installed_skill` 表标记安装状态

## 实例生命周期管理

一个实例从创建到销毁的完整生命周期：

| 阶段 | 触发 | 关键操作 |
|------|------|---------|
| PENDING | API 创建请求 | 生成 spec、分配资源、写入 DB |
| DEPLOYING | `deploy_service.py` | `compute/` 创建 Pod、挂载 PVC/NFS |
| INITIALIZING | Pod Running | `companion.py` 启动 Companion、`config_adapter.py` 推送配置 |
| RUNNING | 初始化完成 | `sse_registry.py` 注册 SSE、`messaging/` 开始投递消息 |
| STOPPING | API 停止请求 | `pre-stop` 钩子、`companion.py` 通知 Agent 保存状态 |
| STOPPED | Pod 终止 | 资源保留、SSE 断连 |
| DESTROYING | API 销毁请求 | `post-destroy` 钩子、`retention.py` 清理数据 |
| FAILED | 任何阶段异常 | `failure_recovery.py` 自动恢复或标记失败

## Hermes / OpenClaw / Vibecraft 边界

### 外部运行时概述

- `openclaw/`：OpenClaw Agent 运行时源码（TypeScript），本地副本用于调试和问题排查。运行时行为判断优先读本地 `openclaw/src/`。
- `vibecraft/`：VibeCraft 运行时源码（独立仓库），本地副本。
- `hermes-agent/`：目录当前不存在于本地。

### 集成原则

- 默认不读取外部运行时目录。
- 需要集成接口时，只读取入口协议、adapter 桥接代码、README 或明确指定的文件。
- 不要把外部运行时内部实现复制进 NoDeskClaw 后端代码。
- NoDeskClaw 后端应通过 adapter / gateway / bridge 模式接入外部运行时，保持松耦合。

### 排查 DeskClaw 行为时的源码优先级

1. 本地源码（首选）：`openclaw/src/` 下的 TypeScript 源文件
2. Pod 上验证：通过 `kubectl exec` 查看运行时状态（session store、config 文件）
3. Pod 上读 dist（备用）：本地源码版本与线上不一致时

常用 DeskClaw 源码路径：

| 模块 | 本地路径（`openclaw/src/`） |
|------|------|
| Skill 加载与过滤 | `agents/skills.ts` |
| System Prompt 构建 | `agents/system-prompt.ts` |
| Agent Session / 嵌入式运行 | `agents/pi-embedded-runner.ts` |
| Session 消息处理 / Reply | `auto-reply/` |
| Gateway 路由 | `gateway/` |
| 配置加载 | `config/` |

## 常见任务读取范围

### 修改实例生命周期
读取：
- `nodeskclaw-backend/app/api/instances.py`
- `nodeskclaw-backend/app/services/runtime/`（全部 runtime 文件）
- `nodeskclaw-backend/app/models/instance*.py`
- `nodeskclaw-backend/app/schemas/instance*.py`
- 相关测试

### 修改 K8s 编排
读取：
- `nodeskclaw-backend/app/services/runtime/compute/`
- `nodeskclaw-backend/app/services/k8s/`
- `nodeskclaw-backend/app/services/deploy_service.py`
- `nodeskclaw-backend/app/services/cluster_service.py`
- `nodeskclaw-backend/app/core/config.py`
- 相关测试

### 修改消息/事件系统
读取：
- `nodeskclaw-backend/app/services/runtime/messaging/`
- `nodeskclaw-backend/app/services/runtime/context_bridges/`
- `nodeskclaw-backend/app/services/runtime/transport/`
- `nodeskclaw-backend/app/realtime/`
- `nodeskclaw-backend/app/services/collaboration_service.py`
- `nodeskclaw-backend/app/services/corridor_router.py`

### 修改 Channel 插件
读取：
- 指定 `openclaw-channel-*` 目录
- `nodeskclaw-backend/app/services/runtime/adapters/` 中对应桥接代码
- 不读取所有 channel 插件

### 修改 Gene 安装
读取：
- `nodeskclaw-backend/app/services/runtime/*gene*`
- `nodeskclaw-backend/app/data/gene_templates/`
- `nodeskclaw-backend/app/services/gene_service.py`

### 集成新外部运行时
读取：
- `nodeskclaw-backend/app/services/runtime/adapters/`
- `nodeskclaw-backend/app/services/runtime/registries/`
- 外部运行时的入口协议文件（不读全仓）

## 常见排查入口

| 症状 | 查什么 |
|------|--------|
| 实例一直部署中 | K8s - `kubectl describe pod` → `compute/k8s_provider.py` → `deploy_service.py` |
| 消息发不出 | `messaging/bus.py` → `messaging/pipeline.py` → Channel 插件日志 |
| Gene 安装失败 | `gene_install_adapter.py` → `hermes_gene_install_adapter.py` → Pod 上 `.openclaw/skills/` |
| 实例频繁重启 | `failure_recovery.py` → `companion.py` → `kubectl logs <pod>` |
| SSE 断连 | `sse_registry.py` → `transport/` → `pg_notify.py` |
| 端点解析错误 | `platform_endpoint_resolver.py` → `route_cache.py` |

## 禁止默认读取

- `nodeskclaw-portal/`
- `nodeskclaw-llm-proxy/`
- `ee/`
- `openclaw/`（仅在排查 DeskClaw 行为时按需读取指定文件）
- `vibecraft/`

除非任务明确要求跨端/跨运行时分析，不要读取以上目录。

## Runtime 调试要点

- 实例状态异常时优先查 K8s 层（Pod Events、Container Status），再追 Runtime 代码
- `pg_notify.py` 依赖 PostgreSQL LISTEN/NOTIFY，确认数据库连接正常
- `sse_registry.py` 管理 SSE 连接池，断连时检查 Pod 网络策略
- `failure_recovery.py` 的恢复逻辑有重试上限，多次失败会标记 FAILED
- `platform_endpoint_resolver.py` 的缓存由 `route_cache.py` 管理，路由变更后需刷新缓存

## 常用命令

```bash
# 后端测试（Runtime 相关测试在后端）
cd nodeskclaw-backend && uv run pytest

# Runtime 关键词搜索
rg "<keyword>" nodeskclaw-backend/app/services/runtime

# Channel 关键词搜索
rg "<keyword>" openclaw-channel-<target>

# 实例相关搜索（API + Model + Runtime）
rg "<keyword>" nodeskclaw-backend/app/api/instance nodeskclaw-backend/app/models/instance nodeskclaw-backend/app/services/runtime

# K8s 排查（需明确 context 和 namespace）
kubectl get pods -n <namespace> --context <context-name>
kubectl describe pod <pod> -n <namespace> --context <context-name>
kubectl logs <pod> -n <namespace> --context <context-name> --tail=30
```
