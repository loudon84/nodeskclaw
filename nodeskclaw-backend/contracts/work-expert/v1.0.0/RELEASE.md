# WORK-EXPERT-CONTRACT v1.0.0 Release Notes

## 锁定信息（apps/work）

| 项 | 值 |
|---|---|
| contractName | WORK-EXPERT-CONTRACT |
| contractVersion | 1.0.0 |
| 产物路径 | `nodeskclaw-backend/contracts/work-expert/v1.0.0/` |
| 发布 tag | `work-expert-contract-v1.0.0`（需维护者打 annotated tag 后填入 tag SHA） |
| 校验 | 对比 `SHA256SUMS` 与 `manifest.json.artifacts` |

Consumer 应锁定 **tag 名 + tag commit SHA + SHA256SUMS**，而非 `main` 或 `manifest.backendCommit`（生成 commit 与 tag commit 可能不同）。

## 覆盖接口

Expert MCP：`GET /api/v1/expert/health`、`POST /api/v1/expert/mcp`、`POST /api/v1/expert/mcp/{slug}`

Hermes Task 跟进：`GET/POST` snapshot、events、events-token、result、artifacts、cancel、retry；artifact preview/download。

完整 OpenAPI 子集见同目录 `openapi.yaml`。

## Capability Flags

`asyncEvent`、`sseResume`、`idempotency`、`taskOwnerPolicy`、`retryContract`、`cancelSafe`：true  
`runtimeProgress`：false  
`artifactMode`：pull_only  
`loadGate`：**unmet**（20-run 吞吐未验证，见 `scripts/contracts/load_test_20_runs.md`）

## 破坏性变更（相对未按合同实现的客户端）

1. **Task Owner Policy**：非 admin/operator 成员访问他人 task → `403`（`errors.task.owner_forbidden`）。
2. **result 字段**：`content` 使用 `result_content` 全文；`result_summary` 仅为截断摘要（不再把 500 字摘要当最终正文）。
3. **Health / system/info**：新增 `contractVersion: "1.0.0"` 与 `capabilities`；勿用 `gateway.version`。
4. **MCP Client Token**：强制 `scopes`（`mcp:tools:list` / `mcp:tools:call`）与可选 `allowed_tools` / `allowed_skills` 过滤。
5. **幂等**：重复 `X-Idempotency-Key` 返回原 task accepted 响应，不新建 invocation。

## 冻结行为

- JSON-RPC 应用错误：**HTTP 200** + `{ jsonrpc, id, error }`，错误码在 `error.data.errorCode`（camelCase）。
- Expert health 未授权：**HTTP 200** + `ok: false`（非 401）。
- `sync_legacy` run mode 仍可用，但 **不属于** apps/work v1.0.0 契约面（见 `lat.md/decisions/work-expert-contract.md`）。

## 生成与校验

```bash
cd nodeskclaw-backend
uv run python scripts/contracts.py generate
uv run python scripts/contracts.py check
```

CI quality-gate 在 pytest 之后执行 `contracts.py check`。

## 已知限制

- 单 Worker poll batch 内顺序执行；队列上限为配置声明，非吞吐 SLA。
- `runtimeProgress: false`：仅保证最低阶段事件（含 `preparing`、`finalizing`），远端 delta stage 可透传但不可视为可信工具级进度。
