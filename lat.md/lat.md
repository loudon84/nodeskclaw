# NoDeskClaw

DeskClaw 团队版（NoDeskClaw）是人与 AI 共同经营的实例管理平台：组织治理、AI 员工部署、赛博办公室协作、基因能力分发与 LLM 用量控制。

本目录用 [lat.md](https://www.npmjs.com/package/lat.md) 锚定架构意图、领域概念与关键设计决策，供 Agent 与开发者在改码前对齐「做什么、为什么」，而不是复述源码细节。

- [[domain]] — 领域概念：组织、集群、实例、工作区、基因、协作消息、知识对象与 AutoTask 对象
- [[architecture]] — 系统与组件架构：Backend、Skill Agent、Portal、LLM Proxy、Knowledge、Task、Runtime
- [[decisions]] — 跨组件设计决策：软删除、错误契约、CE/EE、计算 Provider、Knowledge/RAGFlow 边界、WORK-EXPERT-CONTRACT、Skill Platform 执行平面

## Product Mission

产品只服务于「人和 AI 共同经营」：工作区协作、AI 员工（实例）编排、基因进化与组织治理。偏离该方向的需求应先质疑再实现。

对外首次称呼必须是「DeskClaw 团队版」；技术上下文可用 DeskClaw、NoDeskClaw、CE、EE。

实现路径定位仍用 `.cursor/context/*-codemap.md`。Expert MCP 对 apps/work 的消费契约以 [[decisions/work-expert-contract]] 与 `contracts/work-expert/v1.0.2/` 为准；员工 Skill-first 合同与执行平面见 [[decisions/skill-platform-execution]] 与 `contracts/skill-run/v1.0.0/`。其余 Backend 契约见 `docs/backend/`。本目录描述意图与边界。

## Component Boundaries

仓库内主要组件边界固定，跨端改动需明确授权。

| 组件 | 目录 | 职责 |
|------|------|------|
| Backend | `nodeskclaw-backend/` | API、鉴权、编排、审计、SSE、MCP Gateway |
| Skill Agent | `nodeskclaw-agent/` | Skill Run 执行平面（Queue / Event SoT / Hermes Adapter） |
| Portal | `nodeskclaw-portal/` | 用户门户 UI |
| LLM Proxy | `nodeskclaw-llm-proxy/` | LLM 转发、额度、用量 |
| Knowledge | `nodeskclaw-knowledge/` | 知识治理、ACL、安全检索、RAGFlow Adapter |
| Task | `nodeskclaw-task/` | AutoTask 业务 API（独立 FastAPI） |
| Channel Plugins | `openclaw-channel-*/` | 运行时 Channel 插件 |
| EE | `ee/` | 企业版私有扩展（默认不读） |

默认策略：只读当前任务相关目录；禁止为普通 backend 任务扫 portal / llm-proxy / knowledge / ee / openclaw。Skill Run 执行改动需同时看 backend Gateway 与 `nodeskclaw-agent`。详见 [[knowledge]]、[[decisions/skill-platform-execution]]。
