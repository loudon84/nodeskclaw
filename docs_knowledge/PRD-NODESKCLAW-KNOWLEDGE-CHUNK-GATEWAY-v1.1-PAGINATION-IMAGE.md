---
title: "nodeskclaw-knowledge Chunk Gateway v1.1 分页一致性 + Chunk Image Proxy 方案 PRD"
prd_id: "PRD-NK-KNOWLEDGE-CHUNK-GATEWAY-V1.1"
version: "1.1"
status: "APPROVED_FOR_PLAN"
template_version: "需求PRD工程模板 v1.0"
product: "nodeskclaw-knowledge"
repository: "loudon84/nodeskclaw"
branch: "feat/knowledge-v2.0"
remote_baseline_commit: "c030bfd9fd14f7a255ae660863b55e1a6629c0dd"
owner: "Knowledge Platform"
reviewers: ["Architecture", "Backend", "RAGFlow Integration", "Security", "QA"]
created_at: "2026-09-20"
updated_at: "2026-09-20"
target_release: "Chunk Gateway v1.1"
change_type: ["BROWNFIELD_CHANGE", "INTEGRATION", "BUGFIX"]
golden_consumer: "smc-copilot apps/work DocumentDetail + live RAGFlow"
implementation_head_sha: "74ebfeb3b33e2f817a90a107d2c6ffbbc04d3a9f"
chunk_gateway_v1_0_commit: "314a1934"
live_ragflow_version_observed: "0.27.0"
golden_ragflow_dataset_id: "956a88c8b26311f1a0c48d3842373341"
golden_ragflow_document_id: "fe656706b41311f1a0c48d3842373341"
grilling_decisions:
  - "Q1=A request-echo page/page_size + live Page1/Page2 + keyword total proof"
  - "Q2=A additive into contracts/frontend/v1.0.0 (no new 1.1.0 dir)"
  - "Q3=A missing image-bearing Golden doc → whole Release Gate BLOCKED"
  - "Q4=A Image GET auth = FilePermission.read (same as List)"
  - "Q5=A chunk not in current Active Document → 404 KNOWLEDGE_CHUNK_NOT_FOUND; image fetch=0"
  - "Q6=A resolve image via same-document list + id= then GET /documents/images/{token}"
  - "Q7=A Content-Length>20MiB reject before body; else stream with abort on oversize"
  - "Q8=A no Content-Disposition (preview); Cache-Control private,max-age=300 only"
  - "Q9=A bind implementation_head_sha=74ebfeb3; note Chunk Gateway land 314a1934"
  - "Q10=A encode Q1–Q9 into PRD; keep REVIEW until human APPROVED_FOR_PLAN"
  - "Q11=A image fetch timeout inherits RAGFLOW_TIMEOUT_SECONDS (default 60s)"
  - "Q12=A follow_redirects=false; any 3xx → provider failure path"
  - "Q13=A status=APPROVED_FOR_PLAN after Q11/Q12 encoded"
related_docs:
  - "需求PRD工程模板.md"
  - "PRD-NODESKCLAW-KNOWLEDGE-CHUNK-THIN-GATEWAY-v1.0.md"
  - "contracts/frontend/v1.0.0/FRONTEND-INTEGRATION.md"
  - "smc-copilot DocumentDetail Hybrid v2.1 PRD"
supersedes: "PRD-NODESKCLAW-KNOWLEDGE-CHUNK-THIN-GATEWAY-v1.0.md"
---

# 0. PRD 使用原则

本 PRD 按《需求PRD工程模板.md》编写，作为 Human + AI Coding 的 Machine-Executable Engineering Contract。

## 0.1 规范关键词

`MUST / MUST NOT / SHOULD / SHOULD NOT / MAY` 按工程模板定义。所有 `MUST / MUST NOT` MUST 映射至少一个 Acceptance。

## 0.2 No-Inference Rule

若 Plan/Coding Agent 无法唯一确定状态事实源、默认值、selection semantics、ownership、identity/hash scope、side effects、rollback、conflict、error 或 acceptance oracle：

```text
MUST report SPEC_SEMANTIC_GAP
MUST BLOCK plan generation
MUST NOT 自行补全
```

## 0.3 Source Integrity Gate

当前远端 `feat/knowledge-v2.0` HEAD 不一定包含用户本地已完成的 Chunk Thin Gateway 最新实现。本 PRD 依据：

```text
1. 已实施的 Chunk Thin Gateway v1.0 语义（land commit 314a1934）
2. contracts/frontend/v1.0.0/FRONTEND-INTEGRATION.md
3. live RAGFlow Document Chunk REST 行为（observed version 0.27.0）
4. 本 PRD v1.1 delta
5. grilling Q1–Q13 决议（见 frontmatter grilling_decisions）
```

在 `APPROVED_FOR_PLAN` 前：

```text
MUST 记录实际 nodeskclaw implementation HEAD SHA
MUST 验证 FRONTEND-INTEGRATION.md 与本 PRD Schema 一致
MUST 记录 live RAGFlow version / immutable deployment identity
```

已绑定（grilling Q9=A）：

```text
implementation_head_sha = 74ebfeb3b33e2f817a90a107d2c6ffbbc04d3a9f
chunk_gateway_v1_0_commit = 314a1934
live_ragflow_version_observed = 0.27.0
```

