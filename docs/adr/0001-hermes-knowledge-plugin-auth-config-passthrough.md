---
status: accepted
---

# Hermes Knowledge Plugin：静态用户 JWT、配置双读、响应透传

Hermes Agent v0.21 通过 `hermes-plugin-nodeskclaw-knowledge` 调用 nodeskclaw-knowledge 的已有 `knowledge.retrieve`。v1.0 决定：鉴权复用 backend 用户 JWT（`SMC_KB_API_TOKEN`）经 `Authorization: Bearer` 透传并由服务端 `get_member_context` 换取 `KnowledgePrincipal`（与 Desktop/Portal 一致，不用服务令牌）；配置以 Hermes `config.yaml` 展开值优先、回退 `os.environ` 的 `SMC_KB_API_URL`/`SMC_KB_API_TOKEN`，URL 仅为 origin；插件透传真实检索契约作 Tool Result，不做 Evidence 二次注入，也不负责 `.env` 写入或 Session `knowledge_set_id` 注入。选择静态 JWT 是为了先打通联调；过期由运维刷新 `.env` 并重启，Session 动态 Token 留后续版本。

## Considered Options

- Session 动态注入 Token vs 静态 `.env` JWT → v1.0 选静态，降低应用改造面
- 插件侧简化映射 FR-005 vs 透传服务端契约 → 选透传，避免双契约
- 仅 env / 仅 nested config / 双读 → 选双读，兼容官方 `${VAR}` 与本仓 bridge 的 env 实践
- `KNOWLEDGE_SERVICE_TOKEN` vs 用户 JWT → 选用户 JWT，权限模型与 ACL 一致

## Consequences

- 源码落在 `nodeskclaw-knowledge/plugins/`；运行时安装到 `~/.hermes/plugins/`
- v1.0 Tool 参数仅 `knowledge_set_id` + `query` + `top_k`；多 KB 失败语义跟随服务端
- 服务侧默认零检索语义变更；可补契约测试与 401 可操作性提示
