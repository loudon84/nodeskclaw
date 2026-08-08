---
name: knowledge-service-impl
overview: 按 PRD v1.0 在 monorepo 新建独立兄弟服务 nodeskclaw-knowledge，技术栈对齐 nodeskclaw-task，实现知识库治理、ACL、入库与 RAGFlow 安全检索闭环。
todos:
  - id: scaffold
    content: nodeskclaw-knowledge 脚手架：pyproject/Dockerfile/.env.example/alembic 骨架
    status: completed
  - id: core
    content: core/：config、JWT security、deps、错误契约 exceptions
    status: completed
  - id: backend-context
    content: backend 增加 GET /auth/knowledge-context 接口（单独 commit）
    status: completed
  - id: models
    content: models/ 8 域表 + BaseModel 软删除 + Alembic autogenerate 迁移
    status: completed
  - id: ragflow-adapter
    content: integrations/ragflow/ Adapter：client/models/mapper/exceptions + 错误映射
    status: completed
  - id: backend-client
    content: integrations/nodeskclaw_backend/ context client
    status: completed
  - id: acl
    content: services/permission_service.py AccessPlan 计算
    status: completed
  - id: ingestion
    content: services/ingestion_service.py 状态机 + metadata 写入 + 蓝绿
    status: completed
  - id: retrieval
    content: services/retrieval_service.py + chunk_security_service.py 安全检索
    status: completed
  - id: api
    content: api/ 路由 + schemas + /api/v1 注册
    status: completed
  - id: tests
    content: tests/ 权限/入库/检索/软删 用例（mock RAGFlow）
    status: completed
  - id: verify
    content: uv run pytest + ruff + alembic upgrade head 验证 + lat.md 锚点 + lat check
    status: completed
isProject: false
---

# nodeskclaw-knowledge 实施计划

## 前端表现变化
本次为纯后端新服务，无前端表现变化。

## 技术栈对齐（相对 PRD §28 的调整）
- 分层 `api → schemas → services → models`（对齐 backend/task）；不建强制 `repositories/`，`api/v1/` 子目录改为 `api/*.py` + `router.py` 聚合
- 错误契约：`error_code` + `message_key` + `message`（参考 [nodeskclaw-backend/app/core/exceptions.py](nodeskclaw-backend/app/core/exceptions.py)）
- 软删除 `BaseModel`（UUID id + `deleted_at` + `soft_delete()` + `not_deleted()`，复制自 [nodeskclaw-task/app/models/base.py](nodeskclaw-task/app/models/base.py)）
- 唯一约束一律 Partial Unique Index `postgresql_where=text("deleted_at IS NULL")`
- 首版不引入 Redis（member context 进程内短 TTL 或不缓存）

## 目标结构（nodeskclaw-knowledge/）
```text
pyproject.toml / Dockerfile(linux/amd64) / .env.example / alembic.ini
app/
  main.py                 # lifespan: alembic upgrade head + router 注册
  api/                    # router.py + knowledge_bases/knowledge_sets/source_files/ingestion/retrieval.py
  core/                   # config.py(pydantic-settings) / security.py(JWT) / deps.py / exceptions.py
  schemas/                # pydantic 请求/响应
  services/               # member_context/permission/knowledge_base/knowledge_set/source_file/ingestion/retrieval/chunk_security
  models/                 # base.py + 8 域表
  integrations/
    nodeskclaw_backend/client.py   # GET knowledge-context
    ragflow/{client.py, models.py, mapper.py, exceptions.py}
alembic/                  # 自管 versions
tests/
```

## 1. 脚手架与基础设施
- `pyproject.toml`：fastapi、uvicorn[standard]、sqlalchemy[asyncio]、asyncpg、pydantic-settings、python-jose、httpx、alembic、boto3（下载/存储）、python-multipart；dev: pytest/pytest-asyncio/ruff（对齐 [nodeskclaw-backend/pyproject.toml](nodeskclaw-backend/pyproject.toml)）
- `core/config.py`：`DATABASE_URL`、`JWT_SECRET`/`JWT_ALGORITHM`、`NODESKCLAW_BACKEND_URL`、`RAGFLOW_BASE_URL`/`RAGFLOW_API_KEY`、CORS、PORT
- `core/security.py`：本地解 JWT 验签名/过期/token 类型 → `user_id`
- `core/deps.py`：`get_db`、`get_member_context`（调 backend context，转 KnowledgePrincipal）

