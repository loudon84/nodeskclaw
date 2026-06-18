# NoDeskClaw Cursor Token 优化 PRD

## 1. 文档信息

版本：v1.0
目标仓库：NoDeskClaw
目标工具：Cursor
优化对象：`.cursor/rules` 与 `.cursor/context`
核心目标：降低 Cursor Vibe Coding 过程中的无效上下文加载、重复规则注入、全仓扫描和跨域读取。

## 2. 背景

当前 NoDeskClaw 是多子系统单仓库，包含后端、门户前端、LLM Proxy、Runtime Channel 插件、EE 私有扩展以及若干外部源码目录。Cursor 在根目录进行 Vibe Coding 时，容易将多个无关子系统同时纳入上下文，导致 token 消耗过高。

本次优化不改业务代码，只调整 Cursor 可读取的规则与上下文索引，让 Cursor 在开发任务中优先读取最小必要范围。

## 3. 优化目标

### 3.1 目标一：重构 `.cursor/rules`

将现有规则收敛为 5 个规则文件：

```text
.cursor/rules/
├── 00-project-map.mdc
├── 10-backend.mdc
├── 20-portal.mdc
├── 30-ee-boundary.mdc
└── 90-security.mdc
```

设计原则：

1. 只有 `00-project-map.mdc` 和 `90-security.mdc` 可以 `alwaysApply: true`。
2. 其余规则必须通过 `globs` 精确匹配文件路径。
3. 每个规则文件只保留当前任务必须知道的约束。
4. 禁止把长架构说明、重复规范、历史背景写入规则。
5. 禁止在规则中要求默认读取全局 Skill、外部仓库、全量 README、AGENTS、CLAUDE 文档。
6. 默认要求 Cursor 限定目录搜索，不做全仓扫描。

### 3.2 目标二：新增短 CODEMAP

新增子系统级短索引目录：

```text
.cursor/context/
├── backend-codemap.md
├── portal-codemap.md
├── llm-proxy-codemap.md
└── runtime-codemap.md
```

每个 CODEMAP 控制在 200～400 行，只写：

1. 子系统职责。
2. 常用入口文件。
3. 关键路由 / service / model / store / adapter。
4. 常见修改路径。
5. 推荐读取文件范围。
6. 禁止跨域读取范围。
7. 常用测试命令。

CODEMAP 不是架构长文，也不是 README。它的用途是让 Cursor 在任务开始时快速定位上下文，避免自由全仓探索。

## 4. 非目标

本次不处理以下内容：

1. 不修改业务代码。
2. 不重构目录结构。
3. 不删除 AGENTS.md / CLAUDE.md / README。
4. 不调整 Cursor 模型配置。
5. 不实现 MCP Server。
6. 不修改后端、前端、LLM Proxy、Runtime 的运行逻辑。
7. 不新增测试用例，除非只是校验文档路径和 markdown 格式。

## 5. 文件变更范围

### 5.1 允许新增或修改

```text
.cursor/rules/00-project-map.mdc
.cursor/rules/10-backend.mdc
.cursor/rules/20-portal.mdc
.cursor/rules/30-ee-boundary.mdc
.cursor/rules/90-security.mdc

.cursor/context/backend-codemap.md
.cursor/context/portal-codemap.md
.cursor/context/llm-proxy-codemap.md
.cursor/context/runtime-codemap.md
```

### 5.2 允许清理

如果 `.cursor/rules/` 下存在旧规则文件，可以迁移、合并或删除，但必须满足：

1. 删除前先检查是否有唯一规则只存在于旧文件。
2. 安全、CE/EE、敏感信息、软删除、Alembic、i18n 等必要约束必须保留。
3. 重复规则只保留一处。
4. 旧规则中涉及具体业务开发规范的内容，应移入对应子系统规则或 CODEMAP，而不是继续 alwaysApply。

### 5.3 禁止修改

```text
nodeskclaw-backend/**
nodeskclaw-portal/**
nodeskclaw-llm-proxy/**
openclaw-channel-*/**
ee/**
openclaw/**
vibecraft/**
hermes-agent/**
```

除非只是为了读取文件结构生成 CODEMAP，不得写入这些目录。

## 6. 规则文件详细需求

## 6.1 `.cursor/rules/00-project-map.mdc`

