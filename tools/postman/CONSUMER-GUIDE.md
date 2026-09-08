# Skill Run 消费端 Postman 联调指南

本文说明外部 Work / 消费端如何使用 **唯一公共联调包** [nodeskclaw-skill-run-consumer-v1.2.1.postman_collection.json](nodeskclaw-skill-run-consumer-v1.2.1.postman_collection.json)。

该 Collection 只覆盖 Backend JWT 鉴权面：

- `POST /api/v1/mcp`（`tools/list`、`tools/call`）
- `GET|POST /api/v1/runs/*`（Run 投影、Result、Events、Artifacts、Cancel）

**禁止**直连 Agent（`4580`）或 Internal Edge（`/api/v1/internal/edge/*`）。合同锚点：`nodeskclaw-backend/contracts/skill-run/v1.2.1/`。

内部 Agent / Edge 调试请使用 [nodeskclaw-agent-full-flow.postman_collection.json](nodeskclaw-agent-full-flow.postman_collection.json) 与 [GUIDE.md](GUIDE.md)。旧版 `nodeskclaw-skill-platform-v1.5.postman_collection.json` 不作消费基线。

## 1. 前置条件

1. Backend 已启动（默认 `http://127.0.0.1:4510`），`SKILL_AGENT_ENABLED=true`。
2. 测试组织内已有 **已 published** 且 **`is_mcp_exposed: true`** 的 Skill，并已 **central 安装** 到某个 Agent。
3. 推荐先用内部 Collection 准备数据（隔离测试组织）：

| 内部请求 | 作用 |
| --- | --- |
| 04–06 | 创建 Catalog v1.1 chat Skill、发布 Release（需 Skill 具备 `canonical_path` 才能生成 Bundle） |
| 09 | 创建 Central Installation（需填写 `central_agent_id`） |

4. 将内部 Collection 中的 `tool_name`（默认 `postman_agent_debug`）与消费 Collection 的 `consumer_tool_name` 对齐。

## 2. 变量配置

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `backend_base_url` | 是 | Backend 地址 |
| `backend_access_token` | 是 | 测试组织成员 JWT |
| `org_id` | 是 | 与 JWT 对应的组织 ID |
| `user_id` | 是 | 调用用户 ID（文档/reference） |
| `other_org_id` | 是 | 跨租户负向测试，必须不同于 `org_id` |
| `consumer_tool_name` | 是 | 已发布且已安装的 MCP 工具名，默认 `postman_agent_debug` |
| `idempotency_key` | 否 | 由预请求脚本自动生成 |

Collection 级 Auth 为 Bearer Token；每个请求额外带 `X-Org-Id`。

## 3. 推荐执行顺序

按编号手工 Send，不要用 Collection Runner 一键跑完。

| 阶段 | 请求 | 预期 |
| --- | --- | --- |
| 连通性 | 00 | Backend health 200 |
| Catalog | 01 | `tools/list` 返回 v1.1 描述符，无内部凭证泄漏 |
| 调用与幂等 | 02–02c | `tools/call` 返回 `run_id`；同 key 重放同一 Run；不同参数同 key 返回 `IDEMPOTENCY_CONFLICT` |
| Run 投影 | 03–07 | 公共 Run/Result/Events/Artifacts/Download |
| 取消 | 08–08b | Cancel 200 或幂等 409 |
| 负向 | 09–11 | 无 JWT 401；跨 org 404；未知 tool JSON-RPC error |
| 未冻结能力 | 90–91 | Resume / Approve 可达（非 v1.2.1 合同承诺） |

## 4. 已知限制

### SSE 语义事件

当 Agent 已持久对应结构化事件时，公共 SSE 投影以下已发布类型（payload 对齐冻结 `run-event.schema.json`）：

- 控制事件（`run.*`）
- `assistant.message`
- `reasoning.summary`
- `tool.call`
- `clarify.requested`
- `approval.requested`
- `artifact.persisted`

未知内部事件类型会被丢弃，不会虚构。流响应声明 `Cache-Control: no-store`；可用 `Last-Event-ID` 续播。

### Approval / Resume

`POST /api/v1/runs/{run_id}/resume` 与 `POST /api/v1/runs/{run_id}/approvals/{approval_id}` 已在 Backend 实现，但 v1.2.1 合同 manifest 标 `approval: unsupported`。第 90–91 项仅用于提前联调，**不保证向后兼容**。

### Artifact 下载

第 07 项在 Run 尚无 PERSISTED Artifact 时会跳过断言。需要 Artifact 时请先等待 Run 完成或改用产生 Artifact 的 Skill。

## 5. 与内部 Collection 的关系

```
内部 full-flow (04–09)  →  准备 Skill / Release / Central Install
消费 consumer (00–11)   →  验证公共 MCP + Run 合同面
内部 full-flow (10+)    →  Agent / Edge 内部调试（不交给消费端）
```

## 6. 问题反馈

请附带：请求编号、URL、HTTP 状态码、`error_code` / `message_key`、`consumer_run_id`、Generation（如有）及 Backend 日志时间段。不要提交真实 JWT。
