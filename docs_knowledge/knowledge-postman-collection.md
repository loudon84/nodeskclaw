# nodeskclaw-knowledge — Postman Collection 调试文档

**适用版本：v1.3（Knowledge Connector & Continuous Sync）**
**服务：`nodeskclaw-knowledge`（FastAPI）**
**Base URL：`http://127.0.0.1:4530`**（容器镜像默认端口 `4530`；本地开发 `uv run uvicorn app.main:app --reload --port 4530`）
**所有业务路由前缀：`/api/v1`**

---

## 1. 认证与环境前置

所有业务接口都要求 Bearer Token。`nodeskclaw-knowledge` 不自己签发 token，而是把 Bearer 转发给 `nodeskclaw-backend`（`NODESKCLAW_BACKEND_URL`，默认 `http://127.0.0.1:4510`）换取 `KnowledgePrincipal`。

### 1.1 Postman Environment 变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `base_url` | Knowledge 服务地址 | `http://127.0.0.1:4530` |
| `api` | API 前缀 | `{{base_url}}/api/v1` |
| `access_token` | 登录 backend 拿到的用户 token | `eyJhbGciOi...` |
| `kb_id` | 调试时缓存的知识库 ID | — |
| `set_id` | 知识集 ID | — |
| `file_id` | 来源文件 ID | — |
| `job_id` | 入库任务 ID | — |
| `connector_id` | Connector ID | — |
| `run_id` | Sync Run ID | — |
| `session_id` | Chat Session ID | — |

### 1.2 获取 Token

先调用 **nodeskclaw-backend** 的登录接口（以实际后端为准）拿到用户 token，存到 `access_token`。

> 若 Knowledge 返回 `40100 errors.auth.credentials_missing`，说明 Authorization 头缺失或 token 失效。

### 1.3 Collection 级 Headers

| Header | 值 |
|--------|-----|
| `Authorization` | `Bearer {{access_token}}` |
| `Content-Type` | `application/json`（文件上传用 `multipart/form-data`，自动覆盖） |

### 1.4 统一响应结构

```json
{
  "code": 0,
  "error_code": null,
  "message_key": null,
  "message": "success",
  "data": { "...": "..." }
}
```

- 成功：`code = 0`，`data` 为业务数据
- 失败：`error_code` 非空，`message_key` 供 i18n，`message` 为默认中文文案
- 分页：`data.items[]`、`data.total`、`data.page`、`data.page_size`

---

## 2. Collection 目录结构（建议）

```
nodeskclaw-knowledge/
├── 00 Health & Meta
│   ├── GET  Health Live
│   ├── GET  Health Ready
│   └── GET  Metrics (Prometheus)
├── 01 Dashboard
│   └── GET  Dashboard
├── 02 Knowledge Bases
│   ├── GET    List KBs
│   ├── POST   Create KB
│   ├── GET    Get KB
│   ├── PATCH  Update KB
│   ├── DELETE Delete KB
│   ├── GET    Get Metadata Schema
│   ├── PUT    Put Metadata Schema
│   ├── GET    List KB ACL
│   ├── POST   Create KB ACL
│   └── DELETE Delete KB ACL
├── 03 Source Files (KB-scoped)
│   ├── GET    List Files in KB
│   └── POST   Upload File  (multipart)
├── 04 Source Files (Global)
│   ├── GET    List All Files
│   ├── GET    Get File
│   ├── PATCH  Patch Metadata
│   ├── GET    List Versions
│   ├── POST   Upload New Version  (multipart)
│   ├── POST   Activate Version
│   ├── POST   Archive / Unarchive
│   ├── POST   Detach (connector → manual)
│   ├── POST   Reparse
│   ├── GET    Download
│   └── ACL CRUD
├── 05 Knowledge Sets
│   └── CRUD + ACL + Bind KB
├── 06 Retrieval & Playground
│   ├── POST Retrieval
│   └── POST Retrieval Playground
├── 07 Chat (SSE)
│   ├── CRUD Sessions
│   ├── List Messages
│   └── POST Send Message (stream)
├── 08 Source Connectors (v1.3)
│   ├── GET  Types
│   ├── CRUD Connector
│   ├── PUT/DELETE Credential
│   ├── POST Test / Pause / Resume / Sync
│   └── Sync Runs (list/get/retry/cancel) + Objects
├── 09 Ingestion Jobs
│   └── List / Get / Retry / Cancel
├── 10 Evaluation
│   └── Sets / Cases / Runs / Compare
├── 11 Citations
│   └── GET Resolve Citation
└── 12 Audit
    └── GET Audit Logs
```

