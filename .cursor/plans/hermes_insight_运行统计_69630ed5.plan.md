---
name: Hermes Insight 运行统计
overview: 在 Hermes Agent 详情页【运行状态】Tab 内新增 Insight 统计区块，后端在现有 /hermes/agents/{profile_name} 路由族下新增 insight 子模块（Python/FastAPI），按 profile 独立 HERMES_HOME 读取 state.db 与 webui/sessions/_index.json 做最近 30 天用量统计，并采集 Docker 容器与 profile 运行时状态，全程只读、可降级、不泄漏密钥。
todos:
  - id: resolver
    content: Phase 1：新增 insight 子模块目录与 safe_path（基于 resolve_profile_from_host_data_dir 推导 state.db/_index.json 路径并做越界校验），复用 host_dir_from_agent 与现有 profile 列表
    status: completed
  - id: usage
    content: Phase 2：实现 sqlite_readonly 只读工具与 UsageCollector（state.db introspect+聚合、_index.json fallback、去重、30天cutoff、daily/model 聚合、warning）
    status: completed
  - id: runtime
    content: Phase 3：实现 ContainerHealthCollector（复用 inspect + 新增 docker stats/磁盘）与 ProfileRuntimeCollector（状态枚举判定）
    status: completed
  - id: api
    content: Phase 4：定义 hermes_insight schemas，实现 HermesInsightService（all 聚合/单 profile/短缓存），新增 insight_router 并注册 GET /agents/{profile_name}/insight
    status: completed
  - id: frontend
    content: Phase 5：新增 insight.ts API、AgentRuntimeInsightPanel.vue（含工具条/卡片/CSS图表/表格/降级态），接入 AgentDetailView 运行状态 Tab，新增 hermes.insight.* i18n 词条
    status: completed
  - id: tests
    content: Phase 6：补齐后端 usage/runtime/container/service 单测（tmp_path + mock subprocess）
    status: completed
  - id: docs
    content: 同步后端 README 与 ee/docs 后端架构/API 文档的 insight 章节
    status: completed
isProject: false
---

## Hermes Insight 运行统计能力（PRD v5.0 裁剪版）

### 关键适配决策（PRD ↔ 本仓库）

- 后端为 **Python/FastAPI**（非 PRD 的 Nest/TS），路由前缀 `/api/v1`，响应包统一 `{code, message, data}`。
- PRD 的 `instanceId` ≈ 本仓库 Hermes Agent 的 **`profile_name`**（如 `common-writer`）；PRD 的 `profile` ≈ 文件系统子 profile（`default` / `writer-zh` …）。
- Insight API 复用现有 Agent 路由族：`GET /api/v1/hermes/agents/{profile_name}/insight`（鉴权 `require_org_member` + `hermes_agent:view`，前端无需改路由）。
- profile 选择器复用现有 `GET /api/v1/hermes/agents/{profile_name}/profiles`；profile 级 runtime 细节由 insight 响应内 `profiles[]` 提供。
- `state.db` / `webui/sessions/_index.json` 在 external docker 下本仓库无任何依赖，按 PRD 假定路径 `{profile_dir}/state.db`、`{profile_dir}/webui/sessions/_index.json` **防御式**实现：表/字段缺失降级为空统计 + warning，schema 不兼容回退 `_index.json`。

### 复用的现有能力

- `[_agent_profile_context.py](nodeskclaw-backend/app/api/hermes_skill/_agent_profile_context.py)`：`host_dir_from_agent()` 返回 `(host_data_dir, record, instance)`，`host_data_dir_context()` 提供 `container_name`、`gateway_url`。
- `[path_resolver.py](nodeskclaw-backend/app/services/hermes_external/path_resolver.py)`：`HermesExternalPathResolver.resolve_profile_from_host_data_dir(host_data_dir, profile)` → `HermesProfilePaths.profile_dir`，自带 `ensure_profile_dir_safe()` / `validate_profile_path()` 路径越界与软链接校验。
- `[profile_service.py](nodeskclaw-backend/app/services/hermes_external/profile_service.py)`：`list_profiles()` / `list_profiles_for_host_data_dir()` 列举 profiles。
- `[docker_container_inspect_service.py](nodeskclaw-backend/app/services/hermes_external/docker_container_inspect_service.py)`：`docker inspect` 取 status/health/端口。

