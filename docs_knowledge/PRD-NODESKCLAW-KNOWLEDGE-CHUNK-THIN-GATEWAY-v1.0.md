---
title: "nodeskclaw-knowledge SourceFile Chunk Thin Gateway v1.0 方案 PRD"
subtitle: "RAGFlow Chunk API → nodeskclaw-knowledge Thin Gateway"
prd_id: "PRD-NK-KNOWLEDGE-CHUNK-GATEWAY-V1"
version: "1.0"
status: "APPROVED_FOR_PLAN"
template_version: "需求PRD工程模板 v1.0"
product: "nodeskclaw-knowledge"
repository: "loudon84/nodeskclaw"
branch: "feat/knowledge-v2.0"
baseline_commit: "1d29fac6383ce64e0d82dfe4d445b4fd549a14ec"
owner: "Knowledge Platform"
reviewers:
  - "Architecture"
  - "Backend"
  - "RAGFlow Integration"
  - "Security"
  - "QA"
created_at: "2026-09-19"
updated_at: "2026-09-19"
grilling_decisions:
  - "Q1=A active-version-only; history chunks NON-GOAL"
  - "Q2=A available-only PATCH; content edit out of scope"
  - "Q3=A file_version_id stale guard required"
  - "Q4=A keep minimal public Chunk DTO"
  - "Q5=A available may be null on list"
  - "Q6=A additive frontend contract 1.0.0"
  - "Q7=C-then-A live RAGFlow probe PASS (v0.27.0) before APPROVED_FOR_PLAN"
  - "Q8=A PATCH auth = FilePermission.update OR KbPermission.manage"
  - "Q9=A additive into contracts/frontend/v1.0.0"
  - "Q10=A probe FAIL blocks whole PRD (did not trigger)"
  - "Q11=A provider chunk miss → 404 KNOWLEDGE_CHUNK_NOT_FOUND"
  - "Q12=A NON-GOAL-014 no historical file_version_id chunk read"
  - "Q13=A RagflowClient uses Provider PATCH not deprecated PUT"
  - "Q14=A confirm = HTTP+code success; Golden Consumer MAY delayed GET"
  - "Q15=A project available bool only; never expose available_int"
  - "Q16=A encode decisions into PRD then human APPROVED_FOR_PLAN"
target_release: "nodeskclaw-knowledge Chunk Gateway v1.0"
change_type:
  - "BROWNFIELD_CHANGE"
  - "INTEGRATION"
golden_consumer: "nodeskclaw-knowledge HTTP API + real RAGFlow runtime"
related_docs:
  - "需求PRD工程模板.md"
  - "smc-copilot Knowledge DocumentDetail Hybrid v1.0"
supersedes: null
---

# 0. PRD 使用原则

本 PRD 严格按《需求PRD工程模板.md》编写，作为 Human + AI Coding 可执行 Engineering Contract。

本文规范关键词：

```text
MUST
MUST NOT
SHOULD
SHOULD NOT
MAY
```

语义：

- `MUST`：必须实现、必须测试、必须有 Evidence。
- `MUST NOT`：违反即 Requirement FAIL。
- `SHOULD`：默认必须满足；偏离必须在 Plan / Review 中记录原因。
- `SHOULD NOT`：原则上禁止；偏离必须记录明确原因。
- `MAY`：可选，不影响本版本主 Release Gate。

No-Inference Rule：

若 Plan Agent / Coding Agent 无法从本 PRD 唯一确定：

```text
状态事实源
默认值
selection semantics
ownership
identity scope
side effects
rollback / uncertain mutation behavior
conflict resolution
error behavior
acceptance oracle
```

则：

```text
MUST report SPEC_SEMANTIC_GAP
MUST BLOCK plan generation
MUST NOT 自行补全
```

---

# 1. Document Meta / 源码基线

## 1.1 Repository Baseline

```text
repository:
  loudon84/nodeskclaw

branch:
  feat/knowledge-v2.0

baseline commit:
  1d29fac6383ce64e0d82dfe4d445b4fd549a14ec

baseline date:
  2026-09-17
```

Plan 阶段若 HEAD 已改变：

```text
MUST compare current HEAD with baseline commit
MUST record impact
MUST NOT silently use a different baseline
```

## 1.2 Current Source Facts

当前代码已经存在：

```text
nodeskclaw-knowledge/app/api/source_files.py
nodeskclaw-knowledge/app/services/source_file_service.py
nodeskclaw-knowledge/app/runtime/ragflow.py
nodeskclaw-knowledge/app/integrations/ragflow/client.py
nodeskclaw-knowledge/app/schemas/knowledge.py
nodeskclaw-knowledge/app/models/source_file.py
nodeskclaw-knowledge/app/models/source_file_version.py
nodeskclaw-knowledge/app/models/knowledge_base.py
nodeskclaw-knowledge/app/services/runtime_binding_service.py
nodeskclaw-knowledge/app/services/active_runtime_documents.py
```

当前已具备的核心映射：

```text
SourceFile.id
    │
    ├── knowledge_base_id
    └── active_version_id
             │
             ▼
      SourceFileVersion
             │
             └── ragflow_document_id

KnowledgeBase / RuntimeBinding
             │
             └── RAGFlow dataset identity
```

当前 RAGFlow Client 已实现：

```text
GET /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks
```

并通过：

```text
RagflowClient.list_document_chunks()
RagflowRuntimeAdapter.read_document_chunks()
```

读取 RAGFlow Chunk。

当前缺少：

```text
GET   /api/v1/source-files/{source_file_id}/chunks
PATCH /api/v1/source-files/{source_file_id}/chunks/{chunk_id}

Provider-neutral SourceFile Chunk schema
RAGFlow chunk page total preservation
keywords pass-through
chunk availability update wrapper
SourceFile-level permission/version mapping for Chunk API
Chunk API contract tests
```

---

# 2. Goal / 一句话目标

让 **nodeskclaw-knowledge API Consumer** 在已通过 Work/Knowledge 身份认证并拥有目标 SourceFile 权限时，通过 **SourceFile 级 Chunk API** 获取和更新该文件当前 Active Version 在 RAGFlow 中的 Chunk，同时保证：

```text
RAGFlow 是 Chunk 唯一业务事实源；
nodeskclaw-knowledge 只承担：
- 权限
- SourceFile → Active Version → RAGFlow Document 映射
- API 转发
- 最小协议规范化
- 错误映射
- 审计 / 可观测性

nodeskclaw-knowledge MUST NOT 成为第二套 Chunk Processing / Storage Engine。
```

可观察结果：

```text
Consumer 只需要 source_file_id，
不需要知道 dataset_id / document_id / RAGFlow URL / API Key，
即可分页、搜索读取 Chunk，并在授权条件下修改 Chunk available 状态。
```

---

# 3. Background / Problem

## 3.1 Current State

当前 `nodeskclaw-knowledge` 已经具备：

```text
SourceFile CRUD
SourceFile Version
Active Version
Download
Reparse
Metadata
ACL
Runtime Binding
RAGFlow Dataset / Document mapping
RAGFlow document chunks read
RAGFlow runtime capability probe
```

现有 SourceFile API 已包含：

```text
GET    /api/v1/source-files/{source_file_id}
GET    /api/v1/source-files/{source_file_id}/versions
POST   /api/v1/source-files/{source_file_id}/versions/{version_id}/activate
POST   /api/v1/source-files/{source_file_id}/reparse
GET    /api/v1/source-files/{source_file_id}/download
PATCH  /api/v1/source-files/{source_file_id}/metadata
...
```

现有 RAGFlow Adapter 已可：

```text
dataset_id + document_id
→ list_document_chunks(page, page_size)
```

但目前：

```text
Consumer 无法用 source_file_id 直接获取当前 active version 的 chunks。
```

## 3.2 Problem

### P-001 — Chunk Runtime Capability 未暴露为 Knowledge Product API

当前 Chunk 读取能力位于 RAGFlow integration/runtime 层，而 SourceFile Product API 没有对外 Chunk endpoint。

### P-002 — 当前 Chunk Client 丢失分页元数据

现有 `list_document_chunks()` 将 RAGFlow response 收敛为：

```python
list[dict[str, Any]]
```

导致 Provider 返回的：

```text
total
page
page_size
```

不能作为 SourceFile Chunk Page Contract 输出。

### P-003 — 当前 Chunk Client 不支持 `keywords` 透传

Document Chunk API 支持关键词过滤，但现有 wrapper 只有：

```text
page
page_size
```

Consumer 无法进行 provider-side Chunk 内容搜索。

### P-004 — 当前没有 Chunk availability update

当前支持 `set_document_enabled()`，但它操作的是 Document，不是 Chunk。

缺少：

```text
PATCH /datasets/{dataset}/documents/{document}/chunks/{chunk}
```

的 thin wrapper（Provider PUT 同路径已 deprecated，v1 不采用）。

### P-005 — 若 nodeskclaw 自己处理 Chunk，会形成第二事实源

禁止出现：

```text
RAGFlow Chunk
  ↓
nodeskclaw local Chunk copy / re-chunk / re-rank / local filter
  ↓
Consumer
```

否则将形成：

```text
RAGFlow state
vs
nodeskclaw state
```

