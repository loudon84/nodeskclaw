已检查 `loudon84/nodeskclaw` 当前代码。结论：**team_v2.1_mcp-skill-gateway 的骨架已经落地，但还不建议进入正式联调**。核心表结构、管理 API、代理入口、路由器、策略引擎、健康检查、审计模型都已创建；但存在几个会直接影响运行闭环的问题。

## 已完成的部分

代码已经新增 Gateway 管理路由和代理路由，并挂载到 `/api/v1/gateway` 下。`api_router` 已引入 `gateway_router` 与 `gateway_proxy_router`，并分别挂到 Gateway 管理和 Gateway 代理前缀。 

数据库层已新增三张核心表：`mcp_gateway_routes`、`mcp_gateway_policies`、`mcp_gateway_audit_logs`，迁移文件中也包含对应索引和外键。  

MCP 代理入口已实现 `POST /gateway/mcp`，会从请求参数中读取 `instance_id` 和 tool name，并校验当前用户组织下是否有权访问该实例。 

## 阻塞问题

### P0-1：Gateway CRUD 和审计日志没有提交事务，数据可能不会持久化

当前 `get_db()` 只 `yield session`，没有自动 `commit()`。

但 Gateway 的创建、更新、删除只做了 `flush()`，没有 `commit()`。例如创建路由只 `db.add(route)`、`flush()`、`refresh()` 后直接返回。 删除路由也只是 `soft_delete()` 后 `flush()`。 策略更新同样只有 `flush()`。

审计日志也只 `db.add(log_entry)` 和 `flush()`，没有提交。

**影响：** 路由、策略、审计日志在请求结束后可能回滚。Gateway 管理页面看似创建成功，但数据库无记录；代理调用产生的审计日志也可能丢失。

**修复要求：**

* Gateway CRUD 接口在写操作后执行 `await db.commit()`。
* `AuditService.record()` 不建议内部强制 commit，建议由调用方在代理请求结束后统一 commit。
* 或调整 `get_db()` 为事务型依赖，但需要评估全项目其他 API 的事务行为，避免破坏现有显式 commit 逻辑。

---

### P0-2：按 skill 路由实际没有生效

代理入口已经从 `body.params` 中取了 `tool_name = body.params.get("name")`。

`RouteMatcher.match()` 也支持按 `match_tools` 匹配 tool name，只有传入 `tool_name` 时才会判断匹配规则。

但 `ProxyService._handle_tools_call()` 调用路由匹配时没有传 `tool_name`，只传了 `instance_id` 和 `org_id`。 通用方法 `_handle_generic()` 也没有传。

**影响：** 未来按 `writer.article.generate`、`writer.ic.review`、`finance.report.generate` 等 skill/tool 做路由时不会命中 `match_tools`，只会走无匹配工具条件的默认路由或第一个可用 MCP Server。这会导致 Writer / Finance / Coding Agent 路由错发。

**修复要求：**

```python
targets = self._route_matcher.match(
    instance_id,
    tool_name=params.get("name") if params else None,
    org_id=org_id,
)
```

同时建议在 `tools/call` 中强制校验 `params.name`，缺失时直接返回 400 级错误。

---

### P1-1：路由中的 `mcp_server_ids` 没有校验归属，存在跨实例 / 跨组织调用风险

创建路由时直接保存 `body.mcp_server_ids`，没有校验这些 MCP Server 是否存在、是否 active、是否属于当前 instance。

后续 `_get_server()` 只按 `server_id` 查 `InstanceMcpServer`，没有校验 `instance_id` 或组织归属。

而 `InstanceMcpServer` 模型本身只有 `instance_id`，没有直接的 `org_id` 字段。

**影响：** 如果路由记录中写入了其他实例的 MCP Server ID，Gateway 可能把请求转发到不属于当前实例的服务。多组织场景下，如果 ID 泄露，存在越权调用风险。

**修复要求：**

* 创建 / 更新路由时校验所有 `mcp_server_ids`：

  * MCP Server 必须存在；
  * 必须属于 `body.instance_id`；
  * `body.instance_id` 必须属于当前 org；
  * MCP Server 必须未删除且 active。
* `_get_server()` 改为带 `instance_id` / `org_id` 约束查询，不能只按 server id 查。

---

### P1-2：策略字段定义了 `max_connections` 和 `retry_count`，但代理层没有执行

策略 Schema 已定义 `rate_limit_rpm`、`max_connections`、`timeout_seconds`、`retry_count` 等字段。

策略引擎也会把 `retry_count`、`max_connections` 返回到 `PolicyResult`。

但 `ProxyService` 当前只使用了 `timeout_seconds`，没有执行并发连接限制，也没有按 `retry_count` 做重试。转发逻辑只是单次 `httpx.AsyncClient.post()`。 

