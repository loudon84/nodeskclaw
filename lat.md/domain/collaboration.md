# Collaboration

赛博办公室协作覆盖黑板、群聊消息与 Agent 协作；消息统一经运行时 MessageBus 投递，保证可靠与可审计。

协作数据以 Workspace 为作用域。黑板承载任务与 OKR 式目标；消息走 CloudEvents 对齐的信封与中间件管道。运行时细节见 [[runtime]]。

## Blackboard

黑板是工作区内的共享协作面：帖子、回复与附件，供人与 Agent 共同读写任务与目标。

黑板不是聊天记录替代品；聊天走消息总线，黑板偏结构化协作状态。变更 Agent 对黑板的行为时，需同步评估 Gene / Skill 提示。

## Message Envelope

`MessageEnvelope` 是跨节点消息的统一信封，对齐 CloudEvents 语义（id、type、workspace、sender、data）。

所有入站消息应封装为信封再进入总线，避免各 Channel 私有格式泄漏到上层。实现：[[nodeskclaw-backend/app/services/runtime/messaging/envelope.py#MessageEnvelope]]。

## Message Bus

`MessageBus` 是运行时消息中枢：经校验、过滤、限流、路由、熔断、传输与审计中间件后投递。

可靠性依赖 PGMQ、ACK/Retry/DLQ、幂等与 SSE / PG NOTIFY 跨实例推送。入口：[[nodeskclaw-backend/app/services/runtime/messaging/bus.py#MessageBus]]。

### Middleware Pipeline

消息管道按固定顺序挂载中间件：metrics → validation → content filter → rate limit → semantic → routing → circuit breaker → transport → audit。

新增中间件必须插入明确位置并说明对延迟、失败语义与审计的影响；禁止绕过管道直接写传输层。

## Agent Tunnel

Agent Tunnel 用 WebSocket 隧道替代「SSE + HTTP 直连」组合，支持 @mention 与 no_reply 等交互。

隧道属于 runtime transport，不替代 MessageBus 的业务路由；业务事件仍应进信封与管道。