---

## 3. 逐接口调试（Method / Path / Body / 关键断言）

### 3.0 Health & Meta（无鉴权）

| # | Method & Path | 说明 |
|---|---------------|------|
| 1 | `GET /health/live` | 存活探针，`{"status":"ok"}` |
| 2 | `GET /health/ready` | 就绪探针（DB / RAGFlow） |
| 3 | `GET /metrics` | Prometheus 指标（无鉴权） |

---

### 3.1 Dashboard

**GET** `{{api}}/dashboard`

断言：`data.stats`、`data.recent_knowledge_sets`、`data.recent_documents` 存在。

---

### 3.2 Knowledge Bases

**POST** `{{api}}/knowledge-bases`
```json
{
  "name": "公司制度库",
  "description": "HR & Admin",
  "embedding_model": "bge-m3",
  "chunk_method": "naive",
  "visibility": "private",
  "tags": ["hr"]
}
```
测试脚本：
```javascript
const d = pm.response.json().data;
pm.environment.set("kb_id", d.id);
pm.test("created", () => pm.expect(d.id).to.exist);
```

**GET** `{{api}}/knowledge-bases?page=1&page_size=20&q=制度`
**GET** `{{api}}/knowledge-bases/{{kb_id}}`
**PATCH** `{{api}}/knowledge-bases/{{kb_id}}` body `{ "description": "..." }`
**PUT** `{{api}}/knowledge-bases/{{kb_id}}/metadata-schema` body `{ "fields": [ { "key": "dept", "label": "部门", "type": "string", "options": ["HR","IT"] } ] }`

**KB ACL**
- `GET    {{api}}/knowledge-bases/{{kb_id}}/acl`
- `POST   {{api}}/knowledge-bases/{{kb_id}}/acl`
```json
{ "subject_type": "member", "subject_id": "m_xxx", "permission": "read", "effect": "allow" }
```
- `DELETE {{api}}/knowledge-bases/{{kb_id}}/acl/{{acl_id}}`

---

### 3.3 Source Files

**List（KB 内）** `GET {{api}}/knowledge-bases/{{kb_id}}/files?page=1&page_size=20`
**List（全局）** `GET {{api}}/source-files?knowledge_base_id={{kb_id}}&parse_status=active`
**Get** `GET {{api}}/source-files/{{file_id}}`

**Upload（multipart）** `POST {{api}}/knowledge-bases/{{kb_id}}/files`
| Key | Type | Value |
|-----|------|-------|
| file | File | 选择本地文件 |
| metadata | Text | `{"dept":"HR"}` |

断言：返回 `data.id`、`data.source_kind = "manual"`。保存 `file_id`。

**Patch Metadata** `PATCH {{api}}/source-files/{{file_id}}/metadata` body `{ "metadata": {"dept": "IT"} }`
**Versions** `GET {{api}}/source-files/{{file_id}}/versions`
**Upload New Version** `POST {{api}}/source-files/{{file_id}}/versions`（multipart，同 upload）
**Activate** `POST {{api}}/source-files/{{file_id}}/versions/{{version_id}}/activate`
**Archive / Unarchive** `POST .../archive` / `.../unarchive`
**Detach** `POST {{api}}/source-files/{{file_id}}/detach`（仅 connector 管理的文件；把 connector 来源转成 manual）
**Reparse** `POST {{api}}/source-files/{{file_id}}/reparse`
**Download** `GET {{api}}/source-files/{{file_id}}/download`