用途：极简项目地图，始终加载。
配置：`alwaysApply: true`
长度：建议 30 行以内。

目标内容：

```md
---
description: NoDeskClaw minimal project map
alwaysApply: true
---

NoDeskClaw 是 DeskClaw 团队版实例管理平台。

目录边界：
- nodeskclaw-backend：FastAPI 后端，API / Service / Model / K8s / Runtime。
- nodeskclaw-portal：CE+EE 共用用户门户，Vue 3。
- nodeskclaw-llm-proxy：LLM 请求转发、鉴权、额度、用量记录。
- openclaw-channel-*：运行时 Channel 插件。
- ee/：企业版私有扩展，未明确要求不要读取。
- openclaw/、vibecraft/、hermes-agent/：外部源码，未明确要求不要读取。

默认策略：
- 只读取当前任务相关目录。
- 不要全仓扫描。
- 修改同源逻辑时，先用 rg 限定目录搜索。
- 优先读取 .cursor/context 下对应 CODEMAP，再读取目标文件。
```

验收标准：

1. 文件存在。
2. `alwaysApply: true`。
3. 不包含长架构说明。
4. 不要求默认读取 AGENTS.md、CLAUDE.md、README。
5. 明确要求不要全仓扫描。

## 6.2 `.cursor/rules/10-backend.mdc`

用途：后端 Python 代码规则。
配置：`alwaysApply: false`
匹配范围：

```yaml
globs:
  - "nodeskclaw-backend/**/*.py"
```

目标内容：

```md
---
description: Backend coding rules
globs:
  - "nodeskclaw-backend/**/*.py"
alwaysApply: false
---

后端分层：
- api：路由与权限边界
- schemas：请求/响应契约
- services：业务逻辑
- models：SQLAlchemy ORM
- alembic：迁移
- core：配置、依赖、权限、feature gate
- services/runtime：实例运行时、K8s、消息、上下文桥接

规则：
- 删除必须软删除，除非已有代码明确是物理删除语义。
- 新增或修改 SQLAlchemy Model 字段，必须同步 Alembic migration。
- API 错误返回必须包含 error_code / message_key / message。
- K8s 操作必须显式 context，禁止依赖隐式当前集群。
- 变更 API 时同步检查 schemas、service、测试与前端调用。
- 默认先读取 .cursor/context/backend-codemap.md。
- 不要读取 portal、llm-proxy、ee、openclaw、vibecraft，除非任务明确要求。
```

验收标准：

1. 文件存在。
2. `alwaysApply: false`。
3. 只匹配 `nodeskclaw-backend/**/*.py`。
4. 保留软删除、Alembic、API 错误结构、K8s context 规则。
5. 明确默认读取 `backend-codemap.md`。

## 6.3 `.cursor/rules/20-portal.mdc`

用途：Portal 前端代码规则。
配置：`alwaysApply: false`
匹配范围：

```yaml
globs:
  - "nodeskclaw-portal/src/**/*.vue"
  - "nodeskclaw-portal/src/**/*.ts"
```

目标内容：

```md
---
description: Portal coding rules
globs:
  - "nodeskclaw-portal/src/**/*.vue"
  - "nodeskclaw-portal/src/**/*.ts"
alwaysApply: false
---

Portal 使用 Vue 3 + Vite + TypeScript + Tailwind + Pinia + vue-i18n。

规则：
- 新增用户可见文案必须加 i18n。
- 图标使用 lucide-vue-next，不使用 emoji。
- API 调用走 src/services。
- 跨页面共享状态走 Pinia stores。
- 页面组件避免直接写复杂请求逻辑。
- 修改路由时检查 router、layout、导航入口和权限。
- 默认先读取 .cursor/context/portal-codemap.md。
- 不要读取 backend、llm-proxy、ee、openclaw、vibecraft，除非任务明确要求。
```

验收标准：

1. 文件存在。
2. `alwaysApply: false`。
3. 只匹配 Portal `src` 下的 Vue/TS 文件。
4. 保留 i18n、lucide、services、Pinia 规则。
5. 明确默认读取 `portal-codemap.md`。

## 6.4 `.cursor/rules/30-ee-boundary.mdc`

用途：CE/EE 边界规则。
配置：`alwaysApply: false`
匹配范围：