`APPROVED_FOR_PLAN` 当日若本地 HEAD 已前进，MUST 更新本 PRD 的 `implementation_head_sha` 为当日真实 HEAD；不一致则 `SPEC_SEMANTIC_GAP`，不得进入 Plan。

# 1. 文档元数据 / 源码基线

## 1.1 Remote Baseline

```text
repository: loudon84/nodeskclaw
branch: feat/knowledge-v2.0
remote HEAD observed (PRD draft): c030bfd9fd14f7a255ae660863b55e1a6629c0dd
local implementation HEAD bound: 74ebfeb3b33e2f817a90a107d2c6ffbbc04d3a9f
chunk gateway v1.0 land: 314a1934
```

## 1.2 已实现 v1.0 Contract 基线

```http
GET /api/v1/source-files/{source_file_id}/chunks?page={page}&page_size={page_size}&keywords={keywords}

PATCH /api/v1/source-files/{source_file_id}/chunks/{chunk_id}
Content-Type: application/json

{
  "file_version_id": "...",
  "available": true
}
```

冻结语义：

```text
RAGFlow = Chunk SOT
nodeskclaw-knowledge = Thin Gateway
GET = FilePermission.read
PATCH = FilePermission.update / 既有等价 KB manage policy
SourceFile.active_version_id = 当前版本 SOT
Consumer 不接触 dataset_id/document_id/RAGFlow URL/API Key
nodeskclaw 不持久化 Chunk content
nodeskclaw 不做 local keyword filter/rerank/re-chunk
```

## 1.3 v1.1 Delta

```text
A. Chunk 分页 contract 修复与证明
B. Chunk has_image 投影
C. SourceFile-scoped Chunk Image Proxy
D. frontend contract / tests / Golden Evidence
```

# 2. 一句话目标

让 `smc-copilot` 等 API Consumer 在拥有 SourceFile 读取权限且存在 active parsed version 的条件下，通过 SourceFile Chunk API 获得 **真实分页的 Chunk Page + 当前 Chunk 的安全图片字节**，同时保证 Provider `image_id` 永不暴露、图片访问受 SourceFile 权限和 FileVersion guard 约束、nodeskclaw 仍保持 Thin Gateway。

# 3. 背景与问题定义

## 3.1 Current State

当前已有：

```text
SourceFile.active_version_id
→ SourceFileVersion.ragflow_document_id
→ RuntimeBinding dataset identity
→ RagflowRuntimeAdapter/RagflowClient
→ SourceFile Chunk GET/PATCH
```

前端真实页面已经能加载文本 Chunk 与 available 状态，但：

```text
分页没有通过真实 Page1/Page2 Contract 证明
Chunk DTO 无图片能力
```

RAGFlow Document Chunk list 支持 `keywords/page/page_size/id`；Chunk/引用对象可能包含 `image_id/img_id`，RAGFlow 提供 document image GET。

## 3.2 Problem

### P-001 分页合同缺少真实证明

必须证明 `page=2` 真正下推 RAGFlow，`total` 不被 `items.length` 或 document chunk_count 覆盖。

### P-002 Consumer 无法显示 Chunk 图片

直接暴露 `image_id` 会泄漏 Provider identity、绕过 SourceFile ACL 并将 Desktop 绑定 RAGFlow。

### P-003 图片读取缺少版本/归属校验

仅凭 `chunk_id` 不能证明其属于当前 SourceFile + active FileVersion。

### P-004 二进制代理扩大攻击面

必须定义 MIME、大小、timeout、redirect 和日志边界。

## 3.3 Impact

```text
业务：DocumentDetail 无法达到 RAGFlow 图文 Chunk 阅读效果。
工程：分页 bug 难以区分 backend/frontend；image_id 会形成强耦合。
安全：可能越权读取其它文档图片或把活动内容送入 Renderer。
运维：RAGFlow 变化应只影响 Adapter。
AI Coding：若 total authority、图片归属、byte cap 未冻结，会产生多种实现。
```

# 4. Scope

## 4.1 In Scope

```text
SCOPE-001 page/page_size/keywords 精确透传。
SCOPE-002 total 来自 RAGFlow 当前 query response。
SCOPE-003 multi-page live contract tests。
SCOPE-004 Chunk DTO 增加 has_image:boolean。
SCOPE-005 新增 SourceFile Chunk Image GET。
SCOPE-006 Image GET 使用 file_version_id stale guard。
SCOPE-007 server-side chunk_id → provider image token 解析。
SCOPE-008 MIME/byte cap/timeout/redirect 安全。
SCOPE-009 更新 frontend integration contract。
SCOPE-010 live RAGFlow Golden Consumer。
```

## 4.2 Out of Scope

```text
NON-GOAL-001 MUST NOT 暴露 image_id/img_id。
NON-GOAL-002 MUST NOT 接受 dataset_id/document_id/provider URL。
NON-GOAL-003 MUST NOT 新建 Chunk/Image ORM 业务表。
NON-GOAL-004 MUST NOT 持久化图片副本作为 SOT。
NON-GOAL-005 MUST NOT Chunk Add/Delete/content edit。
NON-GOAL-006 MUST NOT 本地重算 filtered total。
NON-GOAL-007 MUST NOT 用 document.chunk_count 替代 query total。
NON-GOAL-008 MUST NOT 跟随任意 redirect（follow_redirects=false；grilling Q12=A）。
```

