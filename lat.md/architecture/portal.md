# Portal Architecture

`nodeskclaw-portal` 是 CE/EE 共用用户门户：工作区、实例、组织设置、Gene 市场、任务与用量等页面。

技术栈：Vue 3、Vite、TypeScript、Tailwind、Pinia、vue-i18n、Three.js。改码定位用 `.cursor/context/portal-codemap.md`。

## Page Domains

页面按域分目录：实例、工作区、组织设置、Gene、Auth、黑板、Hermes 等。

Hermes Skills 运营页负责工作副本与 **SkillRelease** 发布/废弃（员工 MCP 只见 published）；注册到组织 MCP 只写工作副本 + draft，不自动 published（见 [[decisions/skill-platform-execution]]）。

Hermes Connectors（`/hermes/connectors`）与 Edge 节点（`/hermes/edge-nodes`）运营页管理 Connector 定义/实例/公开 Tool、SecretRef 元数据与 Edge 登记；Portal 不收集密钥明文。API 封装见 [[nodeskclaw-portal/src/api/hermes/connectors.ts]]。

标准触及链：`router` → `views` → `components` → `services` → `stores` → `i18n` → `types`。跨页状态用 Pinia（`useXxxStore`），局部状态留在组件内。

## API Client Rules

页面禁止散落 fetch/axios；一律经 `src/services/<domain>.ts`，底层走 `src/api` 的 axios 实例。

请求必须带 `Accept-Language`。错误优先用后端 `message_key` 翻译，缺失回退 `message`。后端 Schema 变更时同步检查 service 与页面。

## I18n And UX

用户可见文案必须走 i18n；禁止新增硬编码中文 UI（专有名词除外）。

message_key 小写点分层（如 `errors.auth.token_invalid`），插值用命名参数。图标统一 `lucide-vue-next`，禁止 emoji。空状态与错误必须可操作引导。

## Visualization

Hex2D / Hex3D 与工作区可视化依赖 `src/lib` 的 Three.js 场景；它们展示协作拓扑，不替代 REST 状态源。

可视化只读后端权威状态；部署中、失败等以实例/工作区 API 为准，避免用动画状态冒充运行时真相。
