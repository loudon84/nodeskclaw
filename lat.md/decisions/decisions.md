# Decisions

跨组件不变量与架构取舍；改相关代码前先确认决策仍成立，变更需同步更新本节。

- [[soft-delete]] — 全库软删除与 Partial Unique Index
- [[error-contract]] — 失败响应的 error_code / message_key / message
- [[ce-ee-split]] — FeatureGate 控制社区版与企业版能力
- [[compute-providers]] — k8s / docker / process 三计算 Provider
- [[dual-api-prefix]] — Portal 与 Admin 双前缀共享 handler、成员表分离
- [[knowledge-ragflow-split]] — Knowledge 权限治理与 RAGFlow 语义检索职责分离
- [[work-expert-contract]] — Expert MCP 对 apps/work 的 WORK-EXPERT-CONTRACT 绑定（当前 v1.0.1，v1.0.0 冻结）

临时笔记与逐步代码 walkthrough 不属于此处。
