```markdown
# NoDeskClaw 系统架构知识文档

> 面向 AI 编码助手。预设读者将基于此文档修改代码库。

---

## 系统本质

NoDeskClaw **是**：Kubernetes 上 AI Agent 实例的生命周期管理平台 + 多 Agent 协作编排层。

NoDeskClaw **不是**：AI 推理引擎、LLM 服务、通用 DevOps 平台。

推理执行由外部子模块 `openclaw/` 承担，本仓库只负责**部署、配置、路由、监控**。

---

## 架构分层

```
┌─────────────────────────────────────────────────────┐
│  Control Plane（本仓库）                              │
│  nodeskclaw-portal (Vue3, :5174)                     │
│  ee/nodeskclaw-frontend (Vue3, :5173, EE-only)       │
│  nodeskclaw-backend (FastAPI, :8000)                 │
│  nodeskclaw-llm-proxy (Go)                           │
└──────────────────────┬──────────────────────────────┘
                       │ kubectl / K8s Python client
┌──────────────────────▼──────────────────────────────┐
│  Data Plane（K8s 集群）                               │
│  namespace: instance-{id}                            │
│  Pod: openclaw-instance                              │
│    └─ openclaw runtime (submodule)                   │
│         └─ openclaw-channel-nodeskclaw (NPM plugin)  │
└─────────────────────────────────────────────────────┘
```

Channel plugin 通过 SSE 回调 Control Plane，形成双向通信闭环。

---

## 核心领域模型

**Workspace（赛博办公室）**：六边形拓扑空间，坐标系 `(hex_q, hex_r)`，原点 `(0,0)` 为黑板（Blackboard）。

**Instance（AI 员工）**：一个 K8s Pod，运行 OpenClaw 进程。与 Workspace 的关联通过 `workspace_id + hex_position_q/r` 表达。

**Gene（能力基因）**：热加载到 Instance 的 `SKILL.md` + MCP server 配置。来源：GeneHub 外部注册表 或 组织私有基因。

**Corridor（走廊）**：Workspace 内 hex 格之间的连接，决定消息路由路径，防止广播风暴。

**Blackboard（黑板）**：Workspace 共享上下文，存储为 Markdown `content` 字段（迁移18后）。

---

## CE/EE 双版本架构

### 检测机制

`app/core/feature_gate.py` 中 `FeatureGate` 类检测 `ee/` 目录是否存在，决定 `is_ee` 布尔值。

### 后端 4 个 Factory 抽象层

| 抽象接口 | CE 实现 | EE 实现（`ee/backend/`） |
|---------|---------|------------------------|
| `DeploymentAdapter` | `BasicK8sAdapter` | `FullK8sAdapter` |
| `EmailTransport` | `GlobalSmtpTransport` | `OrgSmtpTransport` |
| `OrgProvider` | `SingleOrgProvider` | `MultiOrgProvider` |
| `QuotaChecker` | `NoopQuotaChecker` | `PlanBasedQuotaChecker` |

这 4 个接口是**稳定抽象层**，CE/EE 实现可替换，调用方不感知版本。

### 前端路由注入

Portal (`nodeskclaw-portal/`) 在 `src/router/index.ts` 中 import `@/router/ee-stub`。
- CE 模式：`ee-stub.ts` 导出空数组
- EE 模式：Vite alias 将 `ee-stub` 替换为 `ee/frontend/portal/routes.ts`

`eePortalRoutes` 和 `eeOrgSettingsChildren` 是两个注入点。

### EE Model 注册

EE Model 必须使用 CE 的 `Base`/`BaseModel`。在 `main.py` lifespan 的 `create_all` **之前**条件导入 `ee.backend.models`。

### features.yaml

`features.yaml` 是 EE 功能的权威清单。后端用 `require_feature()` 守卫，前端用 `useFeature()` 判断。`/api/v1/system/info` 暴露当前版本的 feature 列表。

---

## 数据库迁移策略

**所有迁移内联在 `main.py` 的 `lifespan()` 函数中**，每次启动幂等执行。无独立迁移框架（无 Alembic）。

迁移模式：先 `SELECT column_name FROM information_schema.columns` 检查列是否存在，不存在则 `ALTER TABLE ADD COLUMN`。

当前已执行迁移编号：1–24, 30, 31。新增迁移必须追加编号，保持幂等。

---

## 不可违反的不变式

**软删除**：所有删除操作设置 `deleted_at = func.now()`，禁止物理删除。所有查询必须过滤 `Model.deleted_at.is_(None)`。

**唯一约束**：必须使用 Partial Unique Index（`WHERE deleted_at IS NULL`），禁止普通 `UNIQUE` 约束，否则软删除后无法重建同名记录。

**平台架构**：所有 Docker 操作显式指定 `--platform linux/amd64`。

**i18n**：所有用户可见文案必须接入 i18n，错误响应必须包含 `error_code + message_key + message` 三元组。

**同源同步**：修改一处逻辑后必须同步 `ee/nodeskclaw-frontend` 和 `nodeskclaw-portal` 的对应副本，以及 `resource_builder.py` 和 `deploy_service.py` 中的 K8s 资源构建逻辑。

**破坏性操作**：K8s 资源删除、DB DROP/DELETE/TRUNCATE、`git push --force` 必须先报告用户确认。

---

## 显式扩展点

| 扩展点 | 位置 | 用途 |
|--------|------|------|
| Factory 抽象层 | `app/services/{deploy,email,org,quota}/` | CE/EE 行为替换 |
| `app/core/hooks.py` | hooks.py | EE 钩子注入 |
| `ee-stub.ts` | `nodeskclaw-portal/src/router/` | EE Portal 路由注入 |
| `eeOrgSettingsChildren` | router/index.ts | EE 组织设置子路由 |
| `features.yaml` | 根目录 | 新增 EE feature 声明 |
| Channel Plugin Tools | `openclaw-channel-nodeskclaw/src/tools.ts` | Agent 可调用工具注册 |
| `app/api/router.py` | `admin_router` / `api_router` / `webhook_router` | 路由挂载点 |

---

## 隐式扩展点

**OAuth Provider 注册**：`main.py` lifespan 中 `register_provider(FeishuProvider())`，新增 OAuth 提供商在此注册，实现在 `app/utils/oauth_providers/`。

**预设 Workspace 模板**：`app/presets/workspace_templates/*.json`，lifespan 启动时种子化，新增预设模板在此目录添加 JSON 文件并在 lifespan 中追加。

**EE 种子数据**：`ee/backend/seed.py` 的 `seed_plans()` 在 lifespan 中条件调用。

---

## Channel Plugin 通信协议

```
OpenClaw Pod
  └─ channel-nodeskclaw plugin (index.ts)
       ├─ register() → api.registerChannel(nodeskclawPlugin)
       ├─ startSSEServer() → 本地 SSE 服务端
       └─ api.registerTool() → 5 个工具:
            nodeskclaw_blackboard / topology / performance / proposals / gene_discovery

Plugin → Backend: CollaborationPayload { workspace_id, source_instance_id, target, text, depth }
Backend → Frontend: SSE stream via collaboration_service.py / sse_listener.py
```

`sessionKey` 格式：`workspace:{workspace_id}`，channel plugin 据此提取 `wsId`。

---

## 新增功能归属规则

**新增 CE 功能**：直接在主仓库开发，`app/api/`、`app/services/`、`app/models/`、`nodeskclaw-portal/src/`。

**新增 EE 功能**：
1. 在 `features.yaml` 的 `edition_features.ee` 中声明 feature id
2. 在 `ee/backend/` 中实现后端逻辑
3. 在 `ee/frontend/portal/routes.ts` 或 `ee/nodeskclaw-frontend/` 中实现前端
4. CE 侧通过 Factory/Hook/Stub 扩展点接入，不直接引用 `ee/` 代码

**新增 K8s 资源字段**：修改 `app/services/deploy/resource_builder.py`，同步修改 `deploy_service.py`，并在 `main.py` lifespan 追加迁移。

**新增 Agent 工具**：在 `openclaw-channel-nodeskclaw/src/tools.ts` 实现，在 `index.ts` 的 `api.registerTool()` 的 `names` 数组中声明。

---

## 高风险修改区域

**`main.py` lifespan()**：包含所有迁移逻辑，修改此函数可能破坏生产数据库。新增迁移必须幂等，必须追加而非修改已有迁移块。

**`app/services/deploy/resource_builder.py`**：K8s 资源定义，修改影响所有新部署实例，已有实例不受影响但会产生配置漂移。

**`app/core/feature_gate.py`**：CE/EE 检测逻辑，修改影响全局功能开关。

**`app/core/deps.py`**：依赖注入（DB session、当前用户、feature 守卫），修改影响所有 API 端点的认证和授权。

**`openclaw-channel-nodeskclaw/src/channel.ts`**：Agent 协作消息路由核心，修改影响所有 Workspace 内的 Agent 通信。

**软删除过滤**：任何新增查询遗漏 `deleted_at.is_(None)` 过滤将导致已删除数据泄露。

---

## 系统预期生命周期

**当前阶段**：CE 功能稳定，EE 功能从 CE 仓库迁移中（`features.yaml` 注释标注"需从 CE 仓库迁移到 ee/"）。

**迁移方向**：`multi_org`、`billing`、`admin_members` 等功能正在从 CE 主仓库迁移到 `ee/backend/`，迁移完成后 CE 版本将通过 Factory 抽象层调用 Noop 实现。

**数据库演进**：当前采用 inline 迁移，随迁移数量增长（已达 31+），未来可能引入 Alembic，但现有模式在迁移数量可控时有效。

**多集群**：`multi_cluster` 在 `features.yaml` 中标注为"未来功能"，`cluster_service.py` 和 `k8s/client_manager.py` 已有多集群基础设施。
``` [1](#0-0) [2](#0-1) [3](#0-2) [4](#0-3) [5](#0-4) [6](#0-5) [7](#0-6) [8](#0-7) [9](#0-8) [10](#0-9)

### Citations

**File:** AGENTS.md (L72-78)
```markdown

所有数据删除必须使用逻辑删除，严禁物理删除。

- 删除操作设置 `deleted_at = func.now()`
- 所有查询过滤：`Model.deleted_at.is_(None)`
- 禁止 `db.delete()` 和原生 `DELETE FROM`
- 唯一约束使用 Partial Unique Index：`Index(..., unique=True, postgresql_where=text("deleted_at IS NULL"))`
```

**File:** AGENTS.md (L188-197)
```markdown
## 同源逻辑同步

修改一处逻辑后，必须搜索项目中是否存在相同或相似的逻辑副本，全部同步修改。

| 逻辑类型 | 可能位置 |
|---------|----------|
| slug 生成、表单校验 | `ee/nodeskclaw-frontend` 和 `nodeskclaw-portal` 的对应页面 |
| API 调用封装 | 两个前端的 `api.ts` |
| K8s 资源构建逻辑 | `resource_builder.py`、`deploy_service.py` |

```

**File:** AGENTS.md (L213-231)
```markdown

4 个 Factory 模式抽象层，CE/EE 各自实现：

| 抽象层 | CE 实现 | EE 实现（ee/backend/） |
|--------|---------|----------------------|
| DeploymentAdapter | BasicK8sAdapter | FullK8sAdapter |
| EmailTransport | GlobalSmtpTransport | OrgSmtpTransport |
| OrgProvider | SingleOrgProvider | MultiOrgProvider |
| QuotaChecker | NoopQuotaChecker | PlanBasedQuotaChecker |

### EE Model 注册

EE Model 使用 CE 的 `Base`，在 `main.py` lifespan 中 `create_all` 前条件导入 `ee.backend.models`。

### 前端架构

- **Admin**（`ee/nodeskclaw-frontend/`）：完整独立的 Vue 项目，EE-only，CE 版不包含此目录。EE 路由直接定义在 `src/router/index.ts` 中。
- **Portal**（`nodeskclaw-portal/`）：CE + EE 共用。CE 前端定义 `src/router/ee-stub.ts`（空数组），Vite 在检测到 `ee/` 时通过 alias 替换为 `ee/frontend/portal/routes.ts` 提供的 EE 路由。

```

**File:** features.yaml (L9-71)
```yaml
edition_features:
  ee:
    # ── 现有功能（需从 CE 仓库迁移到 ee/） ──
    - id: multi_org
      name: Multi-Organization Management
      description: 多组织创建、切换、成员管理

    - id: billing
      name: Plans & Billing
      description: 套餐管理、配额检查、用量统计

    - id: admin_members
      name: Admin Platform Members
      description: 管理平台成员（多管理员角色）

    - id: platform_admin
      name: Platform Admin Pages
      description: 超管页面（Organizations / Users / Plans / OrgMembers / OrgLlmKeys）

    - id: enterprise_files
      name: Enterprise File Browser
      description: 企业空间文件浏览

    - id: org_smtp_config
      name: Organization SMTP Config
      description: 组织级 SMTP 界面配置

    - id: topology_audit
      name: Topology Audit Log
      description: 赛博办公室拓扑变更审计日志

    - id: performance_analytics
      name: Performance Analytics
      description: AI 员工性能快照采集与分析

    - id: llm_analytics
      name: LLM Usage Analytics
      description: LLM 用量统计报表

    - id: network_egress_control
      name: Network Egress Control
      description: 实例级出站流量策略定制（Egress NetworkPolicy）

    - id: akr_management
      name: AKR Management
      description: 组织级 AKR 汇总老板视图

    # ── 未来功能（代码将在 ee/ 仓库中新增） ──
    - id: multi_cluster
      name: Multi-Cluster Management
      description: 多 K8s 集群部署 + 跨集群网关代理

    - id: advanced_audit
      name: Advanced Operation Audit
      description: 全局操作审计中间件 + 查询导出

    - id: sso_ldap
      name: LDAP/SAML SSO
      description: 企业级 SSO 认证集成

    - id: advanced_rbac
      name: Advanced RBAC
      description: 细粒度角色权限控制
```

**File:** nodeskclaw-backend/app/main.py (L64-74)
```python
    # ── EE Model 注册（在 create_all 之前导入，使其加入 Base.metadata）──
    from app.core.feature_gate import feature_gate as _fg
    if _fg.is_ee:
        _proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        if _proj_root not in sys.path:
            sys.path.insert(0, _proj_root)
        try:
            import ee.backend.models  # noqa: F401
            logger.info("EE Models 已注册")
        except ImportError:
            pass
```

**File:** nodeskclaw-backend/app/main.py (L76-100)
```python
    # ── Startup ──────────────────────────────────────
    register_provider(FeishuProvider())

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 自动迁移
    async with engine.begin() as conn:
        from sqlalchemy import text

        # 迁移 1: 为已有表添加 deleted_at 列（首次升级到软删除版本时执行）
        tables = ["users", "clusters", "instances", "deploy_records", "system_configs"]
        for table in tables:
            col_check = await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = 'deleted_at'"
            ), {"table": table})
            if col_check.first() is None:
                await conn.execute(text(
                    f'ALTER TABLE {table} ADD COLUMN deleted_at TIMESTAMPTZ'
                ))
                await conn.execute(text(
                    f'CREATE INDEX IF NOT EXISTS ix_{table}_deleted_at ON {table}(deleted_at)'
                ))
                logger.info("自动迁移：已为 %s 表添加 deleted_at 列和索引", table)
```

**File:** nodeskclaw-portal/src/router/index.ts (L1-5)
```typescript
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { i18n } from '@/i18n'
import { eePortalRoutes, eeOrgSettingsChildren } from '@/router/ee-stub'

const ceRoutes: RouteRecordRaw[] = [
```

**File:** nodeskclaw-portal/src/router/index.ts (L118-166)
```typescript
const routes: RouteRecordRaw[] = [...ceRoutes, ...eePortalRoutes]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('portal_token')
  const isLoginPage = to.path === '/login' || to.path.startsWith('/login/callback/')
  const isSetupPage = to.path === '/setup-org'

  if (isLoginPage) {
    return next()
  }

  if (!token && to.meta.requiresAuth !== false) {
    return next('/login')
  }

  if (token && !isSetupPage && !to.meta.allowNoOrg) {
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    if (!authStore.systemInfo) {
      await authStore.fetchSystemInfo()
    }
    if (!authStore.user) {
      await authStore.fetchUser()
    }
    if (authStore.user && !authStore.user.current_org_id) {
      return next('/setup-org')
    }

    // CE-only routes: redirect to home in EE mode
    if (to.meta.ceOnly && authStore.systemInfo?.edition === 'ee') {
      return next('/')
    }

    const requiredFeature = to.meta.requireFeature as string | undefined
    if (requiredFeature && authStore.systemInfo) {
      const feat = authStore.systemInfo.features.find((f: any) => f.id === requiredFeature)
      if (!feat?.enabled) {
        return next('/')
      }
    }
  }

  next()
})
```

**File:** openclaw-channel-nodeskclaw/index.ts (L10-35)
```typescript
const plugin = {
  id: "nodeskclaw",
  name: "NoDeskClaw",
  description: "DeskClaw cyber office agent collaboration channel",
  configSchema: emptyPluginConfigSchema(),
  register(api: OpenClawPluginApi) {
    setNoDeskClawRuntime(api.runtime);
    api.registerChannel({ plugin: nodeskclawPlugin });
    startSSEServer();
    api.registerTool((ctx: { sessionKey?: string }) => {
      const wsId = ctx.sessionKey?.startsWith(WORKSPACE_SESSION_PREFIX)
        ? ctx.sessionKey.slice(WORKSPACE_SESSION_PREFIX.length)
        : undefined;
      return createNoDeskClawTools(api.config, wsId);
    }, {
      optional: true,
      names: [
        "nodeskclaw_blackboard",
        "nodeskclaw_topology",
        "nodeskclaw_performance",
        "nodeskclaw_proposals",
        "nodeskclaw_gene_discovery",
      ],
    });
  },
};
```

**File:** openclaw-channel-nodeskclaw/src/types.ts (L23-28)
```typescript
export type CollaborationPayload = {
  workspace_id: string;
  source_instance_id: string;
  target: string;
  text: string;
  depth: number;
```
