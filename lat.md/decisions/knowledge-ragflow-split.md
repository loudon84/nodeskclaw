# Knowledge Ragflow Split

RAGFlow 负责「语义相关」；`nodeskclaw-knowledge` 负责「谁有权看到」。二者数据模型不互相替代，也不共享员工账号体系。

该边界保证 RAGFlow 可独立升级，且 Desktop / Agent / LLM 永远不直连 RAGFlow。规格验收见 `docs_knowledge/v1.0.md` §35。

## Responsibility Split

RAGFlow 管语义对象与检索；Knowledge 管企业 ACL、源文件注册与安全网关，二者职责不得互换。

| 侧 | 负责 | 不负责 |
|----|------|--------|
| RAGFlow | Dataset、Document、Chunk、Parser、Embedding、跨 Dataset retrieval | 企业 ACL、组织成员、KnowledgeSet 聚合语义 |
| Knowledge | KB/Set/SourceFile 注册、ACL、版本、安全检索网关、审计、RagflowClient | 自建用户表、直接改 RAGFlow DB、把 ACL 写入 Chunk |

检索前后都必须经过 ACL：请求前 AccessPlan；响应后 Chunk Security Clean。Unauthorized Chunk 不得进入 LLM。

## Monorepo Integration

已选定独立兄弟服务：`nodeskclaw-knowledge/` 进 monorepo，技术栈与 [[backend|Backend]] / `nodeskclaw-task` 对齐，不另起语言或 ORM。

用户与 JWT 权威在 Backend；Knowledge 通过 Context API 取 Principal，自有 PostgreSQL + Alembic，不直连 Backend 表。相对 PRD §28：路由用 `api/router.py` 而非 `api/v1/`；弱化 repositories；首版不做 Redis。软删除与错误契约遵循 [[soft-delete]] 与 [[error-contract]]。包内布局见 [[knowledge#Package Placement]]。
