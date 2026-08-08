# Knowledge Ragflow Split

RAGFlow 负责「语义相关」；`nodeskclaw-knowledge` 负责「谁有权看到」。二者数据模型不互相替代，也不共享员工账号体系。

该边界保证 RAGFlow 可独立升级，且 Desktop / Agent / LLM 永远不直连 RAGFlow。规格见 `docs_knowledge/v1.1.md`（相对 v1.0 增加异步入库、Active Version 与 Secure Chat）。

## Responsibility Split

RAGFlow 管语义对象与检索；Knowledge 管企业 ACL、源文件注册与安全网关，二者职责不得互换。

| 侧 | 负责 | 不负责 |
|----|------|--------|
| RAGFlow | Dataset、Document、Chunk、Parser、Embedding、跨 Dataset retrieval | 企业 ACL、组织成员、KnowledgeSet 聚合语义、Chat |
| Knowledge | KB/Set/SourceFile 注册、ACL、版本权威、安全检索网关、Worker、审计、RagflowClient、经 LLM Proxy 的 Secure Chat | 自建用户表、直接改 RAGFlow DB、把 ACL 写入 Chunk、保存 Provider Key |

检索前后都必须经过 ACL + Active Version：请求前 AccessPlan / RetrievalPlan；响应后 Chunk Security Clean。Unauthorized / superseded Chunk 不得进入 LLM。

## Monorepo Integration

已选定独立兄弟服务：`nodeskclaw-knowledge/` 进 monorepo，技术栈与 [[backend|Backend]] / `nodeskclaw-task` 对齐，不另起语言或 ORM。

用户与令牌权威在 Backend；Knowledge 将 Bearer 视为 opaque credential，通过 Context API 取 Principal，自有 PostgreSQL + Alembic。相对 PRD：路由用 `api/router.py`；弱化 repositories；首版不做 Redis；Worker 与 API 共用镜像、不同 CMD。软删除与错误契约遵循 [[soft-delete]] 与 [[error-contract]]。包内布局见 [[knowledge#Package Placement]]。

## Llm Proxy Boundary

Secure Chat 的模型调用必须走 `nodeskclaw-llm-proxy`，Knowledge 不保存 Provider Key，Desktop 不获得 LLM Proxy Credential。

调用契约：Knowledge 服务端持有 `KNOWLEDGE_SERVICE_TOKEN`，请求头携带 org/member/session；禁止伪装 AI Employee `proxy_token`，禁止把 Desktop JWT 当 LLM 凭证。客户端：[[nodeskclaw-knowledge/app/integrations/llm_proxy/client.py#LlmProxyClient]]。
