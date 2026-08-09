# knowledge-desktop 对接 nodeskclaw-knowledge 接口文档

**目标方：knowledge-desktop（桌面前端）**
**服务方：`nodeskclaw-knowledge`（Knowledge 应用服务）**
**版本：v1.3**
**Base URL：`http(s)://<knowledge-host>:4530` · API 前缀 `/api/v1`**

---

## 1. 概览

`nodeskclaw-knowledge` 是独立 FastAPI 服务，负责知识库 / 知识集 / 来源文件 / 检索 / Secure Chat / Connector 同步。Desktop 通过 HTTP + SSE 与其对接。

| 关注点 | 说明 |
|--------|------|
| 协议 | HTTP/1.1 JSON；聊天为 SSE（`text/event-stream`） |
| 认证 | `Authorization: Bearer <token>`，token 由 nodeskclaw-backend 签发，Knowledge 侧向 backend 换取 Principal |
| 响应封装 | 统一 `ApiResponse`（见 §2） |
| 幂等 | 上传 / 同步通过服务端 Source Identity + sha256 保证；Desktop 无需自行去重 |
| 时区 | 所有时间为 ISO 8601 UTC |

> Desktop 通过网关/内网直连 Knowledge 服务均可；**不要**让 Desktop 直连 RAGFlow。

---

## 2. 通用约定

### 2.1 请求头

| Header | 必须 | 说明 |
|--------|------|------|
| `Authorization` | 是（业务接口） | `Bearer {{access_token}}` |
| `Content-Type` | 是 | `application/json`；上传用 `multipart/form-data` |
| `Accept-Language` | 建议 | `zh-CN` / `en`；影响 `message` 文案（`message_key` 恒不变） |
| `X-Request-ID` | 建议 | 透传 correlation id，便于排障 |

### 2.2 统一响应

```jsonc
// 成功
{ "code": 0, "error_code": null, "message_key": null, "message": "success", "data": { } }

// 失败
{ "code": 40900, "error_code": 40900, "message_key": "errors.knowledge.source_managed_by_connector", "message": "该来源由 Connector 管理，禁止人工上传版本", "data": null }
```

- **成功判断**：HTTP 2xx 且 `error_code == null`（`code == 0`）。
- **失败判断**：`error_code != null`。优先用 `message_key` 做 i18n，`message` 仅作兜底。
- **分页**：`data = { items: T[], total: number, page: number, page_size: number }`

### 2.3 通用 Query 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `page` / `page_size` | 1 / 20（≤100） | 分页 |
| `q` | — | 模糊搜索（名称） |
| `sort_by` / `sort_order` | `created_at` / `desc` | 排序 |

---

## 3. 鉴权与 Principal

Desktop 持有用户在 nodeskclaw-backend 登录后的 access token。每个请求带 `Authorization: Bearer`。Knowledge 会校验并解析出：

```
member_id, org_id, member_role, department, is_super_admin ...
```

Desktop **不需要**、也**不应该**自己传 member/org id；一切以 token 为准。Connector 同步产生的 SourceFile **仍然**受 KB/File/Set ACL 约束，Connector 不会扩大权限（Gate G）。

错误：
- `40100 errors.auth.credentials_missing` → 未登录/token 过期
- `40300 errors.auth.user_inactive` → 账号停用

---

## 4. 领域模型速览（字段即 API 返回）

```
KnowledgeBase ─┬─ SourceFile ── SourceFileVersion ── IngestionJob
               └─ KnowledgeSourceConnector ── ConnectorSyncRun ── ConnectorSyncItem / SourceObject

KnowledgeSet ──绑定多 KnowledgeBase── RetrievalProfile(版本化配置)
ChatSession ── ChatMessage ── ChatCitation
EvaluationSet ── EvaluationCase ── EvaluationRun ── EvaluationResult
```

v1.3 关键新增字段（`SourceFile` / `SourceFileVersion`）：

