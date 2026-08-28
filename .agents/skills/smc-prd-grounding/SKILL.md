---
name: smc-prd-grounding
description: 校准 Stage PRD 到当前源码与 APPROVED Architecture/Roadmap Item；优先复用现有 Capability，支持 discover/verify/revision，并基于 source_revision + grounded_commit 复用证据，禁止源码未变化时重复 full Grounding。
version: 4.0.0
disable-model-invocation: true
---

# SMC PRD Grounding

## Purpose

将一个 READY Roadmap Item 变成可审查 Stage PRD。回答：Current Capability、唯一 Production Owner、KEEP/MODIFY/ADD/REPLACE/REMOVE、必要 Boundary/Behaviour/AC。

读取：
- [`../../references/prd-contract.md`](../../references/prd-contract.md)
- [`../../references/evidence-contract.md`](../../references/evidence-contract.md)
- [`../../references/architecture-convergence.md`](../../references/architecture-convergence.md)

## Preconditions

- 对 governed flow：必须有一个 READY Roadmap Item；一个 Item 只对应一个 Stage PRD。
- PRD 必须记录 `source_revision`（Architecture/Roadmap source）和 `grounded_commit`。

## Evidence Freshness Gate

已有 PRD 在再次 Grounding 前必须运行：

```bash
python tools/agent-skills/evidence_freshness.py <prd> --source-revision <current-source-revision>
```

处理：

- `REUSE`: 禁止 full Grounding；直接复用 Current Inventory/Anchors。
- `VERIFY_ONLY`: 只验证被 commit diff 影响的 anchors/capabilities。
- `REGROUND_REQUIRED`: 只重做受影响 Capability 的 targeted grounding。
- `UNKNOWN`: 取得真实 source/commit baseline 后再继续。

## Modes

- `discover`: 首次 Stage PRD 或当前证据确实缺失。
- `verify`: 已有可靠 Source Anchors/Inventory；做抽查与 Owner/Classification 校验。
- `revision`: Review REVISE 后，只关闭 OPEN finding + direct regression。

## Capability Rules

- EXISTS -> KEEP
- PARTIAL -> MODIFY existing owner
- MISSING -> 证明无等价/可扩展 owner 后才 ADD
- CONFLICT -> REPLACE + REMOVE
- UNKNOWN -> 不猜

Architecture Minimality Guard：新增 Service/Store/Client/Protocol 前必须证明 existing owner/contract 无法承载。

## Stable Change IDs

新 PRD 的 `Change Classification` 使用稳定 `C01...`。一个 Change ID 对应一个架构原子变更；Plan 继承该 ID。

## PRD / Plan Boundary

PRD 冻结 Capability、Owner、Boundary、observable Behaviour、Change Classification、AC。

exact file/symbol、root-cause call chain、Ponytail implementation strategy、Todo WRITE_OWNER、test file 交给 `smc-plan-from-approved-prd-ponytail`。

## Exit

Grounding 完成 -> `status: REVIEW_REQUIRED` -> `smc-prd-review`。