```yaml
globs:
  - "ee/**"
  - "**/features.yaml"
  - "**/feature_gate.py"
  - "**/feature*.py"
```

目标内容：

```md
---
description: CE/EE boundary rules
globs:
  - "ee/**"
  - "**/features.yaml"
  - "**/feature_gate.py"
  - "**/feature*.py"
alwaysApply: false
---

CE/EE 边界规则：
- CE 代码不得直接 import ee 模块。
- 企业版能力必须通过 feature gate、adapter、配置或运行时注册接入。
- EE 私有实现不要复制到 CE。
- 涉及 features.yaml、feature_gate、license、quota、tenant isolation 时必须检查 CE fallback。
- 未明确要求时，不要读取 ee/ 目录。
- 修改 EE 能力时，必须说明 CE 行为是否保持不变。
```

验收标准：

1. 文件存在。
2. `alwaysApply: false`。
3. 只在 EE、feature gate、feature 配置相关文件触发。
4. 明确 CE 不得直接 import EE。
5. 明确未要求不要读取 `ee/`。

## 6.5 `.cursor/rules/90-security.mdc`

用途：全局安全短规则。
配置：`alwaysApply: true`
长度：必须控制在 20 行以内。

目标内容：

```md
---
description: Security and sensitive information rules
alwaysApply: true
---

安全规则：
- 不要读取、输出、提交 .env、密钥、token、cookie、私有证书。
- 不要把真实密钥写入示例配置。
- 日志、截图、报错中出现敏感信息时必须脱敏。
- 不要修改生产连接信息、云账号、K8s kubeconfig、CI secret。
- 涉及权限、租户隔离、鉴权、审计、账单、额度时，必须保持默认拒绝策略。
- 不要将 ee/ 私有实现、客户信息、内部部署细节复制到公开文档。
```

验收标准：

1. 文件存在。
2. `alwaysApply: true`。
3. 不超过 20 行正文。
4. 不包含长篇安全解释。
5. 覆盖 secrets、日志脱敏、生产配置、权限默认拒绝、EE 私有信息边界。

## 7. CODEMAP 详细需求

## 7.1 `.cursor/context/backend-codemap.md`

用途：后端任务短索引。
长度：200～400 行。

必须包含章节：

```md
# Backend CODEMAP

## 子系统职责

## 常用入口

## API 修改默认路径

## 数据模型与迁移

## Runtime v2

## 权限与租户边界

## 常见任务读取范围

## 禁止默认读取

## 常用命令
```

建议内容方向：

```md
# Backend CODEMAP

## 子系统职责

nodeskclaw-backend 是 NoDeskClaw 的 FastAPI 后端，负责 API、认证依赖、Workspace、Instance、Runtime、K8s 编排、审计、任务状态、SSE、用量汇总等服务端能力。

## 常用入口

- app/main.py：FastAPI app / lifespan / 中间件。
- app/api/router.py：公共 API 与 Admin API 聚合。
- app/core/deps.py：权限与 DB 依赖。
- app/core/config.py：后端配置。
- app/core/feature_gate.py：CE/EE 功能判断。
- app/db/session.py：数据库 Session。
- app/models/：SQLAlchemy ORM。
- app/schemas/：Pydantic 请求/响应。
- app/services/：业务逻辑。

## API 修改默认路径

1. app/api/<domain>.py
2. app/schemas/<domain>.py
3. app/services/<domain>_service.py
4. app/models/<domain>.py
5. tests/
6. alembic/versions/（如涉及 Model）

## 数据模型与迁移

- 修改 model 字段时检查 app/models。
- 修改 schema 时检查 app/schemas。
- 修改持久化行为时检查 service 与 migration。
- 新增字段必须考虑默认值、nullable、索引、唯一约束、租户隔离。
- 涉及删除语义时优先软删除。

## Runtime v2

- app/services/runtime/registries：运行时注册表。
- app/services/runtime/adapters：运行时适配器。
- app/services/runtime/messaging：消息与事件。
- app/services/runtime/context_bridges：上下文桥接。
- app/services/runtime/compute：计算资源与实例调度。
- app/services/runtime/...：只在 Runtime 任务中读取，不要默认读取全部。

## 权限与租户边界

- 所有 workspace、instance、profile、task、usage 数据必须考虑 tenant/workspace/user 边界。
- API 层负责鉴权入口，service 层负责业务约束。
- 管理员 API 与用户 API 不混用。
- 默认拒绝未授权访问。

## 常见任务读取范围

### 修改普通 API
读取：
- app/api/<domain>.py
- app/schemas/<domain>.py
- app/services/<domain>_service.py
- app/models/<domain>.py
- tests/

### 修改实例运行时
读取：
- app/api/instances*.py
- app/services/runtime/**
- app/services/k8s*.py
- app/models/instance*.py
- app/schemas/instance*.py

### 修改权限
读取：
- app/core/deps.py
- app/core/feature_gate.py
- app/services/*permission*
- app/models/user*.py
- app/models/workspace*.py

## 禁止默认读取

- nodeskclaw-portal/
- nodeskclaw-llm-proxy/
- ee/
- openclaw/
- vibecraft/
- hermes-agent/
- node_modules/
- dist/

除非任务明确要求跨端联调，不要读取以上目录。

## 常用命令

- 后端测试：在 nodeskclaw-backend 目录执行 pytest。
- 静态检查：按项目现有 pyproject / ruff / mypy 配置执行。
- 迁移检查：涉及 model 时检查 alembic/versions。
```

