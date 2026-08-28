# knowledge-desktop（copilot-knowledge）对接 nodeskclaw-knowledge 接口文档

**前端工程：`copilot-knowledge`（Electron + React 19 + TanStack Query/Router + oRPC IPC + shadcn）**
**服务方：`nodeskclaw-knowledge`（FastAPI，v2.3 Intelligence API）**
**Base URL：`http(s)://<knowledge-host>:4530` · API 前缀 `/api/v2`（需 `KNOWLEDGE_API_V2_ENABLED=true`）**
**配套调试：见 `docs_knowledge/knowledge-postman-collection.md`**

> **历史附录**：v1.3 `/api/v1` 契约见本文档末尾 [附录 A — v1.3 `/api/v1` 历史基线](#appendix-v1-api)。

---

## 0. 前端架构对接点（先读）

copilot-knowledge 是**三层进程**架构，对接必须落在正确层：

```
Electron Main (src/main/, src/ipc/)      ← 持有 token、发 HTTP（唯一允许出网层）
    ↓ MessagePort + oRPC
Preload (src/preload.ts)                 ← 只做桥接，不写业务
    ↓
Renderer (src/actions/, src/features/)   ← 只能经 actions 调 IPC，禁止直接 fetch / Node API
    ↓
src/services/knowledge/  Repository 抽象 ← Feature 唯一数据入口
```

| 层 | 目录 | 对接职责 |
|----|------|----------|
| Main | `src/main/knowledge/`（**新增**） | `remote-knowledge-client.ts`：发 HTTP 到 Knowledge 服务；token 注入 |
| IPC | `src/ipc/` | 在 `router.ts` 增加 `knowledge` 命名空间，转发 Repository 调用 |
| Service | `src/services/knowledge/remote-knowledge-repository.ts`（**待实现**） | 实现 `KnowledgeRepository`，内部走 IPC |
| Feature | `src/features/`、`src/routes/` | **不改签名**，继续依赖 `knowledgeService` |

**关键约束（来自工程 AGENTS/lat.md）：**
- Renderer **禁止**直接 `fetch` / 访问 Node API——所有 Knowledge HTTP 必须在 **Main 进程**发起。
- Feature 只依赖 `KnowledgeRepository` 契约，**不因换 remote 改 Feature**。
- 数据模式由 `getKnowledgeDataMode()`（`VITE_KNOWLEDGE_DATA_MODE`）决定 `mock` / `remote`；认证与数据模式**解耦**。
- Query key 统一用 `knowledgeQueryKeys`，保证失效/缓存一致。

---

## 1. 认证与 Endpoint 配置

### 1.1 现有认证（已实现，复用）

认证**只对接 nodeskclaw-backend**，token 存 Main 进程 `safeStorage`（`knowledge-auth-session.bin`）。Renderer 只见 `PublicAuthState`（无 token）。

- 登录：`actions/auth.ts#login` → oRPC `auth.login` → `main/auth/auth-client.ts#loginWithCredentials` → backend `POST {authBackendUrl}{authPrefix}/login`
- 配置：登录页可改 `authBackendUrl`（默认 `http://127.0.0.1:4510`），经 IPC `saveEndpoint` 持久化

### 1.2 新增：Knowledge 服务地址

`KnowledgeEndpointConfig` 目前只有 backend 地址。**需新增 Knowledge 服务地址字段**：

```ts
// src/types/endpoint-config.ts（扩展）
export interface KnowledgeEndpointConfig {
  authBackendUrl: string;         // 现有：认证
  authPrefix: string;             // 现有
  knowledgeApiUrl: string;        // 新增：http://127.0.0.1:4530
  knowledgeApiPrefix: string;     // 新增：/api/v2
}
```

### 1.3 Knowledge 侧鉴权方式

Knowledge 服务**不签发 token**：它把 Desktop 的 Bearer 转发给 backend 换 `KnowledgePrincipal`（member/org/role/department）。

- Desktop 每个 Knowledge 请求带 `Authorization: Bearer <backend token>`
- token 由 **Main 进程**从 `token-store` 读取并注入请求头；Renderer 拿不到 token
- Knowledge 返回 `40100` → 触发前端重新登录

---

## 2. 通用契约（Remote 实现必读）

### 2.1 统一响应包裹

```jsonc
// 成功
{ "code": 0, "error_code": null, "message_key": null, "message": "success", "data": { } }
// 失败
{ "code": 40900, "error_code": 40900, "message_key": "errors.knowledge.source_managed_by_connector", "message": "…", "data": null }
```

- 成功：`HTTP 2xx && error_code == null`
- 失败：`error_code != null`，**用 `message_key` 做 i18n**，`message` 仅兜底
- 分页：`data = { items: T[], total, page, page_size }`

### 2.2 请求头（Main 进程统一注入）

| Header | 值 |
|--------|-----|
| `Authorization` | `Bearer <backend token>` |
| `Content-Type` | `application/json`（上传用 `multipart/form-data`） |
| `Accept-Language` | 从 i18next 当前语言映射（`zh-CN` / `en`） |

---

## 3. Repository 方法 → API 映射（核心对照表）

Feature 契约方法不变，Remote 实现按下表逐个对接。✅=已够 ❌=Knowledge 暂无该接口（需补或用组合实现）。

### 3.1 Dashboard / Knowledge Base

| Repository 方法 | Knowledge API | 说明 |
|-----------------|---------------|------|
| `getDashboard()` | `GET /dashboard` | ✅ 直接映射（stats + recent sets/documents） |
| `listKnowledgeBases()` | `GET /knowledge-bases` | ✅ 返回分页，取 `data.items` |
| `getKnowledgeBase(id)` | `GET /knowledge-bases/{id}` | ✅ |
| `createKnowledgeBase(input)` | `POST /knowledge-bases` | ✅ 字段映射见 §4.1 |
| `updateKnowledgeBase(id, input)` | `PATCH /knowledge-bases/{id}` | ✅ |
| `deleteKnowledgeBase(id)` | `DELETE /knowledge-bases/{id}` | ✅ 软删 |

### 3.2 Document / Source File

| Repository 方法 | Knowledge API | 说明 |
|-----------------|---------------|------|
| `listDocuments(filter)` | `GET /source-files?knowledge_base_id=&parse_status=&q=` | ✅ 过滤参数映射见 §4.2 |
| `getDocument(id)` | `GET /source-files/{id}` + `GET /{id}/versions` | ⚠️ **两次调用组合**成 `KnowledgeDocumentDetail` |
| `createDocumentVersion(docId, file)` | `POST /source-files/{id}/versions`（multipart） | ✅ connector 管理文件会 409 |
| （上传新文档） | `POST /knowledge-bases/{kb_id}/files`（multipart） | ✅ 返回 SourceFile，随后轮询 IngestionJob |

### 3.3 Knowledge Set

| Repository 方法 | Knowledge API |
|-----------------|---------------|
| `listKnowledgeSets()` | `GET /knowledge-sets` |
| `getKnowledgeSet(id)` | `GET /knowledge-sets/{id}` |
| `createKnowledgeSet(input)` | `POST /knowledge-sets` |
| `updateKnowledgeSet(id, input)` | `PATCH /knowledge-sets/{id}` |
| `bindKnowledgeBases(setId, kbIds)` | `POST /knowledge-sets/{set_id}/knowledge-bases`（循环或批量） |

### 3.4 Chat

| Repository 方法 | Knowledge API | 说明 |
|-----------------|---------------|------|
| `listChatSessions()` | `GET /chat/sessions` | ✅ |
| `createChatSession(input)` | `POST /chat/sessions` | ✅ |
| `getChatMessages(sessionId)` | `GET /chat/sessions/{id}/messages` | ✅ |
| `sendMessage(sessionId, input)` | `POST /chat/sessions/{id}/messages` | ✅ `stream:false` 返回 JSON；`stream:true` 走 SSE（见 §6） |

### 3.5 Upload Job

| Repository 方法 | Knowledge API | 说明 |
|-----------------|---------------|------|
| `createUploadJobs(files)` | `POST /knowledge-bases/{kb_id}/files` × N | ⚠️ 逐个上传，返回后建 job 跟踪 |
| `listUploadJobs()` | `GET /ingestion-jobs?knowledge_base_id=` | ✅ 状态映射见 §4.4 |

### 3.6 v1.3 新增：Connector（Desktop 新界面）

Knowledge v1.3 提供 Connector 全套 API，copilot-knowledge **当前无对应 Repository 方法**。若要支持「接入共享盘 / HTTP / S3」，需新增契约方法：

| 建议新方法 | Knowledge API |
|-----------|---------------|
| `listConnectorTypes()` | `GET /source-connectors/types` |
| `listConnectors(kbId)` | `GET /source-connectors?knowledge_base_id=` |
| `createConnector(kbId, input)` | `POST /knowledge-bases/{kb_id}/source-connectors` |
| `updateConnector / deleteConnector` | `PATCH/DELETE /source-connectors/{id}` |
| `putCredential / deleteCredential` | `PUT/DELETE /source-connectors/{id}/credential` |
| `triggerSync(id)` | `POST /source-connectors/{id}/sync` → 202 + SyncRun |
| `listSyncRuns / getSyncRun / retry / cancel` | `GET/POST /source-connectors/{id}/sync-runs…` |
| `listConnectorObjects(id)` | `GET /source-connectors/{id}/objects` |

---

## 4. 字段映射（Mock 类型 ↔ Knowledge API）

copilot-knowledge 现有类型与 Knowledge API 字段命名不一致（camelCase vs snake_case），Remote 层做转换。

### 4.1 KnowledgeBase

| 前端 `KnowledgeBase` | API `KnowledgeBaseOut` | 转换 |
|----------------------|------------------------|------|
| `id` | `id` | — |
| `name` / `description` | 同名 | — |
| `status` (`active/disabled/syncing/error`) | `status` | 对齐：API `active/error/updating` → 前端 |
| `embeddingModel` | `embedding_model` | snake→camel |
| `parserStrategy` | `chunk_method` | 语义对应 |
| `documentCount` / `chunkCount` | `document_count` / `chunk_count` | |
| `owner` | `owner_member_id` | ⚠️ 前端要 `UserSummary` 对象，需另查成员或后端补 join |
| `visibility` | `visibility` | `private/department/organization` |
| `tags` | `tags` | — |
| `runtimeInfo.ragflowDatasetId` | `ragflow_dataset_id` | |

**注意**：`KnowledgeBaseOut` 不返回 `members` 与 `runtimeInfo.parseSuccessRate`。`getKnowledgeBase` Detail 需**组合** `GET /knowledge-bases/{id}/acl`（成员）+ 计算或新增统计接口。

### 4.2 Document（KnowledgeDocument ↔ SourceFileOut）

| 前端 | API | 说明 |
|------|-----|------|
| `name` | `file_name` | |
| `parseStatus` (`pending/parsing/completed/failed`) | `parse_status` | API 更细（见 §4.4），映射：`active→completed`，`parsing/validating/parse_dispatched→parsing`，`failed→failed`，其余→`pending` |
| `size` | （SourceFileOut 无 size，取版本 `file_size`） | ⚠️ 从 active version 取 |
| `currentVersion` | `version_no` | |
| `visibility` | （SourceFile 无 visibility，继承 KB） | ⚠️ 前端 visibility 需从 KB 继承或忽略 |
| **v1.3 新增** | `source_kind` / `connector_id` / `sync_state` / `last_synced_at` / `archive_reason` | 前端新增字段用于「来源治理」展示 |

**v1.3 建议给 `KnowledgeDocument` 加可选字段**：

```ts
export interface KnowledgeDocument {
  // ...现有
  sourceKind?: "manual" | "connector";
  connectorId?: string;
  syncState?: "in_sync" | "stale" | "error" | "detached";
  lastSyncedAt?: string;
  archiveReason?: "manual" | "source_deleted" | "connector_deleted" | string;
}
```

### 4.3 Knowledge Set

| 前端 | API |
|------|-----|
| `knowledgeBaseIds` | `knowledge_bases[].id`（Detail 返回绑定列表） |
| `weights` | 绑定接口的 `weight` |
| `retrievalConfig.topK` | `retrieval_config.top_n` |
| `retrievalConfig.similarityThreshold` | `retrieval_config.similarity_threshold` |
| `retrievalConfig.vectorWeight/keywordWeight` | `vector_similarity_weight` / `keyword` |
| `retrievalConfig.answerModel` | `answer_model` |
| `retrievalConfig.enableRerank` | `rerank_id != null`（API 用 rerank_id 而非 bool）⚠️ |

### 4.4 UploadJob（↔ IngestionJob）

| 前端 `UploadJob.status` | API `IngestionJob.status` |
|------------------------|---------------------------|
| `waiting` | `pending` |
| `uploading` | `uploading` / `upload_unknown`（后者显示「确认中」） |
| `parsing` | `ragflow_uploaded` / `metadata_synced` / `parse_dispatched` / `parsing` / `validating` |
| `completed` | `active` |
| `failed` | `failed` |
| `cancelled` | `cancelled` |

上传后**轮询** `GET /ingestion-jobs/{job_id}`（1–2s）直到终态。

### 4.5 Chat / Citation

| 前端 | API |
|------|-----|
| `ChatSession.answerMode` | `answer_mode`（`concise/detailed/structured`） |
| `ChatSession.showCitations` | `show_citations` |
| `ChatMessage.status` (`streaming/done/error`) | SSE 事件推进 / `status` |
| `KnowledgeCitation.documentId` | `source_file_id`（注意：是 SourceFile，不是 RAGFlow document_id） |
| `KnowledgeCitation.documentName` | `file_name` |
| `KnowledgeCitation.chunkText` | `quote` |
| `KnowledgeCitation.page` / `score` | `page` / `score` |
| **v1.3 新增** | `source_kind`/`connector_type`/`source_path`/`sync_state`/`source_freshness` |

**v1.3 建议给 `KnowledgeCitation` 加**：
```ts
sourceFreshness?: "fresh" | "stale" | "unknown";  // stale 显示「来源可能过期」徽标（非权限问题）
syncState?: string;
```

---

## 5. 鉴权 HTTP 调用（Main 进程）

### 5.1 新建 `src/main/knowledge/remote-knowledge-client.ts`

```ts
import { loadSession } from "@/main/auth/token-store";

export class KnowledgeApiError extends Error {
  constructor(
    public errorCode: number,
    public messageKey: string | null,
    message: string,
  ) { super(message); }
}

export async function knowledgeFetch<T>(
  endpoint: { knowledgeApiUrl: string; knowledgeApiPrefix: string },
  path: string,
  init?: RequestInit,
): Promise<T> {
  const session = await loadSession();
  if (!session?.accessToken) throw new KnowledgeApiError(40100, "errors.auth.credentials_missing", "未登录");

  const base = endpoint.knowledgeApiUrl.replace(/\/$/, "");
  const prefix = endpoint.knowledgeApiPrefix.replace(/\/$/, "");
  const resp = await fetch(`${base}${prefix}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${session.accessToken}`,
      "Content-Type": "application/json",
      "Accept-Language": getCurrentLocale(),   // zh-CN / en
      ...init?.headers,
    },
  });
  const body = await resp.json();
  if (body.error_code) throw new KnowledgeApiError(body.error_code, body.message_key, body.message);
  return body.data as T;
}
```

### 5.2 IPC 暴露

`src/ipc/router.ts` 增加 `knowledge` 命名空间 handler（调 Main 侧 client），Renderer 经 `src/actions/knowledge.ts`（**新增**）调用。Repository 的 remote 实现只依赖 `actions/knowledge`，不直接 fetch。

> token 全程不出 Main 进程，符合「Renderer 只见 PublicAuthState」的安全约束。

---

## 6. 聊天 SSE 对接（关键）

copilot-knowledge Mock 聊天是关键词匹配 fixtures；Remote 需接 SSE。

### 6.1 请求

```
POST /chat/sessions/{session_id}/messages
Authorization: Bearer <token>
Content-Type: application/json
{ "content": "年假政策", "stream": true }
```

### 6.2 SSE 事件 → 前端状态机

```
event: retrieval_started    → 消息 status=streaming，显示「检索中」
event: retrieval_degraded   → 提示「部分知识源不可用」（message_key 可 i18n）
event: retrieval_completed  → 显示 chunk_count
event: generation_started   → 显示「生成中」+ model
event: delta                → 追加 data.content 到当前消息（流式渲染）
event: citation             → 收集 citation（v1.3 含 provenance/freshness）
event: message_completed    → status=done，落 citations[]，停止流
event: error                → status=error，展示 message（i18n: message_key）
```

### 6.3 Main 进程解析（Renderer 不直接碰网络）

```ts
// src/main/knowledge/chat-stream.ts
export async function* streamChat(endpoint, sessionId: string, content: string) {
  const session = await loadSession();
  const resp = await fetch(url(endpoint, `/chat/sessions/${sessionId}/messages`), {
    method: "POST",
    headers: { Authorization: `Bearer ${session.accessToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({ content, stream: true }),
  });
  const reader = resp.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "", event = "message";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += value;
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, i); buf = buf.slice(i + 2);
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) yield { event, data: JSON.parse(line.slice(5)) };
      }
      event = "message";
    }
  }
}
```

SSE 跨进程传输：Main 逐事件 `port.postMessage` 给 Renderer，或聚合后一次性返回（`stream:false` 简化版）。

### 6.4 引用点击

`GET /citations/{citation_id}` → `accessible` + `reason`（`ok/not_found/deleted/archived/permission_revoked`）。Desktop 决定是否可点开原文。

---

## 7. v1.3 来源治理 UX 规则（Desktop 落地）

| 场景 | UI 行为 |
|------|---------|
| `sourceKind = "connector"` 文档 | 「上传新版本」禁用 + tooltip「由 Connector 管理」；提供「Detach」入口（`POST /source-files/{id}/detach`） |
| 上传 connector 文档版本 | 捕获 `409 source_managed_by_connector` → 提示并引导 Detach |
| `syncState = "stale"/"error"` | 文档行显示「来源过期/同步异常」徽标，悬浮 `lastSyncedAt` |
| `sourceFreshness = "stale"` 引用 | 引用角标「可能过期」，**不**当作无权限 |
| `archiveReason = "source_deleted"` | 「上游已删除」置灰，不可恢复 |
| Connector 凭证 | **永不回显**；表单仅在「设置凭证」时出现，不回填；状态用 `credential_configured` 灯 |
| 空列表 | 必须给引导（「还没有知识库，去创建」「该 Connector 未同步，点手动同步」） |
| 操作 | 立即 loading + 结果 toast（sonner），异步任务给进度 |

---

## 8. 错误码 → 前端处理

| error_code / message_key | 处理 |
|--------------------------|------|
| `40100 errors.auth.credentials_missing` | 清会话，跳登录 |
| `40300 errors.auth.user_inactive` / 403 | 提示无权限 |
| `404` / `*_not_found` | 空态「资源不存在」 |
| `409 errors.knowledge.source_managed_by_connector` | 引导 Detach |
| `400 errors.knowledge.connector_config_invalid` | 提示 secret 需走凭证接口 |
| `400 errors.knowledge.connector_interval_too_small` | 提示同步间隔 ≥300s |
| `50000` / 其他 | 通用错误 toast + 保留 `message_key` 供上报 |

---

## 9. 对接落地步骤（建议顺序）

1. **扩 Endpoint 配置**：`KnowledgeEndpointConfig` 加 `knowledgeApiUrl`/`knowledgeApiPrefix`；登录页可填 Knowledge 地址
2. **建 Main 侧 client**：`src/main/knowledge/remote-knowledge-client.ts`（注入 token + 解 ApiResponse）
3. **加 IPC 命名空间**：`src/ipc/router.ts` 暴露 `knowledge.*`；`src/actions/knowledge.ts` 供 Renderer 调
4. **实现 RemoteKnowledgeRepository**：逐方法对接（§3 表），camelCase↔snake_case 转换集中在一个 mapper
5. **类型对齐**：`KnowledgeDocument`/`KnowledgeCitation` 补 v1.3 可选字段
6. **聊天接 SSE**：Main 解析 → IPC 转发 → Renderer 流式渲染
7. **联调**：按 `knowledge-postman-collection.md` §4 冒烟顺序，对照 Repository 方法逐条验证
8. **（可选）Connector 界面**：新增 Repository 契约方法 + features/connectors 页面

---

## 9.1 v2.2 API 增量（`/api/v2`）

v2.2 在 v1.3 基线上新增 headless 运维/发布契约，Desktop 后续可按需接入：

| 域 | 方法 | 路径 | 说明 |
|---|---|---|---|
| Applications | GET | `/api/v2/applications/{id}/readiness` | 发布前 readiness 诊断（blocking/warnings） |
| Applications | POST | `/api/v2/applications/{id}/publish` | 未就绪返回 **409** + diagnostics |
| Runtime | GET | `/api/v2/knowledge-bases/{kb_id}/runtime` | KB Runtime 诊断（不含 API Key） |
| Runtime | POST | `/api/v2/knowledge-bases/{kb_id}/runtime/reconcile` | Config reconcile；`repair_mode=reprovision` 才重建 Dataset |
| Runtime | GET | `/api/v2/runtime/workers` | Worker heartbeat 快照（ingestion/build/maintenance/connector） |
| Engineering | GET | `/api/v2/knowledge-bases/{id}/indexes` | 增加 `build_status` / `retrieval_status` / `validation` / `coverage` / `last_validated_at` |
| Retrieval | POST | `/api/v2/retrieval/playground` | 返回 `execution_slices[]` 与 per-slice 诊断 |

启用开关：`KNOWLEDGE_API_V2_ENABLED=true`；Graph/Summary/TOC runtime 分别由 `KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED` 等 flag 控制。

---

## 10. 边界与注意事项

- Desktop **只连** nodeskclaw-knowledge，**不直连 RAGFlow**（所有 RAGFlow 调用在服务端 Adapter 内）。
- v2.3 基线为 `/api/v2`；v1.3 `/api/v1` 仅作历史兼容（见附录 A）。
- Connector 静态注册，不支持 API 上传自定义 Connector 代码。
- Knowledge 不产生 token；认证链路仍是 backend，Knowledge 仅校验。
- 联调前置：服务端起 `nodeskclaw-knowledge`（4530）+ `nodeskclaw-backend`（4510）+ 可用 PostgreSQL/RAGFlow。

---

## 附录 A — v1.3 `/api/v1` 历史基线

v1.3 时代 Desktop 对接前缀为 `/api/v1`。v2.3 起新功能（Applications、Runtime、Artifacts、Quality、KnowledgeModel Revision 等）均在 `/api/v2` 发布；`/api/v1` 保留只读/兼容，不再作为新集成基线。

| 项 | v1.3 历史值 | v2.3 当前基线 |
|---|---|---|
| API 前缀 | `/api/v1` | `/api/v2` |
| 启用开关 | 默认开启 | `KNOWLEDGE_API_V2_ENABLED=true` |
| Application 发布 | 无正式 readiness gate | `POST .../publish` + readiness |
| Artifact / Quality | 无 | `/api/v2/artifacts`、`/api/v2/quality` |