## 2. Backend Context（在 nodeskclaw-backend 加薄接口）
- `nodeskclaw-backend/app/api/auth.py` 新增 `GET /api/v1/auth/knowledge-context`：复用 `get_current_user_unchecked` + org provider，返回 `member_id/org_id/department/employee_no/job_title/member_role/supervisor_member_id/is_active/is_super_admin`
- 新建 `nodeskclaw-backend/app/schemas/auth.py` 对应 `KnowledgeContextInfo` schema
- 该改动属 backend，单独成 commit

## 3. 数据模型（8 表，全软删除 + Partial Unique Index）
`models/`：`knowledge_base` / `knowledge_base_acl` / `source_file` / `source_file_version` / `source_file_acl` / `knowledge_set` / `knowledge_set_item` / `ingestion_job` / `retrieval_audit`
- 跨服务 ID（`member_id`/`org_id`/`owner_member_id`）仅存字符串，不建跨库 FK
- 关键唯一：`(org_id,name)` KB/Set、`(kb_id,file_name)` source_file、`(source_file_id,version_no)` version、`ragflow_document_id`、ACL 复合键
- 状态 Enum 小写 snake（`provisioning/active/...`）
- 同 commit 生成 `alembic revision --autogenerate`

## 4. RAGFlow Adapter（integrations/ragflow/）
- `client.py`：`httpx.AsyncClient(base_url, Bearer key)`；方法 `create_dataset/update_dataset/delete_dataset/list_datasets`、`upload_document/update_document_metadata/delete_documents/download_document/list_documents`、`parse_documents/stop_parsing`、`retrieve`
- 判定成功用响应 `code==0`（非 HTTP 状态）；`mapper.py` 把 `code!=0`/超时/网络 映射为 `RagflowError` → 平台 `errors.knowledge.ragflow_*`
- 幂等 GET/delete 可重试（≤3，退避）；upload/parse 不自动重试，交给 ingestion job
- 日志脱敏：不落 Key / 完整 chunk

## 5. ACL 与权限计算（services/permission_service.py）
- `subject_type`: member/role/department/organization；`effect`: allow/deny
- 优先级：File DENY > File ALLOW > KB ACL；KB 内 DENY > MEMBER > ROLE/DEPARTMENT > ORGANIZATION
- `build_access_plan(member, knowledge_bases) -> AccessPlan{FULL_ACCESS|FILTERED_ACCESS|NO_ACCESS, dataset_ids, document_ids, source_file_ids}`
- FULL_ACCESS 只传 dataset_ids；FILTERED 才展开 document_ids

## 6. 入库闭环（services/ingestion_service.py）
状态机 `pending→uploading→ragflow_uploaded→metadata_synced→parsing→validating→active|failed|cancelled`
- 顺序铁律：建 source_file/version → RAGFlow upload → 写 `meta_fields`(nk_source_file_id/nk_file_version_id/nk_knowledge_base_id/nk_org_id) → parse → ACTIVE
- 蓝绿：更新生成新 version，失败不动旧 active；成功才切 `active_version_id` + 旧 version `superseded`

## 7. 安全检索（services/retrieval_service.py + chunk_security_service.py）
`retrieve`：resolve member → set → kbs → ACL AccessPlan → `ragflow.retrieve(dataset_ids, document_ids)` → chunk 清洗（按 `document_metadata.nk_source_file_id`，缺失则 `document_id` 反查 meta_fields，仍缺则丢弃告警）→ safe chunks → 写 `retrieval_audit`
- Citation 下载 `source_files/{id}/download` 必须重新鉴权

## 8. API（api/，挂 /api/v1）
按 PRD §26：knowledge-bases(+acl)、knowledge-sets(+绑定)、source-files(+versions/reparse/download/acl)、ingestion、retrieval。统一 `ApiResponse` 包裹 + 错误契约。

## 9. 测试（tests/）
- 权限优先级矩阵、AccessPlan 三分支、metadata 四元组必写、chunk 清洗丢弃未授权、蓝绿切换、软删后同键重建
- Mock RagflowClient（httpx mock），不连真实 RAGFlow

## 验证
- `cd nodeskclaw-knowledge && uv sync && uv run pytest`
- `uv run ruff check .`
- `uv run alembic upgrade head`（需可用 DATABASE_URL）
- 更新 `lat.md/architecture/knowledge.md` 等锚点后 `lat check`

## 待确认点
1. 数据库：独立 `nodeskclaw_knowledge` 库，还是与 backend 同 RDS 不同 schema？（默认独立 database）
2. 是否本轮就把 backend 的 `knowledge-context` 接口一并实现？（默认：是，单独 commit）
3. `retrieval_audit` 是否记录完整 query？（默认：只存 `query_hash`，不落明文）