验收标准：

1. 文件存在。
2. 控制在 200～400 行。
3. 有明确常用入口。
4. 有 API 修改默认路径。
5. 有 Runtime v2 指引。
6. 有禁止默认读取范围。
7. 没有复制 README 长段落。

## 7.2 `.cursor/context/portal-codemap.md`

用途：Portal 前端任务短索引。
长度：200～400 行。

必须包含章节：

```md
# Portal CODEMAP

## 子系统职责

## 常用入口

## 页面修改默认路径

## API 调用路径

## 状态管理

## i18n 与 UI 规范

## 常见任务读取范围

## 禁止默认读取

## 常用命令
```

建议内容方向：

```md
# Portal CODEMAP

## 子系统职责

nodeskclaw-portal 是 NoDeskClaw 的用户门户，负责 Workspace、Instance、Profile、任务、文件、运行状态、设置、组织、用量等前端页面。

## 常用入口

- src/main.ts：应用入口。
- src/router/：路由配置。
- src/views/：页面级组件。
- src/components/：复用组件。
- src/services/：API 调用封装。
- src/stores/：Pinia 状态。
- src/i18n/：多语言文案。
- src/types/：类型定义。

## 页面修改默认路径

1. src/router/
2. src/views/<domain>/
3. src/components/<domain>/
4. src/services/<domain>.ts
5. src/stores/<domain>.ts
6. src/i18n/
7. src/types/

## API 调用路径

- 页面组件不要直接散落 fetch/axios 逻辑。
- 新 API 调用优先放入 src/services。
- 请求和响应类型放入 src/types 或 service 局部类型。
- 后端 API 变更时，需要检查对应 service 与页面调用。

## 状态管理

- 跨页面共享状态使用 Pinia。
- 页面局部状态留在组件内。
- 长列表、筛选、分页、当前 workspace/instance 状态要避免重复请求。
- 修改 store 时检查所有引用页面。

## i18n 与 UI 规范

- 用户可见文案必须走 vue-i18n。
- 中文和英文文案都要补齐。
- 图标使用 lucide-vue-next。
- 不使用 emoji 作为正式 UI 图标。
- Tailwind class 保持可读，复杂样式抽组件。

## 常见任务读取范围

### 修改页面
读取：
- src/router/
- src/views/<page>.vue
- src/components/<domain>/
- src/services/<domain>.ts
- src/stores/<domain>.ts
- src/i18n/

### 修改 API 对接
读取：
- src/services/<domain>.ts
- src/types/
- 相关页面组件
- 必要时读取 backend 对应 schema，但不要全量读取 backend。

### 修改导航或布局
读取：
- src/router/
- layout 相关组件
- sidebar/nav 相关组件
- 权限判断相关 store

## 禁止默认读取

- nodeskclaw-backend/
- nodeskclaw-llm-proxy/
- ee/
- openclaw/
- vibecraft/
- hermes-agent/
- node_modules/
- dist/

除非任务明确要求跨端联调，不要读取以上目录。

## 常用命令

- 安装依赖：pnpm install 或项目既有包管理命令。
- 本地运行：使用项目现有 dev 脚本。
- 类型检查：按 package.json 中 typecheck 脚本执行。
- 构建检查：按 package.json 中 build 脚本执行。
```

