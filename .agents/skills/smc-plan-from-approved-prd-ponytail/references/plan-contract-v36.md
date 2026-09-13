# SMC Cursor Plan Contract v3.6 — Test Asset Binding Extension

Plan v3.6 inherits v3.5 and turns reusable test implementation into a durable project asset rather than a Plan-local filename.

## Test Asset Ledger

Every Plan contains one ledger. A LIVE, FAULT_INJECTION, or EXTERNAL verification with a non-None Subject / Fixture and non-reused evidence has exactly one row.

```markdown
## Test Asset Ledger

| Verification ID | Asset ID | Kind | Path / Entrypoint | Required Capabilities | Action | Impact | Reason |
|---|---|---|---|---|---|---|---|
| V03 | TA-APPROVAL-LIVE | TEST | `tests/live/approval.py` | waiting_approval;approve | REUSE | provider path unaffected | Existing asset covers the scenario |
```

`Action` is one of `REUSE`, `EXTEND`, or `NEW`.

- `REUSE` requires an ACTIVE manifest with a matching current content digest and may not write the asset or manifest.
- `EXTEND` requires the asset file and its manifest in the Change Matrix and cannot use `REUSE_EVIDENCE`.
- `NEW` requires the new asset file and `docs_agent/test-assets/<asset-id>.json` in the Change Matrix and cannot use `REUSE_EVIDENCE`.

## Durable Manifest

Each ACTIVE asset has a git-tracked manifest at the Consumer Profile `test_asset_root` (default `docs_agent/test-assets/`). It records `asset_id`, kind, path, capabilities, and the content digest of the referenced test file.

Delivery runs `test_assets.py sync` after implementation and before Completion Audit. The Evidence Manifest then records each asset ID, manifest path, action, and digest.