双事实源。

## 3.3 Impact

```text
业务影响：
- smc-copilot DocumentDetail 无法只使用 SourceFile ID 获取 Chunk。
- 管理界面需要接触 RAGFlow Provider identity。

工程影响：
- 若前端直接接 RAGFlow，将把 Provider identity 和协议泄漏到 Consumer。
- 若 nodeskclaw 二次处理 Chunk，将产生重复逻辑与状态漂移。

安全影响：
- RAGFlow API Key / Base URL 不应进入 Desktop / Browser。
- Chunk update 必须经过 SourceFile 权限边界。

运维影响：
- Provider API 变化应该只影响 nodeskclaw RAGFlow Adapter。
- Consumer 不应跟随 RAGFlow 路径变化。

AI Coding 影响：
- 必须明确“Thin Gateway”边界，防止 Agent 自动增加缓存、持久化、
  search post-filter、re-ranking 或 Chunk DB model。
```

---

# 4. Scope / Non-goal

## 4.1 In Scope

```text
SCOPE-001 新增 SourceFile Chunk List API。
SCOPE-002 新增 SourceFile Chunk Availability Update API。
SCOPE-003 新增 SourceFile → Active Version → Runtime Document resolver flow。
SCOPE-004 扩展 RAGFlow Client，保留 Chunk Page total / page / page_size。
SCOPE-005 扩展 RAGFlow Client，透传 keywords。
SCOPE-006 扩展 RAGFlow Client，支持设置 Chunk available。
SCOPE-007 新增最小 provider-neutral SourceFile Chunk DTO。
SCOPE-008 GET 继续复用 FilePermission.read。
SCOPE-009 PATCH 必须要求 FilePermission.update **或** KbPermission.manage（与 activate/archive/metadata 写路径对齐）。
SCOPE-010 新增 Chunk operation observability / audit。
SCOPE-011 新增 unit / API / RAGFlow contract / Golden Consumer 验收。
SCOPE-012 在 `contracts/frontend/v1.0.0` 以 **additive** 方式补充 Chunk List/PATCH 合同与 FRONTEND-INTEGRATION（不新开 1.1.0）。
```

## 4.2 Out of Scope

```text
NON-GOAL-001 MUST NOT 新建 nodeskclaw Chunk ORM 表。
NON-GOAL-002 MUST NOT 本地持久化 RAGFlow Chunk content。
NON-GOAL-003 MUST NOT 在 nodeskclaw 二次切分 Chunk。
NON-GOAL-004 MUST NOT 在 nodeskclaw 合并 Chunk。
NON-GOAL-005 MUST NOT 在 nodeskclaw 对 List API 结果进行本地全文过滤。
NON-GOAL-006 MUST NOT 在 nodeskclaw 对 Chunk List 做 rerank。
NON-GOAL-007 MUST NOT 实现 Chunk Add / Delete。
NON-GOAL-008 MUST NOT 实现 Chunk content 编辑。
NON-GOAL-009 MUST NOT 将 RAGFlow dataset_id / document_id 返回给 API Consumer。
NON-GOAL-010 MUST NOT 将 RAGFlow URL / API Key 返回给 API Consumer。
NON-GOAL-011 MUST NOT 新建独立 Knowledge Gateway 服务；nodeskclaw-knowledge 本身就是 Knowledge Gateway。
NON-GOAL-012 MUST NOT 改变现有 SourceFile / Retrieval API response semantics。
NON-GOAL-013 MUST NOT 让 GET Chunk API 修改 RAGFlow 或 nodeskclaw 业务数据。
NON-GOAL-014 MUST NOT 接受 Consumer 传入历史 `file_version_id`（或任何非 Active Version identity）来读取/修改 Chunk；v1 Chunk API 只服务 `SourceFile.active_version_id`。
NON-GOAL-015 MUST NOT 将 RAGFlow `available_int` 暴露到 Public Chunk DTO。
```

## 4.3 Architecture Boundary

| Domain | Owner | Input | Output | 不负责 |
|---|---|---|---|---|
| SourceFile API | nodeskclaw-knowledge API | source_file_id/query/body | provider-neutral JSON | 不处理 UI |
| Permission | nodeskclaw permission service | member/source_file | allow/deny | 不管理 RAGFlow ACL |
| Source Resolver | nodeskclaw service | source_file_id | dataset/document/version refs | 不存 Chunk |
| Runtime Adapter | RagflowRuntimeAdapter | resolved refs | RAGFlow call | 不做业务加工 |
| RAGFlow Client | integration/ragflow | HTTP params/body | provider response | 不决定权限 |
| Chunk Storage | RAGFlow | chunk state | provider data | 不知道 SourceFile ACL |
| Consumer | smc-copilot / future client | SourceFile Chunk API | UI/interaction | 不知道 Provider identity |

---

# 5. Terminology / Domain Model

## 5.1 SourceFile

nodeskclaw-knowledge 中面向产品的源文件对象。

业务 identity：

```text
source_file_id
```

## 5.2 Active File Version

`SourceFile.active_version_id` 指向的 `SourceFileVersion`。

它是 SourceFile 当前有效文件版本的 SOT。

## 5.3 Runtime Document

Active `SourceFileVersion.ragflow_document_id` 对应的 RAGFlow Document。

## 5.4 Runtime Dataset

当前 Knowledge Base 在 RuntimeBinding 中解析出的 RAGFlow dataset identity。

## 5.5 Chunk

由 RAGFlow 创建、持久化和管理的解析片段。

```text
Chunk Business Source of Truth = RAGFlow
```

## 5.6 Thin Gateway

只执行：

```text
Authenticate
Authorize
Resolve IDs
Forward provider operation
Minimal normalize
Map error
Audit / Observe
```

不执行：

```text
re-chunk
merge
local filter
rerank
local persist
local ownership of chunk content
```

## 5.7 Minimal Normalize

只将 Provider 字段投影到稳定 Public DTO：

```text
id
content
available
positions
important_keywords
questions
```

并包装：

```text
source_file_id
file_version_id
page
page_size
total
```

不改变 Chunk content。

## 5.8 Version Token

PATCH Chunk Availability 的并发保护值：

```text
file_version_id
```

它来自最近一次 Chunk List response。

---

# 6. System Context

## 6.1 Context Diagram

```text
API Consumer
    │
    │ source_file_id
    ▼
nodeskclaw-knowledge SourceFile API
    │
    ├─ Auth / Permission
    ├─ SourceFile.active_version_id
    ├─ SourceFileVersion.ragflow_document_id
    ├─ RuntimeBinding.dataset_id
    │
    ▼
RagflowRuntimeAdapter
    │
    ▼
RagflowClient
    │
    ▼
RAGFlow REST API
    │
    ▼
RAGFlow Chunk Store
```

## 6.2 System Boundary

```text
Inside boundary:
- nodeskclaw-knowledge HTTP API
- authentication context
- SourceFile permission
- SourceFile / FileVersion models
- RuntimeBinding
- RAGFlow Runtime Adapter
- RAGFlow Client
- minimal DTO normalization
- error mapping
- audit / metrics

Outside boundary:
- smc-copilot
- other HTTP consumers
- RAGFlow
- RAGFlow storage/index

External dependency:
- RAGFlow REST API

Trusted input:
- authenticated KnowledgePrincipal
- DB records after ORM constraints

Untrusted input:
- query params
- path params
- PATCH body
- RAGFlow HTTP response
- Chunk content
```

---

# 7. Authoritative State / Source of Truth

| State | Role | Type | Authoritative? | Writer | Reader | 自动覆盖 |
|---|---|---|---:|---|---|---:|
| SourceFile | 文件产品状态 | OBSERVED_STATE | YES | nodeskclaw | API/Service | YES |
| active_version_id | 当前文件版本 | OBSERVED_STATE | YES | lifecycle | Chunk Service | YES |
| ragflow_document_id | FileVersion→Runtime Document | RESOLVED_STATE | YES | ingestion lifecycle | Chunk Service | YES |
| Runtime dataset binding | KB→RAGFlow dataset | RESOLVED_STATE | YES | runtime binding | Chunk Service | YES |
| Chunk content | Chunk 文本 | OBSERVED_STATE | YES | RAGFlow | Gateway Consumer | YES |
| Chunk available | Chunk 状态 | OBSERVED_STATE | YES | RAGFlow | Gateway Consumer | YES |
| Chunk search result | Provider 查询结果 | RUNTIME_STATE | NO | RAGFlow | Consumer | YES |
| Public Chunk DTO | Provider projection | RESOLVED_STATE | NO | Gateway | Consumer | YES |
| Test Evidence | 验收证据 | EVIDENCE_STATE | YES | tests/CI | Reviewer | NO |

Authority Rules：

```text
MUST NOT 创建本地 Chunk SOT。
MUST NOT 用 SourceFileVersion.chunk_count 替代 RAGFlow 当前搜索 total。
MUST NOT 用本地 keyword filter 替代 RAGFlow query。
MUST NOT 用本地 available shadow field 替代 RAGFlow available。
```

---

# 8. State Machine

## 8.1 GET Chunk Request State