验收标准：

1. 文件存在。
2. 控制在 200～400 行。
3. 有页面修改默认路径。
4. 有 i18n、lucide、services、Pinia 规则。
5. 有禁止默认读取范围。

## 7.3 `.cursor/context/llm-proxy-codemap.md`

用途：LLM Proxy 任务短索引。
长度：200～400 行。

必须包含章节：

```md
# LLM Proxy CODEMAP

## 子系统职责

## 常用入口

## 请求链路

## 用量与额度

## 常见任务读取范围

## 禁止默认读取

## 常用命令
```

建议内容方向：

```md
# LLM Proxy CODEMAP

## 子系统职责

nodeskclaw-llm-proxy 负责 LLM 请求转发、鉴权、额度、用量记录、模型路由和代理层错误处理。它不应承载 Portal UI 逻辑，也不应直接耦合后端业务页面。

## 常用入口

- app/main.py：服务入口。
- app/config.py：配置。
- app/models.py：本地数据模型或记录结构。
- app/proxy.py：代理请求核心逻辑。
- app/*usage*：用量统计。
- app/*quota*：额度控制。
- tests/：代理层测试。

实际路径以仓库当前文件为准。生成 CODEMAP 时需要读取 nodeskclaw-llm-proxy 目录确认。

## 请求链路

1. 接收上游请求。
2. 校验调用身份、tenant、workspace 或 token。
3. 检查额度与策略。
4. 转发到目标模型提供商。
5. 记录用量、错误、耗时和响应状态。
6. 返回兼容格式。

## 用量与额度

- 额度判断必须在转发前完成。
- 用量记录必须考虑失败请求、流式请求、中断请求。
- 错误码需要稳定，方便 Portal 和 Backend 展示。
- 不要在日志里输出 API Key、Authorization、完整 prompt。

## 常见任务读取范围

### 修改模型路由
读取：
- app/config.py
- app/proxy.py
- app/*provider*
- app/*model*

### 修改额度
读取：
- app/*quota*
- app/*usage*
- app/models.py
- tests/

### 修改错误处理
读取：
- app/proxy.py
- app/main.py
- app/*error*
- tests/

## 禁止默认读取

- nodeskclaw-backend/
- nodeskclaw-portal/
- ee/
- openclaw/
- vibecraft/
- hermes-agent/
- node_modules/
- dist/

除非任务明确要求联调，不要读取以上目录。

## 常用命令

- 测试：在 nodeskclaw-llm-proxy 目录执行项目现有测试命令。
- 运行：按该目录 README 或 package/script 配置执行。
```

验收标准：

1. 文件存在。
2. 控制在 200～400 行。
3. 明确 LLM Proxy 不承载 UI 和后端业务逻辑。
4. 有请求链路、用量、额度、错误处理指引。
5. 有禁止默认读取范围。

## 7.4 `.cursor/context/runtime-codemap.md`

用途：Runtime、K8s、Channel 插件、Agent Gateway 集成任务短索引。
长度：200～400 行。

必须包含章节：

```md
# Runtime CODEMAP

## 子系统职责

## 后端 Runtime v2 入口

## Channel 插件

## Hermes / OpenClaw / Vibecraft 边界

## 常见任务读取范围

## 禁止默认读取

## 常用命令
```

建议内容方向：