## 4.3 Architecture Boundary

| Domain | Owner | Input | Output | 不负责 |
|---|---|---|---|---|
| SourceFile API | nodeskclaw | source_file_id | public contract | UI |
| Permission | nodeskclaw | principal/file | allow/deny | provider auth |
| Runtime Resolver | nodeskclaw | source/version | provider refs | Chunk storage |
| RAGFlow Adapter | nodeskclaw | provider refs/query | page/image | Product ACL |
| Chunk/Image SOT | RAGFlow | provider identity | data/bytes | SourceFile ACL |
| Consumer | smc-copilot | public API | UI | provider IDs |

# 5. Terminology / Domain Model

**Provider Page**：RAGFlow 对 document + keywords + page + page_size 返回的 Chunk page。

**Public Chunk Page**：`source_file_id/file_version_id/items/total/page/page_size`。

**total**：当前完整 query 匹配总数，SOT=`RAGFlow response.data.total`。

**has_image**：Provider Chunk 存在非空图片引用的布尔投影；不是图片 ID。

**Chunk Image Proxy**：Consumer 仅凭 `source_file_id + file_version_id + chunk_id` 请求图片，由 server 解析 Provider image token。

**Version Guard**：`request.file_version_id == SourceFile.active_version_id`。

# 6. System Context

## 6.1 Context Diagram

```text
smc-copilot
 ├─ GET source-file chunks
 │      ↓
 │  nodeskclaw SourceChunkService
 │      ↓
 │  RAGFlow list document chunks
 │
 └─ GET source-file chunk image
        ↓
    ACL + version guard
        ↓
    RAGFlow chunk lookup by id
        ↓
    RAGFlow document image GET
        ↓
    validated image bytes
```

## 6.2 System Boundary

```text
Inside: ACL, source/version mapping, pagination normalization, image proxy, errors, logs
Outside: RAGFlow Chunk/Image storage, Desktop rendering
Trusted: authenticated principal, ORM relations
Untrusted: query params, chunk_id, provider JSON, provider image headers/body
```

# 7. Authoritative State / Source of Truth

| State | Role | Type | Authoritative? | Writer | Reader | Auto Override |
|---|---|---|---:|---|---|---:|
| active_version_id | current version | OBSERVED_STATE | YES | nodeskclaw | gateway | YES |
| ragflow_document_id | mapping | RESOLVED_STATE | YES | ingestion | gateway | YES |
| dataset binding | mapping | RESOLVED_STATE | YES | runtime | gateway | YES |
| Chunk content | data | OBSERVED_STATE | YES | RAGFlow | consumer | YES |
| Chunk total | query count | OBSERVED_STATE | YES | RAGFlow | gateway | YES |
| provider image token | internal identity | OBSERVED_STATE | YES | RAGFlow | adapter only | YES |
| has_image | projection | RESOLVED_STATE | NO | gateway | consumer | YES |
| image bytes | content | OBSERVED_STATE | YES | RAGFlow | consumer | YES |
| Evidence | verification | EVIDENCE_STATE | YES | tests | reviewer | NO |

# 8. State Machine

## 8.1 Chunk List

```text
RECEIVED → AUTHORIZED → RESOLVED → PROVIDER_FETCH → VALIDATED → NORMALIZED → RESPONDED
                                          └──────── failure ───────→ FAILED
```

非法：未授权前 Provider fetch；无 provider total 却 success。

## 8.2 Chunk Image

```text
RECEIVED
→ AUTHORIZED(read)
→ VERSION_GUARDED
→ DOCUMENT_RESOLVED
→ CHUNK_RESOLVED
→ IMAGE_REF_RESOLVED
→ IMAGE_FETCHING
→ IMAGE_VALIDATED
→ RESPONDED
```

错误状态：`NO_IMAGE / VERSION_CONFLICT / CHUNK_NOT_FOUND / PROVIDER_UNAVAILABLE / TYPE_UNSUPPORTED / TOO_LARGE / CONTRACT_INVALID`。

# 9. Data / Schema Contract

## 9.1 SourceFileChunkOut v1.1

```python
class SourceFileChunkOut(BaseModel):
    id: str
    content: str
    available: bool | None = None
    has_image: bool = False
    positions: list | None = None
    important_keywords: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
```

```text
schema id: source-file-chunk-out
version: 1.1
additionalProperties: false
compatibility: additive to v1.0
```

| Field | Type | Required | Default | Authority | Meaning |
|---|---|---:|---|---|---|
| id | string | YES | - | RAGFlow | opaque chunk token |
| content | string | YES | - | RAGFlow | raw content |
| available | bool/null | YES | null | RAGFlow | availability |
| has_image | bool | YES | false | gateway | image ref exists |
| positions | array/null | YES | null | RAGFlow | opaque positions |
| important_keywords | string[] | YES | [] | RAGFlow | keywords |
| questions | string[] | YES | [] | RAGFlow | questions |

Forbidden public fields：`image_id,img_id,dataset_id,document_id,ragflow_*,provider_url`。

## 9.2 SourceFileChunkPageOut v1.1