```text
RECEIVED
  ↓
AUTHENTICATED
  ↓
AUTHORIZED
  ↓
RESOLVED
  ↓
PROVIDER_FETCHING
  ├─ success → NORMALIZED → RESPONDED
  ├─ provider unavailable → FAILED
  ├─ invalid provider response → FAILED
  └─ mapping missing → FAILED
```

非法转移：

```text
AUTHENTICATED → PROVIDER_FETCHING without authorization
AUTHORIZED → RESPONDED without runtime resolution
FAILED → RESPONDED success
```

GET 状态不持久化。

## 8.2 PATCH Availability State

```text
RECEIVED
  ↓
AUTHENTICATED
  ↓
AUTHORIZED(update|kb_manage)
  ↓
VERSION_GUARDED
  ↓
RESOLVED
  ↓
PROVIDER_MUTATING
  ├─ confirmed success → CONFIRMED → RESPONDED
  ├─ confirmed failure → FAILED
  └─ transport outcome unknown → UNCERTAIN
```

`UNCERTAIN`：

```text
MUST return deterministic error
MUST NOT invent final available state
MUST require consumer refetch
```

---

# 9. Data / Schema Contract

## 9.1 Public Chunk DTO

```text
schema id: source-file-chunk-out
version: 1
additionalProperties: false
```

```python
class SourceFileChunkOut(BaseModel):
    id: str
    content: str
    available: bool | None = None
    positions: list | None = None
    important_keywords: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
```

| Field | Type | Required | Default | Authority | Meaning |
|---|---|---:|---|---|---|
| id | string | YES | none | RAGFlow | opaque chunk identity |
| content | string | YES | empty only if provider returns empty | RAGFlow | raw chunk content |
| available | bool/null | YES | null | RAGFlow | provider enabled state（只投影 Provider `available` bool；缺失 → null；MUST NOT 用 `available_int` 合成或暴露） |
| positions | list/null | YES | null | RAGFlow | provider position metadata |
| important_keywords | string[] | YES | [] | RAGFlow | keywords |
| questions | string[] | YES | [] | RAGFlow | generated questions |

MUST NOT include：

```text
dataset_id
document_id
ragflow_document_id
ragflow_dataset_id
provider_url
```

## 9.2 Public Chunk Page DTO

```text
schema id: source-file-chunk-page-out
version: 1
additionalProperties: false
```

```python
class SourceFileChunkPageOut(BaseModel):
    source_file_id: str
    file_version_id: str
    items: list[SourceFileChunkOut]
    total: int
    page: int
    page_size: int
```

规则：

```text
total MUST come from RAGFlow list-chunks response.
total MUST NOT derive from len(items).
total MUST NOT derive from SourceFileVersion.chunk_count when keywords is non-empty.
```

Provider response 缺少 total：

```text
HTTP 502
KNOWLEDGE_CHUNK_CONTRACT_INVALID
```

## 9.3 Availability Patch

```text
schema id: source-file-chunk-availability-patch
version: 1
additionalProperties: false
```

```python
class SourceFileChunkAvailabilityPatch(BaseModel):
    file_version_id: str = Field(min_length=1, max_length=36)
    available: bool
```

`file_version_id` MUST equal current `SourceFile.active_version_id`。

## 9.4 Availability Result

```python
class SourceFileChunkAvailabilityResult(BaseModel):
    source_file_id: str
    file_version_id: str
    chunk_id: str
    available: bool
```

## 9.5 Internal RAGFlow Page DTO

```python
@dataclass
class RagflowChunkPage:
    chunks: list[dict[str, Any]]
    total: int
    page: int
    page_size: int
```

MUST NOT 暴露到 API Consumer。

---

# 10. Requirements

## REQ-ARCH-001 — Thin Gateway Boundary

### Goal
固定 nodeskclaw-knowledge 在 Chunk 场景中的职责，防止二次业务处理。

### Normative Requirement

```text
MUST 将 RAGFlow 定义为 Chunk content / available 的业务 SOT。
MUST nodeskclaw 只执行 authentication、authorization、ID resolve、provider invocation、minimal normalize、error mapping、audit/observability。
MUST NOT 创建 Chunk ORM table。
MUST NOT local-persist Chunk content。
MUST NOT re-chunk。
MUST NOT merge Chunk。
MUST NOT rerank Chunk List。
MUST NOT local-filter keyword results。
```

### Inputs
source_file_id / KnowledgePrincipal / RAGFlow response

### Preconditions
现有 SourceFile 与 RAGFlow runtime integration 可用。

### Authoritative State

```text
SourceFile mapping SOT = nodeskclaw DB
Chunk state SOT = RAGFlow
```

### State Transition

```text
Before: runtime chunk reader only
Event: add SourceFile product API
After: provider-neutral thin gateway
```

### Allowed Side Effects
API/schema/service/client/runtime/test/log/metric code changes。

### Forbidden Side Effects
Chunk business persistence / content transformation。

### Ownership Scope
`FILE / SECTION`; Chunk business content=`NONE`

### Idempotency
GET 对 unchanged provider state observationally equivalent。

### Failure Semantics

```text
trigger: local Chunk persistence or local processing introduced
expected state: review/release blocked
error code: CHUNK_GATEWAY_BOUNDARY_VIOLATION
rollback: remove prohibited implementation
retryable: false
```

### Postconditions
无新 Chunk business SOT。

### Invariants

```text
INV-ARCH-001 RAGFlow is Chunk SOT.
INV-ARCH-002 Consumer never needs provider identity.
```

### Acceptance
`A-ARCH-001`, `A-NEG-001`, `A-NEG-002`

### Evidence
static architecture check + commit SHA。

---

## REQ-DATA-001 — Active Runtime Document Resolution

### Goal
Consumer 只提供 source_file_id，服务端解析当前 RAGFlow document。

### Normative Requirement

GET MUST 按顺序：

```text
1. source_file_service.get_source_file()
2. SourceFile.active_version_id
3. SourceFileVersion
4. SourceFileVersion.ragflow_document_id
5. RuntimeBinding dataset identity
```

MUST NOT 接受 Consumer 传 dataset_id/document_id。

### Inputs
source_file_id / member

### Preconditions
SourceFile exists + FilePermission.read。

### Authoritative State
SourceFile / SourceFileVersion / RuntimeBinding。

### State Transition
unresolved → RuntimeDocumentRef。

### Allowed Side Effects
DB read / permission read。

### Forbidden Side Effects
DB write / RAGFlow mutation。

### Ownership Scope
`NONE`

### Idempotency
同一 DB state 重复 resolve 等价。

### Failure Semantics

```text
source missing → existing source_file_not_found, provider call=0
active version null → KNOWLEDGE_CHUNK_NO_ACTIVE_VERSION, provider call=0
active version invalid → KNOWLEDGE_CHUNK_ACTIVE_VERSION_INVALID, provider call=0
ragflow_document_id missing → KNOWLEDGE_CHUNK_RUNTIME_DOCUMENT_MISSING, provider call=0
dataset binding missing → KNOWLEDGE_CHUNK_RUNTIME_BINDING_MISSING, provider call=0
```

### Postconditions
RuntimeDocumentRef.file_version_id == SourceFile.active_version_id。

### Invariants
`INV-DATA-001 Provider IDs stay server-side.`

### Acceptance
`A-DATA-001`, `A-DATA-002`, `A-NEG-003`

### Evidence
service unit tests。

---

## REQ-API-001 — SourceFile Chunk List API

### Goal
提供 SourceFile-level Chunk List。

### Normative Requirement

MUST 新增：

```http
GET /api/v1/source-files/{source_file_id}/chunks
```

Query Contract：

```text
page: int, default=1, min=1
page_size: int, default=50, min=1, max=100
keywords: string|null, default=null, trim=true, max_length=200
```

MUST：

```text
use FilePermission.read
resolve active version
forward page/page_size/keywords to provider
return SourceFileChunkPageOut
preserve provider total
```

MUST NOT：

```text
local keyword filter
prefetch all chunks
use iter_document_chunks() to emulate public pagination
```

### Inputs
path/query/principal

### Preconditions
authenticated + read permission + resolvable runtime document。

### Authoritative State
RAGFlow response + active version snapshot。

### State Transition
无持久状态转移。

### Allowed Side Effects
DB read / RAGFlow GET / sanitized logs/metrics。

### Forbidden Side Effects
DB write / RAGFlow write / local Chunk SOT cache。

### Ownership Scope
`NONE`

### Idempotency
same provider state + same query → equivalent response。

### Failure Semantics

```text
invalid query → HTTP 422, provider call=0
provider unavailable → KNOWLEDGE_CHUNK_PROVIDER_UNAVAILABLE
provider malformed → KNOWLEDGE_CHUNK_CONTRACT_INVALID
```

### Postconditions
response.file_version_id is the resolved active version; no provider IDs in items。

### Invariants

```text
INV-API-001 GET is business read-only.
INV-API-002 keyword filtering occurs in RAGFlow.
```

### Acceptance
`A-API-001`, `A-API-002`, `A-API-003`, `A-API-004`, `A-NEG-004`

### Evidence
API tests + provider call assertions + real contract test。

---

## REQ-API-002 — Chunk Availability Update API

### Goal
有 File Update 权限的 Consumer 修改 RAGFlow Chunk available。