```md
# Runtime CODEMAP

## 子系统职责

Runtime 相关代码负责 NoDeskClaw 实例生命周期、运行时适配器、K8s 编排、消息事件、上下文桥接、Channel 插件和外部 Agent 运行时集成。

## 后端 Runtime v2 入口

优先从 backend runtime service 读取：

- nodeskclaw-backend/app/services/runtime/registries
- nodeskclaw-backend/app/services/runtime/adapters
- nodeskclaw-backend/app/services/runtime/messaging
- nodeskclaw-backend/app/services/runtime/context_bridges
- nodeskclaw-backend/app/services/runtime/compute
- nodeskclaw-backend/app/api/instances*
- nodeskclaw-backend/app/schemas/instance*
- nodeskclaw-backend/app/models/instance*

实际路径以仓库当前文件为准，必要时用 rg 限定在 nodeskclaw-backend/app/services/runtime 下搜索。

## Channel 插件

- openclaw-channel-* 是运行时 Channel 插件目录。
- 只有在任务明确涉及 Channel 协议、插件注册、消息收发、运行时适配时才读取。
- 不要为了普通 backend 或 portal 任务读取全部 Channel 插件。

## Hermes / OpenClaw / Vibecraft 边界

- openclaw/、vibecraft/、hermes-agent/ 是外部源码或运行时参考目录。
- 默认不读取。
- 需要集成接口时，只读取入口协议、adapter、README 或明确指定文件。
- 不要把外部运行时内部实现复制进 NoDeskClaw。
- NoDeskClaw 后端应通过 adapter / gateway / bridge 接入外部运行时。

## 常见任务读取范围

### 修改实例生命周期
读取：
- backend app/api/instances*
- backend app/services/runtime/**
- backend app/models/instance*
- backend app/schemas/instance*

### 修改 K8s 编排
读取：
- backend app/services/runtime/compute
- backend app/services/*k8s*
- backend app/core/config.py
- 相关测试

### 修改 Channel 插件
读取：
- 指定 openclaw-channel-* 目录
- backend runtime adapter 中对应桥接代码
- 不读取所有 channel 插件

### 修改 Hermes 集成
读取：
- backend runtime adapter / gateway / bridge 相关文件
- 必要时读取 hermes-agent 的接口文档或入口文件
- 不读取 hermes-agent 全仓

## 禁止默认读取

- nodeskclaw-portal/
- nodeskclaw-llm-proxy/
- ee/
- openclaw/
- vibecraft/
- hermes-agent/

除非任务明确要求，不要读取以上目录。

## 常用命令

- 后端测试：在 nodeskclaw-backend 中执行相关 pytest。
- Runtime 搜索：rg "<keyword>" nodeskclaw-backend/app/services/runtime
- Channel 搜索：rg "<keyword>" openclaw-channel-<target>
```

验收标准：

1. 文件存在。
2. 控制在 200～400 行。
3. 明确 Runtime v2 的后端入口。
4. 明确 Channel 插件读取边界。
5. 明确 Hermes / OpenClaw / Vibecraft 默认不读取。

## 8. Cursor 执行策略

Cursor 在执行本 PRD 时必须遵守：

1. 先列出当前 `.cursor/rules` 文件。
2. 读取现有规则，识别需要保留的唯一约束。
3. 不要全仓扫描。
4. 使用限定目录搜索：

   * `rg "soft delete|软删除" .cursor AGENTS.md CLAUDE.md`
   * `rg "Alembic|migration" .cursor AGENTS.md CLAUDE.md`
   * `rg "i18n|vue-i18n|lucide" .cursor AGENTS.md CLAUDE.md`
   * `rg "feature_gate|features.yaml|EE|CE" .cursor AGENTS.md CLAUDE.md`
5. 创建或覆盖目标 5 个 rules 文件。
6. 创建 `.cursor/context` 目录。
7. 为 4 个子系统创建 CODEMAP。
8. CODEMAP 可以用 `find` 或 `rg --files` 限定在目标子目录中确认真实路径，但不得全仓展开。
9. 输出变更文件清单。
10. 输出后续使用说明。

## 9. 验收标准

### 9.1 文件验收

必须存在：

```text
.cursor/rules/00-project-map.mdc
.cursor/rules/10-backend.mdc
.cursor/rules/20-portal.mdc
.cursor/rules/30-ee-boundary.mdc
.cursor/rules/90-security.mdc

.cursor/context/backend-codemap.md
.cursor/context/portal-codemap.md
.cursor/context/llm-proxy-codemap.md
.cursor/context/runtime-codemap.md
```

### 9.2 Rules 验收

1. `00-project-map.mdc` 是 `alwaysApply: true`。
2. `90-security.mdc` 是 `alwaysApply: true` 且正文不超过 20 行。
3. `10-backend.mdc` 是 `alwaysApply: false` 且只匹配后端 Python。
4. `20-portal.mdc` 是 `alwaysApply: false` 且只匹配 Portal Vue/TS。
5. `30-ee-boundary.mdc` 是 `alwaysApply: false` 且只匹配 EE / feature gate 相关文件。
6. 不存在冗长 alwaysApply 规则。
7. 不存在要求默认读取全局 Skill 的规则。
8. 不存在要求默认全仓扫描的规则。