| 字段 | 含义 |
|------|------|
| `source_kind` | `manual` / `connector` |
| `connector_id` / `external_object_id` | 连接器与外部稳定身份 |
| `source_path` / `source_uri` / `source_revision` / `source_etag` | 来源定位与版本指纹 |
| `sync_state` | `in_sync` / `stale` / `error` / `detached` |
| `last_synced_at` | 最近一次同步时间（用于新鲜度展示） |
| `archive_reason` | `manual` / `source_deleted` / `connector_deleted` 等 |

---

## 5. 接口分组对接

### 5.1 知识库 Knowledge Base

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge-bases` | 列表（q、status、sort） |
| POST | `/knowledge-bases` | 创建 |
| GET/PATCH/DELETE | `/knowledge-bases/{kb_id}` | 详情 / 更新 / 软删 |
| GET/PUT | `/knowledge-bases/{kb_id}/metadata-schema` | 业务元数据 Schema（字段定义） |
| GET/POST/DELETE | `/knowledge-bases/{kb_id}/acl[/{acl_id}]` | KB 级 ACL（read/upload/update/manage） |

创建 body：
```json
{ "name": "公司制度库", "description": "...", "embedding_model": "bge-m3",
  "chunk_method": "naive", "visibility": "private", "tags": ["hr"] }
```

### 5.2 来源文件 Source File

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/knowledge-bases/{kb_id}/files` | KB 内文件列表 |
| POST | `/knowledge-bases/{kb_id}/files` | 上传（multipart：`file` + `metadata`） |
| GET | `/source-files` | 全局列表（可按 kb/parse_status/status 过滤） |
| GET/PATCH | `/source-files/{id}` · `/metadata` | 详情 / 业务元数据补丁 |
| GET | `/source-files/{id}/versions` | 版本列表 |
| POST | `/source-files/{id}/versions` | 上传新版本（multipart） |
| POST | `/source-files/{id}/versions/{vid}/activate` | 蓝绿切换激活版本 |
| POST | `/source-files/{id}/archive` / `unarchive` | 归档 / 取消归档 |
| POST | `/source-files/{id}/detach` | **v1.3**：把 connector 管理来源转为 manual |
| POST | `/source-files/{id}/reparse` | 触发重新解析 |
| GET | `/source-files/{id}/download` | 下载 |
| GET/POST/DELETE | `/source-files/{id}/acl[/{acl_id}]` | 文件级 ACL |

**对接要点（Desktop UI）：**

- `source_kind = "connector"` 的文件：上传新版本会返回 `409 errors.knowledge.source_managed_by_connector`。UI 应在「上传新版本」按钮上禁用并提示「该来源由 Connector 管理」，或引导「Detach」。
- `sync_state != in_sync` 时展示「来源已过期 / 同步异常」徽标（`last_synced_at` 悬浮提示）。
- `archived_at != null` 时置灰，区分 `archive_reason`（`source_deleted` = 上游已删除）。

### 5.3 知识集 Knowledge Set

| 方法 | 路径 |
|------|------|
| GET/POST | `/knowledge-sets` |
| GET/PATCH/DELETE | `/knowledge-sets/{set_id}` |
| GET/POST/DELETE | `/knowledge-sets/{set_id}/acl[/{acl_id}]`（read/use/update） |
| POST/DELETE | `/knowledge-sets/{set_id}/knowledge-bases[/{kb_id}]` 绑定/解绑 |

### 5.4 检索 Retrieval

**POST `/retrieval`**
```json
{
  "knowledge_set_id": "set_1",
  "query": "报销流程",
  "options": { "top_n": 8, "similarity_threshold": 0.2, "highlight": true },
  "filters": { "dept": ["HR"] }
}
```
返回 `data.chunks[]`：`chunk_id / file_name / content / similarity / highlight / source_file_id`。

**POST `/retrieval/playground`**：同 Retrieval，额外返回 `plan`（kb/slice 数）、`timing`（acl/ragflow/security/merge 耗时）、`filter_summary`（`unauthorized`、`metadata_mismatch`、`superseded` 计数）——用于 Desktop 的「检索诊断/调试」面板。

### 5.5 聊天 Chat（SSE）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/chat/sessions` | 列表 / 创建 |
| GET/DELETE | `/chat/sessions/{session_id}` | 详情 / 删除 |
| GET | `/chat/sessions/{session_id}/messages` | 历史消息 |
| POST | `/chat/sessions/{session_id}/messages` | 发送（`stream=true` → SSE） |

