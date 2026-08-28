---
name: smc-prd-converge
description: 将 PRD Review PASS 的 Stage PRD 做确定性清理与 APPROVED 状态转换；保留 source_revision/grounded_commit/Evidence Baseline，不重新分析架构或源码。
version: 3.0.0
disable-model-invocation: true
---

# SMC PRD Converge

## Preconditions

- latest `smc-prd-review` Verdict=PASS;
- no OPEN BLOCKER/MAJOR;
- PRD state DRAFT/REVIEW_REQUIRED;
- `validate_prd.py` passes.

## Preserve

- Current/Target Capability Inventory;
- stable Change IDs + Change Classification;
- Replacement/Removal and Compatibility contracts where required;
- final Behaviour/Boundary/AC;
- minimal Source Anchors;
- **Evidence Baseline**;
- **source_revision**;
- **grounded_commit**.

Process-only Review/Closure notes may be removed.

## Deterministic State Transition

Set only:

```yaml
status: APPROVED
review_verdict: PASS
approved_at: <ISO-8601>
```

Drop `-DRAFT` suffix. Do not change Owner/Classification/Boundary during converge.

## Validation

```bash
python tools/agent-skills/validate_prd.py <final-prd> --require-approved --require-evidence
```

## Exit

`APPROVED -> smc-plan-from-approved-prd-ponytail`.