> **v1.3 断言**：`GET /source-files/{id}` 的 `data` 应包含 `source_kind`、`connector_id`、`external_object_id`、`source_path`、`source_revision`、`sync_state`、`last_synced_at`。

**File ACL**
`GET/POST {{api}}/source-files/{{file_id}}/acl`，`DELETE .../acl/{{acl_id}}`，permission ∈ `read|download|update`。

---

### 3.4 Knowledge Sets

**POST** `{{api}}/knowledge-sets`
```json
{
  "name": "产品知识集",
  "knowledge_base_ids": ["{{kb_id}}"],
  "retrieval_config": { "top_n": 8, "similarity_threshold": 0.2 }
}
```
其余 CRUD、ACL（permission ∈ `read|use|update`）、`POST {{api}}/knowledge-sets/{{set_id}}/knowledge-bases`（绑定 KB，body `{ "knowledge_base_id": "...", "weight": 1.0 }`）。

---

### 3.5 Retrieval & Playground

**POST** `{{api}}/retrieval`
```json
{
  "knowledge_set_id": "{{set_id}}",
  "query": "报销流程是什么",
  "options": { "top_n": 8, "similarity_threshold": 0.2, "highlight": true },
  "filters": { "dept": ["HR"] }
}
```
断言：`data.query_id`、`data.chunks[]`（含 `chunk_id`、`file_name`、`content`、`similarity`、`highlight`）。

**POST** `{{api}}/retrieval/playground` — 额外返回 `plan`、`timing`、`filter_summary`（含 `unauthorized` / `metadata_mismatch` 计数，用于验证 ACL 与 metadata 过滤）。

---

### 3.6 Chat（SSE）

**Create Session** `POST {{api}}/chat/sessions`
```json
{ "knowledge_set_id": "{{set_id}}", "title": "咨询", "answer_mode": "detailed", "show_citations": true }
```
**List** `GET {{api}}/chat/sessions`，**Messages** `GET {{api}}/chat/sessions/{{session_id}}/messages`

**Send（流式）** `POST {{api}}/chat/sessions/{{session_id}}/messages`
```json
{ "content": "介绍一下年假政策", "stream": true }
```
- `Accept: text/event-stream`，响应为 SSE
- 事件序列：`retrieval_started` → `retrieval_completed` → `generation_started` → `delta`*（`data.content` 增量）→ `citation`* → `message_completed`
- `stream: false` 时返回标准 JSON（`data.content`、`data.citations[]`）

Postman 流式查看较受限，建议用 **Postman → Code → cURL** 或 VS Code REST Client 观察事件流。

**Citation 解析** `GET {{api}}/citations/{{citation_id}}`
断言 v1.3：`data` 含 `source_kind`、`connector_type`、`connector_name`、`source_path`、`source_revision`、`sync_state`、`source_freshness`、`accessible`、`reason`。

---

### 3.7 Source Connectors（v1.3 新增）

**Types** `GET {{api}}/source-connectors/types`
返回注册类型：`filesystem`、`http_manifest`、`s3_compatible`（含 capabilities）。

**List** `GET {{api}}/source-connectors?knowledge_base_id={{kb_id}}`
**Create** `POST {{api}}/knowledge-bases/{{kb_id}}/source-connectors`
```json
{
  "name": "共享盘-制度",
  "connector_type": "filesystem",
  "config": { "root_alias": "documents", "sub_path": "hr" },
  "sync_mode": "interval",
  "sync_interval_seconds": 3600
}
```
**Get / Patch / Delete** `GET|PATCH {{api}}/source-connectors/{{connector_id}}`；`DELETE ...?policy=archive_sources`（policy ∈ `archive_sources|detach_sources|delete_sources`）

**Test** `POST .../test`；**Pause / Resume** `POST .../pause|resume`
**Trigger Sync** `POST .../sync` body `{ "trigger": "manual" }` → 202 + SyncRun