```python
class SourceFileChunkPageOut(BaseModel):
    source_file_id: str
    file_version_id: str
    items: list[SourceFileChunkOut]
    total: int
    page: int
    page_size: int
```

```text
total = provider data.total
page = validated request page（MUST 请求回显；MUST NOT 用 Provider 回写覆盖）
page_size = validated request page_size（同上）
```

## 9.3 Chunk Image Request

```http
GET /api/v1/source-files/{source_file_id}/chunks/{chunk_id}/image?file_version_id={file_version_id}
```

权限：`FilePermission.read`（与 Chunk List 相同；grilling Q4=A）。

## 9.4 Chunk Image Response

```http
200
Content-Type: image/png | image/jpeg | image/webp | image/gif
Cache-Control: private, max-age=300
Content-Length: <= 20971520
<body bytes>
```

MIME allowlist：`image/png,image/jpeg,image/webp,image/gif`。

MUST deny：`image/svg+xml,text/html,application/xml,application/javascript`。

Byte cap：`20 MiB = 20971520`。

Content-Disposition（grilling Q8=A）：

```text
MUST NOT set Content-Disposition: attachment
MUST NOT invent download filename
MAY omit Content-Disposition entirely（推荐）或仅 Content-Disposition: inline
```

# 10. Requirement Units

## REQ-PAGE-001 — Provider Pagination Preservation

### Goal
保证 SourceFile Chunk API 的分页由 RAGFlow 执行。

### Normative Requirement

```text
MUST pass page exactly.
MUST pass page_size exactly.
MUST pass trimmed keywords exactly when non-empty.
MUST use provider data.total.
MUST return validated request page/page_size（请求回显；grilling Q1=A）。
MUST NOT 用 Provider 返回的 page/page_size 覆盖请求回显。
MUST NOT total=len(chunks).
MUST NOT use document chunk_count as filtered total.
```

### Inputs
`source_file_id,page>=1,1<=page_size<=100,keywords<=200 trimmed chars`。

### Preconditions
SourceFile readable；active version/runtime document exists。

### Authoritative State
`total=RAGFlow data.total`；items=`RAGFlow data.chunks`。

### State Transition
request → provider fetch → normalized page。

### Allowed Side Effects
DB reads、RAGFlow GET、sanitized telemetry。

### Forbidden Side Effects
DB write、Provider write、local all-chunk pagination。

### Ownership Scope
`NONE`

### Idempotency
同 provider state + 同 query → equivalent result。

### Failure Semantics

```text
provider total missing/non-int → KNOWLEDGE_CHUNK_CONTRACT_INVALID / 502 / retryable=false
invalid page/page_size → 422 / provider call=0
```

### Postconditions
`result.page=request.page`；`page_size` 相同；`total=provider.total`。

### Invariants
`INV-PAGE-001 filtered total authority = provider`。

### Error Codes
`KNOWLEDGE_CHUNK_CONTRACT_INVALID`

### Acceptance
`A-PAGE-001,A-PAGE-002,A-PAGE-003,A-NEG-001`

### Evidence
unit + live multi-page；implementation SHA；provider request summary。

## REQ-PAGE-002 — Multi-page Golden Contract

### Goal
禁止只测试 Page1。

### Normative Requirement
Golden document MUST have >=11 matching chunks：

```text
page=1,size=10 → items=10,total>=11,page=1
page=2,size=10 → items>=1,page=2
Page1 ids 与 Page2 ids 在稳定数据下不重叠
```

Filtered keyword MUST 证明 total 为 filtered total。

### Inputs
live SourceFile。

### Preconditions
active parsed document >=11 chunks。

### Authoritative State
RAGFlow。

### Side Effects
GET only。

### Failure Semantics
不足 11 chunks → Acceptance `BLOCKED`，MUST NOT PASS。

### Acceptance
`A-PAGE-004`

### Evidence
live JSON summary + runtime identity。

## REQ-IMG-001 — Public `has_image`

### Goal
Consumer 判断是否需要图片请求但不获得 provider token。

### Normative Requirement

```text
MUST non-empty provider image_id OR img_id → has_image=true.
MUST absent/empty → false.
MUST NOT expose image token.
MUST NOT infer image from content HTML.
```

### Inputs
provider chunk JSON。

### Authority
provider image reference。

### Allowed Side Effects
none。

### Forbidden Side Effects
list 时不额外 fetch image。

### Ownership Scope
`FIELD: generated projection`

### Failure Semantics
present but invalid image token type → CONTRACT_INVALID。

### Invariants
`INV-IMG-001 public schema no provider image token`。

### Acceptance
`A-IMG-001,A-NEG-002`

## REQ-IMG-002 — SourceFile Chunk Image Proxy

### Goal
安全获取当前 SourceFile/Version/Chunk 图片。

### Normative Requirement

MUST 实现：

```http
GET /api/v1/source-files/{source_file_id}/chunks/{chunk_id}/image?file_version_id=...
```

执行顺序 MUST：

```text
1 authenticate
2 SourceFile read permission（FilePermission.read；grilling Q4=A）
3 file_version_id == active_version_id
4 resolve active version
5 resolve dataset/document
6 resolve chunk_id within current document via Provider list + id={chunk_id}
   （同一 dataset/document；grilling Q6=A；MUST NOT 全部分页扫描）
7 extract provider image token（image_id OR img_id）from that chunk only
8 fetch provider image via GET /api/v1/documents/images/{provider_image_token}
9 validate MIME/size（见 REQ-IMG-003）
10 return bytes
```