### Normative Requirement

MUST 新增：

```http
PATCH /api/v1/source-files/{source_file_id}/chunks/{chunk_id}
```

Body：

```json
{
  "file_version_id": "<version-id>",
  "available": true
}
```

MUST：

```text
require FilePermission.update OR KbPermission.manage on the SourceFile's Knowledge Base
（与 source_lifecycle_service / metadata_service 写路径对齐）
compare body.file_version_id with SourceFile.active_version_id
mismatch → HTTP 409 before provider mutation
resolve current runtime document
send only {"available": bool} to RAGFlow business payload via Provider PATCH
return SourceFileChunkAvailabilityResult on confirmed success
```

Confirmed success MUST mean：

```text
Provider HTTP success AND provider envelope code indicates success
（现网 RAGFlow：HTTP 200 且 code == 0）
```

MUST NOT：

```text
require read-after-write before returning success
invent final available from local state
expose or round-trip available_int
修改 content / keywords / questions
```

Golden Consumer / live assertions MAY sleep or retry GET after mutation（Provider list 可能短暂最终一致）。

### Inputs
source_file_id / chunk_id / file_version_id / available / principal

### Preconditions
(update OR KB manage) permission + current active version exists + version token matches。

### Authoritative State
RAGFlow available + SourceFile active_version_id。

### State Transition
RAGFlow available T0 → target。

### Allowed Side Effects
RAGFlow available field / audit / logs/metrics。

### Forbidden Side Effects
Chunk content / FileVersion / SourceFile / other Chunk mutation / local persistence。

### Ownership Scope
`FIELD: available`

### Idempotency
SET true on true / SET false on false both success with same final value。

### Failure Semantics

```text
no update permission (neither FilePermission.update nor KbPermission.manage) → 403, provider mutation=0
stale file_version_id → KNOWLEDGE_CHUNK_VERSION_CONFLICT, provider mutation=0
provider confirms chunk missing / not on document → KNOWLEDGE_CHUNK_NOT_FOUND (HTTP 404), no invented local state
confirmed provider failure → mapped error, no local Chunk state
provider unsupported → KNOWLEDGE_CHUNK_UPDATE_UNSUPPORTED
transport outcome unknown → KNOWLEDGE_CHUNK_MUTATION_UNCERTAIN; no inverse write; refetch required
```

### Postconditions
confirmed response.available == requested target；audit written。

### Invariants

```text
INV-API-UPDATE-001 no local authoritative available field.
INV-API-UPDATE-002 stale version cannot mutate current document chunks.
```

### Acceptance
`A-API-UPDATE-001`, `A-API-UPDATE-002`, `A-TXN-001`, `A-NEG-005`, `A-NEG-006`

### Evidence
API mutation tests + failure injection + live provider test。

---

## REQ-INT-001 — RAGFlow Chunk Page Client

### Goal
保留 Provider page metadata，同时避免破坏现有 caller。

### Normative Requirement

MUST 新增：

```python
async def list_document_chunks_page(
    dataset_id: str,
    document_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    keywords: str | None = None,
) -> RagflowChunkPage
```

MUST NOT 直接破坏现有：

```python
list_document_chunks(...) -> list[dict[str, Any]]
```

### Inputs
dataset/document/page/page_size/keywords

### Preconditions
runtime credentials valid。

### Authoritative State
raw RAGFlow response。

### State Transition
none。

### Allowed Side Effects
RAGFlow GET + metrics。

### Forbidden Side Effects
provider mutation。

### Ownership Scope
`FILE/SECTION`

### Idempotency
same provider state → equivalent page。

### Failure Semantics
provider response missing required page contract → `KNOWLEDGE_CHUNK_CONTRACT_INVALID`。

### Postconditions
total/page/page_size/chunks preserved。

### Invariants
`INV-INT-001 MUST NOT fake total from current page length.`

### Acceptance
`A-INT-001`, `A-COMPAT-001`

### Evidence
RagflowClient unit tests。

---

## REQ-INT-002 — RAGFlow Chunk Available Update

### Goal
提供单字段 available update wrapper。

### Normative Requirement

MUST 新增类似：

```python
async def set_document_chunk_available(
    dataset_id: str,
    document_id: str,
    chunk_id: str,
    available: bool,
) -> None
```

MUST 调用：

```http
PATCH /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/{chunk_id}
```

（现网 RAGFlow OpenAPI：同路径 PUT 为 deprecated；v1 Client MUST 使用 PATCH。）

业务 JSON body key set MUST exactly equal：

```json
{"available": true}
```

Confirmed success：Provider HTTP success + envelope success code（现网：200 且 `code == 0`）。
MUST NOT 以 read-after-write 作为成功前置条件。

### Inputs
dataset/document/chunk/available

### Preconditions
runtime reachable。

### Authoritative State
RAGFlow。

### State Transition
provider field SET。

### Allowed Side Effects
one provider Chunk field mutation。

### Forbidden Side Effects
content / keyword / question mutation。

### Ownership Scope
`FIELD: available`

### Idempotency
SET semantics。

### Failure Semantics
unsupported → `KNOWLEDGE_CHUNK_UPDATE_UNSUPPORTED`; uncertain transport → `KNOWLEDGE_CHUNK_MUTATION_UNCERTAIN`。

### Postconditions
confirmed success means provider accepted target state。

### Invariants
`INV-INT-002 wrapper never edits content.`

### Acceptance
`A-INT-002`, `A-NEG-007`

### Evidence
HTTP mock exact-body test + live RAGFlow contract。

---

## REQ-SVC-001 — Thin Source Chunk Service

### Goal
集中 permission + mapping，保持 route/client 简单。

### Normative Requirement

MUST 新增：

```text
app/services/source_chunk_service.py
```

MUST 提供：

```python
list_source_file_chunks(...)
set_source_file_chunk_available(...)
```

MUST 复用：

```text
source_file_service.get_source_file
permission_service.has_file_permission
runtime_binding_service.get_dataset_id
RagflowRuntimeAdapter
```

MUST NOT local search / persistence / rerank / re-chunk。

### Inputs
normalized route input。

### Preconditions
DB/runtime dependency available。

### Authoritative State
Section 7。

### State Transition
read / provider field SET。

### Allowed Side Effects
provider update only for mutation method。

### Forbidden Side Effects
other Chunk processing。

### Ownership Scope
`FILE`

### Idempotency
list idempotent; set target idempotent。

### Failure Semantics
preserve domain exception semantics and deterministic provider mapping。

### Postconditions
API route remains thin。

### Invariants
`INV-SVC-001 no local Chunk collection persistence.`

### Acceptance
`A-SVC-001`

### Evidence
service unit/static tests。

---

## REQ-SEC-001 — Permission / Credential Boundary

### Goal
保证 Chunk API 不绕过 Knowledge 权限和 Provider secret 边界。

### Normative Requirement

```text
GET MUST require FilePermission.read.
PATCH MUST require FilePermission.update OR KbPermission.manage.
MUST use KnowledgePrincipal.
MUST reuse SourceFile org isolation.
MUST keep RAGFLOW_API_KEY server-side.
MUST keep RAGFLOW_BASE_URL server-side.
MUST NOT return dataset_id/document_id.
MUST NOT return available_int.
MUST sanitize provider errors.
MUST treat Chunk content as opaque string.
```

### Inputs
principal + source_file_id。

### Preconditions
authentication valid。

### Authoritative State
permission DB / principal。

### State Transition
none。

### Allowed Side Effects
authorization read；audit on mutation。

### Forbidden Side Effects
credential leakage。

### Ownership Scope
`NONE`

### Idempotency
N/A。

### Failure Semantics
Forbidden → 0 provider calls + 0 business mutation。

### Postconditions
provider credentials remain outside response/logs。

### Invariants
`INV-SEC-001 authorization before provider call.`

### Acceptance
`A-SEC-001`, `A-SEC-002`, `A-SEC-003`, `A-SEC-004`, `A-NEG-008`, `A-NEG-009`, `A-NEG-010`, `A-NEG-011`

---

## REQ-OBS-001 — Audit / Observability

### Goal
Chunk API 可定位故障但不泄露正文/秘密。

### Normative Requirement

GET/PATCH MUST 记录：

```text
operation/correlation id
stage
status
source_file_id
file_version_id
page/page_size for list
keywords_present bool
chunk_id digest for update
target_available for update
provider operation
latency
error code
```

PATCH confirmed success MUST 写 Audit：

```text
CHUNK_AVAILABILITY_UPDATE
```

MUST NOT 记录：

```text
full Chunk content
RAGFlow API key
Authorization header
credential-bearing URL
```

### Inputs
operation context。

### Preconditions
request received。

### Authoritative State
audit/evidence state。

### State Transition
operation stages。

### Allowed Side Effects
logs/metrics/audit。

### Forbidden Side Effects
secret/content leakage。

### Ownership Scope
`ENTRY`

### Idempotency
retry may have distinct operation id; duplicate confirmed SET may have one audit per request。

### Failure Semantics
logging failure MUST NOT alter business state；audit failure after confirmed provider mutation MUST surface error and mark `provider_mutation_confirmed=true` in safe logs。

### Postconditions
mutation traceable。

