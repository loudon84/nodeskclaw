```markdown
# nodeskclaw-backend 架构知识文档

> 面向 AI 编码助手。预设读者将基于此文档修改代码库。

---

## 系统本质

`nodeskclaw-backend` 是 **AI Agent 实例生命周期的控制平面**，职责边界：

- **是**：K8s 资源编排、Agent 部署/更新/删除、Workspace 拓扑管理、多租户 RBAC、LLM Key 路由
- **不是**：AI 推理引擎、LLM 服务本身、K8s 集群管理工具

推理执行在 K8s Pod 内的 OpenClaw 进程中发生，本服务只管理其生命周期。

---

## 目录结构与职责划分

```
nodeskclaw-backend/
└── app/
    ├── main.py          # 唯一入口：FastAPI 实例 + lifespan（迁移 + 种子 + 预热）
    ├── core/            # 稳定基础设施层（不含业务逻辑）
    │   ├── config.py        # pydantic-settings，所有环境变量集中声明
    │   ├── deps.py          # FastAPI DI：DB session + RBAC 依赖工厂
    │   ├── security.py      # JWT + proxy_token 认证 + AES-256-GCM 加密
    │   ├── feature_gate.py  # CE/EE 检测 + feature 开关
    │   ├── hooks.py         # 轻量 Hook 系统（CE emit，EE register）
    │   ├── exceptions.py    # 统一异常体系 + 全局 handler
    │   └── middleware.py    # CORS 等中间件
    ├── models/          # SQLAlchemy ORM 模型（数据契约层）
    │   ├── base.py          # BaseModel：UUID PK + timestamps + soft_delete()
    │   └── __init__.py      # 全量导入（确保 create_all 感知所有表）
    ├── schemas/         # Pydantic 请求/响应 schema（API 契约层）
    ├── api/             # HTTP 路由层（薄层，不含业务逻辑）
    │   ├── router.py        # 路由聚合：api_router / admin_router / webhook_router
    │   └── portal/          # Portal 专用路由（实例级权限内置）
    ├── services/        # 业务逻辑层（核心）
    │   ├── deploy/          # DeploymentAdapter 抽象 + CE/EE 工厂
    │   ├── k8s/             # K8s 客户端 + ResourceBuilder + EventBus
    │   ├── email/           # EmailTransport 抽象 + CE/EE 工厂
    │   ├── org/             # OrgProvider 抽象 + CE/EE 工厂
    │   ├── quota/           # QuotaChecker 抽象 + CE/EE 工厂
    │   └── channel_adapters/ # Agent 通信 channel 适配器
    └── utils/
        └── oauth_providers/ # OAuthProvider 抽象 + 注册表 + Feishu 实现
```

---

## 架构分层

```
HTTP 请求
    │
    ▼
api/router.py          ← 路由聚合，注入 RBAC dependencies
    │
    ▼