MUST NOT 从 Consumer 接受 `image_id/dataset_id/document_id/provider_url`。

chunk 不属于当前 Active Document（list+id 未命中 / total=0 / id 不匹配）时（grilling Q5=A）：

```text
MUST 404 KNOWLEDGE_CHUNK_NOT_FOUND
MUST provider image fetch count = 0
```

### Inputs
source_file_id/chunk_id/file_version_id/principal。

### Preconditions
read permission；version match；chunk current；has image。

### Authority
mapping=nodeskclaw；Chunk/image=RAGFlow。

### Side Effects
GET + logs only。

### Ownership Scope
`NONE`

### Idempotency
read-only。

### Failure Semantics

```text
stale version → 409 KNOWLEDGE_CHUNK_VERSION_CONFLICT / image fetch=0
chunk miss → 404 KNOWLEDGE_CHUNK_NOT_FOUND
no image → 404 KNOWLEDGE_CHUNK_IMAGE_NOT_FOUND
provider unavailable → 503 KNOWLEDGE_CHUNK_PROVIDER_UNAVAILABLE retryable=true
```

### Postconditions
returned bytes belong to guarded current chunk。

### Invariants
`INV-IMG-002 arbitrary provider image token cannot be requested by client`。

### Acceptance
`A-IMG-002,A-IMG-003,A-SEC-001,A-NEG-003`

## REQ-IMG-003 — Image Content Safety

### Goal
限制进入 Desktop 的二进制。

### Normative Requirement

```text
MUST allow only png/jpeg/webp/gif.
MUST reject SVG/HTML/XML/JS.
MUST cap 20 MiB.
MUST Cache-Control private,max-age=300.
MUST NOT set Content-Disposition: attachment（grilling Q8=A）。
MUST NOT log bytes/token/authorization.
```

Content-Type missing → `KNOWLEDGE_CHUNK_IMAGE_TYPE_UNSUPPORTED`。

字节超限策略（grilling Q7=A）：

```text
若存在合法可解析 Content-Length 且 > 20971520 → MUST 不读 body，直接 413 KNOWLEDGE_CHUNK_IMAGE_TOO_LARGE
否则（无 Length / Length 不可信）→ MUST 流式读取；累计字节 > 20971520 → abort + 413
MUST NOT 先整包 buffer 到内存再判大小
```

### Side Effects
network/log only。

### Failure Semantics
`415 KNOWLEDGE_CHUNK_IMAGE_TYPE_UNSUPPORTED`；`413 KNOWLEDGE_CHUNK_IMAGE_TOO_LARGE`。

### Invariants
`INV-IMG-003 SVG never proxied in v1.1`。

### Acceptance
`A-IMG-004,A-IMG-005,A-NEG-004`

## REQ-INT-001 — RAGFlow Chunk Page Client

### Goal
低层 client 保留 REST pagination metadata。

### Normative Requirement
MUST 提供等价 internal API：

```python
list_document_chunks_page(dataset_id, document_id, page, page_size, keywords="", id="") -> RagflowChunkPage
```

`RagflowChunkPage={chunks,total,page,page_size}`。

MUST NOT 破坏既有 `list_document_chunks()` caller-visible 行为，除非全 caller 原子迁移并 regression-proven。

### Failure Semantics
malformed page → contract invalid。

### Acceptance
`A-INT-001,A-COMPAT-001`

## REQ-INT-002 — RAGFlow Image Fetch

### Goal
封装 image endpoint，禁止 service 拼任意 URL。

### Normative Requirement
MUST expose internal operation equivalent：

```python
get_document_image(provider_image_token) -> ProviderBinaryResponse
```

Provider path：`/api/v1/documents/images/{provider_image_token}`。

MUST restrict configured RAGFlow origin；MUST NOT accept absolute URL。

超时与 redirect（grilling Q11=A / Q12=A）：

```text
MUST 使用与 RagflowClient 相同的 RAGFLOW_TIMEOUT_SECONDS（默认 60s）
MUST follow_redirects=false
任意 3xx → MUST 视为 Provider 失败（→ KNOWLEDGE_CHUNK_PROVIDER_UNAVAILABLE 或 CONTRACT_INVALID 路径；MUST NOT 跟随）
MUST NOT 跟随非配置 origin redirect
```

### Acceptance
`A-INT-002,A-NEG-005`

## REQ-CONTRACT-001 — Frontend Integration Contract v1.1 Extension

### Goal
给 smc-copilot 稳定 public contract。

### Normative Requirement
`contracts/frontend/v1.0.0/FRONTEND-INTEGRATION.md` MUST additive document（grilling Q2=A；MUST NOT 新开 `v1.1.0` 目录）：

```text
has_image
Chunk Image endpoint
file_version_id query guard
MIME/bytes response
error codes
20MiB cap
pagination authority/invariants（请求回显 page/page_size；provider total）
Content-Disposition 预览语义（无 attachment）
```

MUST NOT document Provider image/runtime IDs。

### Acceptance
`A-CONTRACT-001,A-NEG-006`

## REQ-OBS-001 — Observability