### Invariants
`INV-OBS-001 no full Chunk content in structured logs.`

### Acceptance
`A-OBS-001`, `A-OBS-002`

### Evidence
captured log/audit tests。

---

## REQ-COMPAT-001 — Existing API Compatibility

### Goal
新增 Chunk API 不破坏现有能力。

### Normative Requirement

MUST NOT 修改：

```text
existing SourceFile route paths
existing SourceFile response fields
existing Retrieval semantics
existing RagflowClient.list_document_chunks caller-visible return type
```

若实施选择重构旧 method：MUST enumerate callers、atomic migrate、full regression。

### Inputs
baseline contracts/tests。

### Preconditions
baseline commit。

### Authoritative State
existing public/internal contracts。

### State Transition
additive change。

### Allowed Side Effects
new routes/methods/types。

### Forbidden Side Effects
breaking change。

### Ownership Scope
`SHARED`

### Idempotency
N/A。

### Failure Semantics
regression → Release Gate FAIL。

### Postconditions
existing test suite remains PASS。

### Invariants
`INV-COMPAT-001 HTTP change is additive.`

### Acceptance
`A-COMPAT-001`, `A-COMPAT-002`

### Evidence
full test suite + route snapshot。

---

# 11. Side-Effect Contract

| Operation | DB Write | RAGFlow Write | Network | Cache | User Data | Business Source |
|---|---:|---:|---:|---:|---:|---:|
| resolve runtime document | NO | NO | NO | NO | NO | NO |
| GET chunks | NO | NO | YES | NO authoritative cache | NO | NO |
| GET chunks with keywords | NO | NO | YES | NO authoritative cache | NO | NO |
| PATCH chunk available | Audit only | YES | YES | NO authoritative cache | YES | YES(field only) |
| capability probe | MAY existing binding metadata | NO | YES | MAY | NO | NO |
| synthetic tests | MAY test DB | mock/test | MAY | NO | test only | NO |
| Golden Consumer mutation | test/audit | YES on test chunk | YES | NO | test data | YES(test scope) |

规则：

```text
v1 SHOULD NOT add Chunk data cache.
任何 cache MUST NOT 成为 SOT。
Telemetry/log count as side effect and MUST be sanitized.
GET is read-only over SourceFile DB and RAGFlow business data.
```

---

# 12. Ownership Contract

## 12.1 Ownership Type

| Resource | Type | Owner |
|---|---|---|
| SourceFile / Version | WHOLE_RESOURCE | nodeskclaw-knowledge |
| RuntimeBinding | WHOLE_RESOURCE | runtime binding |
| RAGFlow Chunk content | BUSINESS_SOURCE | RAGFlow |
| RAGFlow Chunk available | FIELD | RAGFlow |
| Public Chunk DTO | GENERATED_ONLY | nodeskclaw projection |
| Source Chunk service code | FILE | nodeskclaw-knowledge |
| Consumer UI | outside boundary | consumer |

## 12.2 Ownership Rule

```text
Chunk create: RAGFlow owns.
Chunk read: nodeskclaw projects only.
Chunk update: nodeskclaw owns requested available operation only.
Upgrade: Provider mapping MAY evolve; public v1 DTO remains compatible.
Remove: v1 does not implement Chunk delete.
```

## 12.3 Drift

```text
request.file_version_id != SourceFile.active_version_id
→ BLOCK
→ KNOWLEDGE_CHUNK_VERSION_CONFLICT
→ provider mutation=0
```

RAGFlow state external change：

```text
next GET observes provider state
no reconciliation job
```

---

# 13. Identity / Hash Contract

Business Identity：

```text
SourceFile = source_file_id
FileVersion = file_version_id
Chunk = provider opaque chunk_id
```

Chunk ID MUST preserve opaque Provider ID exactly for PATCH round-trip。

Audit digest：

```text
algorithm: SHA-256
input: chunk_id UTF-8 bytes
normalization: none
output: lowercase hex
display: first 12 hex chars
business identity use: forbidden
```

---

# 14. Transaction Contract

## 14.1 Transaction Boundary

GET：无业务 mutation。

PATCH includes：

```text
authorization
file version guard
one RAGFlow available SET
one audit entry after confirmed provider success
```

PATCH excludes：

```text
chunk content
other chunks
SourceFile/FileVersion state
dataset config
```

## 14.2 Commit Order

```text
1 authenticate
2 authorize update
3 resolve current active version
4 compare request.file_version_id
5 resolve runtime document
6 RAGFlow SET available
7 receive confirmed success
8 write audit
9 return success
```

## 14.3 T0

```text
T0 = Provider available state before operation
```

nodeskclaw MUST NOT persist T0 as shadow business state。

## 14.4 Failure Atomicity

Confirmed failure before provider commit：

```text
AfterFailure(nodeskclaw business state) == Before
```

Uncertain transport after send：

```text
MUST return KNOWLEDGE_CHUNK_MUTATION_UNCERTAIN
MUST NOT issue inverse write
MUST NOT claim target state confirmed
MUST require refetch before next mutation
```

## 14.5 Recovery

Recovery evidence：

```text
operation_id
source_file_id
file_version_id
chunk_id_digest
target_available
timestamp
provider_outcome=unknown
```

Recovery procedure：GET current state → observe → if needed issue new idempotent PATCH。

---

# 15. Failure Contract

| Error Code | Trigger | HTTP | Provider Called | Mutation | Retry |
|---|---|---:|---:|---:|---|
| existing source_file_not_found | absent/inaccessible | 404 | NO | 0 | NO |
| existing forbidden | permission denied | 403 | NO | 0 | NO |
| KNOWLEDGE_CHUNK_NO_ACTIVE_VERSION | active_version_id null | 409 | NO | 0 | after activation |
| KNOWLEDGE_CHUNK_ACTIVE_VERSION_INVALID | version missing/deleted | 409 | NO | 0 | after repair |
| KNOWLEDGE_CHUNK_RUNTIME_DOCUMENT_MISSING | ragflow_document_id missing | 409 | NO | 0 | after ingestion |
| KNOWLEDGE_CHUNK_RUNTIME_BINDING_MISSING | dataset binding absent | 503 | NO | 0 | YES |
| KNOWLEDGE_CHUNK_PROVIDER_UNAVAILABLE | timeout/network | 503 | attempted | GET=0 | YES |
| KNOWLEDGE_CHUNK_CONTRACT_INVALID | malformed provider response | 502 | YES | 0 | NO auto |
| KNOWLEDGE_CHUNK_VERSION_CONFLICT | PATCH stale version | 409 | NO | 0 | after GET |
| KNOWLEDGE_CHUNK_NOT_FOUND | provider confirms chunk missing/not on active document | 404 | YES | confirmed 0 | after GET |
| KNOWLEDGE_CHUNK_UPDATE_UNSUPPORTED | provider rejects update capability | 501 | YES | confirmed 0 | provider upgrade |
| KNOWLEDGE_CHUNK_MUTATION_UNCERTAIN | remote outcome unknown | 503 | YES | unknown remote | GET first |

Existing global exception envelope MUST remain authoritative；MUST NOT create second error envelope。

---

# 16. Conflict Contract

| Conflict | Detection | Default Behavior | Error | Mutation |
|---|---|---|---|---:|
| stale file_version_id | compare with active_version_id | BLOCK | VERSION_CONFLICT | 0 |
| missing active version | null | BLOCK | NO_ACTIVE_VERSION | 0 |
| missing runtime document | null mapping | BLOCK | RUNTIME_DOCUMENT_MISSING | 0 |
| missing binding | resolver none | BLOCK | RUNTIME_BINDING_MISSING | 0 |
| update unsupported | provider mapped reject | BLOCK | UPDATE_UNSUPPORTED | 0 |
| external provider state drift | no local copy | OBSERVE provider | none | 0 |
| duplicate same target PATCH | same bool | idempotent SET | none | same field |
| concurrent different target PATCH | provider-confirmed order | provider result | none/error | provider-defined |

禁止：

```text
local last-writer cache
best-effort local merge
automatic inverse write on timeout
```

---

# 17. Compatibility / Migration

## 17.1 Existing State

```text
/api/v1/source-files/*
/api/v1/retrieval
/api/v2/*

RagflowClient.list_document_chunks() -> list[dict]
RagflowRuntimeAdapter.read_document_chunks() -> list[dict]
iter_document_chunks()
probe_document_chunks()
```

## 17.2 Migration

```text
1 Add internal RagflowChunkPage.
2 Add list_document_chunks_page() without deleting old method.
3 Add set_document_chunk_available() using Provider PATCH.
4 Add Runtime Adapter wrappers.
5 Add public SourceFile Chunk schemas.
6 Add source_chunk_service.py.
7 Add two SourceFile routes.
8 Add audit/observability.
9 Additive update contracts/frontend/v1.0.0 (+ FRONTEND-INTEGRATION).
10 Add tests + Golden Consumer evidence.
```

## 17.3 Unknown Ownership

若发现未知现有 Chunk persistence：

```text
PRESERVE
REPORT
MUST NOT DELETE
MUST report SPEC_SEMANTIC_GAP
```

---

# 18. External Dependency Contract

## 18.1 RAGFlow