**SSE 事件序列**（`data:` 为 JSON）：

```
event: retrieval_started     { session_id, message_id }
event: retrieval_degraded    { message, message_key, diagnostics }   # 可选，部分源不可用
event: retrieval_completed   { chunk_count, query_id }
event: generation_started    { model }
event: delta                 { content }                            # 文本增量，可多次
event: citation              { citation_id, source_file_id, file_name, quote, page,
                               source_kind, connector_type, source_path, sync_state, source_freshness }  # 可多次
event: message_completed     { message_id, content, citations[] }
event: error                 { message, message_key }               # 出错时
```

Desktop 处理建议：
- 用 `EventSource` 或 fetch + ReadableStream 逐行解析 `event:` / `data:`。
- `delta` 追加渲染；`citation` 收集后渲染角标；`message_completed` 收尾。
- `citation.source_freshness` 为 `stale` 时在引用上标「来源可能过期」，**不是**权限问题。

**Citation 解析** `GET /citations/{citation_id}`：返回 `accessible` + `reason`（`ok / not_found / deleted / archived / permission_revoked`）+ 完整 provenance。Desktop 据此决定引用是否可点开查看原文。

### 5.6 Source Connectors（v1.3）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/source-connectors/types` | 已注册类型 + capabilities |
| GET | `/source-connectors?knowledge_base_id=` | 列表 |
| POST | `/knowledge-bases/{kb_id}/source-connectors` | 创建 |
| GET/PATCH/DELETE | `/source-connectors/{id}` | 详情 / 更新 / 删除（`policy` 查询参数） |
| POST | `/source-connectors/{id}/test` `/pause` `/resume` `/sync` | 连接测试 / 暂停 / 恢复 / 手动同步 |
| PUT/DELETE | `/source-connectors/{id}/credential` | 写/删凭证 |
| GET | `/source-connectors/{id}/sync-runs` | 同步记录列表 |
| GET | `/source-connectors/{id}/sync-runs/{run_id}` | 同步记录详情（含 metrics） |
| POST | `/source-connectors/{id}/sync-runs/{run_id}/retry` `/cancel` | 重试 / 取消 |
| GET | `/source-connectors/{id}/objects?state=` | 外部对象注册表（诊断） |

**Connector 类型与 config（v1.3 静态注册，禁止 API 上传代码）：**

| connector_type | config 字段 | credential payload |
|----------------|-------------|--------------------|
| `filesystem` | `root_alias`, `sub_path`, `include[]`, `exclude[]` | 无（服务端 `KNOWLEDGE_CONNECTOR_FS_ROOTS` 配根目录） |
| `http_manifest` | `manifest_url`, `page_size`, `rate_limit_per_sec` | `{ "auth_type": "none|bearer|api_key_header|basic", "token"?, "header_name"?, "username"?, "password"? }` |
| `s3_compatible` | `endpoint_url`, `bucket`, `prefix`, `region` | `{ "access_key", "secret_key" }` |

**凭证安全（Desktop 必须遵守）：**
- `ConnectorOut` **永不包含** secret。只展示 `credential_configured: bool` 与 `credential_updated_at`。
- 修改凭证走 `PUT /credential`；`config` 中提交 secret 字段会被 `400 errors.knowledge.connector_config_invalid` 拒绝。
- Desktop 表单：secret 输入框只在「设置凭证」时出现，不回填。

**Sync Run 状态机**（轮询 `/sync-runs/{run_id}`）：
```
pending → discovering → applying → (waiting_ingestion) → completed | partial | failed | cancelled
```
`waiting_ingestion` 表示对象已入库、等待解析完成；UI 显示「同步完成，解析中」。

### 5.7 入库任务 Ingestion Job

| 方法 | 路径 |
|------|------|
| GET | `/ingestion-jobs?knowledge_base_id=&source_file_id=&status=` |
| GET | `/ingestion-jobs/{job_id}` |
| POST | `/ingestion-jobs/{job_id}/retry` `/cancel` |