### Normative Requirement
List logs MUST include：`operation_id,source_file_id,file_version_id,page,page_size,keywords_present,provider_total,returned_count,duration_ms,error_code`。

Image logs MUST include：`operation_id,source_file_id,file_version_id,chunk_id_digest,mime_type,byte_count,duration_ms,error_code`。

MUST NOT log keyword text/chunk content/image bytes/provider image token/API key/Authorization。

### Acceptance
`A-OBS-001,A-NEG-007`

# 11. Side-Effect Contract

| Operation | DB Write | File Write | Network | Cache | User Data | Business Source |
|---|---:|---:|---:|---:|---:|---:|
| list chunks | NO | NO | GET | MAY transport | NO | NO |
| page2/search | NO | NO | GET | MAY transport | NO | NO |
| image proxy | NO | NO | GET | private HTTP MAY | NO | NO |
| frontend contract update | NO | YES | NO | NO | NO | NO |

Logs/telemetry 算 side effect，必须 sanitize。

# 12. Ownership Contract

```text
SourceFile/Version = WHOLE_RESOURCE / nodeskclaw
Chunk content/image = USER_OWNED/BUSINESS_SOURCE / RAGFlow
provider image token = PROVIDER_INTERNAL
has_image = GENERATED_ONLY / nodeskclaw
frontend contract = FILE / nodeskclaw
```

Drift：`request.file_version_id != active_version_id → BLOCK`。

# 13. Hash / Identity Contract

```text
SourceFile = source_file_id
FileVersion = file_version_id
Chunk = opaque chunk_id
Provider image identity = server-only
```

Operational chunk digest：`SHA256(chunk_id UTF-8)`，日志只显示前 12 个 lowercase hex；禁止业务使用。

# 14. Transaction Contract

Chunk list/image GET 无业务事务、无 rollback。

Frontend contract 文件修改：`T0=previous file`；写失败 MUST 保持/恢复 T0。

# 15. Conflict Contract

| Conflict | Detection | Default | Error | Mutation |
|---|---|---|---|---:|
| stale image version | request vs active | BLOCK | VERSION_CONFLICT | 0 |
| chunk not current doc | provider lookup miss | BLOCK | CHUNK_NOT_FOUND | 0 |
| no image | no token | BLOCK | IMAGE_NOT_FOUND | 0 |
| total missing | provider schema | BLOCK | CONTRACT_INVALID | 0 |
| page > last | empty + total | RESPOND valid empty | none | 0 |
| invalid MIME | header | BLOCK | TYPE_UNSUPPORTED | 0 |
| too large | header/stream | BLOCK | TOO_LARGE | 0 |

MUST NOT last-writer/best-effort/auto-overwrite。

# 16. Compatibility / Migration

Migration：

```text
bind actual implemented SHA
add page invariants/tests
add has_image projection
add image client/service/route
update frontend contract
run regression
run live Golden
```

`has_image` 是 additive；现有 GET/PATCH routes MUST 不变。

# 17. External Dependency Contract

RAGFlow required：

```text
GET /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks
GET /api/v1/documents/images/{image_id}
list params: keywords,page,page_size,id
list metadata: data.chunks,data.total
```

Before approval MUST pin live RAGFlow version/image digest；无 direct Consumer fallback。

# 18. Security Contract

| Threat | Control | Acceptance |
|---|---|---|
| cross-file image | ACL+version guard+chunk lookup | A-SEC-001 |
| provider ID leak | has_image + server lookup | A-NEG-002 |
| arbitrary URL | fixed RAGFlow origin + follow_redirects=false | A-NEG-005 |
| SVG active content | MIME deny | A-IMG-004 |
| memory pressure | 20MiB cap | A-IMG-005 |
| credentials | server only | A-NEG-007 |
| query injection | typed params | A-PAGE-003 |

# 19. Observability

Stages：`AUTH → AUTHORIZE → RESOLVE_FILE → VERSION_GUARD → RESOLVE_RUNTIME → FETCH_CHUNK_PAGE/RESOLVE_IMAGE → VALIDATE → RETURN`。

Every operation MUST include `operation_id,stage,status,timestamp,source_file_id,error_code`。

# 20. Acceptance Design

## A-PAGE-001 — Page1 Exact Query
Given page1,size10。When GET。Then provider page=1,size=10，call=1。Oracle exact args。

## A-PAGE-002 — Page2 Exact Query
Given page2,size10。Then provider page=2，response page=2,size=10。

## A-PAGE-003 — Provider Total Authority
Given items=10,total=137。Then response.total=137。Oracle `total != len(items)`。

## A-PAGE-004 — Live Multi-page
Live doc >=11 chunks：P1 size10 count10，P2 count>=1，稳定数据下 id sets 不重叠。

## A-IMG-001 — has_image Projection
Provider image token non-empty → `has_image=true`，serialized keys 无 token。

## A-IMG-002 — Image Success
Matching version + valid chunk：HTTP200，MIME allowlist，0<bytes<=20MiB。

## A-IMG-003 — Version Guard
Active V2/request V1 → HTTP409，provider image fetch count=0。

## A-IMG-004 — SVG Rejected
Provider SVG → HTTP415 + exact error。

## A-IMG-005 — Oversize Rejected
20MiB+1 → HTTP413。

