# WORK-EXPERT-CONTRACT v1.0.2 Release Notes

## 锁定信息（apps/work）

Consumer **必须**锁定以下三项，缺一不可：

1. tag name: `work-expert-contract-v1.0.2`
2. tag target commit SHA: `git rev-parse work-expert-contract-v1.0.2^{commit}`
3. `SHA256SUMS`（与 `manifest.json.artifacts` 交叉校验）

**禁止**锁定 `main`。**禁止**只锁定 `manifest.backendCommit`。`manifest.tagTargetCommit` 在打 annotated tag 前为 `null`；打 tag 后以剥出的 commit SHA 为准（commit 无法自包含自身 SHA）。

| 项 | 值 |
|---|---|
| contractName | WORK-EXPERT-CONTRACT |
| contractVersion | 1.0.2 |
| 产物路径 | `nodeskclaw-backend/contracts/work-expert/v1.0.2/` |
| 发布 tag | `work-expert-contract-v1.0.2` |
| 相对 v1.0.1 | 补齐 MCP `tools/list` Catalog/Skill `annotations` 合同；不改写 `v1.0.0/`、`v1.0.1/`；不改 HermesTask / SSE / Artifact 语义 |

### 冻结引用

| 版本 | tag name | 说明 |
|---|---|---|
| 1.0.0 | `work-expert-contract-v1.0.0` | 不可改写 |
| 1.0.1 | `work-expert-contract-v1.0.1` | 不可改写；Hermes HTTP schema 补齐 |

## v1.0.2 范围

为 `POST /api/v1/expert/mcp` 与 `POST /api/v1/expert/mcp/{slug}` 的 JSON-RPC `tools/list` **success `result.tools[]`** 定义：

- `name` / `description` / `inputSchema`
- Catalog `annotations` 与 Skill `annotations`

**禁止**仅用 `additionalProperties: true` 的开放 object 作为 annotations 的唯一合同。允许在已声明字段之外扩展（`extra=allow`），但最低字段必须可校验。

Hermes Task、SSE、Artifact 的 schema 随 generate 重出，语义与 v1.0.1 相同。

## Consumer 解析规则

### 调用 identity（不得用 displayName）

| 端点 | identity | tools/call `params.name` |
|---|---|---|
| Catalog `POST /api/v1/expert/mcp` | `annotations.slug` | **不得**改成 displayName；Catalog 条目的 `tool.name` 与 slug 对齐，但路由 identity 以 `annotations.slug` 为准 |
| Skill `POST /api/v1/expert/mcp/{slug}` | `tool.name` | 必须用 `tool.name` |

`displayName` 仅 UI 展示。缺省或 `null` 时 UI 回退 `tool.name`（Catalog 也可回退 `annotations.slug`）。

### Catalog annotations（最低字段）

| 字段 | 约束 | 缺失 / null / 非法 |
|---|---|---|
| `kind` | `"expert"` \| `"expert_team"` | **拒绝**：不得当作 Catalog 路由项 |
| `slug` | 非空 string | **拒绝**：不得路由 |
| `displayName` | string，可选 | 回退 `tool.name` / `slug` |
| `status` | string；已知语义：`ready` 可用，`offline` 不可用 | 未知值 / 缺失：**不得**当作 ready；可展示为降级 |
| `publicSkillCount` | integer ≥ 0 | **拒绝**该 Catalog 项 |
| `callableSkillCount` | integer ≥ 0 | **拒绝**该 Catalog 项 |

### Skill annotations（最低字段）

| 字段 | 约束 | 缺失 / null / 非法 |
|---|---|---|
| `displayName` | 可选 | 回退 `tool.name` |
| `status` | string；`ready` / `offline` | 未知或缺失：**不得**当作 ready |
| `callEnabled` | boolean | 缺失 / null / 非 boolean：**视为 false**，禁止 `tools/call` |
| `riskLevel` | string | 缺失 / 未知：视为需人工复核，禁止静默调用 |
| `approvalMode` | string | 缺失 / 未知：视为 `approval_required` |

`callEnabled=false` 的 Skill 可出现在 `tools/list`，但 consumer **不得**发起 `tools/call`。

## Fixtures

| 文件 | 用途 |
|---|---|
| `fixtures/catalog-tools-list.json` | Catalog + 中文 `displayName` |
| `fixtures/skill-tools-list.json` | Skill + annotations |
| `fixtures/catalog-tools-list-missing-display-name.json` | 缺省可选 `displayName` |
| `fixtures/skill-tools-list-call-disabled.json` | `callEnabled=false` |
| `fixtures/invalid-tool-annotations.json` | 负例（`publicSkillCount < 0`），**不得**通过 schema |

## 生成与校验

```bash
cd nodeskclaw-backend
uv run python scripts/contracts.py generate
uv run python scripts/contracts.py check
```

## Capability Flags

与 v1.0.1 相同：`asyncEvent` / `sseResume` / `idempotency` / `taskOwnerPolicy` / `retryContract` / `cancelSafe`：true；`runtimeProgress`：false；`artifactMode`：`pull_only`；`loadGate`：**unmet**。
