# SMC Test Asset Contract v1

Test Asset Contract 将可复用的 test、fixture、driver 与 harness 变成项目级、可追溯的资产，避免后续 Roadmap Item 重新发明相同 live test。

## Asset Identity

每个 ACTIVE asset 在 Consumer Profile 的 `test_asset_root`（默认 `docs_agent/test-assets/`）有一个 `<asset_id>.json` manifest。manifest 绑定 asset ID、kind、path、capabilities 与测试文件当前 SHA-256。

manifest 是长期的 Git-tracked 测试资产事实；`.smc/evidence/` 仍只是一次运行的 proof，不代替 manifest。

## Plan Binding

`smc.plan.v3.6` 的 Test Asset Ledger 以 `REUSE | EXTEND | NEW` 显式声明每个 live verification 使用的资产。

- `REUSE`：asset digest 当前、当前 Plan 不写 asset/manifest；Verification 可根据 Claim impact 做 targeted rerun。
- `EXTEND`：asset 与 manifest 都在 Change Matrix；必须运行新的 evidence。
- `NEW`：新 test asset 与 manifest 都在 Change Matrix；必须运行新的 evidence。

Delivery 在 implementation 后、Completion Audit 前同步 manifest；Evidence Manifest 记录最终 asset digest。这样不削弱 scope fingerprint、evidence freshness 或 `post_review`。