---

## 前端表现变化

#### 1. Hermes Agent 详情页 →【运行状态】Tab 新增 Insight 区块

**总结**：运行状态 Tab 从「仅一张 Docker 探活卡片（状态/Health/最后探活/刷新状态按钮）」扩展为「Container Runtime + Profile Runtime + Insight 统计面板」三段式，新增近 30 天 sessions/messages/tokens/cost 统计与图表。

**元素级变化**：
- Container Runtime 卡片：在现有 Docker 状态/Health 基础上**新增** CPU%、内存（已用/上限/百分比）、磁盘（已用/总量/百分比）、端口列表、最后探活时间；Docker stats 不可用时显示「Docker stats 不可用」占位，不报错。
- Profile Runtime 区块：**新增**，以网格/列表展示每个 profile 的状态 pill（running / idle / configured / missing / error / unknown）、API Server 端口、state.db 是否存在、最后写入时间。
- Insight 工具条：**新增** Profile 选择器（自定义 button dropdown，选项 `全部 / default / writer-zh / …`，默认「全部」）+「刷新」按钮；**明确不含**时间范围选择器，旁边固定文案「最近 30 天」。
- Overview 卡片：**新增** 4 张统计卡（Sessions / Messages / Tokens / Estimated Cost）。
- Daily Token Trend：**新增**，CSS bar chart（不引入图表库），固定最近 30 天。
- Token Breakdown：**新增**，展示 input / output / cacheRead / cacheWrite tokens。
- Model Usage 表：**新增**；`profile=all` 时**显示 profileName 列**，含 sessionShare / tokenShare / costShare。
- Profile Usage 表：**新增**，展示每个 profile 的 sessions/messages/tokens/cost。
- 状态变化：state.db 缺失时统计区显示「No usage data」空状态而非报错；加载中显示骨架/loading，失败显示 error 文案 + 重试。
- **不得出现**：LLM Wiki 卡片、时间范围选择器、Activity by Day/Hour、Skill Usage 卡片。

**改动前**（运行状态 Tab）：
```
┌─ 运行状态 ───────────────────────────────┐
│ ┌─ Docker ──────────────────────────────┐ │
│ │ [Docker: running] [Health: healthy]   │ │
│ │ 最后探活: 2026-06-17 ...              │ │
│ │ [刷新状态]                            │ │
│ └───────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

**改动后**：
```
┌─ 运行状态 ───────────────────────────────────────────┐
│ ┌─ Container Runtime ───────────────────────────────┐ │
│ │ [running] [healthy]  CPU 18%  MEM 25%  DISK 42%   │ │
│ │ 端口 8642,8787   最后探活 2026-06-17 07:39        │ │
│ └───────────────────────────────────────────────────┘ │
│ ┌─ Profile Runtime ─────────────────────────────────┐ │
│ │ default [running] 8642  state.db√  writer-zh[idle]│ │
│ └───────────────────────────────────────────────────┘ │
│ ┌─ Insight 工具条 ──────────────────────────────────┐ │
│ │ Profile:[全部 ▾]   最近 30 天   [刷新]            │ │
│ └───────────────────────────────────────────────────┘ │
│ [Sessions 98][Messages 5133][Tokens 100.5M][$1.29]    │
│ ┌─ Daily Token Trend (CSS bars, 30d) ───────────────┐ │
│ │ ▁▂▅▃▇▂▁ ...                                        │ │
│ └───────────────────────────────────────────────────┘ │
│ ┌ Token Breakdown ┐  ┌ Model Usage 表 (含 profile) ┐ │
│ │ in/out/cache    │  │ profile model sessions ...  │ │
│ └─────────────────┘  └─────────────────────────────┘ │
│ ┌─ Profile Usage 表 ────────────────────────────────┐ │
│ │ default  12  642  2.98M  $0.22                    │ │
│ └───────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