### 9.3 CODEMAP 验收

1. 每个 CODEMAP 都有明确子系统职责。
2. 每个 CODEMAP 都有常用入口。
3. 每个 CODEMAP 都有常见任务读取范围。
4. 每个 CODEMAP 都有禁止默认读取范围。
5. 每个 CODEMAP 控制在 200～400 行。
6. CODEMAP 不包含业务代码实现细节。
7. CODEMAP 不复制 README 长段落。

### 9.4 使用验收

后续 Cursor 任务应按以下方式启动：

后端任务：

```text
先读取 @.cursor/context/backend-codemap.md
只读取本任务相关的 3～8 个后端目标文件
不要扫描 portal、llm-proxy、ee、openclaw、vibecraft、hermes-agent
```

Portal 任务：

```text
先读取 @.cursor/context/portal-codemap.md
只读取本任务相关的页面、service、store、i18n 文件
不要扫描 backend、llm-proxy、ee、openclaw、vibecraft、hermes-agent
```

LLM Proxy 任务：

```text
先读取 @.cursor/context/llm-proxy-codemap.md
只读取 proxy、config、usage、quota、tests 相关文件
不要扫描 portal、backend 全量、ee、openclaw、vibecraft、hermes-agent
```

Runtime 任务：

```text
先读取 @.cursor/context/runtime-codemap.md
只读取 runtime adapter、gateway、bridge、K8s、指定 channel 插件
不要扫描外部运行时全仓
```

## 10. 风险与控制

### 10.1 风险：规则过短导致 Cursor 漏掉项目约束

控制方式：

* 保留关键约束：软删除、Alembic、API 错误结构、K8s context、i18n、CE/EE、安全。
* 详细结构放入 CODEMAP，而不是 alwaysApply。

### 10.2 风险：CODEMAP 路径与真实仓库不一致

控制方式：

* 生成 CODEMAP 前用 `rg --files <目标目录>` 限定子目录确认路径。
* 如果路径不存在，写“实际路径待确认”，不要编造文件。

### 10.3 风险：旧规则删除后丢失关键规范

控制方式：

* 删除旧规则前做一次规则内容对照。
* 唯一约束必须迁移到 5 个目标规则之一。
* 重复约束只保留一处。

### 10.4 风险：Cursor 仍然全仓扫描

控制方式：

* `00-project-map.mdc` 明确禁止全仓扫描。
* 每个 CODEMAP 都写禁止默认读取范围。
* 后续任务提示必须显式指定 CODEMAP 和目标文件。

## 11. Definition of Done

当以下条件全部满足，任务完成：

1. `.cursor/rules` 已收敛为目标 5 个规则文件，或旧规则已被合理迁移并说明。
2. `.cursor/context` 已新增 4 个 CODEMAP。
3. alwaysApply 规则只剩极简项目地图和短安全规则。
4. Backend、Portal、EE、Security 规则按 globs 精准触发。
5. CODEMAP 能指导 Cursor 在任务开始时读取最小上下文。
6. 文档中没有真实密钥、私有 token、客户数据、生产连接信息。
7. 输出最终变更清单和使用说明。

## 12. 交付输出格式

Cursor 完成后请输出：

```md
## 变更文件

- .cursor/rules/00-project-map.mdc
- .cursor/rules/10-backend.mdc
- .cursor/rules/20-portal.mdc
- .cursor/rules/30-ee-boundary.mdc
- .cursor/rules/90-security.mdc
- .cursor/context/backend-codemap.md
- .cursor/context/portal-codemap.md
- .cursor/context/llm-proxy-codemap.md
- .cursor/context/runtime-codemap.md

## 已迁移旧规则

列出从旧规则迁移到新规则的关键约束。

## 已删除或不再使用的旧规则

列出删除文件和原因。

## 后续 Cursor 使用方式

说明不同任务应先读取哪个 CODEMAP，以及默认禁止读取哪些目录。

## 风险说明

说明是否存在路径未确认、旧规则未完全迁移、需要人工复核的内容。
```