状态：`pending → uploading → (upload_unknown) → ragflow_uploaded → metadata_synced → parse_dispatched → parsing → validating → active | failed | cancelled`。
Desktop 上传后应轮询 job 直至 `active`；`upload_unknown` 由服务端 recovery，UI 显示「上传确认中」。

### 5.8 评测 Evaluation / 审计 Audit / 仪表盘 Dashboard

- Evaluation：`/evaluation/sets` `/cases` `/runs` `/compare`，用于质量回归（管理端为主）。
- Audit：`GET /audit?action=&resource_type=`，v1.3 含 `CONNECTOR_*` 与 `SOURCE_*` 事件。
- Dashboard：`GET /dashboard` 一次性拿统计 + 最近集合/文档，适合做 Desktop 首页。

---

## 6. Desktop 端技术对接建议

### 6.1 HTTP 客户端

```ts
// api/client.ts
const base = import.meta.env.VITE_KNOWLEDGE_BASE_URL + "/api/v1";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(base + path, {
    ...init,
    headers: {
      Authorization: `Bearer ${getToken()}`,
      "Content-Type": "application/json",
      "Accept-Language": getLocale(),           // zh-CN / en
      ...init?.headers,
    },
  });
  const body = await resp.json();
  if (body.error_code) throw new ApiError(body); // { error_code, message_key, message }
  return body.data as T;
}
```

### 6.2 SSE 聊天

```ts
export async function* streamChat(sessionId: string, content: string) {
  const resp = await fetch(`${base}/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
    body: JSON.stringify({ content, stream: true }),
  });
  const reader = resp.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "", event = "message";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += value;
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx); buf = buf.slice(idx + 2);
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) yield { event, data: JSON.parse(line.slice(5)) };
      }
      event = "message";
    }
  }
}
```

### 6.3 状态与轮询

- **上传后**：轮询 `GET /ingestion-jobs/{job_id}`（1–2s）直到 `active|failed`。
- **Connector 同步后**：轮询 `GET /sync-runs/{run_id}` 直到终态（`completed|partial|failed|cancelled`）。
- 建议用统一 `usePolling` composable，避免每个页面手写定时器。

### 6.4 错误与 i18n

- 统一捕获 `ApiError`，优先 `t(message_key, message_params)`，缺失时回退 `message`。
- `40100` → 跳登录；`40300` → 提示无权限；`40900 source_managed_by_connector` → 引导 Detach 或联系管理员。
- 空状态必须给引导（「还没有知识库，去创建」「该 Connector 尚未同步，点击手动同步」）。

### 6.5 关键 UX 规则

| 场景 | 展示 |
|------|------|
| connector 管理的文件 | 「上传新版本」禁用 + tooltip；提供「Detach」入口 |
| `sync_state = stale/error` | 来源过期/异常徽标 + `last_synced_at` 提示 |
| 引用 `source_freshness = stale` | 引用角标「可能过期」，**不**当作无权限 |
| `archive_reason = source_deleted` | 「上游已删除」，不可恢复（除非 connector 重新同步到） |
| 凭证 | 永不回显；仅 `credential_configured` 状态灯 |

---

## 7. 版本兼容与边界

- v1.3 冻结的是 **Connector / Credential / SyncRun / SourceObject API 契约**；字段只增不减。
- Desktop 不应依赖任何 RAGFlow 直连接口；所有 RAGFlow 调用都在 Knowledge 服务端 Adapter 内。
- Connector 类型为**静态注册**，不支持 API 上传自定义 Connector 代码（防 RCE）。
- `metadata_condition` pushdown 目前作为性能优化通道；默认过滤仍由本地 ACL + `document_ids` 完成，Desktop 无需感知。

---

## 8. 快速联调清单

1. `GET /health/ready` = ok
2. 建 KB → 上传文件 → job 到 `active`
3. 建 Set 绑定 KB → `POST /retrieval` 返回 chunks
4. 建 Chat Session → 流式发送 → 收到 `message_completed` + citations
5. （服务端配好 `KNOWLEDGE_CONNECTOR_FS_ROOTS` 后）建 filesystem connector → `POST /sync` → sync-run 到 `completed`
6. 引用点击 → `GET /citations/{id}` 返回 provenance + `accessible`