---

## 后端实施（Phase 1-4 + 6）

新增子模块目录 `nodeskclaw-backend/app/services/hermes_external/insight/`：

### Phase 1 — Profile Resolver 与 Profile 列表（复用为主）
- 复用 `host_dir_from_agent()` 得到 `host_data_dir` + `record`（含 `container_name`）。
- profile 列表沿用现有 `profile_service.list_profiles*()`，无需新建 manifest（本仓库 profile 为文件系统约定，已有扫描逻辑）。
- 新增 `safe_path` 辅助：基于 `resolve_profile_from_host_data_dir()` 推导 `state_db_path = profile_dir / "state.db"`、`webui_index_path = profile_dir / "webui" / "sessions" / "_index.json"`，并用 `validate_profile_path()` 校验越界/软链接。

### Phase 2 — Usage Collector（`usage_collector.py` + `sqlite_readonly.py`）
- `sqlite_readonly.py`：以 `file:{path}?mode=ro&immutable=1` URI 只读打开，设置 `busy_timeout` 与查询超时；只执行参数化 SELECT，禁止写/PRAGMA 修改；异常一律降级返回空 + warning。
- `collect_from_state_db(profile_dir)`：先 introspect `sessions` 表是否存在及字段集合，按 PRD 推荐字段（`id, model, message_count, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, estimated_cost_usd, started_at, ended_at, source, platform`）取并集；缺字段默认 0/None；`WHERE started_at >= :cutoff OR ended_at >= :cutoff`，`cutoff = now - 30d`。
- `collect_from_webui_index(profile_dir)`：读 `_index.json`（设文件大小上限，超限/失败跳过 + warning）。
- 去重：`dedupeKey = profile_name + ":" + source + ":" + sessionId`，state.db 优先，`_index.json` 仅补 state.db 缺失记录。
- 聚合：单 profile usage、daily tokens（按 date group，补齐 30 天）、models（按 `profileName+model` group 并计算 share）、tokenBreakdown。
- 常量 `INSIGHT_WINDOW_DAYS = 30`。

### Phase 3 — Runtime Collector（`runtime_collector.py` + `container_health_collector.py`）
- `container_health_collector.py`：复用 `DockerContainerInspectService` 取 status/health/端口；**新增** `docker stats --no-stream --format '{{json .}}'` 解析 CPU%/内存；磁盘用 `du -sb {host_data_dir}`（失败回退 `shutil.disk_usage`）；任一不可用降级为占位字段 + warning。
- `runtime_collector.py`：按 PRD 优先级判定 profile 状态（API Server 端口监听 / gateway pid / state.db 存在 / state.db mtime / `_index.json` / `config.yaml`）→ 枚举 `running|idle|configured|missing|error|unknown`；输出 `apiServerEnabled/apiServerPort/webuiPort/stateDbExists/configExists/webuiIndexExists/lastStateWriteAt/lastSessionAt`。

### Phase 4 — Insight Service 与 API
- `schemas.py`（落 `app/schemas/hermes_skill/hermes_insight.py`）：定义 `InsightResponse`、`ContainerRuntime`、`ProfileRuntime`、`UsageSummary`、`DailyTokenItem`、`ModelUsageItem`、`TokenBreakdown`、`InsightWarning` 等，字段严格对齐 PRD §10.2/10.3（`scope/instanceId/profileName/periodDays/generatedAt/container/profiles/usage/dailyTokens/models/tokenBreakdown/warnings`）。
- `service.py`：`HermesInsightService` 提供 `get_insight(host_data_dir, record, profile)`：`profile=all` → 遍历所有 profile 收集后 `aggregate`；指定 profile → 单 profile（`scope=profile`，`dailyTokens/models` 可空，按 PRD §10.3）。短缓存：profile insight TTL 15s、container stats TTL 5s、profiles TTL 30s；`refresh=true` 旁路缓存。
- 新增 `app/api/hermes_skill/insight_router.py`，注册到 `[router.py](nodeskclaw-backend/app/api/hermes_skill/router.py)`：
  - `GET /agents/{profile_name}/insight?profile=all&refresh=false`，固定 `periodDays=30`，传入 `days` 参数则忽略并记 warning。
  - instance 不存在 → `HERMES_INSTANCE_NOT_FOUND`（复用现有 NotFoundError 语义）；profile 不存在 → `HERMES_PROFILE_NOT_FOUND`；state.db 缺失不报 500，返回空 usage + `STATE_DB_NOT_FOUND` warning。
