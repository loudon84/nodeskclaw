# LLM Proxy Architecture

`nodeskclaw-llm-proxy` 是独立 FastAPI 服务：OpenAI 兼容转发、HMAC 鉴权、额度预检、用量记录与多 Provider 适配。

它是透明代理层，不承载 Portal UI，不直接耦合后端页面逻辑。CODEMAP：`.cursor/context/llm-proxy-codemap.md`。

## Request Pipeline

标准链路：收请求 → 解析归因 token → 额度检查 → 模型路由 → 转发 / 流式中转 → 记录用量 → 统一响应。

额度必须在转发前判定；不足返回 429。流式在结束后记实际 token；中断也要记已消耗部分。核心入口：[[nodeskclaw-llm-proxy/app/proxy.py#llm_proxy]]。

## Attribution And Quota

调用方通过 HMAC 归因 token 绑定 tenant / workspace / instance，再映射真实 Provider Key。

组织 Working Plan 与个人 Key 路径不同，但都必须可审计。密钥与完整 prompt 默认不入日志（`LLM_LOG_CONTENT` 默认关闭）。

## Provider Adapters

Proxy 屏蔽 Provider 差异：OpenAI 兼容路径、Gemini 转换、Codex CLI 本地进程等。

新增 Provider 时在 `proxy.py` 完成 URL/headers/body 适配，并补测试；错误响应只返回标准化错误，不回传上游可能含密钥的原文。

## Isolation From Backend

Proxy 可与 Backend 共享 PostgreSQL 中的 Key / 用量表，但进程与部署独立。

不要把业务编排（部署、Gene、黑板）塞进 Proxy；也不要在 Backend 里复制一份完整转发实现绕过额度。
