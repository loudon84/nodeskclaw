# NoDeskClaw Agent Postman 手工联调指南

本文说明如何在开发环境中使用 Postman 调试 `nodeskclaw-agent` 与其 Backend Edge 控制面接口。联调资产是 [nodeskclaw-agent-full-flow.postman_collection.json](nodeskclaw-agent-full-flow.postman_collection.json)。

本指南只面向人工逐项发送请求。它不代表已经完成生产验收，也不要求 Docker、Newman 或当前机器上的服务已经启动。

## 1. 联调边界

Collection 覆盖 Central Run、Approval、Cancel、事件重放、Artifact、Edge Job、Lease、on-demand Artifact 与 Installation Generation。它会创建临时 Skill、Release、Edge Node、Run、Artifact 和 Installation，因此请使用隔离的测试组织。

Collection 里的 Edge 协议段会注册一个独立 Edge Node，避免与正在运行的 Edge Worker 竞争同一个 Job。Installation 段默认验证控制面 Desired/Actual 合同；要验证真实文件系统安装副作用，必须改用实际 Edge Worker 对应的 `edge_node_id` 和 `edge_token`，并在该节点上观察本地安装目录。

## 2. 服务与配置前提

人工启动 Backend 与 Agent 后再导入 Collection。默认地址如下：

| 服务 | 默认地址 | 说明 |
| --- | --- | --- |
| Backend | `http://127.0.0.1:4510` | 对外 API 与 Edge 控制面 |
| Agent | `http://127.0.0.1:4580` | Run、Event 与 Artifact 内部接口 |

Agent 和 Backend 必须连接同一个可用 PostgreSQL（关系数据库）。在启动前确认：

- Backend 已执行迁移，且允许当前用户创建 Skill、发布 Release、注册 Edge Node 和管理 Installation。
- Agent 已执行迁移，`/health/live` 和 `/health/ready` 都返回 HTTP `200`、`status: "ok"`。
- Backend 的 `SKILL_AGENT_ENABLED`（启用 Agent）为 `true`，`SKILL_AGENT_BASE_URL`（Agent 基础地址）指向 Agent，`SKILL_AGENT_INTERNAL_TOKEN`（内部 Token）与 Agent 的 `SKILL_AGENT_INTERNAL_TOKEN` 一致。
- 真实 Edge Worker 联调时，`SKILL_AGENT_EDGE_NODE_ID`（Edge 节点 ID）与 `SKILL_AGENT_EDGE_TOKEN`（Edge Token）必须对应 Backend 已注册节点。

可按项目约定分别启动服务：

```powershell
cd E:\git\nodeskclaw\nodeskclaw-backend
uv run uvicorn app.main:app --reload --port 4510
```

```powershell
cd E:\git\nodeskclaw\nodeskclaw-agent
uv run uvicorn app.main:app --reload --port 4580
```

## 3. 导入与变量配置

在 Postman Desktop 导入 [nodeskclaw-agent-full-flow.postman_collection.json](nodeskclaw-agent-full-flow.postman_collection.json)。该 Collection 自带变量，不需要额外导入 Environment（环境）文件。

先修改下列变量；不要把真实 Token 提交回仓库。

Agent 内部接口不用 Postman 的 Bearer Token（持有者令牌）。集合级 Auth 已设为 API Key，请求选 **Inherit auth from parent**（从父级继承）即可自动带上请求头 `X-Skill-Agent-Token`。把 `agent_internal_token` 改成与 Agent `.env` 中 `SKILL_AGENT_INTERNAL_TOKEN` 完全相同的值；占位符 `REPLACE_WITH_AGENT_INTERNAL_TOKEN` 会返回 HTTP `401`。已打开的旧 Collection 需要重新导入或同步本文件后，Auth 才会变成 API Key。

| 变量 | 必填 | 来源与用途 |
| --- | --- | --- |
| `backend_base_url` | 是 | Backend 地址，默认 `http://127.0.0.1:4510` |
| `agent_base_url` | 是 | Agent 地址，默认 `http://127.0.0.1:4580` |
| `backend_access_token` | 是 | 属于测试组织管理员的 Backend JWT（访问令牌） |
| `org_id` | 是 | 与 JWT 对应的测试组织 ID |
| `user_id` | 是 | 发起 Agent Run 的测试用户 ID |
| `other_org_id` | 是 | 用于跨租户拒绝测试，必须不同于 `org_id` |
| `agent_internal_token` | 是 | Backend 与 Agent 共用的内部 Token |