```text
name: RAGFlow
runtime access: RAGFLOW_BASE_URL + RAGFLOW_API_KEY (server-side only)
required APIs:
  GET /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks
  PATCH /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/{chunk_id}
  （PUT 同路径在现网 OpenAPI 标为 deprecated；v1 MUST NOT 依赖 PUT）
required GET params:
  page
  page_size
  keywords
required update field:
  available
probe evidence (2026-09-19, RAGFlow v0.27.0):
  PATCH {"available": bool} toggle+restore PASS
  PUT {"available": bool} also PASS but deprecated
  list available may lag briefly after mutation; GET-by-id available_int clearer for live asserts
```

Version Policy：

```text
MUST use existing runtime compatibility/version probe.
MUST NOT use RAGFlow Web UI route as API compatibility signal.
```

Golden Consumer Evidence MUST record：

```text
RAGFlow runtime version
container/image digest or deployment immutable digest
nodeskclaw commit SHA
```

无法取得 immutable runtime identity：

```text
Golden Consumer Acceptance = BLOCKED
Release Gate != PASS
```

Provider unavailable：fail closed；无 local Chunk fallback store。

---

# 19. Security Contract

| Threat | Control | Acceptance |
|---|---|---|
| Unauthorized read | FilePermission.read | A-SEC-001 |
| Unauthorized mutation | FilePermission.update OR KbPermission.manage | A-SEC-002 |
| Cross-org access | existing get_source_file org check | A-SEC-001 |
| Credential exposure | server-side adapter | A-NEG-008 |
| Provider ID leakage | public schema excludes IDs | A-DATA-002 |
| Query abuse | pydantic type/length + httpx params | A-API-003 |
| Content execution | opaque string | A-SEC-003 |
| Error leakage | sanitized mapping | A-SEC-004 |
| Write overreach | PATCH only available | A-INT-002 |
| Stale version mutation | file_version_id guard | A-NEG-005 |
| Dependency drift | real runtime evidence | A-DEP-001 |

MUST NOT accept arbitrary provider URL from request。

---

# 20. Observability

GET stages：

```text
AUTH
AUTHORIZE
RESOLVE_FILE
RESOLVE_VERSION
RESOLVE_BINDING
FETCH_PROVIDER
NORMALIZE
RETURN
```

PATCH stages：

```text
AUTH
AUTHORIZE
VERSION_GUARD
RESOLVE_BINDING
MUTATE_PROVIDER
AUDIT
RETURN
```

Required fields：

```text
correlation_id / operation_id
stage
status
timestamp
source_file_id
file_version_id
page/page_size
keywords_present bool
chunk_id_digest for update
target_available
provider operation
duration_ms
error_code
```

Forbidden fields：

```text
full Chunk content
RAGFlow API key
Authorization header
credential-bearing URL
```

Recommended metrics：

```text
chunk_list_requests_total
chunk_list_failures_total
chunk_update_requests_total
chunk_update_failures_total
chunk_provider_latency_seconds
```

Metrics labels MUST NOT contain keyword text / Chunk content / member identity。

---

# 21. Acceptance Design

## A-ARCH-001 — RAGFlow Remains Chunk SOT

### Requirement Refs
`REQ-ARCH-001`

### Given
implementation tree。

### When
scan models/migrations/services。

### Then
no new persistent Chunk business table/model。

### Oracle

```text
new SQLAlchemy Chunk business model count == 0
new migration creating Chunk content table count == 0
```

### Evidence
static architecture check + commit SHA。

---

## A-DATA-001 — Resolve Active Runtime Document

### Requirement Refs
`REQ-DATA-001`

### Given
S.active_version_id=V；V.ragflow_document_id=D；dataset=K。

### When
resolver(S)。

### Then
RuntimeDocumentRef=(S,V,K,D)。

### Oracle
deep equality。

### Evidence
unit test。

---

## A-DATA-002 — Provider IDs Hidden

### Requirement Refs
`REQ-DATA-001`, `REQ-SEC-001`

### Given
successful GET。

### When
serialize JSON。

### Then
no dataset_id/document_id/ragflow IDs/provider_url。

### Oracle
forbidden key set intersection == empty。

### Evidence
API test。

---

## A-API-001 — Default Chunk List

### Requirement Refs
`REQ-API-001`

### Given
readable active SourceFile。

### When
GET `/api/v1/source-files/S/chunks`。

### Then
provider called exactly once with page=1,page_size=50,keywords empty/null；HTTP 200。

### Oracle
exact mock call args + status。

### Evidence
API test。

---

## A-API-002 — Provider Total Preserved

### Requirement Refs
`REQ-API-001`, `REQ-INT-001`

### Given
provider total=137, chunks=10。

### When
GET page_size=10。

### Then
response.total=137；len(items)=10。

### Oracle
exact integer assertions。

### Evidence
client/API test。

---

## A-API-003 — Keyword Pass-through

### Requirement Refs
`REQ-API-001`

### Given
keywords=`"  LiteLLM  "`。

### When
GET。

### Then
provider receives `LiteLLM`；returned provider order unchanged。

### Oracle
exact arg + item order equality。

### Evidence
mock test。

---

## A-API-004 — Empty Page

### Requirement Refs
`REQ-API-001`

### Given
provider chunks=[] total=0。

### When
GET。

### Then
HTTP 200 / items=[] / total=0。

### Oracle
exact JSON fields。

### Evidence
API test。

---

## A-API-UPDATE-001 — Availability SET Success

### Requirement Refs
`REQ-API-002`, `REQ-INT-002`

### Given
current V1；request V1；update permission **or** KB manage；target=false。

### When
PATCH。

### Then
provider method=PATCH；provider body exact `{"available": false}`；confirmed by HTTP+code success；response available=false。

### Oracle
provider mutation count=1 + method=PATCH + body key/value exact + no read-after-write required for success。

### Evidence
API/client test。

---

## A-API-UPDATE-002 — Update Permission

### Requirement Refs
`REQ-API-002`, `REQ-SEC-001`

### Given
read=true；FilePermission.update=false；KbPermission.manage=false。

### When
PATCH。

### Then
403；provider mutation=0。

### Oracle
status + call count。

### Evidence
permission test。

### Also
Given FilePermission.update=false but KbPermission.manage=true → PATCH allowed（与 lifecycle 对齐）。

---

## A-TXN-001 — Uncertain Mutation

### Requirement Refs
`REQ-API-002`

### Given
provider transport timeout after send boundary。

### When
PATCH。

### Then
`KNOWLEDGE_CHUNK_MUTATION_UNCERTAIN`；no inverse write；response does not claim confirmed target。

### Oracle
error code exact + inverse call count=0。

### Evidence
failure injection。

---

## A-INT-001 — Page Client Preserves Metadata

### Requirement Refs
`REQ-INT-001`

### Given
provider page。

### When
`list_document_chunks_page()`。

### Then
chunks/total/page/page_size preserved。

### Oracle
deep equality。

### Evidence
client unit test。

---

## A-INT-002 — Update Field Containment

### Requirement Refs
`REQ-INT-002`

### Given
set available=true。

### When
capture provider request。

### Then
method=PATCH；business JSON key set == `{available}`；MUST NOT use deprecated PUT as primary verb。

### Oracle
exact method + exact key set。

### Evidence
HTTP mock test。

---

## A-SVC-001 — Thin Service

### Requirement Refs
`REQ-SVC-001`

### Given
source_chunk_service implementation。

### When
inspect + run tests。

### Then
only resolve/authorize/forward/normalize；no persistence/filter/rerank/re-chunk。

### Oracle
forbidden import/model check + provider order preservation。

### Evidence
service/static tests。

---

## A-SEC-001 — Read Authorization Before Provider

### Requirement Refs
`REQ-SEC-001`

### Given
member cannot read SourceFile。

### When
GET。

### Then
403/404 per existing semantics；provider call=0。

### Oracle
status + count=0。

### Evidence
security test。

---

## A-SEC-002 — Update Authorization Before Provider

### Requirement Refs
`REQ-SEC-001`

### Given
member lacks FilePermission.update **and** lacks KbPermission.manage。

### When
PATCH。

### Then
403；provider mutation=0。

### Oracle
status + count=0。

### Evidence
security test。

---

## A-SEC-003 — Chunk Content Opaque

### Requirement Refs
`REQ-SEC-001`

### Given
content=`<script>alert(1)</script>`。

### When
gateway returns JSON。

### Then
exact string preserved；server does not evaluate/transform。

### Oracle
string exact equality。

### Evidence
API test。

---

## A-SEC-004 — Provider Error Sanitized

### Requirement Refs
`REQ-SEC-001`

### Given
provider exception contains fake key/token。

### When
response/log captured。

### Then
secret fixture absent。

### Oracle
match count=0。

### Evidence
security log test。

---

## A-OBS-001 — GET Operation Trace

### Requirement Refs
`REQ-OBS-001`

### Given
successful GET。

### When
capture structured logs。

### Then
required fields present；content absent。

### Oracle
required subset true + forbidden strings absent。

### Evidence
log test。

---

## A-OBS-002 — PATCH Audit

### Requirement Refs
`REQ-OBS-001`

### Given
confirmed PATCH success。

### When
query audit。

