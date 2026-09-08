# Plan Completion Audit Contract v2

Plan Completion Audit 是实现者之外的 mandatory gate。

## Deterministic Precheck

必须验证：

- all canonical Cursor todos completed；
- frozen workspace base 与 requested base 一致；
- Plan write set 相对 workspace baseline 有真实 delta；
- pre-existing ambient 保持 stable；
- 无 new scope drift / tooling mutation。

禁止再用整个 repository `git diff <base>` 作为当前 Plan 的 changed-file truth。

## Semantic Audit

Fresh reviewer 读取：canonical Plan + Approved PRD + Plan-owned implementation delta + referenced implementation files。

结果必须包含：

```json
{"total_items":0,"done":0,"changed":0,"deferred":0,"unverifiable":0,"scope_drift":0,"verdict":"PASS","summary":"..."}
```

PASS 必须满足：`done=total_items`、`deferred=0`、`unverifiable=0`、`scope_drift=0`。

Record 绑定 current `scope_fingerprint + ambient_fingerprint`；任一变化使其 STALE。