其余变量由 Collection 的预请求脚本或前序响应自动保存，包括 `skill_key`、`release_id`、`edge_node_id`、`edge_token`、各类 `run_id`、`artifact_id` 和 Generation（代次）。如果需要从头开始，请在 Collection Variables 中清空这些动态变量后重新执行第 04 项。

## 4. 推荐执行顺序

不要使用 Collection Runner（集合运行器）一键运行。该 Collection 是有状态的手工调试资产，应按编号逐项点击 Send（发送）并观察响应。

| 阶段 | 请求编号 | 预期结果 |
| --- | --- | --- |
| 连通性 | 01–03 | Backend 与 Agent 均返回 HTTP `200`；Agent 状态为 `ok` |
| 测试资源准备 | 04–08 | 创建并发布临时 Skill，注册独立 Edge Node，心跳返回 `code: 0` |
| Central 生命周期 | 10–18 | Run 先进入 `WAITING_APPROVAL`，重复创建保持同一 Run，审批转为 `RESUMING`，取消收敛为 `CANCELLED` |
| Event 与 Artifact | 20–30 | Artifact 上传并重试返回同一 ID；下载字节和 SHA256（文件摘要）匹配；旧代返回 `409`；跨组织读取返回 `404`；重复事件计数为 `0` |
| Edge 协议 | 40–53 | Edge Job 可认领并续租；旧 Delivery Generation 返回 `403`；on-demand 请求可签发、拉取、上传及读取；无效 Edge Token 返回 `403` |
| Installation 代次 | 60–68 | Desired/Actual 代次一致时接受；旧 Actual Generation 返回 `403`；卸载进入 `uninstalling` 后由 `uninstalled` Actual 收敛 |

## 5. 关键响应断言

Collection 已内置精确断言。遇到失败时先保留请求和响应，再按下表定位：

| 场景 | 正确结果 | 常见原因 |
| --- | --- | --- |
| `/health/ready` | `200`，`status: "ok"` | 数据库、迁移、内部 Token、存储或 Worker 配置未就绪 |
| 创建 / 查询 Agent Run | `200` | `agent_internal_token` 仍是占位符，或与 Agent `SKILL_AGENT_INTERNAL_TOKEN` 不一致；或缺少 `X-Exec-Org-Id` |
| 审批 Run | `200`，`RESUMING` | Run 不是 `WAITING_APPROVAL`，或 `approval_id` 不一致 |
| Artifact 旧代上传 | `409`，`errors.artifact.stale_generation` | 这是预期负向结果，不应改为成功断言 |
| 跨组织读取 Run | `404` | `other_org_id` 与 `org_id` 相同会使负向验证无效 |
| 旧 Edge Lease | `403`，`errors.connector.stale_delivery_generation` | 这是 Fencing（代次隔离）预期行为 |
| 旧 Installation Actual | `403`，`errors.skill.stale_actual_generation` | 先重新拉取 Desired 获取当前 `desired_generation` |

## 6. 真实 Edge 安装调试

第 60–68 项验证的是 Backend Desired/Actual 合同。若要验证真实 Edge Worker 的安装与卸载副作用：

1. 使用实际 Edge Worker 注册时获得的 `edge_node_id` 和 `edge_token`，不要使用第 07 项临时节点。
2. 创建或选择该节点的 Edge Installation。
3. 调用第 61 项确认 Worker 能拉到 Desired Installation。
4. 在 Edge Worker 本地检查安装目录、安装元数据与日志。
5. 仅在副作用成功后，确认第 62 或第 65 项对应的 Actual 上报成功。
6. 删除 Installation 后，确认 Worker 先执行本地卸载，再上报第 68 项的 `uninstalled`。

当前实现对“真实 Skill 包内容安装、包摘要校验与原子替换”仍有未闭环项；该限制不应被 Postman 的 Actual 上报请求掩盖。

## 7. 已知限制

- 该资产不执行真实多 Pod、断网、崩溃接管、Docker Compose 或 Newman 两连跑。
- Backend 公共 SSE（服务端推送）需要由 Backend Run 投影创建；本 Collection 的事件验证使用 Agent 内部事件重放接口。
- 集合会留下测试 Skill、Edge Node 与 Run 等逻辑数据。请在隔离测试组织中操作，并按团队数据治理流程清理。
- 运行成功只能证明该开发环境中的接口行为；生产验收仍需独立的 PostgreSQL、多 Pod、故障注入和正式发布证据。

## 8. 提交问题时应附带的信息

请至少提供请求编号、请求 URL、HTTP 状态码、响应体中的 `error_code`（错误代码）/`message_key`（消息键）、`run_id`、`edge_job_id`、Generation 和 Agent/Backend 日志时间段。不要提交真实 JWT、Internal Token 或 Edge Token。