**影响：** Gateway 策略页面看起来支持 quota / retry，但实际只有 RPM 生效。高并发或上游短暂失败时，策略能力不完整。

**修复要求：**

* `max_connections`：增加按 `org_id + instance_id + tool_name` 维度的并发计数或 `asyncio.Semaphore`。
* `retry_count`：对超时、连接错误、5xx 响应执行有限重试。
* 审计日志记录 `retry_count_used`、最终上游 server、最终失败原因。

---

### P1-3：审计日志不能满足“记录用户提交了什么需求”的要求

审计模型当前记录了 `caller_user_id`、`caller_org_id`、`instance_id`、`method`、`tool_name`、`request_params_hash`、`response_status` 等字段。

`AuditService` 对请求参数只保存哈希：`request_params_hash = sha256(...)`。

**影响：** 现在只能证明“某用户在某时间调用了某 tool”，不能回放“提交了什么写作需求”。这与 Writer Agent 场景下的审计诉求不一致。

**修复要求：**

新增字段或独立表：

* `request_summary`：脱敏后的用户需求摘要。
* `request_params_redacted`：脱敏后的 JSONB 参数。
* `artifact_ids`：生成文档、引用文件、附件的归档 ID。
* `upstream_request_id`：Hermes Writer Agent 返回的 run id / task id。
* `client_ip`、`user_agent`、`source_client`：用于定位调用来源。

敏感字段仍然可以只存 hash，但写作任务标题、摘要、文章主题、输出 artifact 必须可追溯。

---

### P1-4：JSON-RPC `id` 被代理层丢弃

`McpProxyRequest` Schema 已支持 `id` 字段。

但 `ProxyService.handle_mcp_request()` 没有接收原始 `id`。

转发给上游时固定写死 `"id": 1`。

**影响：** MCP/JSON-RPC 客户端无法正确做请求响应关联。并发调用时尤其容易出现响应匹配错误。

**修复要求：**

* `proxy_mcp_request()` 把 `body.id` 传给 `ProxyService`。
* `_forward_to_server()` 使用原始 `id`。
* 如果上游返回 id 为空，Gateway 返回原始 id。

---

### P2-1：上游健康检查路径可能不适配 MCP 服务

健康检查当前用：

```python
health_url = server.url.rstrip("/") + "/health"
```



如果 MCP Server URL 是 `http://agent.superic.com:8787/mcp`，健康检查会访问 `http://agent.superic.com:8787/mcp/health`，这不一定存在。

另外代理转发选中 server 后，并没有根据健康检查状态跳过不可用上游。

**修复要求：**

* `InstanceMcpServer` 增加 `health_url` 字段。
* 没配置时才使用默认推导。
* `ProxyService` 选择 target 时过滤 `gateway_health_checker.is_available(server.id) == False` 的上游。
* 上游不可用时尝试下一目标，而不是固定取 `targets[0]`。

---

### P2-2：SSE 混合模式还没有真正落地

配置项里已经有 Gateway SSE 相关参数。

`SSEManager` 也定义了连接注册、touch、清理等能力。

但当前 API Router 只挂载了 `gateway_router` 和 `gateway_proxy_router`，没有看到 Gateway SSE 路由挂载。 `main.py` 中启动了 Gateway 健康检查，但没有启动 SSEManager 清理任务。

**影响：** 当前实现更接近 “HTTP JSON-RPC MCP Proxy”，还不是完整的 “MCP + SSE 混合模式”。

**修复要求：**

* 新增 `/api/v1/gateway/sse/{instance_id}` 或 `/api/v1/gateway/events`。
* 增加连接鉴权、实例权限校验、心跳、断线清理。
* 审计 SSE 连接建立、关闭、异常断开。
* 支持 Writer 长任务的 run event / artifact event 推送。

---

## 建议修复顺序

1. **先修事务提交问题**：否则所有管理配置和审计都不可靠。
2. **修按 tool_name 路由问题**：否则 skill gateway 的核心路由目标不成立。
3. **修 MCP Server 归属校验**：避免跨实例 / 跨组织转发风险。
4. **补审计字段与 artifact 归档关系**：满足“谁、什么时候、提交了什么、生成了什么文档”的要求。
5. **补全 Policy 执行能力**：并发限制、retry、timeout、敏感工具审批。
6. **实现 SSE Gateway 路由**：作为 Writer 长任务事件流和文档生成进度推送通道。
7. **补集成测试**：至少覆盖路由匹配、权限越权、审计落库、策略限流、上游失败切换。

## 当前评审结论

`team_v2.1_mcp-skill-gateway` 已完成基础框架，但当前状态应定义为：

> **代码骨架完成，核心闭环未完成。**

建议进入下一轮修复版本，例如：

`team_v2.1.1_mcp-skill-gateway-hardening`

修复完成后再做 Writer Agent 内网调用联调。