**Credential（AES-256-GCM，绝不在响应回显）**
- `PUT {{api}}/source-connectors/{{connector_id}}/credential` body `{ "payload": { "auth_type": "bearer", "token": "xxx" } }`
- `DELETE .../credential`
- 断言：`ConnectorOut` 仅含 `credential_configured`、`credential_updated_at`，**无** secret 字段。

**Sync Runs**
- `GET  {{api}}/source-connectors/{{connector_id}}/sync-runs`
- `GET  {{api}}/source-connectors/{{connector_id}}/sync-runs/{{run_id}}`
- `POST .../sync-runs/{{run_id}}/retry` / `cancel`

**Objects** `GET {{api}}/source-connectors/{{connector_id}}/objects?state=active`

> 断言：`ConnectorOut.status` ∈ `active|paused|auth_error|error|deleting`；`sync_run.status` ∈ `pending|discovering|applying|waiting_ingestion|completed|partial|failed|cancelled`。

---

### 3.8 Ingestion Jobs

- `GET {{api}}/ingestion-jobs?knowledge_base_id={{kb_id}}&status=active`
- `GET /{{job_id}}`
- `POST /{{job_id}}/retry` / `cancel`

状态机（v1.3）：`pending → uploading → (upload_unknown) → ragflow_uploaded → metadata_synced → parse_dispatched → parsing → validating → active|failed|cancelled`

---

### 3.9 Evaluation

Sets / Cases CRUD、`POST {{api}}/evaluation/runs`（`{ "evaluation_set_id": "...", "profile_id": "..." }`）、`GET /runs`、`GET /runs/{id}/results`、`POST /compare`。

---

### 3.10 Audit

`GET {{api}}/audit?page=1&page_size=20&action=CONNECTOR_SYNC_START&resource_type=connector`

v1.3 新增动作：`CONNECTOR_*`、`SOURCE_DISCOVERED|SOURCE_CHANGED|SOURCE_DELETED|SOURCE_RESTORED|SOURCE_DETACHED`、`FILE_DETACH`。

---

## 4. 调试清单（冒烟）

按顺序跑：

1. Health Ready = ok
2. Create KB → 存 `kb_id`
3. Upload File → 存 `file_id`；轮询 `GET /ingestion-jobs?source_file_id=` 直到 `status=active`
4. Create Set 绑定 KB → 存 `set_id`
5. `POST /retrieval` 有 chunks
6. Create Chat Session → send message（stream=false）→ `message_completed` + citations
7. `GET /source-connectors/types` 有 filesystem
8. Create filesystem Connector（需服务端配置 `KNOWLEDGE_CONNECTOR_FS_ROOTS=documents=/data/...`）
9. `POST /sync` → 轮询 sync-run → `completed|partial`
10. `GET /source-connectors/{id}/objects` 有对象；`GET /citations/{id}` 带 connector provenance

---

## 5. 常见错误

| error_code / message_key | 含义 | 处理 |
|--------------------------|------|------|
| `40100 errors.auth.credentials_missing` | 缺 token | 补 Authorization |
| `40300 errors.auth.user_inactive` | 用户停用 | 检查 backend 用户 |
| `errors.knowledge.source_managed_by_connector` | connector 管理的文件人工上传版本 | 走 connector sync 或先 detach |
| `errors.knowledge.connector_interval_too_small` | sync_interval < 300s | 调大间隔 |
| `errors.knowledge.connector_config_invalid` | config 含 secret 字段 | secret 走 `PUT /credential` |
| `errors.knowledge.kb_not_found` | KB 不存在/无权限 | 校验 kb_id 与 ACL |

---

## 6. Collection 导入

本文档不提供 `.json` 导出文件。按第 3 节结构在 Postman 建 Collection，或直接在 Postman 中「Import → cURL」粘贴示例请求。建议把 `{{base_url}}`、`{{access_token}}` 配在 Environment，便于切 dev / staging。
