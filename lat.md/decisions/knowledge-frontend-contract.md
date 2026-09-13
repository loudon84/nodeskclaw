# Knowledge Frontend Contract

Browser clients consume a frozen Knowledge HTTP surface at `contracts/frontend/v1.0.0/`, independent of `/api/v1` versus `/api/v2` path versions.

Frontend identity is domain IDs plus `evidence_id`. Provider runtime IDs (`dataset_id`, `document_id`, `chunk_id`, non-metric `ragflow_*`) are not public. Auth reuses the opaque Backend Bearer token.

| 项 | 值 |
|---|---|
| contractName | knowledge-frontend-contract |
| contractVersion | 1.0.0 |
| 产物目录 | `nodeskclaw-knowledge/contracts/frontend/v1.0.0/` |
| Provider | nodeskclaw-knowledge |
| Consumer | browser / Portal frontend |
| 发布 tag | `knowledge-frontend-contract-v1.0.0`（annotated） |

Consumer 必须锁定 **tag name + tag commit SHA + SHA256SUMS**，禁止只锁 `main` 或 `manifest.source.commit`。

生成与校验：[[nodeskclaw-knowledge/scripts/frontend_contract.py#generate]]、[[nodeskclaw-knowledge/scripts/frontend_contract.py#check_contract]]。规格源是 [[nodeskclaw-knowledge/scripts/frontend_contract_spec.py]]，产物目录不可手改。

稳定性：`stable` 与 `stable-compat` 在 v1.x 冻结构字段含义；`stable-compat` 仍走 `/api/v1` 路径（入库任务）；`compatibility` 可迁 `/api/v2` 但需重叠窗口；`optional` 必须按 feature flag 门控。

## Check Gate

The check gate proves the frozen package is closed: checksums, OpenAPI and TypeScript match the matrix, fixtures validate, and public schemas forbid provider runtime IDs.

[[nodeskclaw-knowledge/scripts/frontend_contract.py#check_contract]] 校验 `SHA256SUMS` 闭环、`manifest.artifacts`、矩阵 77 条与 OpenAPI 操作对齐、fixtures 对照 schema，以及负例 `invalid-chunk-provider-ids.json` 不得通过 `evidence-item`。
