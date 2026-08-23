# Architecture

架构文档描述系统组成、分层与各组件职责边界，不替代 CODEMAP 的文件定位。

- [[system-overview]] — 总体请求路径、分层、数据存储与安全边界
- [[backend]] — FastAPI 后端、双前缀 API、租户鉴权与 Hermes/MCP
- [[portal]] — 用户门户页面域、API 客户端、i18n 与可视化
- [[llm-proxy]] — LLM 转发、HMAC 归因、额度预检与用量记录
- [[knowledge]] — 知识治理、ACL、安全检索、评测与 RAGFlow Adapter
- [[task]] — AutoTask 独立服务、打包约束与后继作业
- [[runtime]] — 计算 Provider、实例生命周期、Channel 与外部运行时
