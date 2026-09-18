# NoDeskClaw / DeskClaw 团队版

DeskClaw 团队版实例与企业知识管理的共享领域语言。本文件只定义术语，不含实现细节。

## Language

### Knowledge

**KnowledgeSet**:
一组可检索的 KnowledgeBase 编排单元，Agent 检索的默认作用域。
_Avoid_: Dataset, collection, corpus

**KnowledgeBase**:
纳入 KnowledgeSet 的单个知识库成员。
_Avoid_: Dataset（除非特指 RAGFlow Dataset）

**Evidence**:
一次检索返回的可引用证据投影（含 evidence_id、内容与来源引用）；对 Hermes Agent 而言以 Tool Result 形式提供。
_Avoid_: Citation（对外产品语言优先 Evidence；内部持久化名可并存）, snippet

**KnowledgePrincipal**:
由 backend 用户身份换算出的知识访问主体（成员/组织/角色等），用于 ACL。
_Avoid_: User（在 Knowledge 边界内）, service account

**SMC_KB_API_TOKEN**:
供 Hermes Knowledge 插件调用 Knowledge API 的 backend 用户 JWT（Bearer）；不是 Knowledge 服务令牌。
_Avoid_: KNOWLEDGE_SERVICE_TOKEN, API key（本插件路径）

**SMC_KB_API_URL**:
nodeskclaw-knowledge 服务的 origin（scheme://host:port），不含 API path。
_Avoid_: 完整 tool URL, 带 `/api/v2` 的 base

### Hermes plugin

**hermes-plugin-nodeskclaw-knowledge**:
让 Hermes Agent 通过 `knowledge.retrieve` 调用企业 KnowledgeSet 检索的插件。
_Avoid_: MCP Server（v1.0）, nodeskclaw-bridge（另一插件）
