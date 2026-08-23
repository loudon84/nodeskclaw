# WORK-EXPERT-CONTRACT 20-run 负载复现

本文件描述如何验证 20 个并发 Expert Run。**只有脚本在受控真实环境执行且 `passed=true` 时，才允许把 `loadGate` 设为 `met`。** 队列配置上限不是吞吐证据。

## 阈值（预先定义）

| 项 | 通过条件 |
|---|---|
| terminal | completed + failed + cancelled >= 20 |
| accept HTTP 5xx | 0 |
| 普通 Chat 探针失败率 | <= 5%（若提供 `WORK_EXPERT_LOADTEST_CHAT_PATH`） |

## 环境变量

| 变量 | 说明 |
|---|---|
| `WORK_EXPERT_LOADTEST_BASE_URL` | Backend 根 URL，例如 `https://example.com` |
| `WORK_EXPERT_LOADTEST_TOKEN` | JWT 或 `ndsk_mcp_*`（勿写入仓库） |
| `WORK_EXPERT_LOADTEST_SLUG` | 已发布 Expert slug |
| `WORK_EXPERT_LOADTEST_SKILL` | 可调用 skill name |
| `WORK_EXPERT_LOADTEST_CHAT_PATH` | 可选，普通 Chat 探针路径 |
| `WORK_EXPERT_LOADTEST_ENV` | 环境标识，写入证据 |
| `WORK_EXPERT_LOADTEST_WORKER_REPLICAS` | Worker replica 数 |

## 命令

```bash
cd nodeskclaw-backend
uv run python scripts/contracts/load_test_20_runs.py
```

证据写入 `contracts/work-expert/v1.0.1/evidence/load-test-20-runs.json`。缺少环境变量时脚本退出码 2，证据 `executed=false`，`loadGate=unmet`。

## 通过后

1. 将证据 JSON 提交进合同目录。
2. 仅当 `executed=true` 且 `passed=true` 时，把 `WORK_EXPERT_CAPABILITIES["loadGate"]` 改为 `met` 并重新 `contracts.py generate`。
3. 若单 Worker 顺序执行达不到阈值，再改容量模型（可控并发或多 replica）后重测。禁止只改 manifest。

v1.0.1 发布时该 gate 为 **unmet**。