## A-INT-001 — Page Client Metadata
Provider chunks/total preserved exactly。

## A-INT-002 — Fixed Origin
Captured request MUST use configured RAGFlow origin/path；no caller absolute URL。

## A-CONTRACT-001 — Contract Additive
Frontend contract includes v1.1 fields/route/errors and excludes provider IDs。

## A-COMPAT-001 — Existing Regression
Existing v1.0 Chunk GET/PATCH suite PASS。

## A-SEC-001 — Unauthorized Image
No read permission → chunk/image provider call count=0。

## A-OBS-001 — Sanitized Logs
Forbidden token/content fixtures match count=0。

# 21. Acceptance Input Matrix

| Case | page | size | keyword | total | image | version | Expected |
|---|---:|---:|---|---:|---|---|---|
| 1 | 1 | 10 | none | 11 | no | match | 10 items |
| 2 | 2 | 10 | none | 11 | no | match | 1 item |
| 3 | 1 | 50 | none | 11 | no | match | 11/one page |
| 4 | 1 | 10 | x | 3 | no | match | total=3 |
| 5 | 99 | 10 | none | 11 | no | match | empty valid page |
| 6 | 0 | 10 | none | n/a | no | n/a | 422 |
| 7 | 1 | 101 | none | n/a | no | n/a | 422 |
| 8 | 1 | 10 | none | missing | no | match | CONTRACT_INVALID |
| 9 | - | - | - | - | png | match | 200 |
| 10 | - | - | - | - | none | match | 404 |
| 11 | - | - | - | - | png | stale | 409 |
| 12 | - | - | - | - | svg | match | 415 |
| 13 | - | - | - | - | >20MiB | match | 413 |
| 14 | - | - | - | - | provider503 | match | 503 retryable |

# 22. Negative Acceptance

```text
A-NEG-001 total replaced by items.length → FAIL
A-NEG-002 public image_id/img_id → FAIL
A-NEG-003 endpoint accepts client image_id → FAIL
A-NEG-004 SVG returned → FAIL
A-NEG-005 caller absolute provider URL used → FAIL
A-NEG-006 frontend contract exposes provider runtime IDs → FAIL
A-NEG-007 logs contain image token/API key/full content → FAIL
A-NEG-008 local Chunk/Image persistence table introduced → FAIL
```

# 23. Failure Injection

| Point | Postcondition |
|---|---|
| before page GET | 0 mutation |
| page timeout | 503/no local state |
| malformed total | 502 contract invalid |
| before image version guard | no provider image GET |
| chunk lookup timeout | 503 |
| no image | 404 |
| Content-Length > cap | abort before buffer |
| stream crosses cap | abort + 413 |
| invalid MIME | 415 |
| contract file write fail | T0 preserved |

# 24. Evidence Contract

```json
{
  "acceptance_id": "A-PAGE-004",
  "status": "PASS",
  "requirement_ids": ["REQ-PAGE-002"],
  "test_ids": ["TEST-A-PAGE-004"],
  "command": "pytest ...",
  "exit_code": 0,
  "oracle": {"type":"multi_page_distinct_ids","expected":"p1=10,p2>=1","actual":{}},
  "repo": "loudon84/nodeskclaw",
  "branch": "feat/knowledge-v2.0",
  "commit_sha": "<implementation-sha>",
  "ragflow_version": "<version>",
  "ragflow_image_digest": "<immutable-digest>",
  "timestamp": "<ISO8601>",
  "evidence_files": []
}
```

`SKIPPED/BLOCKED != PASS`。

# 25. Release Gate

Required：`A-PAGE-001..004,A-IMG-001..005,A-INT-001..002,A-CONTRACT-001,A-COMPAT-001,A-SEC-001,A-OBS-001,A-NEG-001..008`。

任一非 PASS → `Release Gate FAIL` 且 process exit !=0。

无带图 Golden 文档时（grilling Q3=A）：

```text
MUST 将整份 Release Gate 标为 BLOCKED
MUST NOT 将缺图 Acceptance 记为 PASS / SKIPPED-as-PASS
MUST NOT 用纯文本文档冒充 image Golden
```

# 26. Golden Consumer / Real-world Acceptance

同一真实 SourceFile MUST 验证：

```text
page_size=10 page1
page_size=10 page2
keyword filtered query
至少一个 has_image=true chunk
image bytes endpoint
stale file_version_id image request=409
```

Synthetic fixture MUST NOT 替代。

用户指定的带图 RAGFlow 文档（非盲测碰撞；用于 map 到对应 SourceFile / Evidence）：

```text
golden_ragflow_dataset_id = 956a88c8b26311f1a0c48d3842373341
golden_ragflow_document_id = fe656706b41311f1a0c48d3842373341
```

Evidence MUST 记录将该 Provider document 映射到的 `source_file_id` / `file_version_id`（若映射失败 → Release Gate BLOCKED，不得另选盲扫文档替代，除非用户书面更新本 PRD）。

# 27. Requirement Traceability Matrix