api/*.py               ← 薄路由层：参数解析 → 调用 service → 返回 schema
    │
    ▼
services/*.py          ← 业务逻辑（唯一允许写 DB 的层）
    │
    ├── services/k8s/  ← K8s 操作（resource_builder + k8s_client）
    └── services/deploy/ ← DeploymentAdapter（CE/EE 分叉点）
    │
    ▼
models/*.py            ← ORM 模型（数据契约，不含业务逻辑）
    │
    ▼
PostgreSQL（异步 asyncpg）
```

**规则**：路由层不直接操作 DB，service 层不直接构造 HTTP 响应。

---

## 稳定抽象层

这 5 个接口是系统的稳定骨架，CE/EE 实现可替换，调用方不感知版本：

| 抽象接口 | 位置 | CE 实现 | EE 实现 |
|---------|------|---------|---------|
| `DeploymentAdapter` | `services/deploy/adapter.py` | `BasicK8sAdapter` | `ee/.../FullK8sAdapter` |
| `EmailTransport` | `services/email/` | `GlobalSmtpTransport` | `ee/.../OrgSmtpTransport` |
| `OrgProvider` | `services/org/` | `SingleOrgProvider` | `ee/.../MultiOrgProvider` |
| `QuotaChecker` | `services/quota/` | `NoopQuotaChecker` | `ee/.../PlanBasedQuotaChecker` |
| `OAuthProvider` | `utils/oauth_providers/base.py` | `FeishuProvider` | 任意新 Provider |

所有工厂均使用 `@lru_cache(maxsize=1)` 单例模式，进程内只实例化一次。

---

## 核心数据模型关系

```
Organization (1)
    ├── (N) OrgMembership → User
    ├── (N) AdminMembership → User（管理平台角色）
    ├── (N) Instance（AI 员工 Pod）
    │       ├── proxy_token（Agent 回调认证）
    │       ├── wp_api_key（LLM Proxy 认证）
    │       └── workspace_id + hex_position_q/r
    ├── (N) Workspace（赛博办公室）
    │       ├── Blackboard（content: Markdown TEXT）
    │       ├── WorkspaceMember → User
    │       ├── HumanHex（人类工位，独立表）
    │       ├── CorridorHex + HexConnection（走廊拓扑）
    │       └── WorkspaceMessage（协作消息）
    ├── (N) Cluster（K8s 集群，kubeconfig AES-256-GCM 加密存储）
    ├── (N) Gene / Genome（能力基因）
    └── (N) OrgLlmKey / UserLlmKey（LLM Key 管理）

User
    ├── UserOAuthConnection（OAuth 通用绑定，provider + provider_user_id）
    └── UserLlmConfig（selected_models JSONB）
```

**`BaseModel`** 是所有模型的基类：UUID PK（`String(36)`）+ `created_at` + `updated_at` + `deleted_at`（软删除标记）。

---

## 认证体系

系统存在 **3 种认证身份**，对应不同的 token 类型：

| 身份 | Token 类型 | 依赖函数 |
|------|-----------|---------|
| 人类用户 | JWT Bearer（HS256） | `get_current_user` |
| SSE 连接 | JWT query param（scope=sse） | `get_current_user_from_query` |
| AI Agent Pod | `proxy_token`（`OPENCLAW_GATEWAY_TOKEN`） | `get_current_user_or_agent` |

`get_current_user_or_agent` 先尝试 JWT，失败后查 `instances.proxy_token`，以 `instance.created_by` 用户身份代入。

---

## RBAC 层级

两套独立的角色体系，通过不同路由前缀隔离：

**Portal（`/api/v1`）**：组织成员角色
- `require_org_member`：组织成员（只读）
- `require_org_admin`：组织管理员
- `require_super_admin_dep`：平台超管（`is_super_admin=true`）

**Admin（`/api/v1/admin`）**：管理平台角色（`AdminMembership` 表）
- `require_org_role("member")`：只读查看
- `require_org_role("operator")`：实例操作 + 部署
- `require_org_role("admin")`：集群、配置、基因、密钥

`super_admin` 在两套体系中均自动放行。

---

## 路由架构

`router.py` 聚合三个顶级路由器，挂载到 `main.py`：

```
/api/v1/          ← api_router（Portal 用户 API）
/api/v1/admin/    ← admin_router（管理平台 API，RBAC 通过 dependencies 注入）
/webhooks/        ← webhook_router（外部回调，如 K8s 事件）
```

`api/portal/` 下的路由是 Portal 专用版本，内置实例级权限检查（用户只能操作自己有权限的实例）。同名功能在 `api/` 下的版本供 Admin 使用（通过 `require_org_role` 控制）。

`/api/v1/system/info` 暴露 `edition` + `features` 列表，是前端初始化的唯一数据源。

---

## 部署流水线

**两阶段异步模式**（`deploy_service.py`）：

```
1. deploy_instance()          ← 同步，在请求上下文中
   ├── 创建 Instance 记录（status=creating）
   ├── 创建 DeployRecord
   └── 返回 record.id（立即响应）

2. execute_deploy_pipeline()  ← asyncio.create_task，后台执行
   ├── get_deploy_adapter()   ← CE/EE 分叉
   ├── adapter.resolve_cluster()  ← CE: 直接用 / EE: 配额检查
   ├── adapter.build_namespace()  ← CE: nodeskclaw-default-{slug} / EE: nodeskclaw-{org_slug}-{slug}
   ├── resource_builder.*     ← 构建 K8s 资源清单
   ├── k8s_client.apply()     ← 应用到集群
   ├── adapter.setup_proxy()  ← CE: no-op / EE: 跨集群网关
   └── EventBus.publish()     ← SSE 进度推送
```

`_running_tasks: dict[str, asyncio.Task]` 维护运行中任务引用，支持取消。

---

## CE/EE 分叉机制

**检测**：`FeatureGate._load()` 检测 `ee/` 目录是否存在，进程启动时一次性确定，`@lru_cache` 工厂保证单例。

**后端分叉点**（按调用顺序）：
1. `main.py` lifespan：条件导入 `ee.backend.models`（在 `create_all` 前）
2. `main.py` lifespan：条件调用 `ee.backend.seed.seed_plans()`
3. `deps.py` `get_current_org`：调用 `OrgProvider` 工厂
4. `deploy_service.py`：调用 `DeploymentAdapter` 工厂
5. `hooks.py`：EE 在加载时注册 handler，CE 只 emit

**Feature 守卫**：
- 路由级：`APIRouter(dependencies=[Depends(require_feature("billing"))])`
- CE-only 路由：`Depends(require_ce_edition)`（如 `/settings`）

---

## 数据库迁移策略

**无 Alembic**，所有迁移内联在 `main.py` `lifespan()` 中，每次启动幂等执行。

迁移模式：
```python
col = await conn.execute(text(
    "SELECT 1 FROM information_schema.columns WHERE table_name=:t AND column_name=:c"
))
if col.first() is None:
    await conn.execute(text("ALTER TABLE ... ADD COLUMN ..."))
```

当前迁移编号：1–24, 30, 31（含子迁移 5a–5e, 6a–6d, 18b, 21a–21c, 22a–22e）。

**新增迁移规则**：
- 追加新编号，不修改已有迁移块
- 必须幂等（先检查再执行）
- 数据回填必须在同一迁移块内完成
- 涉及 `DROP COLUMN` 的迁移（如迁移 22）必须先搬迁数据

---

## 不可违反的不变式

**软删除**：所有删除 = `deleted_at = func.now()`，禁止 `db.delete()` 和 `DELETE FROM`。所有查询必须加 `Model.deleted_at.is_(None)` 过滤。`BaseModel.soft_delete()` 是唯一合法删除入口。

**唯一约束**：必须使用 Partial Unique Index（`WHERE deleted_at IS NULL`），禁止普通 `UNIQUE` 约束。迁移 4、10、24 已将历史约束全部替换。

**错误响应格式**：所有错误必须包含三元组 `{error_code, message_key, message}`，`message_key` 供前端 i18n 使用。禁止直接返回裸字符串 `detail`。

**敏感数据加密**：KubeConfig 和其他敏感字段必须通过 `security.encrypt_sensitive()` / `decrypt_sensitive()` 存储，使用 AES-256-GCM，密钥来自 `settings.ENCRYPTION_KEY`。

**DB session 作用域**：每个请求通过 `get_db()` 获取独立 session，后台任务（`execute_deploy_pipeline`）必须使用 `async_session_factory()` 创建独立 session，禁止跨请求共享 session。

**`models/__init__.py` 全量导入**：新增 Model 必须在此文件导入，否则 `Base.metadata.create_all` 无法感知新表。

---

## 显式扩展点

| 扩展点 | 位置 | 操作 |
|--------|------|------|
| 新增 OAuth Provider | `utils/oauth_providers/` | 实现 `OAuthProvider` ABC，在 `main.py` lifespan `register_provider()` |
| 新增 CE/EE 分叉行为 | `services/{deploy,email,org,quota}/` | 实现对应 ABC，在 `factory.py` 中条件返回 |
| 新增 EE Hook | `core/hooks.py` | EE 加载时 `hooks.register(event, handler)` |
| 新增 API 路由 | `api/router.py` | `api_router.include_router()` 或 `admin_router.include_router()` |
| 新增 EE Feature | `features.yaml` | 在 `edition_features.ee` 追加，后端用 `require_feature()` 守卫 |
| 新增预设 Workspace 模板 | `app/presets/workspace_templates/` | 添加 JSON 文件，在 lifespan 种子化逻辑中追加 |
| 新增 K8s 资源字段 | `services/k8s/resource_builder.py` | 修改对应 `build_*` 函数，同步修改 `deploy_service.py` |

---

## 隐式扩展点

**`pending_config` 两步操作模式**：`Instance.pending_config` 存储待应用的配置变更，保存到 DB 但尚未 apply 到 K8s，支持预览/确认流程。新增需要两步确认的配置变更应遵循此模式。

**`advanced_config` JSON 字段**：`Instance.advanced_config` 是开放 JSON，`EgressPolicyConfig` 从中读取 `network.egress` 覆盖。新增实例级高级配置优先考虑扩展此字段而非新增列。

**`SystemConfig` 键值表**：`models/system_config.py` 是全局配置的 KV 存储，新增系统级配置项在此表存储，通过 `config_service.py` 读写。

**`WorkspaceMessage.attachments` JSONB**：消息附件为开放 JSONB，新增附件类型扩展此字段的 schema 即可。

---

## 高风险修改区域

**`main.py` lifespan()**：包含全部迁移逻辑。修改已有迁移块可能破坏生产数据库。新增迁移必须追加，不得修改已有块。

**`core/deps.py`**：所有 API 端点的认证和授权入口。修改 `get_current_org`、`require_org_role` 影响全局权限模型。

**`services/k8s/resource_builder.py`**：K8s 资源定义。修改影响所有新部署实例，已有实例不受影响但产生配置漂移。

**`core/security.py` `get_current_user_or_agent`**：Agent Pod 认证逻辑。修改影响所有 Agent 回调 API 的安全边界。

**`models/__init__.py`**：遗漏导入导致表不被创建，且不会有任何报错，只在运行时查询时失败。

**软删除过滤**：任何新增查询遗漏 `deleted_at.is_(None)` 将导致已删除数据泄露，且无静态检查保障。

---

## 模块扩展逻辑

**新增 CE 业务功能**：
1. `models/` 新增 Model，在 `__init__.py` 导入
2. `schemas/` 新增 Pydantic schema
3. `services/` 新增 service 文件
4. `api/` 新增路由，在 `router.py` 挂载
5. `main.py` lifespan 追加迁移（新表用 `create_all` 自动处理，新列需手动迁移）

**新增 EE 专属功能**：
1. `features.yaml` 声明 feature id
2. `ee/backend/` 实现后端逻辑（使用 CE 的 `BaseModel`）
3. CE 侧通过 Factory/Hook/Stub 接入，不直接 `import ee.*`
4. 路由用 `Depends(require_feature("feature_id"))` 守卫

**新增 OAuth 登录方式**：
1. `utils/oauth_providers/` 实现 `OAuthProvider` ABC（`name` + `exchange_code`）
2. `main.py` lifespan 中 `register_provider(NewProvider())`
3. `api/auth.py` 添加对应的 `/auth/login/{provider}` 和 `/auth/callback/{provider}` 端点

**新增 K8s 部署能力**：
1. `services/k8s/resource_builder.py` 新增 `build_*` 函数
2. `services/deploy_service.py` 的 `execute_deploy_pipeline` 中调用
3. 若 CE/EE 行为不同，在 `DeploymentAdapter` 新增抽象方法，CE/EE 各自实现

---

## 系统预期生命周期

**当前阶段**：CE 功能稳定，EE 功能从 CE 主仓库迁移中（`multi_org`、`billing`、`admin_members` 等）。

**迁移方向**：EE 功能迁移完成后，CE 版本通过 Factory 抽象层调用 Noop 实现，CE 代码库不再包含 EE 业务逻辑。

**数据库演进**：inline 迁移在迁移数量可控时有效（当前 31+）。迁移数量继续增长时，`lifespan()` 将成为维护瓶颈，未来可能引入 Alembic，但现有迁移需保留兼容。

**多集群**：`k8s/client_manager.py` 已有 `k8s_manager`（多集群连接池），`Cluster` 模型已有 `proxy_endpoint` 字段，`multi_cluster` feature 在 `features.yaml` 标注为未来功能，基础设施已就绪。
``` [1](#1-0) [2](#1-1) [3](#1-2) [4](#1-3) [5](#1-4) [6](#1-5) [7](#1-6) [8](#1-7) [9](#1-8) [10](#1-9) [11](#1-10) [12](#1-11) [13](#1-12) [14](#1-13) [15](#1-14) [16](#1-15) [17](#1-16)

### Citations

**File:** nodeskclaw-backend/app/models/base.py (L25-43)
```python
class BaseModel(Base, TimestampMixin):
    """Abstract base with UUID pk + timestamps + soft delete."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None, index=True
    )

    def soft_delete(self) -> None:
        """标记为已删除（逻辑删除）。"""
        self.deleted_at = func.now()


def not_deleted(model: type[BaseModel]):
    """返回排除已删除记录的 where 条件，用于查询过滤。
```

**File:** nodeskclaw-backend/app/core/feature_gate.py (L29-87)
```python
class FeatureGate:
    def __init__(self) -> None:
        self._edition: str = "ce"
        self._ee_feature_ids: set[str] = set()
        self._all_features: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        self._edition = "ee" if _EE_DIR.is_dir() else "ce"

        if _FEATURES_YAML.exists():
            with open(_FEATURES_YAML) as f:
                data = yaml.safe_load(f) or {}
            ee_features = data.get("edition_features", {}).get("ee", [])
            self._all_features.extend(ee_features)

        if self._edition == "ee" and _EE_FEATURES_YAML.exists():
            with open(_EE_FEATURES_YAML) as f:
                data = yaml.safe_load(f) or {}
            extra = data.get("edition_features", {}).get("ee", [])
            existing_ids = {f["id"] for f in self._all_features}
            for feat in extra:
                if feat["id"] not in existing_ids:
                    self._all_features.append(feat)

        self._ee_feature_ids = {f["id"] for f in self._all_features}

        logger.info(
            "FeatureGate: edition=%s, ee_features=%d",
            self._edition,
            len(self._ee_feature_ids),
        )

    @property
    def edition(self) -> str:
        return self._edition

    @property
    def is_ee(self) -> bool:
        return self._edition == "ee"

    def is_enabled(self, feature_id: str) -> bool:
        if feature_id not in self._ee_feature_ids:
            return True
        return self._edition == "ee"

    def enabled_features(self) -> list[str]:
        if self._edition == "ee":
            return sorted(self._ee_feature_ids)
        return []

    def all_features(self) -> list[dict[str, Any]]:
        return [
            {**f, "enabled": self.is_enabled(f["id"])}
            for f in self._all_features
        ]


feature_gate = FeatureGate()
```

**File:** nodeskclaw-backend/app/core/hooks.py (L1-41)
```python
"""轻量级同步 Hook 系统 — CE emit，EE 注册 handler。

用于解耦 CE 核心逻辑与 EE 附加行为（如审计日志）。
CE 代码只负责 emit，不关心是否有 handler。
EE 在加载时注册 handler。
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

logger = logging.getLogger(__name__)

HookHandler = Callable[..., Any]

_handlers: dict[str, list[HookHandler]] = defaultdict(list)


def register(event: str, handler: HookHandler) -> None:
    """注册事件处理函数。"""
    _handlers[event].append(handler)


async def emit(event: str, **kwargs: Any) -> None:
    """触发事件，依次调用所有注册的 handler。"""
    for handler in _handlers.get(event, []):
        try:
            result = handler(**kwargs)
            if hasattr(result, "__await__"):
                await result
        except Exception:
            logger.exception("Hook handler error: event=%s handler=%s", event, handler.__name__)


def clear(event: str | None = None) -> None:
    """清除 handler（测试用）。"""
    if event:
        _handlers.pop(event, None)
    else:
```

**File:** nodeskclaw-backend/app/core/deps.py (L41-64)
```python
async def get_current_org(
    db: AsyncSession = Depends(get_db),
    user=Depends(_get_current_user_dep()),
):
    """获取当前用户所在组织，返回 (user, organization) 元组。

    CE: 通过 SingleOrgProvider 自动解析默认组织
    EE: 通过 MultiOrgProvider 使用 user.current_org_id
    """
    from app.services.org.factory import get_org_provider

    provider = get_org_provider()
    org = await provider.resolve_org_for_user(user, db)

    if org is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": 40010,
                "message_key": "errors.org.user_has_no_org",
                "message": "用户未加入任何组织",
            },
        )
    return user, org
```

**File:** nodeskclaw-backend/app/core/deps.py (L240-319)
```python
def require_org_role(min_role: str):
    """工厂函数：生成要求当前用户在 admin_memberships 中至少拥有 min_role 的依赖。

    用于 admin_router 的 include_router(dependencies=[...])，
    super_admin 自动放行。返回 (user, org)。
    """
    from app.models.org_membership import ADMIN_ROLE_LEVEL

    min_level = ADMIN_ROLE_LEVEL[min_role]

    async def _dependency(
        db: AsyncSession = Depends(get_db),
        user=Depends(_get_current_user_dep()),
    ):
        from app.models.admin_membership import AdminMembership
        from app.models.organization import Organization

        target_org_id = user.current_org_id

        if user.is_super_admin and target_org_id:
            result = await db.execute(
                select(Organization).where(
                    Organization.id == target_org_id,
                    Organization.deleted_at.is_(None),
                )
            )
            org = result.scalar_one_or_none()
            if org:
                return user, org

        if target_org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error_code": 40010,
                    "message_key": "errors.org.user_has_no_org",
                    "message": "用户未加入任何组织",
                },
            )

        result = await db.execute(
            select(AdminMembership).where(
                AdminMembership.user_id == user.id,
                AdminMembership.org_id == target_org_id,
                AdminMembership.deleted_at.is_(None),
            )
        )
        admin_membership = result.scalar_one_or_none()

        if admin_membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": 40314,
                    "message_key": "errors.org.no_admin_access",
                    "message": "您没有管理平台访问权限",
                },
            )

        user_level = ADMIN_ROLE_LEVEL.get(admin_membership.role, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": 40313,
                    "message_key": "errors.org.insufficient_role",
                    "message": f"需要 {min_role} 及以上角色",
                },
            )

        result = await db.execute(
            select(Organization).where(
                Organization.id == target_org_id,
                Organization.deleted_at.is_(None),
            )
        )
        org = result.scalar_one_or_none()
        return user, org

    return _dependency
```

**File:** nodeskclaw-backend/app/api/router.py (L42-141)
```python
api_router = APIRouter()


@api_router.get("/health", tags=["系统"])
async def health_check():
    """NoDeskClaw backend health probe."""
    return {"status": "ok"}


@api_router.get("/system/info", tags=["系统"])
async def system_info():
    """暴露 edition 和启用的 feature 列表，供前端初始化使用。"""
    return {
        "edition": feature_gate.edition,
        "version": settings.APP_VERSION,
        "features": feature_gate.all_features(),
    }


@api_router.get("/system/capabilities", tags=["系统"])
async def system_capabilities():
    """暴露系统能力状态（如文件上传是否可用），供前端控制 UI 状态。"""
    from app.services import storage_service
    return {
        "file_upload_enabled": storage_service.is_configured(),
    }


api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(org_router, prefix="/orgs", tags=["组织"])
api_router.include_router(org_settings_router, prefix="/orgs", tags=["组织设置"])
api_router.include_router(cluster_router, prefix="/clusters", tags=["集群"])
api_router.include_router(portal_deploy_router, prefix="/deploy", tags=["部署"])
api_router.include_router(events_router, prefix="/events", tags=["事件"])
api_router.include_router(portal_instance_router, prefix="/instances", tags=["实例"])
api_router.include_router(portal_instance_members_router, prefix="/instances", tags=["实例成员"])
api_router.include_router(portal_channel_config_router, prefix="/instances", tags=["Channel 配置"])
api_router.include_router(portal_mcp_router, prefix="/instances", tags=["MCP"])
api_router.include_router(portal_instance_files_router, prefix="/instances", tags=["实例文件"])
api_router.include_router(llm_keys_router, tags=["LLM Key 管理"])
api_router.include_router(registry_router, prefix="/registry", tags=["镜像仓库"])
api_router.include_router(settings_router, prefix="/settings", tags=["系统配置"],
    dependencies=[Depends(require_ce_edition), Depends(require_org_admin)])
api_router.include_router(storage_router, prefix="/storage-classes", tags=["存储"])
api_router.include_router(workspace_router, prefix="/workspaces", tags=["赛博办公室"])
api_router.include_router(corridor_router, prefix="/workspaces", tags=["过道系统"])
api_router.include_router(trust_router, prefix="/workspaces", tags=["渐进式信任"])
api_router.include_router(template_router, prefix="/workspaces", tags=["办公室模板"])
api_router.include_router(instance_template_router, tags=["AI 员工模板"])
api_router.include_router(gene_router, tags=["基因进化"])

# ── 管理平台 Admin API（/api/v1/admin）─────────────────────
# Admin 使用原有路由模块，通过 dependencies 注入角色检查。

admin_router = APIRouter()

# 基础路由（无额外角色限制）
admin_router.include_router(auth_router, prefix="/auth", tags=["Admin - 认证"])
admin_router.include_router(org_router, prefix="/orgs", tags=["Admin - 组织"])
admin_router.include_router(workspace_router, prefix="/workspaces", tags=["Admin - 赛博办公室"])
admin_router.include_router(corridor_router, prefix="/workspaces", tags=["Admin - 过道系统"])
admin_router.include_router(trust_router, prefix="/workspaces", tags=["Admin - 渐进式信任"])
admin_router.include_router(template_router, prefix="/workspaces", tags=["Admin - 办公室模板"])
admin_router.include_router(channel_config_router, prefix="/instances", tags=["Admin - Channel 配置"])
admin_router.include_router(mcp_router, prefix="/instances", tags=["Admin - MCP"])

# member 级别（只读查看）
admin_router.include_router(instance_read_router, prefix="/instances",
    tags=["Admin - 实例(读)"],
    dependencies=[Depends(require_org_role("member"))])
admin_router.include_router(events_router, prefix="/events",
    tags=["Admin - 事件"],
    dependencies=[Depends(require_org_role("member"))])
admin_router.include_router(storage_router, prefix="/storage-classes",
    tags=["Admin - 存储"],
    dependencies=[Depends(require_org_role("member"))])

# operator 级别（实例操作 + 部署）
admin_router.include_router(instance_write_router, prefix="/instances",
    tags=["Admin - 实例(写)"],
    dependencies=[Depends(require_org_role("operator"))])
admin_router.include_router(deploy_router, prefix="/deploy",
    tags=["Admin - 部署"],
    dependencies=[Depends(require_org_role("operator"))])

# admin 级别（集群、配置、基因、密钥等）
admin_router.include_router(cluster_router, prefix="/clusters",
    tags=["Admin - 集群"],
    dependencies=[Depends(require_org_role("admin"))])
admin_router.include_router(settings_router, prefix="/settings",
    tags=["Admin - 系统配置"],
    dependencies=[Depends(require_org_role("admin"))])
admin_router.include_router(gene_router,
    tags=["Admin - 基因进化"],
    dependencies=[Depends(require_org_role("admin"))])
admin_router.include_router(llm_keys_router,
    tags=["Admin - LLM Key 管理"],
    dependencies=[Depends(require_org_role("admin"))])
admin_router.include_router(registry_router, prefix="/registry",
    tags=["Admin - 镜像仓库"],
```

**File:** nodeskclaw-backend/app/services/deploy/adapter.py (L35-116)
```python
class DeploymentAdapter(ABC):

    @abstractmethod
    async def resolve_cluster(
        self,
        cluster_id: str,
        db: AsyncSession,
        org_id: str | None,
        *,
        cpu_limit: str = "0",
        mem_limit: str = "0",
        storage_size: str = "0",
    ) -> tuple[str, Any]:
        """解析最终部署集群。

        Returns:
            (effective_cluster_id, org_or_none)
            CE: 直接返回 (cluster_id, None)
            EE: 检查组织配额 + 专属集群覆盖
        """

    @abstractmethod
    def build_namespace(self, slug: str, org: Any) -> str:
        """构建 namespace 名称。

        CE: nodeskclaw-default-{slug}
        EE: nodeskclaw-{org_slug}-{slug}
        """

    @abstractmethod
    def get_namespace_labels(self, org_id: str | None) -> dict[str, str] | None:
        """namespace 额外标签。

        CE: None
        EE: {"nodeskclaw.io/org-id": org_id}
        """

    @abstractmethod
    async def setup_proxy(
        self,
        ctx: Any,
        ingress_host: str,
    ) -> None:
        """Ingress 创建后的跨集群代理设置。

        CE: no-op
        EE: 在网关集群创建 ExternalName Service + Proxy Ingress
        """

    @abstractmethod
    async def cleanup_proxy(self, ctx: Any) -> None:
        """清理跨集群代理资源。

        CE: no-op
        EE: 删除网关集群上的 Proxy Ingress
        """

    @abstractmethod
    def get_network_policy_org_id(self, org_id: str | None) -> str | None:
        """NetworkPolicy 的 org_id 参数。

        CE: None（不做组织级隔离）
        EE: org_id
        """

    @abstractmethod
    def get_tls_secret(
        self, tls_secret_name: str | None, has_proxy: bool,
    ) -> str | None:
        """Ingress TLS secret 名称。

        CE: 直接返回 tls_secret_name
        EE: 有 proxy 时返回 None（TLS 由网关集群处理）
        """

    @abstractmethod
    def get_egress_config(self, advanced_config: dict | None) -> EgressPolicyConfig:
        """获取 Egress NetworkPolicy 配置。

        CE: 返回全局环境变量配置
        EE: 合并全局 + advanced_config.network.egress 覆盖
        """
```

**File:** nodeskclaw-backend/app/services/deploy/factory.py (L1-22)
```python
"""DeploymentAdapter 工厂 — 根据 edition 返回对应适配器。"""

from __future__ import annotations

from functools import lru_cache

from app.services.deploy.adapter import DeploymentAdapter


@lru_cache(maxsize=1)
def get_deploy_adapter() -> DeploymentAdapter:
    from app.core.feature_gate import feature_gate

    if feature_gate.is_ee:
        try:
            from ee.backend.services.deploy.full_k8s import FullK8sAdapter
            return FullK8sAdapter()
        except ImportError:
            pass

    from app.services.deploy.basic_k8s import BasicK8sAdapter
    return BasicK8sAdapter()
```

**File:** nodeskclaw-backend/app/core/security.py (L155-207)
```python
async def get_current_user_or_agent(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT 优先，失败后尝试 proxy_token（OPENCLAW_GATEWAY_TOKEN）认证。"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40100,
                "message_key": "errors.auth.credentials_missing",
                "message": "未提供认证信息",
            },
        )

    token = credentials.credentials

    try:
        return await _get_user_by_token(token, db)
    except HTTPException:
        pass

    from app.models.instance import Instance
    result = await db.execute(
        select(Instance).where(
            Instance.proxy_token == token,
            Instance.deleted_at.is_(None),
        )
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40101,
                "message_key": "errors.auth.token_invalid",
                "message": "Token 无效",
            },
        )

    user = (await db.execute(
        select(User).where(User.id == instance.created_by, User.deleted_at.is_(None))
    )).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40105,
                "message_key": "errors.auth.user_not_found_or_disabled",
                "message": "用户不存在或已禁用",
            },
        )
    return user
```

**File:** nodeskclaw-backend/app/utils/oauth_providers/base.py (L19-32)
```python
class OAuthProvider(ABC):
    """Each OAuth provider (Feishu, DingTalk, WeCom ...) implements this interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. 'feishu', 'dingtalk'."""
        ...

    @abstractmethod
    async def exchange_code(
        self, code: str, redirect_uri: str | None = None, client_id: str | None = None
    ) -> OAuthUserInfo:
        """Exchange an authorization code for user info."""
```

**File:** nodeskclaw-backend/app/utils/oauth_providers/registry.py (L1-19)
```python
"""Provider registry: register / lookup by name."""

import logging

from app.utils.oauth_providers.base import OAuthProvider

logger = logging.getLogger(__name__)

_providers: dict[str, OAuthProvider] = {}


def register_provider(provider: OAuthProvider) -> None:
    _providers[provider.name] = provider
    logger.info("OAuth provider registered: %s", provider.name)


def get_provider(name: str) -> OAuthProvider:
    provider = _providers.get(name)
    if provider is None:
```

**File:** nodeskclaw-backend/app/core/exceptions.py (L9-67)
```python
class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        code: int,
        message: str,
        status_code: int = 400,
        message_key: str | None = None,
        error_code: int | None = None,
        message_params: dict[str, str] | None = None,
    ):
        self.code = code
        self.error_code = error_code if error_code is not None else code
        self.message = message
        self.message_key = message_key
        self.message_params = message_params
        self.status_code = status_code


class NotFoundError(AppException):
    def __init__(self, message: str = "资源不存在", message_key: str = "errors.common.not_found"):
        super().__init__(code=40400, message=message, status_code=404, message_key=message_key)


class ForbiddenError(AppException):
    def __init__(self, message: str = "无权限", message_key: str = "errors.common.forbidden"):
        super().__init__(code=40300, message=message, status_code=403, message_key=message_key)


class BadRequestError(AppException):
    def __init__(
        self,
        message: str = "请求参数错误",
        message_key: str = "errors.common.bad_request",
        message_params: dict[str, str] | None = None,
    ):
        super().__init__(
            code=40000, message=message, status_code=400,
            message_key=message_key, message_params=message_params,
        )


class ConflictError(AppException):
    def __init__(
        self,
        message: str = "资源冲突",
        message_key: str = "errors.common.conflict",
        message_params: dict[str, str] | None = None,
    ):
        super().__init__(
            code=40900, message=message, status_code=409,
            message_key=message_key, message_params=message_params,
        )


class K8sError(AppException):
    def __init__(self, message: str = "K8s 操作失败", message_key: str = "errors.k8s.operation_failed"):
        super().__init__(code=50010, message=message, status_code=502, message_key=message_key)
```

**File:** nodeskclaw-backend/app/models/instance.py (L29-116)
```python
class Instance(BaseModel):
    __tablename__ = "instances"
    __table_args__ = (
        Index(
            "uq_instances_slug_org_active",
            "slug", "org_id",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    cluster_id: Mapped[str] = mapped_column(String(36), ForeignKey("clusters.id"), nullable=False)
    namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    image_version: Mapped[str] = mapped_column(String(64), nullable=False)
    replicas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Resource requests/limits
    cpu_request: Mapped[str] = mapped_column(String(16), default="500m", nullable=False)
    cpu_limit: Mapped[str] = mapped_column(String(16), default="2000m", nullable=False)
    mem_request: Mapped[str] = mapped_column(String(16), default="2Gi", nullable=False)
    mem_limit: Mapped[str] = mapped_column(String(16), default="2Gi", nullable=False)

    # Network
    service_type: Mapped[str] = mapped_column(String(16), default=ServiceType.cluster_ip, nullable=False)
    ingress_domain: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # OpenClaw gateway token (Control UI / WebSocket 认证)
    proxy_token: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    # Working Plan API Key (LLM Proxy 认证，格式 nodeskclaw-wp-{hex})
    wp_api_key: Mapped[str | None] = mapped_column(
        String(96), nullable=True, unique=True, index=True
    )

    # Config
    env_vars: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string

    # Namespace quota
    quota_cpu: Mapped[str] = mapped_column(String(16), default="4", nullable=False)
    quota_mem: Mapped[str] = mapped_column(String(16), default="8Gi", nullable=False)
    quota_max_pods: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    # Storage
    storage_class: Mapped[str] = mapped_column(String(64), default="nas-subpath", nullable=False)
    storage_size: Mapped[str] = mapped_column(String(16), default="80Gi", nullable=False)

    # Advanced config (JSON)
    advanced_config: Mapped[str | None] = mapped_column(Text, nullable=True)

    # LLM provider 白名单 (实例级隔离)
    llm_providers: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Pending config (JSON) -- 两步操作模式: 保存到 DB 但尚未 apply 到 K8s
    pending_config: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Runtime
    available_replicas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(16), default=InstanceStatus.creating, nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # FK
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    org_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=True, index=True
    )

    # Workspace / Agent hex position (nullable for backward compat)
    workspace_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True
    )
    hex_position_q: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hex_position_r: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agent_display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_theme_color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    # relationships
    cluster = relationship("Cluster", back_populates="instances")
    creator = relationship("User", back_populates="instances", foreign_keys=[created_by])
    organization = relationship("Organization", back_populates="instances")
    deploy_records = relationship("DeployRecord", back_populates="instance", cascade="save-update, merge")
    workspace = relationship("Workspace", foreign_keys=[workspace_id])
    members = relationship("InstanceMember", back_populates="instance")
```

**File:** nodeskclaw-backend/app/services/deploy_service.py (L1-59)
```python
"""Deploy service: precheck, step-by-step deploy, SSE progress push.

部署采用「同步建记录 + 异步执行」两阶段模式：
  1. deploy_instance()  —— 在请求上下文中同步创建 Instance + DeployRecord，立即返回 record.id
  2. execute_deploy_pipeline() —— 通过 asyncio.create_task 在后台执行 K8s 资源创建，
     使用独立的 DB session，通过 EventBus 推送进度供 SSE 消费
"""

import asyncio
import logging
import re as _re
import json as _json
import secrets as _secrets
from datetime import datetime, timezone
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError

from app.models.cluster import Cluster
from app.models.deploy_record import DeployAction, DeployRecord, DeployStatus
from app.models.instance import Instance, InstanceStatus
from app.models.user import User
from app.schemas.deploy import DeployProgress, DeployRequest, PrecheckItem, PrecheckResult
from app.services.k8s.client_manager import k8s_manager
from app.services.k8s.event_bus import event_bus
from app.services.k8s.k8s_client import K8sClient
from app.services.deploy.factory import get_deploy_adapter
from app.services.k8s.resource_builder import (
    build_configmap,
    build_deployment,
    build_ingress,
    build_labels,
    build_network_policy,
    build_pvc,
    build_resource_quota,
    build_service,
)

logger = logging.getLogger(__name__)

# 正在运行的部署任务引用（deploy_id -> asyncio.Task）
_running_tasks: dict[str, asyncio.Task] = {}


def register_deploy_task(deploy_id: str, task: asyncio.Task) -> None:
    """注册后台部署任务，供取消时使用。"""
    _running_tasks[deploy_id] = task


def _unregister_deploy_task(deploy_id: str) -> None:
    """任务结束后移除引用。"""
    _running_tasks.pop(deploy_id, None)


_bg_tasks: set[asyncio.Task] = set()
```

**File:** nodeskclaw-backend/app/main.py (L48-100)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    import logging

    from sqlalchemy import select

    from app.core.deps import async_session_factory, engine
    from app.models import Base  # noqa: F811 — 导入全部模型
    from app.models.cluster import Cluster, ClusterStatus
    from app.services.k8s.client_manager import k8s_manager
    from app.utils.oauth_providers.feishu import FeishuProvider
    from app.utils.oauth_providers.registry import register_provider

    logger = logging.getLogger(__name__)

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

**File:** nodeskclaw-backend/app/core/config.py (L1-74)
```python
"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "NoDeskClaw"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────
    DATABASE_URL: str = ""  # PostgreSQL，从 .env 读取

    # ── JWT ──────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # ── 登录安全 ─────────────────────────────────────────
    LOGIN_EMAIL_WHITELIST: str = ""  # 逗号分隔的域名列表，为空则不限制

    # ── Encryption (AES-256-GCM for KubeConfig) ─────────
    ENCRYPTION_KEY: str = "change-me-32-bytes-base64-key__="

    # ── 飞书 SSO（Admin 应用） ────────────────────────────
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_REDIRECT_URI: str = ""

    # ── 飞书 SSO（Portal 应用，可选） ─────────────────────
    FEISHU_APP_ID_PORTAL: str = ""
    FEISHU_APP_SECRET_PORTAL: str = ""

    # ── Portal ────────────────────────────────────────────
    PORTAL_BASE_URL: str = ""  # 用户门户基础 URL，如 https://portal.example.com

    # ── 云平台 ──────────────────────────────────────────
    VKE_SUBNET_ID: str = ""

    # ── LLM Proxy ─────────────────────────────────────────
    NODESKCLAW_HOST: str = ""  # 外部可达域名，如 https://nodeskclaw.example.com（废弃，保留兼容）
    LLM_PROXY_URL: str = ""  # 独立 LLM Proxy 服务外部地址，如 https://llm-proxy.example.com
    LLM_PROXY_INTERNAL_URL: str = ""  # K8s 集群内网地址，用于 openclaw.json 中的 baseUrl（绕过 ALB）

    # ── Agent API（AI 员工 Pod 回调后端的内网地址）────────
    AGENT_API_BASE_URL: str = "http://localhost:8000/api/v1"

    # ── 出站代理（用于访问 OpenAI/Anthropic 等外部 API）────
    HTTPS_PROXY: str = ""

    # ── Egress NetworkPolicy（AI 员工 Pod 出站流量控制）────
    EGRESS_DENY_CIDRS: str = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    EGRESS_ALLOW_PORTS: str = "80,443"

    # ── GeneHub Registry ────────────────────────────────
    GENEHUB_REGISTRY_URL: str = ""  # e.g. https://genehub.example.com
    GENEHUB_API_KEY: str = ""       # publisher-level API Key
    GENEHUB_WEB_URL: str = ""       # GeneHub Web UI, e.g. https://genehub.example.com

    # ── TOS 对象存储 ─────────────────────────────────────
    TOS_ENDPOINT: str = ""
    TOS_REGION: str = ""
    TOS_BUCKET: str = ""
    TOS_ACCESS_KEY_ID: str = ""
    TOS_SECRET_ACCESS_KEY: str = ""

    # ── CORS ─────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]


settings = Settings()
```

**File:** nodeskclaw-backend/app/models/__init__.py (L1-43)
```python
"""Import all models so SQLAlchemy can detect them."""

from app.models.admin_membership import AdminMembership  # noqa: F401
from app.models.base import Base, BaseModel  # noqa: F401
from app.models.blackboard import Blackboard  # noqa: F401
from app.models.cluster import Cluster  # noqa: F401
from app.models.corridor import CorridorHex, HexConnection  # noqa: F401
from app.models.decision_record import DecisionRecord  # noqa: F401
from app.models.deploy_record import DeployRecord  # noqa: F401
from app.models.gene import (  # noqa: F401
    Gene,
    GeneEffectLog,
    GeneRating,
    Genome,
    GenomeRating,
    InstanceGene,
)
from app.models.instance import Instance  # noqa: F401
from app.models.instance_template import InstanceTemplate  # noqa: F401
from app.models.instance_mcp_server import InstanceMcpServer  # noqa: F401
from app.models.instance_member import InstanceMember  # noqa: F401
from app.models.llm_usage_log import LlmUsageLog  # noqa: F401
from app.models.org_llm_key import OrgLlmKey  # noqa: F401
from app.models.org_required_gene import OrgRequiredGene  # noqa: F401
from app.models.org_smtp_config import OrgSmtpConfig  # noqa: F401
from app.models.oauth_connection import UserOAuthConnection  # noqa: F401
from app.models.org_membership import OrgMembership  # noqa: F401
from app.models.org_oauth_binding import OrgOAuthBinding  # noqa: F401
from app.models.organization import Organization  # noqa: F401
from app.models.system_config import SystemConfig  # noqa: F401
from app.models.trust_policy import TrustPolicy  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_llm_config import UserLlmConfig  # noqa: F401
from app.models.user_llm_key import UserLlmKey  # noqa: F401
from app.models.workspace import Workspace  # noqa: F401
from app.models.workspace_agent import WorkspaceAgent  # noqa: F401
from app.models.workspace_file import WorkspaceFile  # noqa: F401
from app.models.workspace_member import WorkspaceMember  # noqa: F401
from app.models.workspace_message import WorkspaceMessage  # noqa: F401
from app.models.workspace_objective import WorkspaceObjective  # noqa: F401
from app.models.workspace_schedule import WorkspaceSchedule  # noqa: F401
from app.models.workspace_task import WorkspaceTask  # noqa: F401
from app.models.workspace_template import WorkspaceTemplate  # noqa: F401
```

## GeneHub Hermes Skill Registry（team_v3.2）

企业 GeneHub 服务端能力，供 Hermes-agent Desktop 消费、安装、回传状态。

### 环境变量

| 变量 | 说明 |
|------|------|
| `GENEHUB_BUNDLE_SIGNING_SECRET` | Bundle HMAC-SHA256 签名密钥 |
| `GENEHUB_BUNDLE_SIGNATURE_ENABLED` | 是否启用 Bundle 签名，默认 `true` |
| `GENEHUB_DESKTOP_SYNC_ENABLED` | 是否启用 Desktop 同步，默认 `true` |

### Admin API（`/api/v1/admin/genehub/*`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/skills` | 创建 GeneHub Skill |
| PUT | `/skills/{gene_id}` | 更新 Skill |
| PUT | `/skills/{gene_id}/review` | 审核 Skill |
| POST | `/skills/{gene_id}/publish` | 发布 Skill |
| POST | `/entitlements` | 授权 organization/user |
| POST | `/install-jobs/assign` | 分配安装任务 |
| GET | `/install-jobs` | 查询安装任务 |

### Desktop API（`/api/v1/desktop/*`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/devices/register` | 注册 Desktop 设备 |
| POST | `/hermes/profiles/register` | 注册 Hermes Profile |
| POST | `/heartbeat` | 心跳 |
| GET | `/genehub/skills` | 查询授权 Skill |
| POST | `/hermes/install-jobs` | 创建自助安装任务 |
| GET | `/hermes/install-jobs/pending` | 拉取 pending jobs |
| POST | `/hermes/install-jobs/{job_id}/claim` | 领取任务 |
| GET | `/hermes/install-jobs/{job_id}/bundle` | 下载 Bundle |
| POST | `/hermes/install-jobs/{job_id}/status` | 回传安装状态 |
| POST | `/hermes/installed-skills/sync` | 同步本地已安装 Skill |

### 新增数据表

- `desktop_devices`
- `desktop_hermes_profiles`
- `genehub_entitlements`
- `hermes_skill_install_jobs`
- `hermes_installed_skills`
