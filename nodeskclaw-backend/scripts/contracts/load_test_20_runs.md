# WORK-EXPERT-CONTRACT 20-run 负载复现步骤

本文件描述如何手工验证 Expert MCP 并发任务吞吐。**不作为 CI gate**；合同 `manifest.json` 中 `loadGate` 为 `unmet`。

## 前置条件

- 已部署含 WORK-EXPERT-CONTRACT v1.0.0 的 `nodeskclaw-backend`
- 组织已配置 Expert catalog 与 Hermes Agent 绑定
- 有效 JWT 或 `ndsk_mcp_*` Client Token（含 `mcp:tools:call` scope）
- Worker 进程已启动（`HermesTaskWorker`）

## 队列配置参考值（非吞吐保证）

| 项 | 配置键 | 默认值 |
|---|---|---|
| 组织排队上限 | org queued | 1000 |
| 用户并发运行 | user running | 3 |
| Skill 并发运行 | skill running | 10 |
| Agent 并发运行 | agent running | 5 |
| Worker 单次 poll | batch | 5（顺序执行） |

## 复现步骤

1. 选定一个已发布的 Expert slug（如 `call-prep`）与可调用 skill name。
2. 并发发起 20 次 `POST /api/v1/expert/mcp/{slug}`，`method=tools/call`，每次使用不同的 `X-Idempotency-Key`。
3. 对每个返回的 `structuredContent.task_id` 订阅 SSE 或轮询 `GET /api/v1/hermes/tasks/{task_id}/result`。
4. 记录：全部进入 terminal 状态的耗时、失败数、队列等待时间、是否触发 org/user/skill 上限拒绝。
5. 对比 Worker 日志与 `hermes_tasks` 表状态，确认无 duplicate completion、cancel-safe 与 result_content 完整性。

## 通过标准（建议，非发布 gate）

- 20 个任务最终均到达 terminal（completed / failed / cancelled）
- 无重复 `TASK_COMPLETED` 事件
- `result.content` 与 `result_summary` 分离正确
- 取消中的 RUNNING 任务不会在 cancel 后被 mark_completed

## 已知限制

- 单 Worker 对 poll batch 内任务 **顺序执行**，20 并发主要为队列与调度验证，非真实 20 路并行 Hermes 调用。
- 合同 v1.0.0 不宣称满足 20 active runs 吞吐 SLA。