| Requirement | Invariant | Acceptance | Test | Evidence | Gate |
|---|---|---|---|---|---|
| REQ-PAGE-001 | INV-PAGE-001 | A-PAGE-001..003,A-NEG-001 | TEST-PAGE-* | EVID-PAGE-* | REQUIRED |
| REQ-PAGE-002 | live multi-page | A-PAGE-004 | TEST-PAGE-LIVE | EVID-PAGE-LIVE | REQUIRED |
| REQ-IMG-001 | INV-IMG-001 | A-IMG-001,A-NEG-002 | TEST-IMG-DTO | EVID-* | REQUIRED |
| REQ-IMG-002 | INV-IMG-002 | A-IMG-002/003,A-SEC-001,A-NEG-003 | TEST-IMG-API-* | EVID-* | REQUIRED |
| REQ-IMG-003 | INV-IMG-003 | A-IMG-004/005,A-NEG-004 | TEST-IMG-SAFE-* | EVID-* | REQUIRED |
| REQ-INT-001 | page preserve | A-INT-001,A-COMPAT-001 | TEST-CLIENT-PAGE | EVID-* | REQUIRED |
| REQ-INT-002 | fixed origin | A-INT-002,A-NEG-005 | TEST-CLIENT-IMG | EVID-* | REQUIRED |
| REQ-CONTRACT-001 | provider-neutral | A-CONTRACT-001,A-NEG-006 | TEST-CONTRACT | EVID-* | REQUIRED |
| REQ-OBS-001 | sanitized | A-OBS-001,A-NEG-007 | TEST-LOG | EVID-* | REQUIRED |

# 28. Plan Generation Contract

仅 `status=APPROVED_FOR_PLAN` 可生成 `.plan.md`。

Before approval MUST bind actual nodeskclaw HEAD SHA、live RAGFlow immutable identity、actual frontend contract revision。

# 29. `.plan.md` 输出标准

每个 Todo MUST 有：

```yaml
id:
requirement_refs:
acceptance_refs:
files_or_symbols:
implementation_goal:
preconditions:
state_transition:
side_effect_scope:
failure_cases:
verification:
status:
evidence:
```

# 30. Code Review Contract

Review 顺序：Requirement → SOT → pagination authority → provider containment → image ACL/version guard → side effects → failure postcondition → AC → Evidence → code quality。

# 31. PRD Quality Gate

```text
[x] Goal/Scope/Boundary 明确
[x] SOT/State Machine 明确
[x] page/page_size/total authority 明确（请求回显；grilling Q1）
[x] has_image/image route/version guard 明确
[x] GET read-only + Image auth=read（grilling Q4）
[x] chunk resolve = list+id；miss → 404 且不拉图（grilling Q5/Q6）
[x] no local image SOT
[x] error codes + byte/MIME failure 明确（grilling Q7）
[x] Content-Disposition 预览语义（grilling Q8）
[x] MUST→AC / MUST NOT→Negative AC
[x] live multi-page matrix + 无图整闸 BLOCKED（grilling Q3）
[x] Golden Provider document 身份已钉（用户指定）
[x] Evidence contract
[x] grilling Q1–Q13 已编码进本 PRD（见 frontmatter grilling_decisions）
[x] image timeout inherit + follow_redirects=false（grilling Q11/Q12）
[x] actual local implementation SHA bound（74ebfeb3；grilling Q9）
[x] status=APPROVED_FOR_PLAN（grilling Q13=A）
```

# 32. PRD 禁止写法

禁止“分页正常即可 / 图片能显示即可 / 按需要缓存 / 安全代理图片 / 兼容 RAGFlow”。必须使用本 PRD 的 exact params、MIME、byte cap、version guard、Oracle。

# 33. 推荐 ID 体系

已采用 `REQ-PAGE/IMG/INT/CONTRACT/OBS`、`A-PAGE/IMG/NEG`。

# 34. 最小完整结构检查

已覆盖 Meta、Goal、Background、Scope、Boundary、Terminology、SOT、State Machine、Schema、Requirements、Side Effects、Ownership、Identity、Transaction、Failure、Conflict、Migration、External Dependency、Security、Observability、Acceptance、Matrix、Negative、Failure Injection、Evidence、Traceability、Release Gate、Plan Gate、DoD。

# 35. Definition of Done

```text
[x] actual nodeskclaw HEAD SHA bound（74ebfeb3；若实现前 HEAD 前进须重绑）
[ ] page/page_size 请求回显 + keywords exact provider pass-through
[ ] provider total preserved
[ ] page1/page2 live test PASS
[ ] filtered total live test PASS
[ ] has_image additive contract implemented（v1.0.0 目录）
[ ] public DTO no image_id/img_id
[ ] SourceFile Chunk image endpoint implemented
[ ] file_version_id stale guard implemented
[ ] chunk current-document resolution via list+id implemented
[ ] PNG/JPEG/WebP/GIF allowed；无 Content-Disposition attachment
[ ] SVG denied
[ ] 20MiB cap：Content-Length 先拒 + stream abort
[ ] no provider credential/image token logs
[ ] frontend integration contract updated（additive v1.0.0）
[ ] existing GET/PATCH regression PASS
[ ] Golden Consumer PASS（指定带图 document；缺图 → Gate BLOCKED）
[ ] Required AC Evidence complete
[ ] Release Gate PASS
```

> 最终原则：**RAGFlow 继续拥有 Chunk 与图片事实；nodeskclaw-knowledge 只提供经过权限、版本与 Provider 隔离后的稳定 SourceFile Contract。**
