# WORK-EXPERT-CONTRACT v1.0.1 Release Notes

## 锁定信息（apps/work）

Consumer **必须**锁定以下三项，缺一不可：

1. tag name: `work-expert-contract-v1.0.1`
2. tag target commit SHA: `git rev-parse work-expert-contract-v1.0.1^{commit}`
3. `SHA256SUMS`（与 `manifest.json.artifacts` 交叉校验）

**禁止**锁定 `main`。**禁止**只锁定 `manifest.backendCommit`（生成时 HEAD 与 annotated tag 的 peeled commit 因鸡蛋问题可以不同）。`manifest.tagTargetCommit` 在打 tag 前为 `null`，以 tag 剥出的 commit 为准。

| 项 | 值 |
|---|---|
| contractName | WORK-EXPERT-CONTRACT |
| contractVersion | 1.0.1 |
| 产物路径 | `nodeskclaw-backend/contracts/work-expert/v1.0.1/` |
| 发布 tag | `work-expert-contract-v1.0.1` |
| 相对 v1.0.0 | 补齐 Hermes HTTP 200/4xx OpenAPI schema；不改动 `v1.0.0/` |

### v1.0.0 冻结引用（不可改写）

| 项 | 值 |
|---|---|
| tag name | `work-expert-contract-v1.0.0` |
| tag object SHA | `b944e2ffef551d39d3e2a4486667e7ea9cf9f8d1` |
| tag target commit SHA | `bbfff0de21fd9a123d70ac4dcdb54b3cfbdf8257` |
| generate-time backendCommit | `ddedaf3bd3e8d3cc351a806c09c9d57a42b9bfa2` |
| RELEASE.md SHA256 | `42c091457d903008c8525a923f7bff34958c2591b561ffbcd3b89c6325b954b4` |
| manifest.json SHA256 | `e4b1cfcc5c9736aee08c0bdfb2740b050ae3c8c9d0bacfc9812aebdadda4462c` |
| SHA256SUMS SHA256 | `6d63873d655bdea4379e7bee7429667e07e22adfad4632e02830557f017ef037` |

## 覆盖接口

Expert MCP：`GET /api/v1/expert/health`、`POST /api/v1/expert/mcp`、`POST /api/v1/expert/mcp/{slug}`

Hermes Task：get / snapshot / events / events-token / result / artifacts / cancel / retry；artifact preview/download。

v1.0.1 相对 v1.0.0：上述 Hermes HTTP 成功响应与 400/401/403/404/422 均有非空 OpenAPI schema。JSON-RPC 业务错误仍为 **HTTP 200** + `error.data.errorCode`。

## Capability Flags

`asyncEvent`、`sseResume`、`idempotency`、`taskOwnerPolicy`、`retryContract`、`cancelSafe`：true  
`runtimeProgress`：false  
`artifactMode`：pull_only  
`loadGate`：**unmet**（20 concurrent Expert Run 未在受控真实环境执行；见 `evidence/load-test-20-runs.json`）

## 破坏性变更（相对未按合同实现的客户端）

与 v1.0.0 相同：Owner Policy 403 `errors.task.owner_forbidden`；`result.content` = `result_content` 全文，`result_summary` 仅为摘要；health/`system/info` 的 `contractVersion` 现为 `1.0.1`。

## 生成与校验

```bash
cd nodeskclaw-backend
uv run python scripts/contracts.py generate
uv run python scripts/contracts.py check
```

`check` 失败条件：OpenAPI/SSE 漂移、空 200 schema、fixture 不通过 schema、SHA256SUMS 或 `manifest.artifacts` 与文件不符、冻结的 v1.0.0 checksum 被改写、P0 测试文件缺失。

## 已知限制

- 单 Worker poll batch 内顺序执行；队列上限为配置声明，非吞吐 SLA。
- `runtimeProgress: false`。
- 20-run load gate 保持 unmet，不得仅凭配置上限宣称 met。
