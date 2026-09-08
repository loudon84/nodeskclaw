# SMC Review Contract v2

## Plan Review

Plan semantic review 绑定 `semantic_plan_sha256`。Cursor runtime `status` 与已验证的 deterministic `content` projection 不属于独立 Plan semantics；Markdown Todo/body/ledgers 改变会使 review STALE。

## Implementation Review

Implementation Review 只审当前 Plan-owned implementation delta，并绑定：

```text
scope_fingerprint
ambient_fingerprint
```

Current scope code 改变、ambient drift 或 non-Plan scope drift 都使 review STALE/BLOCKED。

Router `REQUIRED` 永远不是 PASS；`NOT_REQUIRED` 也必须写 content-bound Plan clearance record。
