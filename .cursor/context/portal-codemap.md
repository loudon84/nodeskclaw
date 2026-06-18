# Portal CODEMAP

## 子系统职责

nodeskclaw-portal 是 NoDeskClaw 的用户门户，负责 Workspace、Instance、Profile、任务、文件、运行状态、设置、组织、用量等前端页面。技术栈：Vue 3 + Vite + TypeScript + Tailwind CSS + Pinia + vue-i18n + Three.js。

## 常用入口

| 文件/目录 | 用途 | 修改频率 |
|------|------|------|
| `src/main.ts` | 应用入口、插件注册、全局配置 | 低 |
| `src/App.vue` | 根组件，layout 壳 | 低 |
| `src/router/` | 路由配置，定义页面路径与懒加载 | 中 |
| `src/views/` | 页面级组件，按功能域分目录 | 高 |
| `src/components/` | 可复用组件 | 高 |
| `src/services/` | API 调用封装 | 高 |
| `src/stores/` | Pinia 状态管理 | 中 |
| `src/api/` | API 请求工具封装（axios 实例、拦截器） | 低 |
| `src/composables/` | 组合式函数 | 中 |
| `src/i18n/` | 多语言文案 | 高 |
| `src/i18n/locales/` | 各语言词条文件 | 高 |
| `src/types/` | TypeScript 类型定义 | 中 |
| `src/lib/` | 工具库（Three.js 场景、图表等） | 低 |
| `src/utils/` | 通用工具函数 | 低 |
| `src/styles/` | 全局样式 | 低 |

## 页面索引

`src/views/` 下的页面文件按功能域分组：

**实例**：
- `InstanceList.vue` — 实例列表
- `InstanceDetail.vue` — 实例详情
- `InstanceLayout.vue` — 实例布局（Tab 容器）
- `CreateInstance.vue` — 创建实例
- `InstanceSettings.vue` — 实例设置
- `InstanceMembers.vue` — 实例成员管理
- `InstanceFiles.vue` — 实例文件
- `InstanceGenes.vue` — 实例 Gene 管理
- `InstanceRuntime.vue` — 实例运行时
- `InstanceBackups.vue` — 实例备份
- `DeployProgress.vue` — 部署进度

**工作区**：
- `WorkspaceList.vue` — 工作区列表
- `WorkspaceView.vue` — 工作区视图（主操作界面）
- `WorkspaceSettings.vue` — 工作区设置
- `CreateWorkspace.vue` — 创建工作区

**组织**：
- `OrgInfo.vue` — 组织信息
- `OrgMembers.vue` — 组织成员
- `OrgSettings.vue` — 组织设置入口
- `OrgSettingsAudit.vue` — 审计日志
- `OrgSettingsClusters.vue` — 集群管理
- `OrgSettingsEngineVersions.vue` — 引擎版本管理
- `OrgSettingsGenes.vue` — Gene 管理
- `OrgSettingsLlmKeys.vue` — LLM Key 管理
- `OrgSettingsNetwork.vue` — 网络配置
- `OrgSettingsRegistry.vue` — Registry 配置
- `OrgSettingsSmtp.vue` — SMTP 配置
- `OrgSettingsSpecs.vue` — Spec 预设
- `OrgSettingsUpload.vue` — 上传配置

**Gene**：
- `GeneMarket.vue` — Gene 市场
- `GeneDetail.vue` — Gene 详情
- `GenomeDetail.vue` — Genome 详情

**Auth / 用户**：
- `Login.vue` — 登录
- `AcceptInvite.vue` — 接受邀请
- `ForceChangePassword.vue` — 强制修改密码
- `Settings.vue` — 个人设置

**其他**：
- `Home.vue` — 首页
- `ClusterDetail.vue` — 集群详情
- `ExternalDockerDetail.vue` — 外部 Docker 详情
- `EvolutionLog.vue` — 进化日志
- `AgentPerformance.vue` — Agent 性能
- `MemberManagement.vue` — 成员管理
- `TemplateDetail.vue` — 模板详情

**按域分组的子目录**：
- `audit/` — 审计页面组件
- `blackboard/` — 黑板协作页面
- `chat/` — 聊天页面
- `gene/` — Gene 相关页面
- `hex2d/` — 2D 六边形可视化
- `hex3d/` — 3D 六边形可视化
- `members/` — 成员页面
- `shared/` — 复用页面组件
- `ui/` — UI 演示/调试页面
- `workspace/` — 工作区页面组件
- `external-docker/` — 外部 Docker 页面
- `hermes/` — Hermes 页面

## 页面修改默认路径

修改一个功能域的标准触及文件链：

1. `src/router/` — 路由定义
2. `src/views/<domain>/` — 页面组件
3. `src/components/<domain>/` — 领域组件
4. `src/services/<domain>.ts` — API 调用
5. `src/stores/<domain>.ts` — Pinia store
6. `src/i18n/locales/` — 多语言词条
7. `src/types/` — TypeScript 类型定义

## API 调用路径

- 页面组件不要直接散落 fetch/axios 逻辑。所有 API 调用统一通过 `src/services/` 中封装的函数。
- 新 API 调用优先放入 `src/services/<domain>.ts`，与后端 API 路由域对应。
- `src/api/api.ts` 是基础 axios 实例和拦截器，配置统一的 baseURL、headers、错误处理。
- 请求参数和响应数据类型放入 `src/types/` 或 service 文件局部类型。
- 后端 API 变更（Schema 字段、错误码、接口路径）时，需要同步检查对应 service 封装与页面调用。
- API 请求必须携带 `Accept-Language` 语言请求头。
- 错误展示优先使用后端 `message_key` 经 i18n 翻译，词条缺失时回退 `message`。