### Then
one `CHUNK_AVAILABILITY_UPDATE` entry。

### Oracle
row count=1 + fields exact。

### Evidence
DB test。

---

## A-COMPAT-001 — Existing Chunk Runtime Callers Preserve Behavior

### Requirement Refs
`REQ-COMPAT-001`, `REQ-INT-001`

### Given
existing test suite。

### When
full pytest。

### Then
existing tests PASS。

### Oracle
exit code=0。

### Evidence
full suite report。

---

## A-COMPAT-002 — HTTP API Additive

### Requirement Refs
`REQ-COMPAT-001`

### Given
baseline route snapshot。

### When
post implementation route snapshot。

### Then
baseline route set is subset of post route set。

### Oracle
set subset=true。

### Evidence
route diff artifact。

---

## A-DEP-001 — Real RAGFlow Contract

### Requirement Refs
`REQ-INT-001`, `REQ-INT-002`, `REQ-API-001`, `REQ-API-002`

### Given
Golden Consumer RAGFlow deployment + disposable test resource。

### When
contract suite runs。

### Then
list/keywords/total/available/SET/restore all pass。
SET confirmed by Provider HTTP+code；GET 断言 MAY 含短延迟/重试（list 最终一致）。

### Oracle
all exact assertions PASS；cleanup confirms restored/removed test state。

### Evidence
runtime version + image digest + nodeskclaw SHA + command + exit 0。

---

# 22. Acceptance Input Matrix

| Case | Source | Active Ver | Runtime Doc | Permission | Provider | Operation | Expected |
|---|---|---|---|---|---|---|---|
| 1 | exists | exists | exists | read | OK | GET default | 200 page |
| 2 | exists | exists | exists | read | OK | GET empty | 200 empty |
| 3 | exists | exists | exists | read | OK | GET keywords | provider filter |
| 4 | exists | exists | exists | read | OK | page_size=100 | 200 |
| 5 | exists | exists | exists | read | OK | page_size=101 | 422 / 0 provider |
| 6 | missing | n/a | n/a | n/a | n/a | GET | 404 / 0 provider |
| 7 | exists | null | n/a | read | n/a | GET | NO_ACTIVE_VERSION |
| 8 | exists | invalid | n/a | read | n/a | GET | ACTIVE_VERSION_INVALID |
| 9 | exists | exists | null | read | n/a | GET | RUNTIME_DOCUMENT_MISSING |
| 10 | exists | exists | exists | read | timeout | GET | PROVIDER_UNAVAILABLE |
| 11 | exists | exists | exists | read | malformed | GET | CONTRACT_INVALID |
| 12 | exists | V1 | exists | update | OK | PATCH V1 false | success |
| 13 | exists | V2 | exists | update | OK | PATCH stale V1 | 409 / 0 provider |
| 14 | exists | V1 | exists | read only（无 update 且无 KB manage） | OK | PATCH | 403 / 0 provider |
| 14b | exists | V1 | exists | no file update；KB manage | OK | PATCH V1 | success |
| 15 | exists | V1 | exists | update | unsupported | PATCH | UPDATE_UNSUPPORTED |
| 16 | exists | V1 | exists | update | timeout unknown | PATCH | MUTATION_UNCERTAIN |
| 17 | exists | V1 | exists | read | OK | malicious content | opaque string |
| 18 | exists | V1 | exists | read | total=137 | page 10 | total 137 |
| 19 | exists | V1 | exists | read | no total | GET | CONTRACT_INVALID |
| 20 | exists | V1 | exists | read | OK | keyword 201 chars | 422 / 0 provider |
| 21 | exists | V1 | exists | update | chunk missing | PATCH | NOT_FOUND |

---

# 23. Negative Acceptance

```text
A-NEG-001
new Chunk ORM persistent model exists
→ FAIL CHUNK_GATEWAY_BOUNDARY_VIOLATION

A-NEG-002
local keyword filter / rerank / re-chunk exists
→ FAIL CHUNK_GATEWAY_BOUNDARY_VIOLATION

A-NEG-003
Consumer API accepts dataset_id/document_id
→ FAIL PROVIDER_ID_BOUNDARY_VIOLATION

A-NEG-004
GET triggers business DB/RAGFlow write
→ FAIL READ_ONLY_VIOLATION

A-NEG-005
stale file_version_id PATCH reaches provider
→ FAIL; provider mutation count must be 0

A-NEG-006
PATCH updates content/keywords/questions
→ FAIL; business body key set must equal {available}

A-NEG-007
update wrapper sends full raw Chunk object
→ FAIL WRITE_SCOPE_VIOLATION

A-NEG-008
response/log exposes RAGFLOW_API_KEY / Authorization / provider secret URL
→ FAIL CREDENTIAL_EXPOSURE

A-NEG-009
Public DTO / response includes available_int
→ FAIL PROVIDER_FIELD_LEAK

A-NEG-010
Chunk API accepts historical file_version_id as target version
→ FAIL VERSION_SCOPE_VIOLATION

A-NEG-011
RagflowClient chunk update uses deprecated Provider PUT as primary verb
→ FAIL PROVIDER_VERB_VIOLATION
```

---

# 24. Failure Injection

| Injection Point | Required Postcondition |
|---|---|
| before SourceFile read | fail; provider call=0 |
| after SourceFile read before version resolve | no provider call; no mutation |
| after version resolve before binding | no provider call; no mutation |
| before RAGFlow GET | GET error; no business mutation |
| RAGFlow GET timeout | provider unavailable; no local Chunk state |
| RAGFlow GET malformed | contract invalid; fail closed |
| before PATCH version guard | stale → 409; provider mutation=0 |
| after guard before provider PATCH | failure; provider mutation=0 |
| provider PATCH confirmed reject | mapped error; no local Chunk state |
| provider PATCH timeout after send | MUTATION_UNCERTAIN; no inverse write |
| provider PATCH success but audit write fails | error + safe log provider_mutation_confirmed=true; no inverse write |
| logging failure | business state follows operation result; no secret output |

---

# 25. Evidence Contract

每个 Required Acceptance 至少：

```json
{
  "acceptance_id": "A-API-001",
  "status": "PASS",
  "requirement_ids": ["REQ-API-001"],
  "test_ids": ["TEST-A-API-001"],
  "command": "pytest ...",
  "exit_code": 0,
  "oracle": {
    "type": "exact_assertion",
    "expected": "...",
    "actual": "..."
  },
  "repo": "loudon84/nodeskclaw",
  "branch": "feat/knowledge-v2.0",
  "commit_sha": "<implementation-sha>",
  "timestamp": "<ISO8601>",
  "tool_version": "<pytest/python>",
  "evidence_files": []
}
```

Golden Consumer MUST 额外记录：

```text
RAGFlow version
RAGFlow image/deployment digest
test SourceFile identity
pre/post/restored available
cleanup result
```

Rules：

```text
SKIPPED != PASS
BLOCKED != PASS
```

---

# 26. Requirement Traceability Matrix

| Requirement | Invariant | Acceptance | Test | Evidence | Release Gate |
|---|---|---|---|---|---|
| REQ-ARCH-001 | INV-ARCH-001/002 | A-ARCH-001, A-NEG-001/002 | TEST-A-ARCH-* | EVID-A-ARCH-* | REQUIRED |
| REQ-DATA-001 | INV-DATA-001 | A-DATA-001/002, A-NEG-003 | TEST-A-DATA-* | EVID-A-DATA-* | REQUIRED |
| REQ-API-001 | INV-API-001/002 | A-API-001..004, A-NEG-004 | TEST-A-API-* | EVID-A-API-* | REQUIRED |
| REQ-API-002 | INV-API-UPDATE-001/002 | A-API-UPDATE-001/002, A-TXN-001, A-NEG-005/006 | TEST-A-API-UPDATE-* | EVID-A-API-UPDATE-* | REQUIRED |
| REQ-INT-001 | INV-INT-001 | A-INT-001, A-COMPAT-001 | TEST-A-INT-001 | EVID-A-INT-001 | REQUIRED |
| REQ-INT-002 | INV-INT-002 | A-INT-002, A-NEG-007 | TEST-A-INT-002 | EVID-A-INT-002 | REQUIRED |
| REQ-SVC-001 | INV-SVC-001 | A-SVC-001 | TEST-A-SVC-001 | EVID-A-SVC-001 | REQUIRED |
| REQ-SEC-001 | INV-SEC-001 | A-SEC-001..004, A-NEG-008..011 | TEST-A-SEC-* | EVID-A-SEC-* | REQUIRED |
| REQ-OBS-001 | INV-OBS-001 | A-OBS-001/002 | TEST-A-OBS-* | EVID-A-OBS-* | REQUIRED |
| REQ-COMPAT-001 | INV-COMPAT-001 | A-COMPAT-001/002 | TEST-A-COMPAT-* | EVID-A-COMPAT-* | REQUIRED |
| External Dependency | runtime contract | A-DEP-001 | TEST-A-DEP-001 | EVID-A-DEP-001 | REQUIRED |

任何 MUST 无映射 → PRD BLOCKED。

---

# 27. File Change Contract

## 27.1 New Files