- 安全：响应永不含 `.env` / API key / API_SERVER_KEY / session 正文 / 绝对路径（如需展示路径用 masked path）。

### Phase 6 — 后端测试（`tests/hermes_skill/test_hermes_insight.py`，沿用 tmp_path 模式）
- UsageCollector：state.db 正常聚合 / 缺字段降级 / `_index.json` fallback / 去重 / 30 天 cutoff / model group / daily group。
- RuntimeCollector：running/idle/configured/missing/error 判定。
- ContainerHealthCollector：mock subprocess 覆盖 running / stopped / stats 不可用。
- Service：`profile=all` 聚合 = 各 profile 之和；单 profile scope。

---

## 前端实施（Phase 5）

- API 层：新增 `[insight.ts](nodeskclaw-portal/src/api/hermes/insight.ts)`，定义与后端对齐的类型 + `getHermesInsight(profileName, profile, refresh?)`，复用 `@/services/api`（baseURL `/api/v1`、`Accept-Language`、`unwrapEnvelope`、`resolveApiErrorMessage`）。
- 组件：新增 `[AgentRuntimeInsightPanel.vue](nodeskclaw-portal/src/views/hermes/AgentRuntimeInsightPanel.vue)`，内部含 Container Runtime 卡、Profile Runtime 网格、Insight 工具条（profile dropdown 参考 `ProfileActionBar.vue` 的 button dropdown 模式 + 刷新按钮）、4 张 Overview 卡（参考 `MetricsView` grid）、Daily Token CSS bar chart（参考 `AgentPerformance.vue` 进度条）、Token Breakdown、Model Usage 表、Profile Usage 表（参考 `TasksView` Table）；loading/empty/error 状态完整。
- 接入：在 `[AgentDetailView.vue](nodeskclaw-portal/src/views/hermes/AgentDetailView.vue)` 的 `activeTab === 'runtime'` 区块内，于现有 Docker 探活卡片之后插入 `<AgentRuntimeInsightPanel :profile-name="profileName" />`，并把现有探活卡片纳入 Container Runtime 区。Profile 选择器选项来自现有 `listProfiles(profileName)` + 「全部」。
- i18n：在 `[zh-CN.ts](nodeskclaw-portal/src/i18n/locales/zh-CN.ts)` 与 `[en-US.ts](nodeskclaw-portal/src/i18n/locales/en-US.ts)` 的 `hermes` 区块新增 `hermes.insight.*` 词条（标题、列名、状态、空态、错误、单位），均走 `t()`，无硬编码中文 UI 文案；图标用 `lucide-vue-next`。
- 自检：确认页面无 LLM Wiki / 时间范围选择器 / activity 图表 / Skill Usage。

---

## 文档同步

- 更新 `[nodeskclaw-backend/README.md](nodeskclaw-backend/README.md)`：补充 hermes insight 子模块说明与新端点。
- 同步后端架构设计文档（按仓库约定放 `ee/docs/`）的 Hermes 模块与 API 章节，补充 insight 端点、数据来源与降级策略。

## 验收对齐（PRD §17）

- 功能：默认 `profile=all`、`periodDays=30`，无时间范围选择器；切 profile 仅显示该 profile；Container/Profile Runtime 分开；all 模式 Model Usage 显示 profileName；state.db / docker stats / webui / API Server 缺失均不报错。
- 安全：前端无法传路径；不返回 .env/API key/session 正文；SQLite 只读；无 path traversal；不同 profile 不串数据。
- 性能：单 profile <500ms、all <1000ms；不阻塞现有运行状态展示；不扫描完整 session message。