## 状态管理

`src/stores/` 下的主要 store：

- `auth.ts` — 认证状态（token、user、login/logout）
- `workspace.ts` — 当前工作区状态
- `instance.ts` — 当前实例状态
- `cluster.ts` — 集群状态
- `org.ts` — 组织状态
- `gene.ts` — Gene 状态
- `memberManagement.ts` — 成员管理状态

使用规则：
- 跨页面共享状态使用 Pinia store（`src/stores/`）。
- 页面局部状态留在组件内（`ref`、`reactive`）。
- 长列表、筛选、分页、当前 workspace/instance 状态要避免重复请求（store 缓存 + 手动刷新）。
- 修改 store 时检查所有引用该 store 的页面和组件。
- Store 命名约定：`use<Domain>Store`（如 `useInstanceStore`、`useWorkspaceStore`）。

## i18n 与 UI 规范

### i18n 规则

- 用户可见文案必须走 vue-i18n（`t('...')`），不允许硬编码中文（专有名词除外）。
- message_key 用小写点分层：`errors.auth.token_invalid`、`notices.instance.restart_submitted`。
- 一律使用命名参数插值：`t('errors.instance.not_found', { name })`。
- 计数文案统一使用 `count` 参数。
- 中文和英文词条都要补齐（`zh-CN.ts`、`en-US.ts`）。

### UI 规范

- 图标使用 lucide-vue-next（按需导入），不使用 emoji。
- 禁止给 `<button>` 元素手动加 `cursor-pointer`（全局 CSS 已在 `globals.css` 的 `@layer base` 中覆盖）。
- 非按钮可点击元素（`<div @click>`、`<span @click>`、`<label>`）仍需手动加 `cursor-pointer`。
- 滚动条走全局定义（`overflow-y-auto`），组件内禁止自定义 `::-webkit-scrollbar`。紧凑场景使用 `.scrollbar-compact` 类。
- 下拉选择使用自定义 button-based dropdown（`<button @click="open = !open">` + 下拉面板 `<div v-if="open">`），禁止原生 `<select>`。
- Tailwind class 保持可读，复杂样式抽组件。

## 常见任务读取范围

### 修改页面或新增页面
读取：
- `src/router/`
- `src/views/<page>.vue`
- `src/components/<domain>/`
- `src/services/<domain>.ts`
- `src/stores/<domain>.ts`
- `src/i18n/locales/zh-CN.ts`
- `src/i18n/locales/en-US.ts`

### 修改 API 对接
读取：
- `src/services/<domain>.ts`
- `src/api/api.ts`
- `src/types/`
- 相关页面组件（调用方）
- 必要时读取 backend 对应 schema（`nodeskclaw-backend/app/schemas/<domain>.py`），但不要全量读取 backend。

### 修改导航或布局
读取：
- `src/router/`
- `src/App.vue`
- layout 相关组件
- sidebar/nav 相关组件
- 权限判断相关 store（`src/stores/auth.ts`）

### 新增 i18n 词条
读取：
- `src/i18n/locales/zh-CN.ts`
- `src/i18n/locales/en-US.ts`
- 涉及页面/组件中 `t('...')` 调用处

### 修改全局样式
读取：
- `src/styles/`
- `tailwind.config.*`
- 受影响的组件

## 路由结构

`src/router/` 定义了应用的完整路由表。路由按功能域组织：

- 公开路由：`/login`、`/accept-invite`
- 认证路由：`/force-change-password`
- 工作区路由：`/workspaces`、`/workspaces/:id`、`/workspaces/:id/settings`
- 实例路由：`/instances`、`/instances/:id`（嵌套多个子路由 Tab）
- 组织路由：`/org/*`（设置、成员、集群、Gene、LLM Key 等子页面）
- 其他：`/gene-market`、`/settings`、`/template/:id`、`/cluster/:id`

修改路由时需同时检查：
- 路由守卫（auth required、role required）
- 面包屑导航
- 侧边栏高亮状态
- 权限判断逻辑（store 中的 user role）

## 组件目录索引

`src/components/` 下的主要组件域：

- UI 组件（按钮、输入框、弹窗、下拉菜单等基础组件）
- 实例组件（实例卡片、日志面板、终端组件）
- 工作区组件（工作区表单、成员列表）
- 布局组件（侧边栏、顶栏、面包屑）
- 六边形可视化组件（2D/3D）

组件复用原则：
- 跨页面复用的组件放入 `src/components/`
- 单页面使用的组件放在对应 `src/views/<domain>/` 目录内
- 先检查是否已有可复用组件，避免重复造轮子

## 禁止默认读取

- `nodeskclaw-backend/`
- `nodeskclaw-llm-proxy/`
- `ee/`
- `openclaw/`
- `vibecraft/`
- `hermes-agent/`
- `node_modules/`
- `dist/`

除非任务明确要求跨端联调，不要读取以上目录。

## 常用命令

```bash
cd nodeskclaw-portal
npm install                    # 安装依赖
npm run dev                    # 开发服务器（默认 localhost:4517）
npm run build                  # 生产构建
npm run test                   # 运行所有测试（vitest）
npm run test:watch             # 监听模式
npm run test -- --run src/components/xxx.spec.ts  # 运行单个测试
vue-tsc -b                     # 类型检查
```