```text
nodeskclaw-knowledge/app/services/source_chunk_service.py
nodeskclaw-knowledge/tests/test_source_chunk_service.py
nodeskclaw-knowledge/tests/test_source_chunks_api.py
nodeskclaw-knowledge/tests/ragflow_contract/test_chunk_contract.py
```

## 27.2 Modified Files

```text
nodeskclaw-knowledge/app/api/source_files.py
```

新增 GET/PATCH Chunk routes。

```text
nodeskclaw-knowledge/app/schemas/knowledge.py
```

新增 SourceFileChunkOut / PageOut / Patch / Result。

```text
nodeskclaw-knowledge/app/integrations/ragflow/client.py
```

新增 RagflowChunkPage / list_document_chunks_page / set_document_chunk_available（Provider **PATCH**）；保持 old list method compatibility。

```text
nodeskclaw-knowledge/app/runtime/ragflow.py
```

新增 thin wrappers。

```text
nodeskclaw-knowledge/app/models/enums.py
```

新增 AuditAction：

```text
chunk_availability_update = "CHUNK_AVAILABILITY_UPDATE"
```

## 27.3 Must Not Create

```text
app/models/chunk.py
DB migration for Chunk content
Chunk local repository/store
Chunk content cache table
```

## 27.4 Frontend Contract (additive)

```text
nodeskclaw-knowledge/contracts/frontend/v1.0.0/
  （经 frontend_contract_spec.py 再生）
  openapi.frontend.yaml
  FRONTEND-INTEGRATION.md
  及相关 generated artifacts
```

MUST：additive 补充 SourceFile Chunk List/PATCH；MUST NOT 另开 1.1.0 目录。

---

# 28. Release Gate

Required Acceptance：

```text
A-ARCH-001
A-DATA-001
A-DATA-002
A-API-001
A-API-002
A-API-003
A-API-004
A-API-UPDATE-001
A-API-UPDATE-002
A-TXN-001
A-INT-001
A-INT-002
A-SVC-001
A-SEC-001
A-SEC-002
A-SEC-003
A-SEC-004
A-OBS-001
A-OBS-002
A-COMPAT-001
A-COMPAT-002
A-DEP-001
A-NEG-001
A-NEG-002
A-NEG-003
A-NEG-004
A-NEG-005
A-NEG-006
A-NEG-007
A-NEG-008
A-NEG-009
A-NEG-010
A-NEG-011
```

Rule：

```text
SKIPPED != PASS
BLOCKED != PASS
任一 Required Acceptance != PASS
→ Release Gate FAIL
→ process exit != 0
```

---

# 29. Golden Consumer / Real-world Acceptance

Golden Consumer：

```text
nodeskclaw-knowledge HTTP API
+
real RAGFlow deployment
```

Required real flow：

```text
1 create/use test KB
2 ensure one active parsed SourceFile
3 GET /source-files/{id}/chunks
4 assert total/items/file_version_id
5 GET with keywords
6 choose disposable test Chunk
7 PATCH available to inverse current value
8 GET and confirm provider state
9 PATCH back to original value
10 GET and confirm restoration
```

Evidence MUST record：

```text
nodeskclaw repo/branch/commit SHA
RAGFlow runtime version
RAGFlow image/deployment digest
SourceFile/FileVersion test identity
pre/post/restored available
test command
exit code
timestamp
cleanup result
```

Synthetic Fixture MUST NOT replace Golden Consumer。

---

# 30. Plan Generation Gate

当前 PRD status：

```text
APPROVED_FOR_PLAN
```

已确认 shared understanding；**暂不生成** `.plan.md`（待后续明确授权）。

只有 `status = APPROVED_FOR_PLAN` 时才允许生成 `.plan.md`。

以下语义 Plan Agent MUST NOT 改写：

```text
RAGFlow = Chunk SOT
nodeskclaw = Thin Gateway
GET 不接收 dataset/document id
GET 不要求 consumer 传 active version
GET/PATCH MUST NOT 接受历史 file_version_id 作为 Chunk 目标版本（NON-GOAL-014）
PATCH 必须传 file_version_id 做 stale guard
GET default page=1/page_size=50
page_size max=100
keywords max=200
keyword search provider-side
total provider-side
PATCH only available field
Public DTO MUST NOT 暴露 available_int
Provider mutation verb = PATCH（非 deprecated PUT）
Confirmed success = Provider HTTP + envelope success；不强制 read-after-write
GET uses FilePermission.read
PATCH uses FilePermission.update OR KbPermission.manage
no local Chunk persistence/filter/rerank/re-chunk
uncertain remote mutation requires refetch
frontend contract v1.0.0 additive chunks endpoints
provider chunk miss → KNOWLEDGE_CHUNK_NOT_FOUND
```

Plan Todo MUST 使用：

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

---

# 31. PRD Quality Gate

## Architecture

```text
[x] Goal 唯一明确
[x] Scope / Non-goal 完整
[x] Owner 不重叠
[x] System Boundary 明确
```

## State

```text
[x] 所有持久状态有 SOT
[x] Observed / Resolved / Runtime / Evidence 分离
[x] State transition 明确
```

## Semantics

```text
[x] default 行为明确
[x] optional / required 明确
[x] conflict 行为明确
[x] ownership 明确
[x] identity/hash scope 明确
```

## Side Effects

```text
[x] 每个 operation 有 mutation contract
[x] GET read-only 可证明
```

## Failure

```text
[x] 每个 failure 有 error code
[x] confirmed failure postcondition 明确
[x] uncertain mutation 有恢复方案
[x] retryable / non-retryable 已区分
```

## Acceptance

```text
[x] 每个 MUST 有 AC
[x] 每个 MUST NOT 有 Negative AC
[x] mutation 有 failure injection
[x] 高风险需求有输入矩阵
[x] Oracle 可机器判断
```

## Evidence

```text
[x] 每个 required AC 有 Evidence schema
[x] Evidence 绑定 repo commit
[x] BLOCKED/SKIPPED 不算 PASS
[x] Release Gate 与 process exit code 一致
```

## Plan Readiness

```text
[x] grilling Q1–Q16 已编码进本 PRD（见 frontmatter grilling_decisions）
[x] 现网 RAGFlow v0.27.0 PATCH available probe PASS
[x] 无 SPEC_SEMANTIC_GAP（当前设计语义）
[x] 无 TBD
[x] Traceability 完整
[x] status = APPROVED_FOR_PLAN（grilling shared understanding 已确认；暂不生成 .plan.md）
```

---

# 32. Definition of Done

```text
[ ] SourceFile GET Chunks API 已存在
[ ] SourceFile PATCH Chunk available API 已存在
[ ] GET 只要求 source_file_id + query
[ ] PATCH 使用 file_version_id 做 stale guard
[ ] SourceFile → active version → document mapping 正确
[ ] RuntimeBinding → dataset mapping 正确
[ ] RAGFlow list chunks total 未丢失
[ ] keywords 完全下推 RAGFlow
[ ] no local keyword filtering
[ ] no local rerank
[ ] no local re-chunk
[ ] no Chunk ORM / Chunk business table
[ ] no local Chunk content persistence
[ ] Public response 无 dataset_id/document_id/provider URL/API key
[ ] GET requires FilePermission.read
[ ] PATCH requires FilePermission.update OR KbPermission.manage
[ ] PATCH provider JSON only contains available
[ ] Provider verb is PATCH（not deprecated PUT）
[ ] Public response 无 available_int
[ ] contracts/frontend/v1.0.0 additive chunks 已更新
[ ] stale version PATCH provider call=0
[ ] chunk not found → KNOWLEDGE_CHUNK_NOT_FOUND
[ ] uncertain mutation 不做反向写，要求 refetch
[ ] mutation audit 可追踪
[ ] logs 无 Chunk full content / credential
[ ] existing API regression suite PASS
[ ] RAGFlow contract tests PASS
[ ] Golden Consumer PASS（断言前允许短延迟 GET）
[ ] Required Acceptance 全部有 Evidence
[ ] Release Gate PASS
```

---

# 33. 最终目标架构

```text
                    smc-copilot / API Consumer
                               │
                               │ source_file_id
                               ▼
                  nodeskclaw-knowledge API
                               │
                  ┌────────────┼─────────────┐
                  │            │             │
                  ▼            ▼             ▼
             Permission   Active Version   Runtime Binding
                  │            │             │
                  └────────────┼─────────────┘
                               │
                               ▼
                    Source Chunk Service
                        (Thin Gateway)
                               │
                               ▼
                    RagflowRuntimeAdapter
                               │
                               ▼
                       RagflowClient
                               │
                               ▼
                 RAGFlow Document Chunk API
                               │
                               ▼
                     RAGFlow Chunk Store
```

稳定职责：

```text
RAGFlow：
- create Chunk
- store Chunk
- keyword filtering
- pagination source
- total source
- available source
- available mutation

nodeskclaw-knowledge：
- auth
- permission
- SourceFile active version mapping
- dataset/document mapping
- provider forwarding
- minimal normalize
- error mapping
- audit / observability

Consumer：
- display
- interaction
- local UI state
```

最终原则：

> **Chunk 数据和 Chunk 状态属于 RAGFlow；nodeskclaw-knowledge 只做可信的、可审计的 Thin Gateway。**
